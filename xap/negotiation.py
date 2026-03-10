"""NegotiationContract implementation for XAP v0.2."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, ClassVar

from ._common import (
    deep_copy,
    parse_utc,
    utc_now_iso,
    validate_against_schema,
)
from .crypto import canonical_json_hash, generate_keypair, sign_payload
from .errors import XAPExpiredError, XAPStateError

_SYSTEM_PRIVATE_KEY, _SYSTEM_PUBLIC_KEY = generate_keypair()


def _generate_negotiation_id() -> str:
    return f"neg_{secrets.token_hex(4)}"


@dataclass
class NegotiationContract:
    _data: dict[str, Any]

    SCHEMA: ClassVar[str] = "negotiation-contract.json"

    @property
    def negotiation_id(self) -> str:
        return self._data["negotiation_id"]

    @classmethod
    def create(
        cls,
        from_agent: str,
        to_agent: str,
        task: dict[str, Any],
        pricing: dict[str, Any],
        sla: dict[str, Any],
        expires_in_seconds: int,
        max_rounds: int = 20,
        identity_snapshot: dict[str, Any] | None = None,
        parent_negotiation_id: str | None = None,
    ) -> "NegotiationContract":
        created = parse_utc(utc_now_iso())
        expires = created + timedelta(seconds=expires_in_seconds)

        data: dict[str, Any] = {
            "negotiation_id": _generate_negotiation_id(),
            "state": "OFFER",
            "round_number": 1,
            "max_rounds": max_rounds,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "task": task,
            "pricing": pricing,
            "sla": sla,
            "expires_at": expires.isoformat() + "Z",
            "xap_version": "0.2.0",
            "created_at": created.isoformat() + "Z",
            "signature": "",
        }
        if identity_snapshot is not None:
            data["identity_snapshot"] = identity_snapshot
        if parent_negotiation_id is not None:
            data["parent_negotiation_id"] = parent_negotiation_id

        validate_against_schema(cls.SCHEMA, data)
        return cls(data)

    def is_expired(self) -> bool:
        return parse_utc(utc_now_iso()) > parse_utc(self._data["expires_at"])

    def counter(
        self,
        pricing: dict[str, Any],
        proposed_by: str,
        private_key: str | None = None,
        sla: dict[str, Any] | None = None,
    ) -> "NegotiationContract":
        if self.is_expired():
            raise XAPExpiredError("Negotiation is expired")

        current = self._data["state"]
        if current not in {"OFFER", "COUNTER"}:
            raise XAPStateError(f"Invalid transition from {current} to COUNTER")

        max_rounds = self._data.get("max_rounds", 20)
        next_round = self._data["round_number"] + 1
        if next_round > max_rounds:
            raise XAPStateError("Maximum negotiation rounds reached")

        prev_hash = f"sha256:{canonical_json_hash(self._data, exclude_fields=['signature'])}"

        self._data["pricing"] = pricing
        if sla is not None:
            self._data["sla"] = sla
        self._data["state"] = "COUNTER"
        self._data["round_number"] = next_round
        self._data["previous_state_hash"] = prev_hash
        self._data["from_agent"], self._data["to_agent"] = proposed_by, self._data["from_agent"]
        self._data["created_at"] = utc_now_iso()
        self._data["signature"] = sign_payload(
            self._data, private_key or _SYSTEM_PRIVATE_KEY, exclude_fields=["signature"]
        )

        validate_against_schema(self.SCHEMA, self._data)
        return self

    def accept(self, agent_id: str, private_key: str) -> "NegotiationContract":
        if self.is_expired():
            raise XAPExpiredError("Negotiation is expired")

        current = self._data["state"]
        if current not in {"OFFER", "COUNTER"}:
            raise XAPStateError(f"Invalid transition from {current} to ACCEPT")

        prev_hash = f"sha256:{canonical_json_hash(self._data, exclude_fields=['signature'])}"

        self._data["state"] = "ACCEPT"
        self._data["previous_state_hash"] = prev_hash
        self._data["from_agent"] = agent_id
        self._data["to_agent"] = (
            self._data["to_agent"]
            if self._data["from_agent"] == agent_id
            else self._data["from_agent"]
        )
        self._data["created_at"] = utc_now_iso()
        self._data["signature"] = sign_payload(
            self._data, private_key, exclude_fields=["signature"]
        )

        validate_against_schema(self.SCHEMA, self._data)
        return self

    def reject(self, agent_id: str, private_key: str | None = None) -> "NegotiationContract":
        current = self._data["state"]
        if current in {"ACCEPT", "REJECT"}:
            raise XAPStateError(f"Negotiation is already in terminal state {current}")

        prev_hash = f"sha256:{canonical_json_hash(self._data, exclude_fields=['signature'])}"

        other = self._data["to_agent"] if self._data["from_agent"] == agent_id else self._data["from_agent"]
        self._data["state"] = "REJECT"
        self._data["previous_state_hash"] = prev_hash
        self._data["from_agent"] = agent_id
        self._data["to_agent"] = other
        self._data["created_at"] = utc_now_iso()
        self._data["signature"] = sign_payload(
            self._data, private_key or _SYSTEM_PRIVATE_KEY, exclude_fields=["signature"]
        )

        validate_against_schema(self.SCHEMA, self._data)
        return self

    def to_dict(self) -> dict[str, Any]:
        return deep_copy(self._data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NegotiationContract":
        validate_against_schema(cls.SCHEMA, data)
        return cls(deep_copy(data))
