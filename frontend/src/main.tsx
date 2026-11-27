import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  buildStakeholderOptions,
  filterStakeholderOptions,
  formatStakeholderLoadedCopy,
  type StakeholderOption,
} from "./stakeholderCatalog";
import { projectAssessmentSemantics, type SemanticsReport } from "./assessmentSemantics";
import "./styles.css";

type PathfinderReport = SemanticsReport & {
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
    regulatory_status?: string;
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

type BoundaryQuestion = {
  question_id: string;
  label: string;
  question_type: "single_choice" | "multi_choice" | "numeric" | "text";
  required: boolean;
  options: string[];
  min_value: number | null;
  max_value: number | null;
  capability_id?: string;
  state_field?: string;
};
type BoundaryQuestionnaire = {
  stakeholder_type: string;
  title: string;
  target_scenarios: string[];
  questions: BoundaryQuestion[];
};
type Answer = string | number | string[];

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";
const API_VERSION = import.meta.env.VITE_PATHFINDER_API_VERSION || "v1";
if (!["v1", "v2"].includes(API_VERSION)) throw new Error("VITE_PATHFINDER_API_VERSION must be v1 or v2");
const API_PREFIX = `/${API_VERSION}`;
let accessToken = import.meta.env.DEV ? "demo-token" : "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
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
  const semantics = projectAssessmentSemantics(report);
  const [viewError, setViewError] = useState("");

  async function openVisualization() {
    if (!assessmentId) return;
    const tab = window.open("", "_blank");
    if (!tab) { setViewError("Allow pop-ups to open the visualization."); return; }
    tab.opener = null;
    try {
      const response = await fetch(`${API_BASE}${API_PREFIX}/assessments/${encodeURIComponent(assessmentId)}/report?format=html${semantics.resultId ? `&result_id=${encodeURIComponent(semantics.resultId)}` : ""}`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!response.ok) throw new Error(`Report request failed (${response.status})`);
      const url = URL.createObjectURL(await response.blob());
      tab.location.href = url;
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      setViewError("");
    } catch (err) {
      tab.close();
      setViewError(String(err));
    }
  }

  const backendLabel =
    path?.path_backend === "cypher" ? "AGE Cypher" :
    path?.path_backend === "n/a (blocked)" ? "n/a" :
    "Python BFS";

  return (
    <div className="report-summary">
      <div className="status-row">
        <strong>{semantics.heading}</strong>
        <span>{report.audit_chain_valid ? "Audit chain valid" : "Audit chain needs review"}</span>
      </div>

      {report.disclaimer && <p className="notice">{report.disclaimer}</p>}
      {path?.regulatory_status === "unverified" && <p className="notice">Regulatory status is unverified.</p>}

      <div className="summary-grid">
        <div>
          <h3>Assessment</h3>
          <dl>
            <dt>Stakeholder</dt>
            <dd>{report.session?.stakeholder_type || "unknown"}</dd>
            <dt>Scenario</dt>
            <dd>{report.session?.target_scenario || "unknown"}</dd>
            <dt>{semantics.confidenceLabel}</dt>
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

      {snapshot?.derivation_mode && <KeyValueList
        title="Derived readiness"
        values={{
          Mode: snapshot?.derivation_mode,
          "WP2 stakeholder": snapshot?.source_wp2_stakeholder_id,
          "WP2 snapshot": snapshot?.source_wp2_snapshot_version,
          "WP3 snapshot": snapshot?.source_wp3_snapshot_version,
        }}
      />}
      {semantics.profile === "legacy-v1" && <>
        <p className="notice">Legacy semantics: type-derived information is reference/demo guidance.</p>
        <EvidenceList title="WP2 type reference capabilities" items={snapshot?.capabilities} />
        <EvidenceList title="WP2 pain points" items={snapshot?.pain_points} />
        <EvidenceList title="Derived reference gaps" items={snapshot?.missing_capabilities} />
        <EvidenceList title="Derived regulatory flags" items={snapshot?.regulatory_flags} />
      </>}
      <KeyValueList title="Result evidence and current validity" values={{
        "Result ID": semantics.resultId,
        "Answer revision": semantics.answerRevision,
        "Original result": semantics.originalStatus,
        "Current validity": semantics.validityStatus,
        "Lifecycle revision": semantics.lifecycleRevision,
        "Semantic profile": semantics.profile,
      }} />
      {semantics.historical && <p className="notice" role="status">This result is historical. Its original output is preserved; withdrawn inputs cannot support new guidance.</p>}
      <EvidenceList title="Missing information" items={semantics.missingInformation} />
      {semantics.findings.length > 0 && <div className="evidence-block">
        <h3>Capability findings</h3>
        <p>Answer completeness does not verify a self-report.</p>
        {semantics.findings.map((finding) => <dl key={finding.capabilityId}>
          <dt>{finding.capabilityId}</dt>
          <dd>{finding.judgmentLabel} · {finding.sourceLabel} · {finding.verificationLabel}</dd>
          <dt>Answer evidence</dt><dd>{finding.answer_ids.join(", ") || "No current answer"}</dd>
          <dt>Evidence references</dt><dd>{finding.evidence_refs.join(", ") || "None recorded"}</dd>
        </dl>)}
      </div>}
      <EvidenceList title="Affected input versions" items={semantics.affectedInputs.map((item) => `${item.contract} / ${item.snapshot_id} (${item.producer_wp}): ${item.reason}; notice ${item.notice_id}; dependency ${item.dependency_path.join(" → ")}`)} />

      <EvidenceList title="Blockers" items={path?.blockers} />

      {path?.next_steps?.length ? (
        <div className="evidence-block">
          <h3>{semantics.pathHeading}</h3>
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
          <button type="button" className="visualization-link" onClick={openVisualization}>View visualization →</button>
          {viewError && <span className="error" role="alert"> {viewError}</span>}
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
  const [token, setToken] = useState(accessToken);
  const [tokenInput, setTokenInput] = useState(accessToken);
  const [stakeholderType, setStakeholderType] = useState("");
  const [report, setReport] = useState<PathfinderReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [pathBackend, setPathBackend] = useState("python");
  const [bannerText, setBannerText] = useState("Loading status…");
  const [lastAssessmentId, setLastAssessmentId] = useState("");
  const [boundaryMode, setBoundaryMode] = useState(false);
  const [questionnaire, setQuestionnaire] = useState<BoundaryQuestionnaire | null>(null);
  const [targetScenario, setTargetScenario] = useState("");
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [invalidQuestions, setInvalidQuestions] = useState<string[]>([]);
  const validationRef = useRef<HTMLDivElement>(null);
  const assessmentRunRef = useRef(0);
  const stakeholderOptions = useMemo(() => buildStakeholderOptions(types), [types]);
  const loadedCopy = useMemo(() => formatStakeholderLoadedCopy(stakeholderOptions), [stakeholderOptions]);

  function handleStakeholderTypeChange(nextStakeholderType: string) {
    assessmentRunRef.current += 1;
    setStakeholderType(nextStakeholderType);
    setReport(null);
    setError("");
    setLastAssessmentId("");
    setLoading(false);
    setQuestionnaire(null);
    setAnswers({});
    setInvalidQuestions([]);
  }

  function invalidateDraftResult() {
    assessmentRunRef.current += 1;
    setReport(null);
    setLastAssessmentId("");
    setLoading(false);
    setError("");
  }

  function handleAnswersChange(nextAnswers: Record<string, Answer>) {
    invalidateDraftResult();
    setAnswers(nextAnswers);
  }

  useEffect(() => {
    if (!token) return;
    api<{ stakeholder_types: string[]; mock_data_mode: boolean }>(`${API_PREFIX}/questionnaires`)
      .then((data) => {
        setTypes(data.stakeholder_types);
        setBoundaryMode(!data.mock_data_mode);
        setStakeholderType((current) => (
          current && data.stakeholder_types.includes(current)
            ? current
            : (data.stakeholder_types[0] || "")
        ));
      })
      .catch((err) => setError(String(err)));
    api<{ mode: string; active_snapshot_ids?: Record<string, string>; import_reports?: Record<string, { activated_records?: number }> }>("/health")
      .then((h) => {
        if (API_VERSION === "v2") {
          setBannerText("Evidence v2: current answers and validated partner snapshots are required.");
        } else if (h.active_snapshot_ids && Object.keys(h.active_snapshot_ids).length) {
          setBannerText("Validated partner snapshots active.");
        } else if (h.mode === "deployed" && h.import_reports?.upstream) {
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
  }, [token]);

  useEffect(() => {
    if (!boundaryMode || !stakeholderType) return;
    let cancelled = false;
    setQuestionnaire(null);
    setAnswers({});
    setInvalidQuestions([]);
    api<BoundaryQuestionnaire>(`${API_PREFIX}/questionnaires/${encodeURIComponent(stakeholderType)}`)
      .then((data) => {
        if (cancelled) return;
        setQuestionnaire(data);
        setTargetScenario(data.target_scenarios[0] || "");
        setAnswers(Object.fromEntries(data.questions.filter((q) => q.question_type === "multi_choice").map((q) => [q.question_id, []])));
      })
      .catch((err) => { if (!cancelled) setError(String(err)); });
    return () => { cancelled = true; };
  }, [boundaryMode, stakeholderType]);


  async function runAssessment() {
    if (!stakeholderType) return;
    if (boundaryMode) {
      if (!questionnaire || questionnaire.stakeholder_type !== stakeholderType || !targetScenario) return;
      const invalid = questionnaire.questions.filter((q) => {
        const value = answers[q.question_id];
        if (q.required && (value === undefined || value === "")) return true;
        if (value === undefined || value === "") return false;
        return q.question_type === "numeric" && value !== undefined &&
          (typeof value !== "number" || !Number.isInteger(value) ||
           (q.min_value !== null && value < q.min_value) || (q.max_value !== null && value > q.max_value));
      });
      if (invalid.length) {
        setInvalidQuestions(invalid.map((q) => q.question_id));
        setTimeout(() => validationRef.current?.focus(), 0);
        return;
      }
      setInvalidQuestions([]);
    }
    const runId = assessmentRunRef.current + 1;
    assessmentRunRef.current = runId;
    setError("");
    setLoading(true);
    setReport(null);
    try {
      const session = await api<{ assessment_id: string }>(`${API_PREFIX}/assessments`, {
        method: "POST",
        body: JSON.stringify({ stakeholder_type: stakeholderType, target_scenario: boundaryMode ? targetScenario : "secondary-use-readiness" }),
      });
      if (assessmentRunRef.current !== runId) return;
      setLastAssessmentId(session.assessment_id);
      if (boundaryMode) {
        await api(`${API_PREFIX}/assessments/${session.assessment_id}/answers/batch`, {
          method: "POST", body: JSON.stringify({ answers }),
        });
        if (assessmentRunRef.current !== runId) return;
      }
      await api(`${API_PREFIX}/assessments/${session.assessment_id}/recommendations?path_backend=${pathBackend}`, {
        method: "POST",
      });
      if (assessmentRunRef.current !== runId) return;
      const r = await api<PathfinderReport>(`${API_PREFIX}/assessments/${session.assessment_id}/report`);
      if (assessmentRunRef.current !== runId) return;
      setReport(r);
    } catch (err) {
      if (assessmentRunRef.current === runId) {
        setError(String(err));
      }
    } finally {
      if (assessmentRunRef.current === runId) {
        setLoading(false);
      }
    }
  }

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>SCAILED Pathfinder</h1>
          <p>{API_VERSION === "v2" ? "Evidence v2 assessment" : "Legacy assessment semantics"}</p>
          <p>EHDS readiness path planner. Select a stakeholder to build a roadmap path with full trace.</p>
        </div>
        <div className="toolbar-actions">
          <BackendToggle value={pathBackend} onChange={setPathBackend} />
          <button type="button" className="submit-btn" onClick={runAssessment} disabled={!stakeholderType || loading || (boundaryMode && (!questionnaire || questionnaire.stakeholder_type !== stakeholderType))}>
            {loading ? "Running..." : boundaryMode ? "Run assessment" : "Run derived assessment"}
          </button>
        </div>
      </section>

      <section className="layout">
        <aside className="panel">
          <form className="token-form" onSubmit={(event) => {
            event.preventDefault();
            const next = tokenInput.trim();
            if (next === token) return;
            accessToken = next;
            setToken(next);
            setTypes([]);
            setStakeholderType("");
            setQuestionnaire(null);
            setReport(null);
            setError("");
          }}>
            <label htmlFor="access-token">Access token</label>
            <input id="access-token" type="password" autoComplete="current-password" value={tokenInput} onChange={(event) => setTokenInput(event.target.value)} />
            <button type="submit">Connect</button>
          </form>
          {!token && <p className="notice">Enter your access token to load stakeholder profiles.</p>}
          <StakeholderPicker
            options={stakeholderOptions}
            value={stakeholderType}
            onChange={handleStakeholderTypeChange}
          />
          <div className="banner">
            <strong>{boundaryMode ? `${types.length} stakeholder profile${types.length === 1 ? "" : "s"} available.` : loadedCopy}</strong>
            <span>{bannerText}</span>
          </div>
        </aside>

        <section className="panel">
          <h2>{boundaryMode ? "Readiness questionnaire" : "Derived readiness evidence"}</h2>
          <p className="notice">{boundaryMode ? "Answer the questions to generate a traceable roadmap." : "Readiness is derived from WP2 stakeholder capabilities and WP3 roadmap evidence."}</p>
          {boundaryMode && questionnaire && <div className="question-list">
            {invalidQuestions.length > 0 && <div className="error" role="alert" tabIndex={-1} ref={validationRef}>
              <strong>Please check these answers:</strong>
              <ul>{questionnaire.questions.filter((q) => invalidQuestions.includes(q.question_id)).map((q) => <li key={q.question_id}><a href={`#${q.question_id}`}>{q.label}</a></li>)}</ul>
            </div>}
            <label htmlFor="target-scenario">Target scenario</label>
            <select id="target-scenario" value={targetScenario} onChange={(event) => { invalidateDraftResult(); setTargetScenario(event.target.value); }}>
              {questionnaire.target_scenarios.map((scenario) => <option key={scenario} value={scenario}>{scenario.split(":").at(-1)?.replaceAll("-", " ")}</option>)}
            </select>
            {questionnaire.questions.map((q) => <div className="question" key={q.question_id}>
              {q.question_type === "multi_choice" ? <fieldset id={q.question_id}>
                <legend>{q.label}{q.required ? " *" : ""}</legend>
                <small>{API_VERSION === "v2" ? q.state_field === "missing_capabilities" ? "Select only capabilities you explicitly lack. Unselected items remain unknown." : "Select capabilities you can assert. Unselected items remain unknown." : "Select all that apply, or leave empty if none apply."}</small>
                {q.options.map((option) => <label className="check-label" key={option}><input type="checkbox" checked={(answers[q.question_id] as string[] || []).includes(option)} onChange={(event) => {
                  const current = answers[q.question_id] as string[] || [];
                  handleAnswersChange({ ...answers, [q.question_id]: event.target.checked ? [...current, option] : current.filter((item) => item !== option) });
                }} />{option}</label>)}
              </fieldset> : <>
                <label htmlFor={q.question_id}>{q.label}{q.required ? " *" : ""}</label>
                {q.question_type === "single_choice" ? <select id={q.question_id} value={String(answers[q.question_id] ?? "")} aria-required={q.required} aria-invalid={invalidQuestions.includes(q.question_id)} aria-describedby={invalidQuestions.includes(q.question_id) ? `${q.question_id}-error` : undefined} onChange={(event) => handleAnswersChange({ ...answers, [q.question_id]: event.target.value })}>
                  <option value="">Select an answer</option>{q.options.map((option) => <option key={option} value={option}>{option}</option>)}
                </select> : <input id={q.question_id} type={q.question_type === "numeric" ? "number" : "text"} min={q.min_value ?? undefined} max={q.max_value ?? undefined} step={q.question_type === "numeric" ? 1 : undefined} value={answers[q.question_id] as string | number ?? ""} aria-required={q.required} aria-invalid={invalidQuestions.includes(q.question_id)} aria-describedby={invalidQuestions.includes(q.question_id) ? `${q.question_id}-error` : undefined} onChange={(event) => handleAnswersChange({ ...answers, [q.question_id]: q.question_type === "numeric" && event.target.value !== "" ? Number(event.target.value) : event.target.value })} />}
                {invalidQuestions.includes(q.question_id) && <span id={`${q.question_id}-error`} className="error">Enter a valid answer{q.question_type === "numeric" ? ` (${q.min_value}–${q.max_value})` : ""}.</span>}
              </>}
            </div>)}
          </div>}
          <div className="evidence-block">
            <h3>Selected source</h3>
            <dl>
              <dt>Stakeholder</dt>
              <dd>{stakeholderType || "n/a"}</dd>
              <dt>Scenario</dt>
              <dd>{boundaryMode ? targetScenario || "n/a" : "secondary-use-readiness"}</dd>
            </dl>
          </div>
        </section>
        <section className="panel report">
          <h2>Traceable report</h2>
          {error && <p className="error">{error}</p>}
          {loading && <p>Running assessment…</p>}
          {!report && !loading && <p>{boundaryMode ? "Complete the questionnaire to see your roadmap path." : "Run a derived assessment to see your roadmap path."}</p>}
          {report && <ReportSummary report={report} assessmentId={lastAssessmentId} />}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
