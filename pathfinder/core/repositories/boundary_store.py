"""Transactional, cross-process storage for boundary generations and sessions."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pathfinder.core.boundary_validation import canonical_checksum


class SessionConflict(ValueError):
    """A concurrent request changed this assessment since it was read."""


class PostgresBoundaryStore:
    def __init__(self, dsn: str, schema: str = "pf_boundary") -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("invalid boundary storage schema")
        self.dsn = dsn
        self.schema = schema

    def _connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5)

    def _lock(self, conn):
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (self.schema + ":boundary-writes",))

    def migrate(self):
        """Apply the idempotent v1 storage migration under a database lock."""
        s = self.schema
        with self._connect() as conn:
            self._lock(conn)
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
            conn.execute(f"CREATE TABLE IF NOT EXISTS {s}.schema_version (singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton), version INTEGER NOT NULL)")
            conn.execute(f"INSERT INTO {s}.schema_version(singleton,version) VALUES (TRUE,1) ON CONFLICT(singleton) DO NOTHING")
            version = conn.execute(f"SELECT version FROM {s}.schema_version WHERE singleton=TRUE").fetchone()["version"]
            if version != 1:
                raise RuntimeError(f"unsupported boundary schema version {version}")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.snapshots (
                snapshot_id TEXT PRIMARY KEY, digest TEXT NOT NULL, document JSONB NOT NULL)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.generations (
                generation_id TEXT PRIMARY KEY, documents JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.active_generation (
                singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
                generation_id TEXT NOT NULL REFERENCES {s}.generations(generation_id))""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.sessions (
                session_id TEXT PRIMARY KEY, generation_id TEXT NOT NULL REFERENCES {s}.generations(generation_id),
                revision BIGINT NOT NULL DEFAULT 0, document JSONB NOT NULL)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.audit_events (
                sequence BIGSERIAL PRIMARY KEY, event_hash TEXT NOT NULL UNIQUE,
                prev_hash TEXT, payload JSONB NOT NULL)""")
            conn.execute(f"CREATE INDEX IF NOT EXISTS audit_events_assessment ON {s}.audit_events ((payload->'event_data'->>'assessment_id'))")
            conn.execute(f"""CREATE OR REPLACE FUNCTION {s}.prevent_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'boundary history is append-only'; END $$""")
            for table in ("snapshots", "generations", "audit_events"):
                conn.execute(f"DROP TRIGGER IF EXISTS prevent_mutation ON {s}.{table}")
                conn.execute(f"CREATE TRIGGER prevent_mutation BEFORE UPDATE OR DELETE ON {s}.{table} FOR EACH ROW EXECUTE FUNCTION {s}.prevent_mutation()")

    def check_schema(self):
        """Fail closed if the explicit migration has not been applied."""
        with self._connect() as conn:
            for table in ("schema_version", "snapshots", "generations", "active_generation", "sessions", "audit_events"):
                if conn.execute("SELECT to_regclass(%s) AS name", (f"{self.schema}.{table}",)).fetchone()["name"] is None:
                    raise RuntimeError(f"boundary database migration missing: {self.schema}.{table}")
            row = conn.execute(f"SELECT version FROM {self.schema}.schema_version WHERE singleton=TRUE").fetchone()
            if row is None or row["version"] != 1:
                raise RuntimeError("unsupported boundary database schema version")
            for table in ("snapshots", "generations", "audit_events"):
                trigger = conn.execute("""SELECT 1 FROM pg_trigger WHERE tgrelid=to_regclass(%s)
                    AND tgname='prevent_mutation' AND NOT tgisinternal AND tgenabled IN ('O','A')""",
                    (f"{self.schema}.{table}",)).fetchone()
                if not trigger:
                    raise RuntimeError(f"append-only trigger missing or disabled: {self.schema}.{table}")
        if not self.verify_audit_chain():
            raise RuntimeError("boundary audit chain failed integrity verification")

    @staticmethod
    def _hash(value: str | None):
        return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None

    def _append(self, conn, event_type, data, ip=None, user_agent=None):
        previous = conn.execute(f"SELECT event_hash FROM {self.schema}.audit_events ORDER BY sequence DESC LIMIT 1").fetchone()
        prev_hash = previous["event_hash"] if previous else None
        payload = {"event_type": event_type, "event_data": data,
                   "timestamp": datetime.now(timezone.utc).isoformat(), "prev_hash": prev_hash,
                   "ip_hash": self._hash(ip), "user_agent_hash": self._hash(user_agent)}
        event_hash = canonical_checksum(payload)
        conn.execute(f"INSERT INTO {self.schema}.audit_events(event_hash, prev_hash, payload) VALUES (%s,%s,%s)",
                     (event_hash, prev_hash, Jsonb(payload)))

    def append_event(self, event_type, data, ip=None, user_agent=None):
        with self._connect() as conn:
            self._lock(conn)
            self._append(conn, event_type, data, ip, user_agent)

    def activate(self, snapshots, generation, ip=None, user_agent=None):
        generation_id = str(uuid4())
        with self._connect() as conn:
            self._lock(conn)
            for snapshot in snapshots:
                snapshot_id = snapshot["manifest"]["snapshot_id"]
                digest = canonical_checksum(snapshot)
                existing = conn.execute(f"SELECT digest FROM {self.schema}.snapshots WHERE snapshot_id=%s", (snapshot_id,)).fetchone()
                if existing and existing["digest"] != digest:
                    raise ValueError(f"snapshot_id {snapshot_id} was already used for different content")
                if not existing:
                    conn.execute(f"INSERT INTO {self.schema}.snapshots(snapshot_id,digest,document) VALUES (%s,%s,%s)",
                                 (snapshot_id, digest, Jsonb(snapshot)))
            conn.execute(f"INSERT INTO {self.schema}.generations(generation_id,documents) VALUES (%s,%s)", (generation_id, Jsonb(snapshots)))
            conn.execute(f"""INSERT INTO {self.schema}.active_generation(singleton,generation_id) VALUES (TRUE,%s)
                ON CONFLICT(singleton) DO UPDATE SET generation_id=excluded.generation_id""", (generation_id,))
            self._append(conn, "boundary_snapshots_activated", {"generation_id": generation_id,
                "snapshot_ids": dict(generation.snapshot_ids), "questionnaire_ids": dict(generation.questionnaire_ids),
                "regulatory_status": generation.regulatory_status}, ip, user_agent)
        return generation_id

    def load_active(self):
        with self._connect() as conn:
            row = conn.execute(f"""SELECT g.generation_id,g.documents FROM {self.schema}.active_generation a
                JOIN {self.schema}.generations g ON g.generation_id=a.generation_id WHERE a.singleton=TRUE""").fetchone()
        return (row["generation_id"], row["documents"]) if row else None

    def active_generation_id(self):
        with self._connect() as conn:
            row = conn.execute(f"SELECT generation_id FROM {self.schema}.active_generation WHERE singleton=TRUE").fetchone()
        return row["generation_id"] if row else None

    def load_generation(self, generation_id):
        with self._connect() as conn:
            row = conn.execute(f"SELECT documents FROM {self.schema}.generations WHERE generation_id=%s", (generation_id,)).fetchone()
        if row is None:
            raise ValueError(f"boundary generation {generation_id} not found")
        return row["documents"]

    def create_session(self, session, generation_id, ip=None, user_agent=None):
        with self._connect() as conn:
            self._lock(conn)
            conn.execute(f"INSERT INTO {self.schema}.sessions(session_id,generation_id,document) VALUES (%s,%s,%s)",
                         (session["assessment_id"], generation_id, Jsonb(session)))
            self._append(conn, "assessment_session_created", {"assessment_id": session["assessment_id"],
                "generation_id": generation_id, "snapshot_ids": session["snapshot_ids"]}, ip, user_agent)

    def load_session(self, session_id):
        with self._connect() as conn:
            row = conn.execute(f"SELECT document,revision,generation_id FROM {self.schema}.sessions WHERE session_id=%s", (session_id,)).fetchone()
        if row is None:
            return None
        return row["document"], row["revision"], row["generation_id"]

    def save_session(self, session, revision, event_type, event_data, ip=None, user_agent=None):
        with self._connect() as conn:
            self._lock(conn)
            row = conn.execute(f"""UPDATE {self.schema}.sessions SET document=%s,revision=revision+1
                WHERE session_id=%s AND revision=%s RETURNING revision""",
                (Jsonb(session), session["assessment_id"], revision)).fetchone()
            if row is None:
                raise SessionConflict("assessment session changed concurrently; reload and retry")
            self._append(conn, event_type, event_data, ip, user_agent)

    def verify_audit_chain(self):
        with self._connect() as conn:
            with conn.cursor(name="verify_boundary_audit") as cursor:
                cursor.execute(f"SELECT prev_hash,event_hash,payload FROM {self.schema}.audit_events ORDER BY sequence")
                previous = None
                for row in cursor:
                    if row["prev_hash"] != previous or row["payload"].get("prev_hash") != previous or canonical_checksum(row["payload"]) != row["event_hash"]:
                        return False
                    previous = row["event_hash"]
        return True

    def audit_count(self):
        with self._connect() as conn:
            return conn.execute(f"SELECT count(*) AS n FROM {self.schema}.audit_events").fetchone()["n"]

    def events_for_assessment(self, assessment_id):
        with self._connect() as conn:
            rows = conn.execute(f"""SELECT payload,event_hash FROM {self.schema}.audit_events
                WHERE payload->'event_data'->>'assessment_id'=%s ORDER BY sequence""", (assessment_id,)).fetchall()
        return [{**row["payload"], "event_hash": row["event_hash"]} for row in rows]
