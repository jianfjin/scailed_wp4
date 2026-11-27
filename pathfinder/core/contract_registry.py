"""Explicit business-contract versions and compatible evaluation profiles."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable


@dataclass(frozen=True)
class ContractDefinition:
    contract: str
    producer: str | None
    schema: str
    dependencies: tuple[str, ...] = ()
    runtime_input: bool = True
    envelope: str = "envelope.schema.json"

    @property
    def major(self) -> int:
        return int(self.contract.rsplit(".v", 1)[1])


@dataclass(frozen=True)
class EvaluationProfile:
    profile_id: str
    semantics_version: str
    questionnaire_contract: str
    rulebundle_contract: str

    @property
    def runtime_contracts(self) -> frozenset[str]:
        return frozenset(("pf.taxonomy.v1", "pf.roadmap.v1", self.questionnaire_contract, self.rulebundle_contract))


LEGACY_PROFILE = EvaluationProfile("legacy-v1", "legacy-v1.0", "pf.questionnaire.v1", "pf.rulebundle.v1")
EVIDENCE_PROFILE = EvaluationProfile("evidence-v2", "evidence-v2.0", "pf.questionnaire.v2", "pf.rulebundle.v2")
PROFILES = MappingProxyType({p.profile_id: p for p in (LEGACY_PROFILE, EVIDENCE_PROFILE)})

_definitions = (
    ContractDefinition("pf.taxonomy.v1", "WP2", "wp2-taxonomy.schema.json"),
    ContractDefinition("pf.roadmap.v1", "WP3", "wp3-roadmap.schema.json", ("pf.taxonomy.v1",)),
    ContractDefinition("pf.questionnaire.v1", "WP4", "wp4-questionnaire.schema.json", ("pf.taxonomy.v1",)),
    ContractDefinition("pf.rulebundle.v1", "WP8", "wp8-rulebundle.schema.json", ("pf.taxonomy.v1", "pf.roadmap.v1")),
    ContractDefinition("pf.feedback.v1", "WP4", "wp4-feedback.schema.json",
                       ("pf.taxonomy.v1", "pf.questionnaire.v1", "pf.roadmap.v1", "pf.rulebundle.v1"), False),
    ContractDefinition("pf.questionnaire.v2", "WP4", "wp4-questionnaire.v2.schema.json",
                       ("pf.taxonomy.v1",), envelope="envelope.v2.schema.json"),
    ContractDefinition("pf.rulebundle.v2", "WP8", "wp8-rulebundle.v2.schema.json",
                       ("pf.taxonomy.v1", "pf.roadmap.v1"), envelope="envelope.v2.schema.json"),
    ContractDefinition("pf.withdrawal.v1", None, "withdrawal.schema.json", (), False, "envelope.v2.schema.json"),
)
CONTRACTS = MappingProxyType({d.contract: d for d in _definitions})


def contract_definition(contract: str) -> ContractDefinition:
    try:
        return CONTRACTS[contract]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unsupported contract: {contract}") from exc


def profile_for_contracts(contracts: Iterable[str]) -> EvaluationProfile:
    supplied = frozenset(contracts)
    for profile in PROFILES.values():
        if supplied == profile.runtime_contracts:
            return profile
    raise ValueError("activation requires one compatible runtime contract profile")
