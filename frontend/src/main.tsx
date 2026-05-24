import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  buildStakeholderOptions,
  filterStakeholderOptions,
  formatStakeholderLoadedCopy,
  type StakeholderOption,
} from "./stakeholderCatalog";
import "./styles.css";

type Questionnaire = {
  stakeholder_type: string;
  title: string;
  target_scenarios: string[];
  questions: Array<{
    question_id: string;
    label: string;
    question_type: string;
    required: boolean;
    options: string[];
    min_value: number | null;
    max_value: number | null;
  }>;
};

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
  };
  recommended_path?: {
    status?: string;
    current_node?: string;
    target_node?: string;
    next_steps?: Array<{ node_id?: string; label?: string; dimension?: string }>;
    blockers?: string[];
    warnings?: string[];
    triggered_rules?: Array<{
      rule_id: string;
      rule_type?: string;
      priority?: number;
      action?: {
        title?: string;
        text?: string;
        node_id?: string;
        warning?: string;
        block?: boolean;
      };
    }>;
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

/* ─── question widgets ───────────────────────────────────── */

function NumericInput({
  questionId,
  label,
  min,
  max,
  value,
  onChange,
}: {
  questionId: string;
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (id: string, v: number) => void;
}) {
  return (
    <div className="question">
      <label htmlFor={questionId}>{label} (1–{max})</label>
      <input
        id={questionId}
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(questionId, Number(e.target.value))}
      />
      <strong>{value}</strong>
    </div>
  );
}

