"""CLI demo for the Pathfinder V1 deterministic kernel."""

from __future__ import annotations

import json

from pathfinder.services.assessment_service import AssessmentService


def run_demo() -> dict[str, object]:
    service = AssessmentService()
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
    print(json.dumps(run_demo(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
