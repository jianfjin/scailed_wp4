"""Append-only in-memory audit chain for V1 demo mode."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    event_data: dict[str, Any]
    timestamp: str
    prev_hash: str | None
    event_hash: str
    ip_hash: str | None = None
    user_agent_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AuditLog:
    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def append(
        self,
        event_type: str,
        event_data: dict[str, Any],
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        prev_hash = self._events[-1].event_hash if self._events else None
        timestamp = datetime.now(timezone.utc).isoformat()
        ip_hash = self._hash(ip) if ip else None
        user_agent_hash = self._hash(user_agent) if user_agent else None
        payload = {
            "event_type": event_type,
            "event_data": event_data,
            "timestamp": timestamp,
            "prev_hash": prev_hash,
            "ip_hash": ip_hash,
            "user_agent_hash": user_agent_hash,
        }
        event = AuditEvent(
            **payload,
            event_hash=self._hash(json.dumps(payload, sort_keys=True)),
        )
        self._events.append(event)
        return event

    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def verify_chain(self) -> bool:
        previous: str | None = None
        for event in self._events:
            if event.prev_hash != previous:
                return False
            previous = event.event_hash
        return True

    def _hash(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
