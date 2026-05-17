import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
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
    throw new Error((body as { detail?: string }).detail || response.statusText);
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

/* ─── main app ──────────────────────────────────────────── */

function App() {
  const [types, setTypes] = useState<string[]>([]);
  const [stakeholderType, setStakeholderType] = useState("biotech-sme");
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api<{ stakeholder_types: string[] }>("/v1/questionnaires")
      .then((data) => setTypes(data.stakeholder_types))
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    api<Questionnaire>(`/v1/questionnaires/${stakeholderType}`)
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
        if (q.question_type === "multi_choice") return Array.isArray(v) && v.length > 0;
        return v !== "" && v !== null && v !== undefined;
      });
  }, [questionnaire, answers]);

  async function runAssessment() {
    if (!questionnaire) return;
    setError("");
    setLoading(true);
    setReport(null);
    try {
      // extract capabilities/missing/regulatory from answers or use defaults
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
      await api(`/v1/assessments/${session.assessment_id}/answers/batch`, {
        method: "POST",
        body: JSON.stringify({ answers: payload }),
      });
      await api(`/v1/assessments/${session.assessment_id}/recommendations`, { method: "POST" });
      const r = await api<Record<string, unknown>>(`/v1/assessments/${session.assessment_id}/report`);
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
        <button type="button" onClick={runAssessment} disabled={!allAnswered || loading}>
          {loading ? "Running…" : "Submit assessment"}
        </button>
      </section>

      <section className="layout">
        <aside className="panel">
          <label htmlFor="stakeholder">Stakeholder type</label>
          <select id="stakeholder" value={stakeholderType} onChange={(e) => setStakeholderType(e.target.value)}>
            {types.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <div className="banner">Demo mode. WP2/WP3/WP8 inputs pending.</div>
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
          {report && <pre>{JSON.stringify(report, null, 2)}</pre>}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
