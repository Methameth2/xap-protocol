"""NegotiationContract implementation for ACP v0.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, ClassVar

from ._common import (
    deep_copy,
    generate_prefixed_id,
    parse_utc,
    utc_now_iso,
    validate_against_schema,
)
from .crypto import generate_keypair, sign_payload
from .errors import ACPExpiredError, ACPStateError

_SYSTEM_PRIVATE_KEY, _SYSTEM_PUBLIC_KEY = generate_keypair()


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
        initiator_id: str,
        counterparty_id: str,
        capability_id: str,
        offer: dict[str, Any],
        sla: dict[str, Any],
        expires_in_seconds: int,
    ) -> "NegotiationContract":
        created = parse_utc(utc_now_iso())
        expires = created + timedelta(seconds=expires_in_seconds)

        data = {
            "acp_version": "0.1",
            "negotiation_id": generate_prefixed_id("neg_"),
            "state": "OFFER",
            "initiator_agent_id": initiator_id,
            "counterparty_agent_id": counterparty_id,
            "capability_id": capability_id,
            "offer": offer,
            "sla_declaration": sla,
            "negotiation_history": [],
            "created_at": created.isoformat() + "Z",
            "expires_at": expires.isoformat() + "Z",
        }

        validate_against_schema(cls.SCHEMA, data)
        return cls(data)

    def is_expired(self) -> bool:
        return parse_utc(utc_now_iso()) > parse_utc(self._data["expires_at"])

    def _append_history_entry(self, state: str, proposed_by: str, private_key: str, note: str = "") -> None:
        entry = {
            "state": state,
            "proposed_by": proposed_by,
            "offered_rate": self._data["offer"].get("offered_rate"),
            "note": note,
            "timestamp": utc_now_iso(),
        }
        entry["signature"] = sign_payload(entry, private_key, exclude_fields=["signature"])
        self._data.setdefault("negotiation_history", []).append(entry)

    def counter(
        self,
        new_offer: dict[str, Any],
        proposed_by: str,
        private_key: str | None = None,
    ) -> "NegotiationContract":
        if self.is_expired():
            raise ACPExpiredError("Negotiation is expired")

        current = self._data["state"]
        if current == "OFFER":
            next_state = "COUNTER"
        elif current == "COUNTER":
            next_state = "OFFER"
        else:
            raise ACPStateError(f"Invalid transition from {current} to COUNTER/OFFER")

        self._data["offer"] = new_offer
        self._data["state"] = next_state
        self._append_history_entry(next_state, proposed_by, private_key or _SYSTEM_PRIVATE_KEY, note="counter")
        validate_against_schema(self.SCHEMA, self._data)
        return self

    def accept(self, agent_id: str, private_key: str) -> "NegotiationContract":
        if self.is_expired():
            raise ACPExpiredError("Negotiation is expired")

        current = self._data["state"]
        if current not in {"OFFER", "COUNTER", "ACCEPT"}:
            raise ACPStateError(f"Invalid transition from {current} to ACCEPT")
        if current != "ACCEPT":
            self._data["state"] = "ACCEPT"
            self._data["accepted_at"] = utc_now_iso()
        if agent_id == self._data["initiator_agent_id"]:
            if self._data.get("final_signature_initiator"):
                raise ACPStateError("Initiator has already accepted this negotiation")
            self._data["final_signature_initiator"] = sign_payload(
                self._data,
                private_key,
                exclude_fields=["final_signature_initiator", "final_signature_counterparty"],
            )
        elif agent_id == self._data["counterparty_agent_id"]:
            if self._data.get("final_signature_counterparty"):
                raise ACPStateError("Counterparty has already accepted this negotiation")
            self._data["final_signature_counterparty"] = sign_payload(
                self._data,
                private_key,
                exclude_fields=["final_signature_initiator", "final_signature_counterparty"],
            )
        else:
            raise ACPStateError("accepting agent_id is not part of the negotiation")

        self._append_history_entry("ACCEPT", agent_id, private_key, note="accept")
        validate_against_schema(self.SCHEMA, self._data)
        return self

    def reject(self, agent_id: str, private_key: str | None = None) -> "NegotiationContract":
        if self._data["state"] == "REJECT":
            raise ACPStateError("Negotiation is already REJECT")

        self._data["state"] = "REJECT"
        self._append_history_entry("REJECT", agent_id, private_key or _SYSTEM_PRIVATE_KEY, note="reject")
        validate_against_schema(self.SCHEMA, self._data)
        return self

    def to_dict(self) -> dict[str, Any]:
        return deep_copy(self._data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NegotiationContract":
        validate_against_schema(cls.SCHEMA, data)
        return cls(deep_copy(data))
