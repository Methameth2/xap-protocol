"""AgentIdentity implementation for XAP v0.2."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any, ClassVar

from ._common import deep_copy, utc_now_iso, validate_against_schema
from .crypto import generate_keypair, sign_payload, verify_payload


def _generate_agent_id() -> str:
    return f"agent_{secrets.token_hex(4)}"


@dataclass
class AgentIdentity:
    """XAP AgentIdentity object with schema validation and Ed25519 signatures."""

    _data: dict[str, Any]

    SCHEMA: ClassVar[str] = "agent-identity.json"
    _registry: ClassVar[dict[str, "AgentIdentity"]] = {}

    @property
    def agent_id(self) -> str:
        return self._data["agent_id"]

    @classmethod
    def create(
        cls,
        capabilities: list[dict[str, Any]],
        public_key: str | None = None,
        org_id: str | None = None,
        team_id: str | None = None,
        risk_profile: dict[str, Any] | None = None,
        external_identities: list[dict[str, Any]] | None = None,
    ) -> "AgentIdentity":
        if public_key is None:
            _, public_key = generate_keypair()

        now = utc_now_iso()
        data: dict[str, Any] = {
            "agent_id": _generate_agent_id(),
            "public_key": public_key,
            "key_version": 1,
            "key_status": "active",
            "capabilities": capabilities,
            "reputation": {
                "total_settlements": 0,
                "success_rate_bps": 0,
                "disputes": 0,
                "dispute_resolution_rate_bps": 0,
                "last_updated": now,
            },
            "xap_version": "0.2.0",
            "status": "active",
            "registered_at": now,
            "last_active_at": now,
            "signature": "",
        }
        if org_id is not None:
            data["org_id"] = org_id
        if team_id is not None:
            data["team_id"] = team_id
        if risk_profile is not None:
            data["risk_profile"] = risk_profile
        if external_identities is not None:
            data["external_identities"] = external_identities

        validate_against_schema(cls.SCHEMA, data)
        obj = cls(data)
        cls._registry[obj.agent_id] = obj
        return obj

    def sign(self, private_key: str) -> str:
        signature = sign_payload(self._data, private_key, exclude_fields=["signature"])
        self._data["signature"] = signature
        validate_against_schema(self.SCHEMA, self._data)
        return signature

    def verify(self, public_key: str) -> bool:
        signature = self._data.get("signature")
        if not signature:
            return False
        return verify_payload(
            self._data,
            signature,
            public_key,
            exclude_fields=["signature"],
        )

    def to_dict(self) -> dict[str, Any]:
        return deep_copy(self._data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentIdentity":
        validate_against_schema(cls.SCHEMA, data)
        obj = cls(deep_copy(data))
        cls._registry[obj.agent_id] = obj
        return obj

    @classmethod
    def register(cls, identity: "AgentIdentity") -> None:
        cls._registry[identity.agent_id] = identity
