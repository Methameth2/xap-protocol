"""AgentIdentity implementation for XAP v0.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from ._common import deep_copy, generate_prefixed_id, utc_now_iso, validate_against_schema
from .crypto import canonical_json_hash, generate_keypair, sign_payload, verify_payload


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
        pricing: dict[str, Any],
        sla: dict[str, Any],
        risk_profile: dict[str, Any] | None = None,
        public_key: str | None = None,
        display_name: str | None = None,
    ) -> "AgentIdentity":
        if public_key is None:
            _, public_key = generate_keypair()

        data: dict[str, Any] = {
            "xap_version": "0.1",
            "agent_id": generate_prefixed_id("xap_"),
            "public_key": public_key,
            "key_algorithm": "Ed25519",
            "registered_at": utc_now_iso(),
            "capabilities": capabilities,
            "pricing": pricing,
            "sla": sla,
            "reputation": {
                "total_executions": 0,
                "successful_settlements": 0,
                "disputed_settlements": 0,
                "auto_resolved_disputes": 0,
                "reputation_score": 1.0,
                "capability_hash": canonical_json_hash(capabilities),
            },
        }
        if risk_profile is not None:
            data["risk_profile"] = risk_profile
        if display_name is not None:
            data["display_name"] = display_name

        validate_against_schema(cls.SCHEMA, data)
        obj = cls(data)
        cls._registry[obj.agent_id] = obj
        return obj

    def sign(self, private_key: str) -> str:
        signature = sign_payload(self._data, private_key, exclude_fields=["identity_signature"])
        self._data["identity_signature"] = signature
        validate_against_schema(self.SCHEMA, self._data)
        return signature

    def verify(self, public_key: str) -> bool:
        signature = self._data.get("identity_signature")
        if not signature:
            return False
        return verify_payload(
            self._data,
            signature,
            public_key,
            exclude_fields=["identity_signature"],
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
