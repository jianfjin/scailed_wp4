"""CLI demo for the Pathfinder V1 deterministic kernel.

Supports AGE backend via USE_AGE=1 environment variable.
When USE_AGE=1, connects to AGE and loads demo data before running the assessment.
"""

from __future__ import annotations

import asyncio
import json
import os

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


async def async_main() -> None:
    use_age = os.environ.get("USE_AGE", "").lower() in ("1", "true", "yes")
    service = AssessmentService(use_age=use_age)

    if use_age:
        print("Connecting to AGE backend...")
        await service.connect_age()
        print("AGE connection established, demo data loaded.")

    result = run_demo(service)
    print(json.dumps(result, indent=2, sort_keys=True))

    if use_age:
        await service.disconnect_age()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
