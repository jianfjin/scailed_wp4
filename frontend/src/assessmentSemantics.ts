export type CapabilityFinding = {
  capability_id: string;
  judgment: "present" | "absent" | "unknown";
  source: string;
  verification_status: string;
  answer_ids: string[];
  evidence_refs: string[];
};

export type AffectedInput = {
  contract: string;
  snapshot_id: string;
  producer_wp: string;
  notice_id: string;
  reason: string;
  dependency_path: string[];
};

export type CurrentValidity = {
  valid: boolean;
  status: string;
  lifecycle_revision: number;
  affected_inputs: AffectedInput[];
};

export type SemanticsReport = {
  session?: { result_id?: string; answer_revision?: number | null; profile_id?: string };
  current_validity?: CurrentValidity;
  readiness_snapshot?: { capability_findings?: Record<string, CapabilityFinding> } | null;
  result?: { binding_status?: string } | null;
  recommended_path?: {
    status?: string;
    profile_id?: string;
    recommendation_kind?: string;
    missing_information?: string[];
    capability_findings?: Record<string, CapabilityFinding>;
    result_id?: string;
    answer_revision?: number | null;
    current_validity?: CurrentValidity;
  };
};

export function projectAssessmentSemantics(report: SemanticsReport) {
  const path = report.recommended_path;
  const validity = report.current_validity ?? path?.current_validity;
  const profile = path?.profile_id ?? report.session?.profile_id ?? "legacy-v1";
  const withdrawn = validity?.valid === false;
  const bindingStatus = report.result?.binding_status ?? "not recorded";
  const unbound = bindingStatus === "legacy_unbound";
  const historical = withdrawn || unbound;
  const conditional = path?.recommendation_kind === "conditional_direction";
  const blocked = path?.status === "blocked";
  const originalStatus = path?.status ?? "unknown";
  let heading = "Result unavailable";
  if (withdrawn) heading = "Historical result — inputs withdrawn";
  else if (unbound) heading = "Historical result — original evidence unavailable";
  else if (blocked) heading = "Blocked";
  else if (conditional) heading = "Conditional direction";
  else if (originalStatus === "degraded") heading = "Unverified regulatory basis";
  else if (profile === "evidence-v2") heading = "Guidance available";
  else if (originalStatus === "ready") heading = "Ready";
  const pathHeading = withdrawn ? "Historical candidate path — unavailable for new guidance" :
    unbound ? "Historical candidate path — original evidence unavailable" :
    blocked ? "Blocked candidate path" : conditional ? "Candidate direction — more information required" :
    "Proposed guidance path";
  const findings = Object.entries(report.readiness_snapshot?.capability_findings ?? path?.capability_findings ?? {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([capabilityId, finding]) => ({
      ...finding,
      capabilityId,
      judgmentLabel: { present: "Present", absent: "Absent", unknown: "Unknown" }[finding.judgment] ?? "Unknown",
      sourceLabel: finding.source === "self_reported" ? "Self-reported" : finding.source === "unanswered" ? "No current answer" : finding.source,
      verificationLabel: finding.verification_status === "verified" ? "Verified" : "Unverified",
    }));
  return {
    heading, pathHeading, historical, originalStatus, profile, bindingStatus,
    historyNote: withdrawn ? "This result is historical. Its original output is preserved; withdrawn inputs cannot support new guidance." : "This result is historical. Original answers are unavailable; use a new assessment for current guidance.",
    confidenceLabel: profile === "evidence-v2" ? "Answer completeness" : "Confidence",
    resultId: path?.result_id ?? report.session?.result_id,
    answerRevision: unbound ? "Unknown (legacy evidence)" : path?.answer_revision ?? report.session?.answer_revision ?? undefined,
    lifecycleRevision: validity?.lifecycle_revision,
    validityStatus: validity?.status ?? "not observed",
    missingInformation: path?.missing_information ?? [],
    affectedInputs: validity?.affected_inputs ?? [],
    findings,
  };
}
