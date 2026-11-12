"""Real PostgreSQL tests; set TEST_BOUNDARY_DATABASE_URL to a disposable database."""
import copy
import os
import uuid
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from test_boundary_activation import answers, snapshot_set


@pytest.fixture
def stores():
    dsn = os.environ.get("TEST_BOUNDARY_DATABASE_URL")
    if not dsn:
        pytest.skip("TEST_BOUNDARY_DATABASE_URL is not configured")
    from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore
    schema = "pf_boundary_test_" + uuid.uuid4().hex
    first = PostgresBoundaryStore(dsn, schema=schema)
    first.migrate()
    yield first, PostgresBoundaryStore(dsn, schema=schema)
    import psycopg
    from psycopg import sql
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def make_service(store):
    from pathfinder.adapters.upstream import UpstreamClient
    from pathfinder.services.assessment_service import AssessmentService
    return AssessmentService(UpstreamClient(), boundary_store=store)


def create_in_process(dsn, schema, stakeholder, scenario):
    from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore
    service = make_service(PostgresBoundaryStore(dsn, schema=schema))
    return service.create_session(stakeholder, scenario)["assessment_id"]


def test_workers_and_restart_preserve_session_and_versions(stores):
    from pathfinder.core.boundary_validation import canonical_checksum
    store1, store2 = stores
    one, two = make_service(store1), make_service(store2)
    first = snapshot_set()
    one.activate_boundary_snapshots(first)
    assert two.active_boundary.snapshot_ids == one.active_boundary.snapshot_ids
    stakeholder = first[1]["payload"]["stakeholder_type"]
    scenario = first[1]["payload"]["target_scenarios"][0]
    session = one.create_session(stakeholder, scenario)
    two.submit_answers(session["assessment_id"], answers())
    second = copy.deepcopy(first)
    second[-1]["manifest"]["snapshot_id"] = str(uuid.uuid4())
    second[-1]["payload"]["rules"][0]["action"]["title"] = "New generation"
    second[-1]["manifest"]["items_checksum"] = canonical_checksum(second[-1]["payload"])
    two.activate_boundary_snapshots(second)
    restarted = make_service(store1)
    old_result = restarted.generate_recommendation(session["assessment_id"])
    assert old_result["trace"]["snapshot_ids"]["pf.rulebundle.v1"] == first[-1]["manifest"]["snapshot_id"]
    new_session = restarted.create_session(stakeholder, scenario)
    assert new_session["snapshot_ids"]["pf.rulebundle.v1"] == second[-1]["manifest"]["snapshot_id"]
    assert restarted.report(session["assessment_id"])["audit_chain_valid"]
    assert restarted.export_fhir_bundle(session["assessment_id"])["resourceType"] == "Bundle"
    assert store1.verify_audit_chain()


def test_snapshot_identity_survives_restart(stores):
    from pathfinder.core.boundary_validation import canonical_checksum
    first, second = (make_service(store) for store in stores)
    snapshots = snapshot_set()
    first.activate_boundary_snapshots(snapshots)
    snapshots[-1]["payload"]["rules"][0]["action"]["title"] = "Mutated"
    snapshots[-1]["manifest"]["items_checksum"] = canonical_checksum(snapshots[-1]["payload"])
    with pytest.raises(ValueError, match="already used"):
        second.activate_boundary_snapshots(snapshots)
    assert second.active_boundary.snapshot_ids["pf.rulebundle.v1"] == snapshot_set()[-1]["manifest"]["snapshot_id"]


def test_concurrent_workers_keep_coherent_audit(stores):
    one, two = (make_service(store) for store in stores)
    snapshots = snapshot_set()
    one.activate_boundary_snapshots(snapshots)
    stakeholder = snapshots[1]["payload"]["stakeholder_type"]
    scenario = snapshots[1]["payload"]["target_scenarios"][0]
    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(lambda i: (one if i % 2 else two).create_session(stakeholder, scenario)["assessment_id"], range(12)))
    assert len(set(ids)) == 12
    assert stores[0].verify_audit_chain()


def test_sessions_created_in_distinct_processes_are_visible(stores):
    service = make_service(stores[0])
    snapshots = snapshot_set()
    service.activate_boundary_snapshots(snapshots)
    stakeholder = snapshots[1]["payload"]["stakeholder_type"]
    scenario = snapshots[1]["payload"]["target_scenarios"][0]
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create_in_process, stores[0].dsn, stores[0].schema, stakeholder, scenario) for _ in range(4)]
        sessions = [future.result(timeout=15) for future in futures]
    assert all(service.get_session(session_id)["stakeholder_type"] == stakeholder for session_id in sessions)
    assert stores[0].verify_audit_chain()


