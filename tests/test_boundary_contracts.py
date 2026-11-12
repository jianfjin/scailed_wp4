"""Behavioral checks for the consortium snapshot acceptance boundary."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from pathfinder.core.compliance import ComplianceEvaluator
from pathfinder.core.models import StakeholderState

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def snapshots(tmp_path):
    for source in (ROOT / "contracts/samples").glob("*.json"):
        (tmp_path / source.name).write_text(source.read_text())
    return tmp_path


def validate(directory):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_contracts.py"), "--snapshot-dir", str(directory)],
        text=True, capture_output=True, cwd=ROOT,
    )


def mutate(directory, name, change):
    import importlib.util
    spec = importlib.util.spec_from_file_location("contract_validator", ROOT / "scripts/validate_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = directory / name
    doc = json.loads(path.read_text())
    change(doc)
    doc["manifest"]["items_checksum"] = module.canonical_checksum(doc["payload"])
    path.write_text(json.dumps(doc))


def test_golden_snapshots_are_executable(snapshots):
    result = validate(snapshots)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("change", [
    lambda d: d["payload"]["tests"][0]["expect"].update(outcome="not-triggered"),
    lambda d: d["payload"]["rules"][0]["condition"]["and"][0].update(field="unknown"),
    lambda d: d["payload"]["rules"].append(copy.deepcopy(d["payload"]["rules"][0])),
    lambda d: d["manifest"].update(generated_at="not-a-date"),
    lambda d: d["manifest"].update(contract_version="9.0.0"),
])
def test_invalid_rule_delivery_is_rejected(snapshots, change):
    mutate(snapshots, "wp8-rulebundle.snapshot.json", change)
    assert validate(snapshots).returncode != 0


def test_feedback_small_cell_is_rejected(snapshots):
    mutate(snapshots, "wp4-feedback.snapshot.json", lambda d: d["payload"]["roadmap"]["node_stats"][0].update(visits=1))
    assert validate(snapshots).returncode != 0


def test_missing_dependency_is_rejected(snapshots):
    (snapshots / "wp2-taxonomy.snapshot.json").unlink()
    assert validate(snapshots).returncode != 0


def test_dependency_must_match_the_named_contract(snapshots):
    wrong = json.loads((snapshots / "wp3-roadmap.snapshot.json").read_text())["manifest"]["snapshot_id"]
    mutate(snapshots, "wp8-rulebundle.snapshot.json", lambda d: d["manifest"]["dependencies"].update({"pf.taxonomy.v1": wrong}))
    assert validate(snapshots).returncode != 0


def test_checksum_mismatch_is_rejected(snapshots):
    path = snapshots / "wp3-roadmap.snapshot.json"
    doc = json.loads(path.read_text())
    doc["payload"]["nodes"][0]["label"] = "Modified"
    path.write_text(json.dumps(doc))
    assert validate(snapshots).returncode != 0


def test_feedback_is_scoped_to_its_recipient(snapshots):
    mutate(snapshots, "wp4-feedback.snapshot.json", lambda d: d["payload"].update(recipient="WP8"))
    assert validate(snapshots).returncode != 0


def test_feedback_cohort_is_checked(snapshots):
    mutate(snapshots, "wp4-feedback.snapshot.json", lambda d: d["payload"]["roadmap"]["node_stats"][0].update(cohort_size=4))
    assert validate(snapshots).returncode != 0


def test_checksum_vectors():
    import importlib.util
    spec = importlib.util.spec_from_file_location("contract_validator_vectors", ROOT / "scripts/validate_contracts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for vector in json.loads((ROOT / "contracts/checksum-vectors.json").read_text()):
        assert module.canonical_checksum(vector["payload"]) == vector["items_checksum"]


def test_rule_operator_is_not_silently_reinterpreted():
    state = StakeholderState("s", "t", {}, {}, ("legal-basis",), (), (), 1, (), "1")
    assert ComplianceEvaluator().evaluate({"field": "capabilities", "op": "contains", "value": "legal-basis"}, state)


def test_questionnaire_answers_drive_boundary_rule():
    from pathfinder.adapters.boundary import questionnaire_from_snapshots
    from pathfinder.core.questionnaire import QuestionnaireEngine

    samples = ROOT / "contracts/samples"
    taxonomy = json.loads((samples / "wp2-taxonomy.snapshot.json").read_text())
    questionnaire = json.loads((samples / "wp4-questionnaire.snapshot.json").read_text())
    bundle = json.loads((samples / "wp8-rulebundle.snapshot.json").read_text())
    engine = QuestionnaireEngine([questionnaire_from_snapshots(taxonomy, questionnaire)])
    answers = {
        "pf:wp4:question:biotech-sme-1": "yes",
        "pf:wp4:question:biotech-sme-2": 3,
        "pf:wp4:question:biotech-sme-3": 3,
        "pf:wp4:question:biotech-sme-4": 3,
        "pf:wp4:question:biotech-sme-capabilities": ["legal-basis"],
    }
    state = engine.build_state(questionnaire["payload"]["stakeholder_type"], questionnaire["payload"]["target_scenarios"][0], answers)
    assert state.maturity_scores["compliance"] == 3
    assert state.capabilities == ("legal-basis",)
    assert ComplianceEvaluator().evaluate(bundle["payload"]["rules"][0]["condition"], state)
