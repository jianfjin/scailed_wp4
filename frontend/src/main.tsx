import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  buildStakeholderOptions,
  filterStakeholderOptions,
  formatStakeholderLoadedCopy,
  type StakeholderOption,
} from "./stakeholderCatalog";
import "./styles.css";

type PathfinderReport = {
  disclaimer?: string;
  audit_chain_valid?: boolean;
  missing_data_warnings?: string[];
  session?: { stakeholder_type?: string; target_scenario?: string; status?: string };
  readiness_snapshot?: {
    maturity_scores?: Record<string, number>;
    capabilities?: string[];
    missing_capabilities?: string[];
    regulatory_flags?: string[];
    confidence?: number;
    confidence_warnings?: string[];
    derivation_mode?: string;
    pain_points?: string[];
    source_wp2_stakeholder_id?: string;
    source_wp2_snapshot_version?: string;
    source_wp3_snapshot_version?: string;
  };
  recommended_path?: {
    status?: string;
    current_node?: string;
    target_node?: string;
    next_steps?: Array<{ node_id?: string; label?: string; dimension?: string }>;
    blockers?: string[];
    warnings?: string[];
    path_backend?: string;
    trace?: {
      answer_ids?: string[];
      roadmap_node_ids?: string[];
      triggered_rule_ids?: string[];
      regulatory_refs?: string[];
      upstream_snapshot_version?: string;
      schema_version?: string;
      rule_version?: string;
    };
  };
};

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const TOKEN = "demo-token";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN}`,
      ...(init?.headers || {}),
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = (body as { detail?: string | { detail?: string } }).detail;
    throw new Error(typeof detail === "string" ? detail : detail?.detail || response.statusText);
  }
  return response.json();
}

function EvidenceList({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="evidence-block">
      <h3>{title}</h3>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </div>
  );
}

function KeyValueList({ title, values }: { title: string; values: Record<string, string | number | undefined> }) {
  return (
    <div className="evidence-block">
      <h3>{title}</h3>
      <dl>
        {Object.entries(values).map(([key, value]) => (
          <React.Fragment key={key}>
            <dt>{key}</dt>
            <dd>{value ?? "n/a"}</dd>
          </React.Fragment>
        ))}
      </dl>
    </div>
  );
}

function ReportSummary({ report, assessmentId }: { report: PathfinderReport; assessmentId?: string }) {
  const path = report.recommended_path;
  const snapshot = report.readiness_snapshot;
  const trace = path?.trace;
  const blocked = path?.status === "blocked";

  const backendLabel =
    path?.path_backend === "cypher" ? "AGE Cypher" :
    path?.path_backend === "n/a (blocked)" ? "n/a" :
    "Python BFS";

  return (
    <div className="report-summary">
      <div className="status-row">
        <strong>{blocked ? "Blocked" : "Ready"}</strong>
        <span>{report.audit_chain_valid ? "Audit chain valid" : "Audit chain needs review"}</span>
      </div>

      {report.disclaimer && <p className="notice">{report.disclaimer}</p>}

      <div className="summary-grid">
        <div>
          <h3>Assessment</h3>
          <dl>
            <dt>Stakeholder</dt>
            <dd>{report.session?.stakeholder_type || "unknown"}</dd>
            <dt>Scenario</dt>
            <dd>{report.session?.target_scenario || "unknown"}</dd>
            <dt>Confidence</dt>
            <dd>{snapshot?.confidence ?? "n/a"}</dd>
          </dl>
        </div>
        <div>
          <h3>Path</h3>
          <dl>
            <dt>Current</dt>
            <dd>{path?.current_node || "n/a"}</dd>
            <dt>Target</dt>
            <dd>{path?.target_node || "n/a"}</dd>
            <dt>Engine</dt>
            <dd className="path-backend-badge" data-backend={path?.path_backend || "python"}>
              {backendLabel}
            </dd>
          </dl>
        </div>
      </div>

      <KeyValueList
        title="Derived readiness"
        values={{
          Mode: snapshot?.derivation_mode,
          "WP2 stakeholder": snapshot?.source_wp2_stakeholder_id,
          "WP2 snapshot": snapshot?.source_wp2_snapshot_version,
          "WP3 snapshot": snapshot?.source_wp3_snapshot_version,
        }}
      />
      <EvidenceList title="WP2 capabilities" items={snapshot?.capabilities} />
      <EvidenceList title="WP2 pain points" items={snapshot?.pain_points} />
      <EvidenceList title="Derived missing capabilities" items={snapshot?.missing_capabilities} />
      <EvidenceList title="Derived regulatory flags" items={snapshot?.regulatory_flags} />

      <EvidenceList title="Blockers" items={path?.blockers} />

      {path?.next_steps?.length ? (
        <div className="evidence-block">
          <h3>Recommended path</h3>
          <ol>
            {path.next_steps.map((step, index) => (
              <li key={step.node_id || index}>
                <strong>{step.label || step.node_id}</strong>
                {step.dimension && <span>{step.dimension}</span>}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      {assessmentId && (
        <p style={{marginTop:12, marginBottom:8}}>
          <a
            href={`/v1/assessments/${assessmentId}/report?format=html&token=${TOKEN}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{color:"#1d5d43",fontWeight:600}}
          >
            View visualization →
          </a>
        </p>
      )}

      <div className="evidence-block">
        <h3>Trace evidence</h3>
        <dl>
          <dt>Answers</dt>
          <dd>{trace?.answer_ids?.join(", ") || "n/a"}</dd>
          <dt>Roadmap nodes</dt>
          <dd>{trace?.roadmap_node_ids?.join(", ") || "n/a"}</dd>
          <dt>Triggered rules</dt>
          <dd>{trace?.triggered_rule_ids?.join(", ") || "n/a"}</dd>
          <dt>Regulatory refs</dt>
          <dd>{trace?.regulatory_refs?.join(", ") || "n/a"}</dd>
          <dt>Snapshot</dt>
          <dd>{trace?.upstream_snapshot_version || "n/a"}</dd>
        </dl>
      </div>
    </div>
  );
}

