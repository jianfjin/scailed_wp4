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
  session?: { result_id?: string; answer_revision?: number; profile_id?: string };
  current_validity?: CurrentValidity;
  readiness_snapshot?: { capability_findings?: Record<string, CapabilityFinding> };
  recommended_path?: {
    status?: string;
    profile_id?: string;
    recommendation_kind?: string;
    missing_information?: string[];
    capability_findings?: Record<string, CapabilityFinding>;
    result_id?: string;
    answer_revision?: number;
    current_validity?: CurrentValidity;
  };
};

export function projectAssessmentSemantics(report: SemanticsReport) {
  const path = report.recommended_path;
  const validity = report.current_validity ?? path?.current_validity;
  const profile = path?.profile_id ?? report.session?.profile_id ?? "legacy-v1";
  const historical = validity?.valid === false;
  const conditional = path?.recommendation_kind === "conditional_direction";
  const blocked = path?.status === "blocked";
  const originalStatus = path?.status ?? "unknown";
  const heading = historical ? "Historical result — inputs withdrawn" :
    blocked ? "Blocked" : conditional ? "Conditional direction" :
    originalStatus === "degraded" ? "Unverified regulatory basis" :
    profile === "evidence-v2" ? "Guidance available" : originalStatus === "ready" ? "Ready" : "Result unavailable";
  const pathHeading = historical ? "Historical candidate path — unavailable for new guidance" :
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
    heading, pathHeading, historical, originalStatus, profile,
    confidenceLabel: profile === "evidence-v2" ? "Answer completeness" : "Confidence",
    resultId: path?.result_id ?? report.session?.result_id,
    answerRevision: path?.answer_revision ?? report.session?.answer_revision,
    lifecycleRevision: validity?.lifecycle_revision,
    validityStatus: validity?.status ?? "not observed",
    missingInformation: path?.missing_information ?? [],
    affectedInputs: validity?.affected_inputs ?? [],
    findings,
  };
}
