"""CLI demo for the Pathfinder V1 deterministic kernel.

Uses InMemoryRoadmapGraph (no external database required).
"""

from __future__ import annotations

import json

from pathfinder.services.assessment_service import AssessmentService


def run_demo(service: AssessmentService) -> dict[str, object]:
    session = service.create_session("biotech-sme", "secondary-use-readiness")
    service.submit_answers(
        str(session["assessment_id"]),
        {
            "governance_maturity": 2,
            "data_maturity": 2,
            "compliance_maturity": 2,
            "capabilities": ["secure-processing"],
            "missing_capabilities": ["data-catalog"],
            "regulatory_flags": ["gdpr-review-needed"],
        },
    )
    service.generate_recommendation(str(session["assessment_id"]))
    return service.report(str(session["assessment_id"]))


def main() -> None:
    service = AssessmentService()
    result = run_demo(service)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
