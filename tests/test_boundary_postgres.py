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
    store.grant_runtime(role)
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
        (document, revision, _), snapshots = persisted_answer_session(limited)
        record = result_for(document, snapshots)
        limited.publish_result(document, revision, record)
        limited.withdraw(withdrawal_for(snapshots[0]), 'runtime administrator')
        assert not limited.current_validity(record['input_set'])['valid']
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


def withdrawal_for(doc, notice_id=None):
    import json
    from pathlib import Path
    from pathfinder.core.boundary_validation import canonical_checksum
    notice=json.loads((Path(__file__).resolve().parents[1]/'contracts/samples/v2/withdrawal.notice.json').read_text())
    notice_id=notice_id or str(uuid.uuid4())
    producer=doc['manifest']['producer_wp']
    notice['manifest']['snapshot_id']=notice_id
    notice['manifest']['producer_wp']=producer
    notice['payload']['notice_id']=notice_id
    notice['payload']['targets']=[{'contract':doc['contract'],'snapshot_id':doc['manifest']['snapshot_id'],'producer_wp':producer}]
    notice['payload']['source_confirmation']['confirmed_by_wp']=producer
    notice['payload']['source_confirmation']['target_checksum']=canonical_checksum(notice['payload']['targets'])
    notice['manifest']['items_checksum']=canonical_checksum(notice['payload'])
    return notice


def test_withdrawal_tombstone_precedes_activation_and_is_idempotent(stores):
    from pathfinder.core.boundary_runtime import build_boundary_generation
    from pathfinder.core.repositories.boundary_store import NoticeConflict
    snapshots=snapshot_set()
    notice=withdrawal_for(snapshots[0])
    receipt=stores[0].withdraw(notice, 'administrator')
    assert receipt['accepted']
    assert not stores[1].withdraw(notice, 'another-administrator')['created']
    before=stores[0].audit_count()
    conflict=copy.deepcopy(notice); conflict['payload']['reason']='different reason'
    from pathfinder.core.boundary_validation import canonical_checksum
    conflict['manifest']['items_checksum']=canonical_checksum(conflict['payload'])
    with pytest.raises(NoticeConflict):
        stores[1].withdraw(conflict,'administrator')
    assert stores[0].audit_count()==before
    with pytest.raises(ValueError,match='withdrawn'):
        stores[1].activate(snapshots,build_boundary_generation(snapshots))
    assert stores[1].active_generation_id() is None


def test_profile_pointers_do_not_overwrite_each_other(stores):
    from pathfinder.core.boundary_runtime import build_boundary_generation
    from types import SimpleNamespace
    snapshots=snapshot_set(); generation=build_boundary_generation(snapshots)
    legacy=stores[0].activate(snapshots,generation)
    v2=SimpleNamespace(profile_id='evidence-v2',snapshot_ids=generation.snapshot_ids,
                       questionnaire_ids=generation.questionnaire_ids,regulatory_status=generation.regulatory_status)
    modern=stores[1].activate(snapshots,v2)
    assert stores[0].active_generation_id()==legacy
    assert stores[0].active_generation_id('evidence-v2')==modern
    assert stores[1].load_active('evidence-v2')[0]==modern


def persisted_answer_session(store):
    service=make_service(store); snapshots=snapshot_set(); service.activate_boundary_snapshots(snapshots)
    session=service.create_session(snapshots[1]['payload']['stakeholder_type'],snapshots[1]['payload']['target_scenarios'][0])
    session, revision, _=store.load_session(session['assessment_id'])
    session['answer_revision']=1; session['answers']={'old': True}
    store.save_session(session,revision,'answers_submitted',{'assessment_id':session['assessment_id']})
    return store.load_session(session['assessment_id']), snapshots


def result_for(session, snapshots):
    from pathfinder.core.boundary_lifecycle import runtime_input_set
    return {'result_id':str(uuid.uuid4()),'assessment_id':session['assessment_id'],
            'answer_revision':session['answer_revision'],'answers':copy.deepcopy(session['answers']),
            'input_set':runtime_input_set(snapshots,session['stakeholder_type']),
            'profile_id':'legacy-v1','original_output':{'status':'ready','confidence':1.0}}