/* ─── backend toggle ────────────────────────────────────── */

function BackendToggle({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const isCypher = value === "cypher";
  return (
    <div className="backend-toggle">
      <span className="backend-label">Path engine</span>
      <button
        type="button"
        className={`toggle-btn ${!isCypher ? "active" : ""}`}
        onClick={() => onChange("python")}
      >
        Python BFS
      </button>
      <button
        type="button"
        className={`toggle-btn ${isCypher ? "active" : ""}`}
        onClick={() => onChange("cypher")}
      >
        AGE Cypher
      </button>
    </div>
  );
}

/* ─── stakeholder picker ─────────────────────────────────── */

function StakeholderPicker({
  options,
  value,
  onChange,
}: {
  options: StakeholderOption[];
  value: string;
  onChange: (value: string) => void;
}) {
  const selected = options.find((option) => option.value === value);
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => filterStakeholderOptions(options, query), [options, query]);
  const hiddenCount = Math.max(0, options.length - filtered.length);
  const shownGroups = useMemo(() => {
    const groups = new Map<string, StakeholderOption[]>();
    for (const option of filtered) {
      groups.set(option.group, [...(groups.get(option.group) || []), option]);
    }
    return Array.from(groups.entries());
  }, [filtered]);

  return (
    <div className="stakeholder-picker">
      <label htmlFor="stakeholder-search">Stakeholder profile</label>
      <input
        id="stakeholder-search"
        type="search"
        placeholder="Search by category, profile ID, or label…"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <div className="selected-stakeholder">
        <span>Selected</span>
        <strong>{selected?.label || "Choose a stakeholder profile"}</strong>
        {selected && <code>{selected.value}</code>}
      </div>
      <div className="stakeholder-results" role="listbox" aria-label="Stakeholder profiles">
        {shownGroups.map(([group, groupOptions]) => (
          <div className="stakeholder-group" key={group}>
            <div className="stakeholder-group-title">{group}</div>
            {groupOptions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`stakeholder-option ${option.value === value ? "active" : ""}`}
                onClick={() => {
                  onChange(option.value);
                  setQuery(option.group);
                }}
                role="option"
                aria-selected={option.value === value}
              >
                <span>{option.label}</span>
                <code>{option.value}</code>
              </button>
            ))}
          </div>
        ))}
        {!filtered.length && <p className="stakeholder-empty">No stakeholder profiles match this search.</p>}
      </div>
      {hiddenCount > 0 && (
        <p className="stakeholder-hint">Showing first {filtered.length} matches. Search to narrow {options.length} profiles.</p>
      )}
    </div>
  );
}

