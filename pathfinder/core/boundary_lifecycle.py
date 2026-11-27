"""Pure exact-version runtime dependencies and current withdrawal observations."""
from __future__ import annotations

from collections.abc import Iterable

from pathfinder.core.contract_registry import contract_definition


def identity(document: dict) -> dict:
    manifest = document['manifest']
    return {'contract': document['contract'], 'snapshot_id': manifest['snapshot_id'],
            'producer_wp': manifest['producer_wp']}


def _key(item: dict) -> tuple[str, str, str]:
    return item['contract'], item['snapshot_id'], item['producer_wp']


def dependency_closure(documents: Iterable[dict], roots: Iterable[dict]) -> list[dict]:
    """Follow manifest dependencies only; supersession and batch membership are not edges."""
    by_version = {}
    for document in documents:
        item = identity(document)
        definition = contract_definition(item['contract'])
        if not definition.runtime_input or definition.producer != item['producer_wp']:
            raise ValueError(f"invalid runtime producer for {item['contract']}")
        key = (item['contract'], item['snapshot_id'])
        if key in by_version and by_version[key] != document:
            raise ValueError(f"conflicting dependency identity: {item['snapshot_id']}")
        by_version[key] = document
    found = {}

    def visit(item: dict, path: list[str], visiting: set[tuple]) -> None:
        key = _key(item)
        if key in visiting:
            raise ValueError(f"cyclic runtime dependency: {item['snapshot_id']}")
        document = by_version.get(key[:2])
        if document is None or identity(document) != {k: item[k] for k in ('contract', 'snapshot_id', 'producer_wp')}:
            raise ValueError(f"unresolved runtime dependency: {item['contract']} {item['snapshot_id']}")
        current_path = path + [item['snapshot_id']]
        previous = found.get(key)
        if previous is not None and len(previous['dependency_path']) <= len(current_path):
            return
        found[key] = {**identity(document), 'dependency_path': current_path}
        for contract, snapshot_id in sorted(document['manifest'].get('dependencies', {}).items()):
            definition = contract_definition(contract)
            visit({'contract': contract, 'snapshot_id': snapshot_id, 'producer_wp': definition.producer},
                  current_path, visiting | {key})

    for root in sorted(roots, key=_key):
        visit(root, [], set())
    return [found[key] for key in sorted(found)]


def runtime_input_set(documents: Iterable[dict], stakeholder_type: str) -> list[dict]:
    """Select common inputs and this assessment's questionnaire, then close dependencies."""
    documents = list(documents)
    roots = []
    selected = []
    for document in documents:
        contract = document['contract']
        if contract.startswith('pf.questionnaire.'):
            if document['payload']['stakeholder_type'] == stakeholder_type:
                selected.append(identity(document))
        else:
            roots.append(identity(document))
    if len(selected) != 1:
        raise ValueError(f"expected exactly one questionnaire for {stakeholder_type}")
    return dependency_closure(documents, roots + selected)


def observe_validity(input_set: Iterable[dict], withdrawals: Iterable[dict], lifecycle_revision: int = 0) -> dict:
    """Annotate original inputs without recomputing or altering their original result."""
    inputs = {_key(item): item for item in input_set}
    affected = []
    for notice in withdrawals:
        payload = notice['payload']
        for target in payload['targets']:
            item = inputs.get(_key(target))
            if item is not None:
                affected.append({**{k: item[k] for k in ('contract', 'snapshot_id', 'producer_wp')},
                                 'dependency_path': item.get('dependency_path', [item['snapshot_id']]),
                                 'notice_id': payload['notice_id'], 'reason': payload['reason']})
    affected.sort(key=lambda item: (_key(item), item['notice_id']))
    status = 'valid'
    if affected:
        status = 'withdrawn' if any(len(item['dependency_path']) == 1 for item in affected) else 'dependency_affected'
    return {'valid': not affected, 'status': status, 'lifecycle_revision': lifecycle_revision,
            'affected_inputs': affected}