def test_publish_checks_answer_binding_withdrawals_and_rolls_back_audit(stores,monkeypatch):
    from pathfinder.core.repositories.boundary_store import SessionConflict
    (session,revision,_),snapshots=persisted_answer_session(stores[0])
    result=result_for(session,snapshots)
    before=stores[0].audit_count()
    mismatch=copy.deepcopy(result); mismatch['answer_revision']=0
    with pytest.raises(SessionConflict):
        stores[1].publish_result(session,revision,mismatch)
    assert stores[0].load_result(session['assessment_id']) is None
    assert stores[0].audit_count()==before
    def fail(*args,**kwargs):
        raise RuntimeError('audit failed')
    with monkeypatch.context() as patch:
        patch.setattr(stores[0],'_append',fail)
        with pytest.raises(RuntimeError,match='audit failed'):
            stores[0].publish_result(session,revision,result)
    assert stores[1].load_result(session['assessment_id']) is None
    assert stores[1].load_session(session['assessment_id'])[1]==revision
    stores[1].withdraw(withdrawal_for(snapshots[0]),'administrator')
    with pytest.raises(ValueError,match='withdrawn'):
        stores[0].publish_result(session,revision,result)
    assert stores[1].load_result(session['assessment_id']) is None


def test_published_result_remains_immutable_when_withdrawn(stores):
    import psycopg
    from pathfinder.core.boundary_validation import canonical_checksum
    (session,revision,_),snapshots=persisted_answer_session(stores[0])
    result=result_for(session,snapshots)
    stores[0].publish_result(session,revision,result)
    stored=stores[1].load_result(session['assessment_id'],result['result_id'])
    assert stored==result
    before=canonical_checksum(stored)
    stores[1].withdraw(withdrawal_for(snapshots[0]),'administrator')
    assert canonical_checksum(stores[0].load_result(session['assessment_id'],result['result_id']))==before
    assert not stores[0].current_validity(result['input_set'])['valid']
    assert stores[0].results_for_session(session['assessment_id'])==[stored]
    for table in ('withdrawals','withdrawal_targets','results'):
        with psycopg.connect(stores[0].dsn) as conn:
            with pytest.raises(psycopg.errors.RaiseException,match='append-only'):
                conn.execute(f'DELETE FROM {stores[0].schema}.{table}')


def test_schema_v1_migration_preserves_content_without_inventing_evidence(stores):
    import psycopg
    from pathfinder.core.boundary_validation import canonical_checksum
    store=stores[0]
    (session,revision,_),snapshots=persisted_answer_session(store)
    original={'status':'ready','answer_ids':['unrecoverable'],'confidence':0.75}
    session['recommendation']=original
    session['answers']={'current':'changed after recommendation'}
    store.save_session(session,revision,'answers_submitted',{'assessment_id':session['assessment_id']})
    with psycopg.connect(store.dsn) as conn:
        before=conn.execute(f'SELECT snapshot_id,digest,document FROM {store.schema}.snapshots ORDER BY snapshot_id').fetchall()
        for table in ('withdrawal_targets','withdrawals','results','profile_active'):
            conn.execute(f'DROP TABLE {store.schema}.{table}')
        conn.execute(f'UPDATE {store.schema}.schema_version SET version=1')
    with pytest.raises(RuntimeError,match='migration missing'):
        store.check_schema()
    store.migrate(); store.check_schema()
    record=stores[1].load_result(session['assessment_id'])
    assert record['original_output']==original
    assert record['binding_status']=='legacy_unbound'
    assert record['answers'] is None and record['answer_revision'] is None
    assert record['findings'] is None
    assert store.active_generation_id()==store.load_session(session['assessment_id'])[2]
    with psycopg.connect(store.dsn) as conn:
        after=conn.execute(f'SELECT snapshot_id,digest,document FROM {store.schema}.snapshots ORDER BY snapshot_id').fetchall()
    assert canonical_checksum(before)==canonical_checksum(after)
    store.migrate()
    assert stores[1].results_for_session(session['assessment_id'])==[record]


def withdraw_in_process(dsn,schema,notice):
    from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore
    return PostgresBoundaryStore(dsn,schema=schema).withdraw(notice,'separate-process administrator')


def test_withdrawal_visible_across_processes_and_session_commit_rechecks(stores):
    store=stores[0]; service=make_service(store); snapshots=snapshot_set()
    service.activate_boundary_snapshots(snapshots)
    stakeholder=snapshots[1]['payload']['stakeholder_type']; scenario=snapshots[1]['payload']['target_scenarios'][0]
    # The service already has its generation in cache before the other process commits.
    assert service.active_boundary is not None
    with ProcessPoolExecutor(max_workers=1) as pool:
        receipt=pool.submit(withdraw_in_process,store.dsn,store.schema,withdrawal_for(snapshots[0])).result(timeout=15)
    assert receipt['created']
    before=store.audit_count()
    with pytest.raises(ValueError,match='withdrawn'):
        service.create_session(stakeholder,scenario)
    assert store.audit_count()==before
    restarted=type(store)(store.dsn,schema=store.schema)
    from pathfinder.core.boundary_lifecycle import runtime_input_set
    assert not restarted.current_validity(runtime_input_set(snapshots,stakeholder))['valid']