function MultiChoiceInput({
  questionId,
  label,
  options,
  selected,
  onChange,
}: {
  questionId: string;
  label: string;
  options: string[];
  selected: string[];
  onChange: (id: string, v: string[]) => void;
}) {
  const toggle = (opt: string) => {
    const next = selected.includes(opt)
      ? selected.filter((o) => o !== opt)
      : [...selected, opt];
    onChange(questionId, next);
  };
  return (
    <div className="question">
      <span>{label}</span>
      <div className="check-group">
        {options.map((opt) => (
          <label key={opt} className="check-label">
            <input
              type="checkbox"
              checked={selected.includes(opt)}
              onChange={() => toggle(opt)}
            />
            {opt}
          </label>
        ))}
      </div>
    </div>
  );
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

function ReportSummary({ report, assessmentId }: { report: PathfinderReport; assessmentId?: string }) {
  const path = report.recommended_path;
  const snapshot = report.readiness_snapshot;
  const trace = path?.trace;
  const blocked = path?.status === "blocked";

  const backendLabel =
    path?.path_backend === "cypher" ? "AGE Cypher" :
    path?.path_backend === "n/a (blocked)" ? "n/a" :
    "Python BFS";

  // Break down triggered rules by impact
  const ruleBreakdown = useMemo(() => {
    const rules = path?.triggered_rules || [];
    const blockers = rules.filter((r) => r.action?.block);
    const withWarning = rules.filter((r) => !r.action?.block && r.action?.warning);
    const info = rules.filter((r) => !r.action?.block && !r.action?.warning);
    return { total: rules.length, blockers, withWarning, info };
  }, [path?.triggered_rules]);

  // Compute capability coverage from answers
  const capabilitySummary = useMemo(() => {
    const s = snapshot || {};
    const caps = s.capabilities || [];
    const missing = s.missing_capabilities || [];
    const flags = s.regulatory_flags || [];
    return { caps, missing, flags };
  }, [snapshot]);

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

      {/* Capability profile — makes checkbox effects visible */}
      {capabilitySummary.caps.length > 0 || capabilitySummary.missing.length > 0 || capabilitySummary.flags.length > 0 ? (
        <div className="evidence-block rule-impact">
          <h3>Capability profile</h3>
          <dl>
            {capabilitySummary.caps.length > 0 && (
              <>
                <dt>Known capabilities</dt>
                <dd><span className="badge badge-cap">{capabilitySummary.caps.join(", ")}</span></dd>
              </>
            )}
            {capabilitySummary.missing.length > 0 && (
              <>
                <dt>Missing capabilities</dt>
                <dd><span className="badge badge-missing">{capabilitySummary.missing.join(", ")}</span></dd>
              </>
            )}
            {capabilitySummary.flags.length > 0 && (
              <>
                <dt>Regulatory flags</dt>
                <dd><span className="badge badge-flag">{capabilitySummary.flags.join(", ")}</span></dd>
              </>
            )}
          </dl>
        </div>
      ) : null}

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

      {/* Rule impact summary — prominently shows checkbox effects */}
      <div className="evidence-block rule-impact">
        <h3>Rule impact</h3>
        <div className="rule-impact-counts">
          <div className="rule-count" data-level={ruleBreakdown.blockers.length > 0 ? "blocker" : ruleBreakdown.withWarning.length > 0 ? "warning" : "info"}>
            <strong>{ruleBreakdown.total}</strong>
            <span>total rules</span>
          </div>
          {ruleBreakdown.blockers.length > 0 && (
            <div className="rule-count" data-level="blocker">
              <strong>{ruleBreakdown.blockers.length}</strong>
              <span>blockers</span>
            </div>
          )}
          {ruleBreakdown.withWarning.length > 0 && (
            <div className="rule-count" data-level="warning">
              <strong>{ruleBreakdown.withWarning.length}</strong>
              <span>warnings</span>
            </div>
          )}
          {ruleBreakdown.info.length > 0 && (
            <div className="rule-count" data-level="info">
              <strong>{ruleBreakdown.info.length}</strong>
              <span>advisory</span>
            </div>
          )}
        </div>
        {ruleBreakdown.blockers.length > 0 && (
          <dl>
            {ruleBreakdown.blockers.map((rule) => (
              <div key={rule.rule_id} className="rule-item">
                <dt className="rule-id blocker">{rule.rule_id}</dt>
                <dd>{rule.action?.text || "no description"}</dd>
              </div>
            ))}
          </dl>
        )}
        {ruleBreakdown.withWarning.length > 0 && (
          <details>
            <summary className="rule-group-toggle">Warnings ({ruleBreakdown.withWarning.length})</summary>
            <dl>
              {ruleBreakdown.withWarning.map((rule) => (
                <div key={rule.rule_id} className="rule-item">
                  <dt className="rule-id warning">{rule.rule_id}</dt>
                  <dd>{rule.action?.warning || rule.action?.text || "no description"}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
        {ruleBreakdown.info.length > 0 && (
          <details>
            <summary className="rule-group-toggle">Advisory rules ({ruleBreakdown.info.length})</summary>
            <dl>
              {ruleBreakdown.info.map((rule) => (
                <div key={rule.rule_id} className="rule-item">
                  <dt className="rule-id">{rule.rule_id}</dt>
                  <dd>{rule.action?.text || "no description"}</dd>
                </div>
              ))}
            </dl>
          </details>
        )}
      </div>

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
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
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

  useEffect(() => {
    if (!stakeholderType) return;
    api<Questionnaire>(`/v1/questionnaires/${encodeURIComponent(stakeholderType)}`)
      .then((q) => {
        setQuestionnaire(q);
        setReport(null);
        setError("");
        // init defaults
        const defaults: Record<string, unknown> = {};
        for (const question of q.questions) {
          if (question.question_type === "multi_choice") defaults[question.question_id] = [];
          else if (question.question_type === "numeric") defaults[question.question_id] = question.min_value ?? 1;
          else defaults[question.question_id] = "";
        }
        setAnswers(defaults);
      })
      .catch((err) => setError(String(err)));
  }, [stakeholderType]);

  const updateAnswer = useCallback((id: string, value: unknown) => {
    setAnswers((prev) => ({ ...prev, [id]: value }));
  }, []);

  const allAnswered = useMemo(() => {
    if (!questionnaire) return false;
    return questionnaire.questions
      .filter((q) => q.required)
      .every((q) => {
        const v = answers[q.question_id];
        if (q.question_type === "multi_choice") return Array.isArray(v);
        return v !== "" && v !== null && v !== undefined;
      });
  }, [questionnaire, answers]);

  async function runAssessment() {
    if (!questionnaire) return;
    setError("");
    setLoading(true);
    setReport(null);
    try {
      const caps = (answers["capabilities"] as string[]) || ["secure-processing"];
      const missing = (answers["missing_capabilities"] as string[]) || [];
      const flags = (answers["regulatory_flags"] as string[]) || [];
      const maturityFields: Record<string, number> = {};
      for (const q of questionnaire.questions) {
        if (q.question_type === "numeric") maturityFields[q.question_id] = Number(answers[q.question_id]) || 1;
      }

      const payload = { ...maturityFields, capabilities: caps, missing_capabilities: missing, regulatory_flags: flags };

      const session = await api<{ assessment_id: string }>("/v1/assessments", {
        method: "POST",
        body: JSON.stringify({ stakeholder_type: stakeholderType, target_scenario: "secondary-use-readiness" }),
      });
      setLastAssessmentId(session.assessment_id);
      await api(`/v1/assessments/${session.assessment_id}/answers/batch`, {
        method: "POST",
        body: JSON.stringify({ answers: payload }),
      });
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
          <p>EHDS readiness path planner. Answer questions → get your roadmap path with full trace.</p>
        </div>
        <div className="toolbar-actions">
          <BackendToggle value={pathBackend} onChange={setPathBackend} />
          <button type="button" className="submit-btn" onClick={runAssessment} disabled={!allAnswered || loading}>
            {loading ? "Running…" : "Submit assessment"}
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
          <h2>{questionnaire?.title || "Questionnaire"}</h2>
          <div className="question-list">
            {questionnaire?.questions.map((q) => {
              if (q.question_type === "numeric") {
                return (
                  <NumericInput
                    key={q.question_id}
                    questionId={q.question_id}
                    label={q.label}
                    min={q.min_value ?? 1}
                    max={q.max_value ?? 5}
                    value={Number(answers[q.question_id]) || 0}
                    onChange={updateAnswer}
                  />
                );
              }
              if (q.question_type === "multi_choice") {
                return (
                  <MultiChoiceInput
                    key={q.question_id}
                    questionId={q.question_id}
                    label={q.label}
                    options={q.options || []}
                    selected={(answers[q.question_id] as string[]) || []}
                    onChange={updateAnswer}
                  />
                );
              }
              return (
                <div className="question" key={q.question_id}>
                  <span>{q.label}</span>
                  <strong>{String(answers[q.question_id] ?? "—")}</strong>
                </div>
              );
            })}
          </div>
          {!allAnswered && <p style={{ color: "#8a6d14", marginTop: 12 }}>Complete all required questions to submit.</p>}
        </section>

        <section className="panel report">
          <h2>Traceable report</h2>
          {error && <p className="error">{error}</p>}
          {loading && <p>Running assessment…</p>}
          {!report && !loading && <p>Complete the questionnaire and submit to see your roadmap path.</p>}
          {report && <ReportSummary report={report} assessmentId={lastAssessmentId} />}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