def test_session_revision_prevents_lost_update(stores):
    one = make_service(stores[0])
    snapshots = snapshot_set()
    one.activate_boundary_snapshots(snapshots)
    session = one.create_session(snapshots[1]["payload"]["stakeholder_type"], snapshots[1]["payload"]["target_scenarios"][0])
    old, revision, _ = stores[0].load_session(session["assessment_id"])
    one.submit_answers(session["assessment_id"], answers())
    with pytest.raises(ValueError, match="changed concurrently"):
        stores[1].save_session(old, revision, "answers_submitted", {})


def test_failed_session_commit_does_not_change_database(stores, monkeypatch):
    service = make_service(stores[0])
    snapshots = snapshot_set()
    service.activate_boundary_snapshots(snapshots)
    session = service.create_session(snapshots[1]["payload"]["stakeholder_type"], snapshots[1]["payload"]["target_scenarios"][0])
    before = stores[0].load_session(session["assessment_id"])
    def fail(*args, **kwargs):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(stores[0], "save_session", fail)
    with pytest.raises(RuntimeError, match="database unavailable"):
        service.submit_answers(session["assessment_id"], answers())
    assert stores[1].load_session(session["assessment_id"]) == before


def test_historical_rows_are_append_only(stores):
    import psycopg
    first = make_service(stores[0])
    first.activate_boundary_snapshots(snapshot_set())
    for table in ("snapshots", "generations", "audit_events"):
        with psycopg.connect(stores[0].dsn) as conn:
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                conn.execute(f"DELETE FROM {stores[0].schema}.{table}")


def test_startup_check_rejects_damaged_audit_chain(stores):
    import psycopg
    service = make_service(stores[0])
    service.activate_boundary_snapshots(snapshot_set())
    with psycopg.connect(stores[0].dsn) as conn:
        conn.execute(f"ALTER TABLE {stores[0].schema}.audit_events DISABLE TRIGGER prevent_mutation")
        conn.execute(f"UPDATE {stores[0].schema}.audit_events SET event_hash='tampered'")
        conn.execute(f"ALTER TABLE {stores[0].schema}.audit_events ENABLE TRIGGER prevent_mutation")
    assert not stores[1].verify_audit_chain()
    with pytest.raises(RuntimeError, match="audit chain"):
        stores[1].check_schema()


