import React, { useEffect, useMemo, useState } from "react";
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
      ...(init?.headers || {})
    }
  });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

function App() {
  const [types, setTypes] = useState<string[]>([]);
  const [stakeholderType, setStakeholderType] = useState("biotech-sme");
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ stakeholder_types: string[] }>("/v1/questionnaires")
      .then((data) => setTypes(data.stakeholder_types))
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    api<Questionnaire>(`/v1/questionnaires/${stakeholderType}`)
      .then(setQuestionnaire)
      .catch((err) => setError(String(err)));
  }, [stakeholderType]);

  const answers = useMemo(
    () => ({
      governance_maturity: 2,
      data_maturity: 2,
      compliance_maturity: 2,
      capabilities: ["secure-processing"],
      missing_capabilities: ["data-catalog"],
      regulatory_flags: ["gdpr-review-needed"]
    }),
    []
  );

  async function runDemo() {
    setError("");
    setReport(null);
    try {
      const session = await api<{ assessment_id: string }>("/v1/assessments", {
        method: "POST",
        body: JSON.stringify({
          stakeholder_type: stakeholderType,
          target_scenario: "secondary-use-readiness"
        })
      });
      await api(`/v1/assessments/${session.assessment_id}/answers/batch`, {
        method: "POST",
        body: JSON.stringify({ answers })
      });
      await api(`/v1/assessments/${session.assessment_id}/recommendations`, {
        method: "POST"
      });
      const nextReport = await api<Record<string, unknown>>(
        `/v1/assessments/${session.assessment_id}/report`
      );
      setReport(nextReport);
    } catch (err) {
      setError(String(err));
    }
  }

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>SCAILED Pathfinder</h1>
          <p>EHDS readiness path planner. Demo mode, deterministic rules, full trace.</p>
        </div>
        <button type="button" onClick={runDemo}>
          Run assessment
        </button>
      </section>

      <section className="layout">
        <aside className="panel">
          <label htmlFor="stakeholder">Stakeholder type</label>
          <select
            id="stakeholder"
            value={stakeholderType}
            onChange={(event) => setStakeholderType(event.target.value)}
          >
            {types.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
          <div className="banner">Mock data mode. WP2/WP3/WP8 inputs pending.</div>
        </aside>

        <section className="panel">
          <h2>{questionnaire?.title || "Questionnaire"}</h2>
          <div className="question-list">
            {questionnaire?.questions.map((question) => (
              <div className="question" key={question.question_id}>
                <span>{question.label}</span>
                <strong>{String((answers as Record<string, unknown>)[question.question_id] ?? "not answered")}</strong>
              </div>
            ))}
          </div>
        </section>

        <section className="panel report">
          <h2>Traceable report</h2>
          {error && <p className="error">{error}</p>}
          {!report && <p>Run assessment to generate roadmap path and trace payload.</p>}
          {report && <pre>{JSON.stringify(report, null, 2)}</pre>}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