/* ─── main app ──────────────────────────────────────────── */

function App() {
  const [types, setTypes] = useState<string[]>([]);
  const [stakeholderType, setStakeholderType] = useState("");
  const [report, setReport] = useState<PathfinderReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [pathBackend, setPathBackend] = useState("python");
  const [bannerText, setBannerText] = useState("Loading status…");
  const [lastAssessmentId, setLastAssessmentId] = useState("");
  const stakeholderOptions = useMemo(() => buildStakeholderOptions(types), [types]);
  const loadedCopy = useMemo(() => formatStakeholderLoadedCopy(stakeholderOptions), [stakeholderOptions]);

  useEffect(() => {
    api<{ stakeholder_types: string[] }>("/v1/questionnaires")
      .then((data) => {
        setTypes(data.stakeholder_types);
        setStakeholderType((current) => (
          current && data.stakeholder_types.includes(current)
            ? current
            : (data.stakeholder_types[0] || "")
        ));
      })
      .catch((err) => setError(String(err)));
    api<{ mode: string; import_reports?: Record<string, { activated_records?: number }> }>("/health")
      .then((h) => {
        if (h.mode === "deployed" && h.import_reports?.upstream) {
          const records = h.import_reports.upstream.activated_records;
          const recordText = typeof records === "number" ? `${records} records` : "upstream records";
          setBannerText(`Deployed mode. Mock upstream data loaded (${recordText}).`);
        } else if (h.mode === "deployed") {
          setBannerText("Deployed mode. PostgreSQL + Apache AGE active.");
        } else {
          setBannerText("Demo mode. WP2/WP3/WP8 inputs pending.");
        }
      })
      .catch(() => setBannerText("Demo mode. WP2/WP3/WP8 inputs pending."));
  }, []);


  async function runAssessment() {
    if (!stakeholderType) return;
    setError("");
    setLoading(true);
    setReport(null);
    try {
      const session = await api<{ assessment_id: string }>("/v1/assessments", {
        method: "POST",
        body: JSON.stringify({ stakeholder_type: stakeholderType, target_scenario: "secondary-use-readiness" }),
      });
      setLastAssessmentId(session.assessment_id);
      await api(`/v1/assessments/${session.assessment_id}/recommendations?path_backend=${pathBackend}`, {
        method: "POST",
      });
      const r = await api<PathfinderReport>(`/v1/assessments/${session.assessment_id}/report`);
      setReport(r);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>SCAILED Pathfinder</h1>
          <p>EHDS readiness path planner. Select a stakeholder to derive your roadmap path with full trace.</p>
        </div>
        <div className="toolbar-actions">
          <BackendToggle value={pathBackend} onChange={setPathBackend} />
          <button type="button" className="submit-btn" onClick={runAssessment} disabled={!stakeholderType || loading}>
            {loading ? "Running..." : "Run derived assessment"}
          </button>
        </div>
      </section>

      <section className="layout">
        <aside className="panel">
          <StakeholderPicker
            options={stakeholderOptions}
            value={stakeholderType}
            onChange={setStakeholderType}
          />
          <div className="banner">
            <strong>{loadedCopy}</strong>
            <span>{bannerText}</span>
          </div>
        </aside>

        <section className="panel">
          <h2>Derived readiness evidence</h2>
          <p className="notice">
            Readiness is derived from WP2 stakeholder capabilities and WP3 roadmap evidence.
          </p>
          <div className="evidence-block">
            <h3>Selected source</h3>
            <dl>
              <dt>Stakeholder</dt>
              <dd>{stakeholderType || "n/a"}</dd>
              <dt>Scenario</dt>
              <dd>secondary-use-readiness</dd>
            </dl>
          </div>
        </section>
        <section className="panel report">
          <h2>Traceable report</h2>
          {error && <p className="error">{error}</p>}
          {loading && <p>Running assessment…</p>}
          {!report && !loading && <p>Run a derived assessment to see your roadmap path.</p>}
          {report && <ReportSummary report={report} assessmentId={lastAssessmentId} />}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
