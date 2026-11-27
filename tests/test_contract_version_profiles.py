"""Version isolation at the snapshot acceptance boundary."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from pathfinder.core.boundary_runtime import build_boundary_generation
from pathfinder.core.boundary_validation import (
    canonical_checksum, inline_external_refs, validate_documents,
)

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "contracts" / "samples"


def sample(name, *, version=1):
    directory = SAMPLES if version == 1 else SAMPLES / "v2"
    return json.loads((directory / name).read_text())


def test_profile_selection_is_explicit_and_rejects_mixed_semantics():
    from pathfinder.core.contract_registry import profile_for_contracts

    common = {"pf.taxonomy.v1", "pf.roadmap.v1"}
    assert profile_for_contracts(common | {"pf.questionnaire.v1", "pf.rulebundle.v1"}).profile_id == "legacy-v1"
    profile = profile_for_contracts(common | {"pf.questionnaire.v2", "pf.rulebundle.v2"})
    assert profile.profile_id == "evidence-v2"
    assert profile.questionnaire_contract == "pf.questionnaire.v2"
    with pytest.raises(ValueError, match="compatible"):
        profile_for_contracts(common | {"pf.questionnaire.v2", "pf.rulebundle.v1"})
    with pytest.raises(ValueError, match="compatible"):
        profile_for_contracts(common | {"pf.questionnaire.v2", "pf.rulebundle.v2", "pf.withdrawal.v1"})


def test_existing_generation_binds_legacy_profile_and_selected_questionnaire():
    snapshots = [sample(name) for name in (
        "wp2-taxonomy.snapshot.json", "wp3-roadmap.snapshot.json",
        "wp4-questionnaire.snapshot.json", "wp8-rulebundle.snapshot.json",
    )]
    generation = build_boundary_generation(snapshots)
    assert generation.profile_id == "legacy-v1"
    assert generation.semantics_version == "legacy-v1.0"
    stakeholder = snapshots[2]["payload"]["stakeholder_type"]
    assert generation.versions_for(stakeholder)["pf.questionnaire.v1"] == snapshots[2]["manifest"]["snapshot_id"]


def test_v2_schema_accepts_explicit_mapping_and_unknown_test_outcome():
    from pathfinder.core.contract_registry import contract_definition

    for name in ("wp4-questionnaire.snapshot.json", "wp8-rulebundle.snapshot.json"):
        doc = sample(name, version=2)
        definition = contract_definition(doc["contract"])
        validator = Draft202012Validator(inline_external_refs(ROOT / "contracts", definition.envelope), format_checker=FormatChecker())
        assert not list(validator.iter_errors(doc))
        old = Draft202012Validator(inline_external_refs(ROOT / "contracts"), format_checker=FormatChecker())
        assert list(old.iter_errors(doc)), "closed old schema must reject the new major"


def test_unsupported_major_is_not_interpreted_as_the_old_contract():
    doc = sample("wp4-questionnaire.snapshot.json")
    doc["contract"] = "pf.questionnaire.v9"
    doc["manifest"]["contract_version"] = "9.0.0"
    errors, _ = validate_documents([doc])
    assert any("unsupported contract" in error for error in errors)


def test_v2_manifest_major_must_match_its_contract():
    doc = sample("wp4-questionnaire.snapshot.json", version=2)
    doc["manifest"]["contract_version"] = "1.0.0"
    errors, _ = validate_documents([doc])
    assert any("major must match" in error for error in errors)


def test_withdrawal_notice_is_validated_separately_from_runtime_inputs():
    from pathfinder.core.boundary_validation import validate_withdrawal_notice

    notice = sample("withdrawal.notice.json", version=2)
    assert validate_withdrawal_notice(notice) == []
    errors, _ = validate_documents([notice])
    assert any("control message" in error for error in errors)
    with pytest.raises(ValueError):
        build_boundary_generation([notice])


@pytest.mark.parametrize("change", [
    lambda n: n["payload"]["source_confirmation"].update(confirmed_by_wp="WP3"),
    lambda n: n["payload"]["source_confirmation"].update(target_checksum="sha256:" + "0" * 64),
    lambda n: n["payload"]["source_confirmation"].pop("reference"),
    lambda n: n["payload"]["targets"][0].update(producer_wp="WP3"),
])
def test_withdrawal_confirmation_scope_and_ownership_must_match(change):
    from pathfinder.core.boundary_validation import validate_withdrawal_notice

    notice = deepcopy(sample("withdrawal.notice.json", version=2))
    change(notice)
    notice["manifest"]["items_checksum"] = canonical_checksum(notice["payload"])
    assert validate_withdrawal_notice(notice)
