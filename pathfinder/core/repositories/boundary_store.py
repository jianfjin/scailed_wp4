"""Transactional, cross-process storage for boundary generations and sessions."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pathfinder.core.boundary_validation import canonical_checksum, validate_withdrawal_notice
from pathfinder.core.boundary_lifecycle import dependency_closure, identity, observe_validity, runtime_input_set


class SessionConflict(ValueError):
    """A concurrent request changed this assessment since it was read."""


class NoticeConflict(ValueError):
    """A notice identity was already accepted with different content."""


class InputsWithdrawn(ValueError):
    """The exact runtime input set is currently withdrawn or affected."""

    def __init__(self, observation):
        self.observation = observation
        super().__init__("runtime inputs withdrawn; new evaluation is unavailable")


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
        """Apply the idempotent storage migration through schema v2 under a database lock."""
        s = self.schema
        with self._connect() as conn:
            self._lock(conn)
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
            conn.execute(f"CREATE TABLE IF NOT EXISTS {s}.schema_version (singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton), version INTEGER NOT NULL)")
            conn.execute(f"INSERT INTO {s}.schema_version(singleton,version) VALUES (TRUE,1) ON CONFLICT(singleton) DO NOTHING")
            version = conn.execute(f"SELECT version FROM {s}.schema_version WHERE singleton=TRUE").fetchone()["version"]
            if version not in (1, 2):
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
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.profile_active (
                profile_id TEXT PRIMARY KEY,
                generation_id TEXT NOT NULL REFERENCES {s}.generations(generation_id))""")
            conn.execute(f"""INSERT INTO {s}.profile_active(profile_id,generation_id)
                SELECT 'legacy-v1',generation_id FROM {s}.active_generation
                ON CONFLICT(profile_id) DO NOTHING""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.withdrawals (
                sequence BIGSERIAL PRIMARY KEY, notice_id TEXT NOT NULL UNIQUE,
                digest TEXT NOT NULL, document JSONB NOT NULL, actor TEXT NOT NULL)""")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.withdrawal_targets (
                notice_id TEXT NOT NULL REFERENCES {s}.withdrawals(notice_id),
                contract TEXT NOT NULL, snapshot_id TEXT NOT NULL, producer_wp TEXT NOT NULL,
                PRIMARY KEY(notice_id,contract,snapshot_id))""")
            conn.execute(f"CREATE INDEX IF NOT EXISTS withdrawal_targets_version ON {s}.withdrawal_targets(snapshot_id,contract,producer_wp)")
            conn.execute(f"""CREATE TABLE IF NOT EXISTS {s}.results (
                sequence BIGSERIAL PRIMARY KEY, result_id TEXT NOT NULL UNIQUE,
                session_id TEXT NOT NULL REFERENCES {s}.sessions(session_id),
                answer_revision BIGINT, document JSONB NOT NULL)""")
            conn.execute(f"CREATE INDEX IF NOT EXISTS results_session_revision ON {s}.results(session_id,answer_revision,sequence)")
            if version == 1:
                rows = conn.execute(f"""SELECT s.session_id,s.document,g.documents
                    FROM {s}.sessions s JOIN {s}.generations g USING(generation_id)""").fetchall()
                for row in rows:
                    original = row['document'].get('recommendation')
                    if original is None:
                        continue
                    result_id = str(uuid5(NAMESPACE_URL, f"{s}:legacy-result:{row['session_id']}"))
                    record = {'result_id': result_id, 'assessment_id': row['session_id'],
                              'answer_revision': None, 'answers': None, 'findings': None,
                              'binding_status': 'legacy_unbound', 'profile_id': 'legacy-v1',
                              'semantics_version': 'legacy-v1.0', 'original_output': original,
                              'input_set': runtime_input_set(row['documents'], row['document']['stakeholder_type'])}
                    conn.execute(f"""INSERT INTO {s}.results(result_id,session_id,answer_revision,document)
                        VALUES (%s,%s,NULL,%s) ON CONFLICT(result_id) DO NOTHING""",
                        (result_id,row['session_id'],Jsonb(record)))
                conn.execute(f"UPDATE {s}.schema_version SET version=2 WHERE singleton=TRUE")
            for table in ("snapshots", "generations", "audit_events", "withdrawals", "withdrawal_targets", "results"):
                conn.execute(f"DROP TRIGGER IF EXISTS prevent_mutation ON {s}.{table}")
                conn.execute(f"CREATE TRIGGER prevent_mutation BEFORE UPDATE OR DELETE ON {s}.{table} FOR EACH ROW EXECUTE FUNCTION {s}.prevent_mutation()")

    def check_schema(self):
        """Fail closed if the explicit migration has not been applied."""
        with self._connect() as conn:
            for table in ("schema_version", "snapshots", "generations", "active_generation", "sessions", "audit_events", "profile_active", "withdrawals", "withdrawal_targets", "results"):
                if conn.execute("SELECT to_regclass(%s) AS name", (f"{self.schema}.{table}",)).fetchone()["name"] is None:
                    raise RuntimeError(f"boundary database migration missing: {self.schema}.{table}")
            row = conn.execute(f"SELECT version FROM {self.schema}.schema_version WHERE singleton=TRUE").fetchone()
            if row is None or row["version"] != 2:
                raise RuntimeError("unsupported boundary database schema version")
            for table in ('schema_version','snapshots','generations','audit_events','withdrawals','withdrawal_targets','results','active_generation','profile_active','sessions'):
                privileges = ['SELECT']
                if table != 'schema_version':
                    privileges.append('INSERT')
                if table in ('active_generation','profile_active','sessions'):
                    privileges.append('UPDATE')
                for privilege in privileges:
                    allowed = conn.execute('SELECT has_table_privilege(current_user,%s,%s) AS allowed', (f'{self.schema}.{table}',privilege)).fetchone()['allowed']
                    if not allowed:
                        raise RuntimeError(f'boundary runtime privilege missing: {privilege} on {self.schema}.{table}')
            for table in ("snapshots", "generations", "audit_events", "withdrawals", "withdrawal_targets", "results"):
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
            inputs = dependency_closure(snapshots, [identity(item) for item in snapshots])
            self._require_valid(conn, inputs)
            for snapshot in snapshots:
                self._check_target_identity(conn, identity(snapshot))
                snapshot_id = snapshot["manifest"]["snapshot_id"]
                digest = canonical_checksum(snapshot)
                existing = conn.execute(f"SELECT digest FROM {self.schema}.snapshots WHERE snapshot_id=%s", (snapshot_id,)).fetchone()
                if existing and existing["digest"] != digest:
                    raise ValueError(f"snapshot_id {snapshot_id} was already used for different content")
                if not existing:
                    conn.execute(f"INSERT INTO {self.schema}.snapshots(snapshot_id,digest,document) VALUES (%s,%s,%s)",
                                 (snapshot_id, digest, Jsonb(snapshot)))
            conn.execute(f"INSERT INTO {self.schema}.generations(generation_id,documents) VALUES (%s,%s)", (generation_id, Jsonb(snapshots)))
            profile_id = generation.profile_id
            conn.execute(f"""INSERT INTO {self.schema}.profile_active(profile_id,generation_id) VALUES (%s,%s)
                ON CONFLICT(profile_id) DO UPDATE SET generation_id=excluded.generation_id""", (profile_id,generation_id))
            if profile_id == 'legacy-v1':
                conn.execute(f"""INSERT INTO {self.schema}.active_generation(singleton,generation_id) VALUES (TRUE,%s)
                    ON CONFLICT(singleton) DO UPDATE SET generation_id=excluded.generation_id""", (generation_id,))
            self._append(conn, "boundary_snapshots_activated", {"generation_id": generation_id,
                "snapshot_ids": dict(generation.snapshot_ids), "questionnaire_ids": dict(generation.questionnaire_ids),
                "regulatory_status": generation.regulatory_status}, ip, user_agent)
        return generation_id

    def load_active(self, profile_id='legacy-v1'):
        with self._connect() as conn:
            row = conn.execute(f"""SELECT g.generation_id,g.documents FROM {self.schema}.profile_active a
                JOIN {self.schema}.generations g ON g.generation_id=a.generation_id WHERE a.profile_id=%s""", (profile_id,)).fetchone()
        return (row["generation_id"], row["documents"]) if row else None

    def active_generation_id(self, profile_id='legacy-v1'):
        with self._connect() as conn:
            row = conn.execute(f"SELECT generation_id FROM {self.schema}.profile_active WHERE profile_id=%s", (profile_id,)).fetchone()
        return row["generation_id"] if row else None

    def load_generation(self, generation_id):
        with self._connect() as conn:
            return self._generation_documents(conn, generation_id)

    def create_session(self, session, generation_id, ip=None, user_agent=None):
        with self._connect() as conn:
            self._lock(conn)
            documents = self._generation_documents(conn, generation_id)
            inputs = runtime_input_set(documents, session['stakeholder_type'])
            self._require_valid(conn, inputs)
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

    def grant_runtime(self, role):
        """Grant the migrated runtime operations without schema ownership or DDL."""
        with self._connect() as conn:
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(self.schema),sql.Identifier(role)))
            conn.execute(sql.SQL('GRANT SELECT ON {}.schema_version TO {}').format(sql.Identifier(self.schema),sql.Identifier(role)))
            for table in ('snapshots','generations','audit_events','withdrawals','withdrawal_targets','results'):
                conn.execute(sql.SQL('GRANT SELECT, INSERT ON {}.{} TO {}').format(sql.Identifier(self.schema),sql.Identifier(table),sql.Identifier(role)))
            for table in ('active_generation','profile_active','sessions'):
                conn.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE ON {}.{} TO {}').format(sql.Identifier(self.schema),sql.Identifier(table),sql.Identifier(role)))
            conn.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}').format(sql.Identifier(self.schema),sql.Identifier(role)))

    def _generation_documents(self, conn, generation_id):
        row = conn.execute(f'SELECT documents FROM {self.schema}.generations WHERE generation_id=%s',(generation_id,)).fetchone()
        if row is None:
            raise ValueError(f'boundary generation {generation_id} not found')
        return row['documents']

    def _observation(self, conn, input_set):
        rows = conn.execute(f'SELECT sequence,document FROM {self.schema}.withdrawals ORDER BY sequence').fetchall()
        return observe_validity(input_set, [row['document'] for row in rows], rows[-1]['sequence'] if rows else 0)

    def current_validity(self, input_set):
        with self._connect() as conn:
            return self._observation(conn, input_set)

    def _require_valid(self, conn, input_set):
        observation = self._observation(conn, input_set)
        if not observation['valid']:
            raise InputsWithdrawn(observation)
        return observation

    def _check_target_identity(self, conn, target):
        row = conn.execute(f'SELECT document FROM {self.schema}.snapshots WHERE snapshot_id=%s', (target['snapshot_id'],)).fetchone()
        if row is not None and identity(row['document']) != {key: target[key] for key in ('contract','snapshot_id','producer_wp')}:
            raise ValueError('snapshot identity conflicts with target contract or producer')
        conflict = conn.execute(f'''SELECT 1 FROM {self.schema}.withdrawal_targets
            WHERE snapshot_id=%s AND (contract<>%s OR producer_wp<>%s) LIMIT 1''',
            (target['snapshot_id'],target['contract'],target['producer_wp'])).fetchone()
        if conflict:
            raise ValueError('snapshot target identity conflicts with contract or producer')

    def withdraw(self, notice, actor, ip=None, user_agent=None):
        errors = validate_withdrawal_notice(notice)
        if errors:
            raise ValueError('invalid withdrawal notice: ' + '; '.join(errors))
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError('withdrawal administrator identity is required')
        notice_id = notice['payload']['notice_id']
        digest = canonical_checksum(notice)
        with self._connect() as conn:
            self._lock(conn)
            previous = conn.execute(f'SELECT digest,sequence FROM {self.schema}.withdrawals WHERE notice_id=%s', (notice_id,)).fetchone()
            if previous is not None:
                if previous['digest'] != digest:
                    raise NoticeConflict('withdrawal notice identity was already used for different content')
                return {'accepted': True, 'created': False, 'notice_id': notice_id, 'lifecycle_revision': previous['sequence']}
            for target in notice['payload']['targets']:
                self._check_target_identity(conn, target)
            row = conn.execute(f'INSERT INTO {self.schema}.withdrawals(notice_id,digest,document,actor) VALUES (%s,%s,%s,%s) RETURNING sequence',
                               (notice_id,digest,Jsonb(notice),actor)).fetchone()
            for target in notice['payload']['targets']:
                conn.execute(f'INSERT INTO {self.schema}.withdrawal_targets(notice_id,contract,snapshot_id,producer_wp) VALUES (%s,%s,%s,%s)',
                             (notice_id,target['contract'],target['snapshot_id'],target['producer_wp']))
            self._append(conn,'boundary_inputs_withdrawn',{'notice_id':notice_id,'actor':actor,
                         'targets':notice['payload']['targets'],'source_confirmation':notice['payload']['source_confirmation']},ip,user_agent)
            return {'accepted': True, 'created': True, 'notice_id': notice_id, 'lifecycle_revision': row['sequence']}

    def publish_result(self, session, revision, result_record, ip=None, user_agent=None):
        """Publish evidence, session state and success audit as one guarded transaction."""
        with self._connect() as conn:
            self._lock(conn)
            row = conn.execute(f'SELECT document,revision,generation_id FROM {self.schema}.sessions WHERE session_id=%s', (session['assessment_id'],)).fetchone()
            if row is None or row['revision'] != revision or row['document'].get('answer_revision',0) != result_record['answer_revision']:
                raise SessionConflict('assessment session changed concurrently; reload and retry')
            if result_record['assessment_id'] != session['assessment_id']:
                raise ValueError('result assessment binding does not match session')
            actual_inputs = runtime_input_set(self._generation_documents(conn,row['generation_id']),row['document']['stakeholder_type'])
            if result_record['input_set'] != actual_inputs:
                raise ValueError('result input set does not match session generation')
            if result_record.get('answers') != row['document'].get('answers'):
                raise SessionConflict('result answers do not match persisted answer revision')
            self._require_valid(conn, actual_inputs)
            conn.execute(f'INSERT INTO {self.schema}.results(result_id,session_id,answer_revision,document) VALUES (%s,%s,%s,%s)',
                         (result_record['result_id'],session['assessment_id'],result_record['answer_revision'],Jsonb(result_record)))
            conn.execute(f'UPDATE {self.schema}.sessions SET document=%s,revision=revision+1 WHERE session_id=%s',
                         (Jsonb(session),session['assessment_id']))
            self._append(conn,'recommendation_generated',{'assessment_id':session['assessment_id'],
                         'result_id':result_record['result_id'],'answer_revision':result_record['answer_revision']},ip,user_agent)
        return result_record['result_id']

    def load_result(self, session_id, result_id=None):
        with self._connect() as conn:
            if result_id is None:
                row = conn.execute(f'SELECT document FROM {self.schema}.results WHERE session_id=%s ORDER BY sequence DESC LIMIT 1', (session_id,)).fetchone()
            else:
                row = conn.execute(f'SELECT document FROM {self.schema}.results WHERE session_id=%s AND result_id=%s', (session_id,result_id)).fetchone()
        return row['document'] if row else None

    def results_for_session(self, session_id):
        with self._connect() as conn:
            rows = conn.execute(f'SELECT document FROM {self.schema}.results WHERE session_id=%s ORDER BY sequence', (session_id,)).fetchall()
        return [row['document'] for row in rows]
