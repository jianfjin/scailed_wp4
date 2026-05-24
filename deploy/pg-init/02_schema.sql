-- ═══════════════════════════════════════════════════════════════
-- PostgreSQL Init: 02_schema.sql
-- SCAILED Pathfinder 核心表结构 (与 architecture-spec.html §04 对齐)
-- 两 Schema: assess (评估数据) + ref (参考数据)
-- ═══════════════════════════════════════════════════════════════

\c pathfinder

-- ─── Schema ────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS assess;
CREATE SCHEMA IF NOT EXISTS ref;

SET search_path TO assess, ref, public;

-- ─── 1. Roadmap Nodes (ref schema, 来自 WP3) ───────────────────
CREATE TABLE ref.roadmap_nodes (
    id              SERIAL PRIMARY KEY,
    node_id         TEXT UNIQUE NOT NULL,       -- 'R2.3-A'
    label           TEXT NOT NULL,              -- 'Establish DPO'
    description     TEXT,
    parent_node     TEXT,                       -- self-ref for DAG
    prerequisites   TEXT[],                     -- ['R1.2', 'R2.1']
    maturity_level  INT CHECK (maturity_level BETWEEN 1 AND 5),
    effort_estimate TEXT,                       -- 'low'|'medium'|'high'
    related_wp      TEXT,                       -- 'WP5'|'WP6'|'WP7'
    x FLOAT, y FLOAT,                          -- visualization coords
    metadata        JSONB,
    schema_version  TEXT NOT NULL DEFAULT 'v1.0-m3-freeze'
);

-- ─── 2. Recommendation Rules (ref schema, 核心IP) ──────────────
CREATE TABLE ref.recommendation_rules (
    id                SERIAL PRIMARY KEY,
    rule_id           TEXT UNIQUE NOT NULL,     -- 'R-PHARMA-AI-001'
    parent_rule_id    INT REFERENCES ref.recommendation_rules(id),
    rule_type         TEXT NOT NULL DEFAULT 'preference'
                      CHECK (rule_type IN ('eligibility','exclusion','preference','override')),
    node_id           TEXT REFERENCES ref.roadmap_nodes(node_id),
    stakeholder_type  TEXT,
    condition         JSONB NOT NULL,           -- {"answers":{"q2.1":{"gte":3}}}
    action_title      TEXT NOT NULL,
    action_text       TEXT NOT NULL,
    compliance_ref    TEXT[],                   -- ['GDPR-Art.37','EHDS-Art.50']
    priority          INT DEFAULT 0,
    source_wp         TEXT,
    source_doc_ref    TEXT,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    rule_version      TEXT NOT NULL
);
CREATE INDEX idx_rules_stakeholder ON ref.recommendation_rules(stakeholder_type);
CREATE INDEX idx_rules_node ON ref.recommendation_rules(node_id);
CREATE INDEX idx_rules_condition ON ref.recommendation_rules USING GIN (condition);

-- ─── 3. Assessment Sessions (assess schema) ────────────────────
CREATE TABLE assess.assessment_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stakeholder_type TEXT,
    status          TEXT DEFAULT 'in_progress',
    answers         JSONB,
    current_node    TEXT REFERENCES ref.roadmap_nodes(node_id),
    recommendations JSONB,
    created_at      TIMESTAMPTZ DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

-- ─── 4. Audit Log (assess schema, 不可变) ──────────────────────
CREATE TABLE assess.audit_log (
    id              SERIAL PRIMARY KEY,
    session_id      UUID REFERENCES assess.assessment_sessions(id),
    event_type      TEXT NOT NULL,
    event_data      JSONB NOT NULL,
    prev_hash       TEXT,                        -- SHA-256 of previous row
    timestamp       TIMESTAMPTZ DEFAULT now(),
    ip_hash         TEXT,
    user_agent_hash TEXT
);

-- 审计日志不可变触发器
CREATE OR REPLACE FUNCTION assess.audit_no_update_fn()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: UPDATE forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION assess.audit_no_delete_fn()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: DELETE forbidden';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_no_update
    BEFORE UPDATE ON assess.audit_log
    FOR EACH ROW EXECUTE FUNCTION assess.audit_no_update_fn();

CREATE TRIGGER audit_no_delete
    BEFORE DELETE ON assess.audit_log
    FOR EACH ROW EXECUTE FUNCTION assess.audit_no_delete_fn();

-- ─── 5. Schema Versions (migration tracking) ───────────────────
CREATE TABLE ref.schema_versions (
    id              SERIAL PRIMARY KEY,
    table_name      TEXT NOT NULL,
    version         TEXT NOT NULL,
    applied_at      TIMESTAMPTZ DEFAULT now(),
    migration_hash  TEXT NOT NULL,
    notes           TEXT
);
CREATE INDEX idx_schema_versions_table ON ref.schema_versions(table_name, version);

-- ─── 6. Rule Versions (auditable rule evolution) ───────────────
CREATE TABLE ref.rule_versions (
    id              SERIAL PRIMARY KEY,
    rule_id         TEXT NOT NULL,
    version         TEXT NOT NULL,
    snapshot        JSONB NOT NULL,
    changed_by      TEXT,
    change_reason   TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(rule_id, version)
);
CREATE INDEX idx_rule_versions_rule ON ref.rule_versions(rule_id, version);

-- ─── 7. Upstream Data Snapshots (WP3/WP8 data lineage) ────────
CREATE TABLE ref.upstream_data_snapshots (
    id              SERIAL PRIMARY KEY,
    source          TEXT NOT NULL,               -- 'WP3' | 'WP8'
    data_hash       TEXT NOT NULL,
    fetched_at      TIMESTAMPTZ DEFAULT now(),
    raw_payload     JSONB,
    schema_version  TEXT,
    superseded_by   INT REFERENCES ref.upstream_data_snapshots(id)
);
CREATE INDEX idx_upstream_snapshots_source ON ref.upstream_data_snapshots(source, fetched_at);

-- ─── 8. AGE Graph Setup (图关系投影到 AGE graph) ───────────────
-- 创建 Cypher 图空间用于 DAG 路径搜索
SELECT ag_catalog.create_graph('pathfinder_graph');

-- ─── Initial schema version record ─────────────────────────────
INSERT INTO ref.schema_versions (table_name, version, migration_hash, notes)
VALUES
    ('all', 'v1.0-m3-freeze', 'init', 'Initial schema from council resolution 2026-05-13'),
    ('recommendation_rules', 'v1.0', 'init', 'Rule tree structure with parent_rule_id'),
    ('audit_log', 'v1.0', 'init', 'TRIGGER-based immutability with prev_hash chain');

-- ─── 9. Request Log (看板数据源) ────────────────────────────────
CREATE TABLE IF NOT EXISTS assess.request_log (
    id              BIGSERIAL PRIMARY KEY,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now(),
    ip              TEXT NOT NULL,
    method          TEXT NOT NULL,
    endpoint        TEXT NOT NULL,
    status_code     INT,
    duration_ms     INT,
    user_agent      TEXT,
    error_message   TEXT,
    assessment_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_request_log_timestamp ON assess.request_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_request_log_ip ON assess.request_log (ip);
CREATE INDEX IF NOT EXISTS idx_request_log_status ON assess.request_log (status_code);