def test_withdrawal_audit_failure_leaves_no_partial_tombstones(stores,monkeypatch):
    def fail(*args,**kwargs):
        raise RuntimeError('withdrawal audit failure')
    snapshots=snapshot_set(); notice=withdrawal_for(snapshots[0])
    with monkeypatch.context() as patch:
        patch.setattr(stores[0],'_append',fail)
        with pytest.raises(RuntimeError,match='withdrawal audit failure'):
            stores[0].withdraw(notice,'administrator')
    from pathfinder.core.boundary_runtime import build_boundary_generation
    stores[1].activate(snapshots,build_boundary_generation(snapshots))
    assert stores[0].withdraw(notice,'administrator')['created']


def test_publish_waits_for_withdrawal_commit_and_rejects_stale_work(stores,monkeypatch):
    import threading
    import time
    import psycopg
    from psycopg.conninfo import make_conninfo
    from pathfinder.core.repositories.boundary_store import PostgresBoundaryStore
    (session,revision,_),snapshots=persisted_answer_session(stores[0])
    result=result_for(session,snapshots)
    waiting_name='pf_publish_'+uuid.uuid4().hex
    publisher=PostgresBoundaryStore(make_conninfo(stores[1].dsn,application_name=waiting_name),stores[1].schema)
    transaction_open=threading.Event(); release=threading.Event()
    append=stores[0]._append
    def hold_commit(conn,*args,**kwargs):
        append(conn,*args,**kwargs)
        transaction_open.set()
        if not release.wait(5):
            raise RuntimeError('test withdrawal release timed out')
    monkeypatch.setattr(stores[0],'_append',hold_commit)
    with ThreadPoolExecutor(max_workers=2) as pool:
        withdrawal=pool.submit(stores[0].withdraw,withdrawal_for(snapshots[0]),'administrator')
        assert transaction_open.wait(5)
        publication=pool.submit(publisher.publish_result,session,revision,result)
        try:
            deadline=time.monotonic()+5
            with psycopg.connect(stores[1].dsn,autocommit=True) as observer:
                while time.monotonic()<deadline:
                    row=observer.execute("SELECT 1 FROM pg_stat_activity WHERE application_name=%s AND wait_event='advisory'",(waiting_name,)).fetchone()
                    if row:
                        break
                    time.sleep(.01)
                assert row, 'publisher did not wait on the lifecycle transaction lock'
            assert not publication.done()
        finally:
            release.set()
        assert withdrawal.result(timeout=5)['created']
        with pytest.raises(ValueError,match='withdrawn'):
            publication.result(timeout=5)
    assert stores[1].load_result(session['assessment_id']) is None
    assert not any(event['event_type']=='recommendation_generated' for event in stores[1].events_for_assessment(session['assessment_id']))


def test_service_answer_revision_and_withdrawal_are_rechecked_at_publication(stores,monkeypatch):
    from test_assessment_revisions import setup
    service,aid,answers=setup(store=stores[0])
    competing=make_service(stores[1])
    compute=service._recommend_for_session
    changed=dict(answers); changed[next(key for key,value in answers.items() if type(value) is int)]=4
    def answer_first(session,state):
        competing.submit_answers(aid,changed)
        return compute(session,state)
    with monkeypatch.context() as patch:
        patch.setattr(service,'_recommend_for_session',answer_first)
        with pytest.raises(ValueError,match='changed'):
            service.generate_recommendation(aid)
    assert stores[0].load_result(aid) is None
    result=service.generate_recommendation(aid)
    assert result['answer_revision']==2
    def withdraw_first(session,state):
        documents=stores[1].load_generation(session['boundary_generation_id'])
        taxonomy=next(doc for doc in documents if doc['contract']=='pf.taxonomy.v1')
        stores[1].withdraw(withdrawal_for(taxonomy),'administrator')
        return compute(session,state)
    with monkeypatch.context() as patch:
        patch.setattr(service,'_recommend_for_session',withdraw_first)
        with pytest.raises(ValueError,match='withdrawn'):
            service.generate_recommendation(aid)
    assert len(stores[0].results_for_session(aid))==1
    history=competing.report(aid,result_id=result['result_id'])
    assert history['result']['answers']==changed
    assert not history['current_validity']['valid']
    assert len([e for e in stores[0].events_for_assessment(aid) if e['event_type']=='recommendation_generated'])==1