def test_http_requests_can_move_between_workers(stores, monkeypatch):
    from pathfinder.api import main
    first, second = (make_service(store) for store in stores)
    monkeypatch.setattr(main, "_service", first)
    client = TestClient(main.app)
    preflight = client.options("/v1/questionnaires", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"})
    assert preflight.status_code == 200
    assert client.get("/v1/questionnaires").status_code == 401
    admin = {"Authorization": "Bearer admin-token"}
    demo = {"Authorization": "Bearer demo-token"}
    snapshots = snapshot_set()
    imported = client.post("/v1/admin/import", headers=admin, json={"snapshots": snapshots})
    assert imported.status_code == 200, imported.text
    monkeypatch.setattr(main, "_service", second)
    response = client.post("/v1/assessments", headers=demo, json={
        "stakeholder_type": snapshots[1]["payload"]["stakeholder_type"],
        "target_scenario": snapshots[1]["payload"]["target_scenarios"][0]})
    assert response.status_code == 200, response.text
    session_id = response.json()["assessment_id"]
    monkeypatch.setattr(main, "_service", first)
    assert client.post(f"/v1/assessments/{session_id}/answers/batch", headers=demo, json={"answers": answers()}).status_code == 200
    monkeypatch.setattr(main, "_service", second)
    response = client.post(f"/v1/assessments/{session_id}/recommendations", headers=demo)
    assert response.status_code == 200, response.text
    assert response.json()["trace"]["boundary_generation_id"] == imported.json()["generation_id"]
    assert client.get(f"/v1/assessments/{session_id}", headers=demo).status_code == 200
    assert client.get(f"/v1/assessments/{session_id}/report", headers=demo).json()["audit_chain_valid"]


def test_database_failure_returns_service_unavailable(stores, monkeypatch):
    import psycopg
    from pathfinder.api import main
    service = make_service(stores[0])
    monkeypatch.setattr(main, "_service", service)
    def unavailable():
        raise psycopg.OperationalError("database unavailable")
    monkeypatch.setattr(stores[0], "_connect", unavailable)
    client = TestClient(main.app)
    response = client.get("/v1/questionnaires", headers={"Authorization": "Bearer demo-token"})
    assert response.status_code == 503


def test_http_concurrent_update_returns_conflict(stores, monkeypatch):
    from pathfinder.api import main
    from pathfinder.core.repositories.boundary_store import SessionConflict
    service = make_service(stores[0])
    snapshots = snapshot_set()
    service.activate_boundary_snapshots(snapshots)
    session = service.create_session(snapshots[1]["payload"]["stakeholder_type"], snapshots[1]["payload"]["target_scenarios"][0])
    monkeypatch.setattr(main, "_service", service)
    def conflict(*args, **kwargs):
        raise SessionConflict("assessment session changed concurrently; reload and retry")
    monkeypatch.setattr(stores[0], "save_session", conflict)
    client = TestClient(main.app)
    response = client.post(f"/v1/assessments/{session['assessment_id']}/answers/batch", headers={"Authorization": "Bearer demo-token"}, json={"answers": answers()})
    assert response.status_code == 409
    assert "answers" not in stores[1].load_session(session["assessment_id"])[0]


def test_production_rejects_memory_storage(monkeypatch):
    import asyncio
    from pathfinder.api import main
    monkeypatch.setattr(main, "ENVIRONMENT", "production")
    monkeypatch.setattr(main, "ADMIN_TOKEN", "admin-test")
    monkeypatch.setattr(main, "DEMO_TOKEN", "demo-test")
    monkeypatch.setenv("BOUNDARY_STORAGE", "memory")
    async def no_op():
        return None
    class Logger:
        start_flush_task = staticmethod(no_op)
    monkeypatch.setattr(main, "init_pool", no_op)
    monkeypatch.setattr(main, "get_logger", lambda: Logger())
    async def start():
        async with main.lifespan(main.app):
            pass
    with pytest.raises(RuntimeError, match="production requires BOUNDARY_STORAGE=postgres"):
        asyncio.run(start())


def test_runtime_role_requires_no_schema_ownership(stores):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore
    store = stores[0]
    role = "pf_runtime_test_" + uuid.uuid4().hex[:12]
    with psycopg.connect(store.dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal("temporary-test-password")))
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(store.schema), sql.Identifier(role)))
        conn.execute(sql.SQL("GRANT SELECT ON {}.schema_version TO {}").format(sql.Identifier(store.schema), sql.Identifier(role)))
        for table in ("snapshots", "generations", "audit_events"):
            conn.execute(sql.SQL("GRANT SELECT, INSERT ON {}.{} TO {}").format(sql.Identifier(store.schema), sql.Identifier(table), sql.Identifier(role)))
        for table in ("active_generation", "sessions"):
            conn.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON {}.{} TO {}").format(sql.Identifier(store.schema), sql.Identifier(table), sql.Identifier(role)))
        conn.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(sql.Identifier(store.schema), sql.Identifier(role)))
    try:
        dsn = make_conninfo(store.dsn, user=role, password="temporary-test-password")
        limited = PostgresBoundaryStore(dsn, schema=store.schema)
        limited.check_schema()
        service = make_service(limited)
        snapshots = snapshot_set()
        service.activate_boundary_snapshots(snapshots)
        session = service.create_session(snapshots[1]["payload"]["stakeholder_type"], snapshots[1]["payload"]["target_scenarios"][0])
        service.submit_answers(session["assessment_id"], answers())
        assert service.report(session["assessment_id"])["audit_chain_valid"]
        with psycopg.connect(dsn) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(f"DELETE FROM {store.schema}.audit_events")
    finally:
        with psycopg.connect(store.dsn, autocommit=True) as conn:
            conn.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} FROM {}").format(sql.Identifier(store.schema), sql.Identifier(role)))
            conn.execute(sql.SQL("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {} FROM {}").format(sql.Identifier(store.schema), sql.Identifier(role)))
            conn.execute(sql.SQL("REVOKE USAGE ON SCHEMA {} FROM {}").format(sql.Identifier(store.schema), sql.Identifier(role)))
            conn.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def test_request_log_flush_uses_one_transaction(stores, monkeypatch):
    import asyncio
    import asyncpg
    from pathfinder.middleware import request_logger
    marker = "/boundary-test-" + uuid.uuid4().hex

    async def exercise():
        pool = await asyncpg.create_pool(stores[0].dsn, min_size=1, max_size=1)
        try:
            async with pool.acquire() as conn:
                if not await conn.fetchval("SELECT to_regclass('assess.request_log') IS NOT NULL"):
                    pytest.skip("base request log schema is not installed")
            logger = request_logger.RequestLogger()
            for _ in range(2):
                logger.buffer.append({"timestamp": "2026-11-12T12:00:00+00:00", "ip": "127.0.0.1",
                                      "method": "GET", "endpoint": marker, "status_code": 200, "duration_ms": 1})
            monkeypatch.setattr(request_logger, "get_pool", lambda: pool)
            await asyncio.wait_for(logger._flush_buffer(), timeout=2)
            async with pool.acquire() as conn:
                count = await conn.fetchval("SELECT count(*) FROM assess.request_log WHERE endpoint=$1", marker)
                await conn.execute("DELETE FROM assess.request_log WHERE endpoint=$1", marker)
            assert count == 2
            assert not logger.buffer
        finally:
            await pool.close()

    asyncio.run(exercise())
