"""ExecutionReceipt implementation for XAP v0.1."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, ClassVar

from ._common import deep_copy, generate_prefixed_id, utc_now_iso, validate_against_schema
from .crypto import canonical_json_bytes, sign_payload, verify_payload


@dataclass
class ExecutionReceipt:
    _data: dict[str, Any]

    SCHEMA: ClassVar[str] = "execution-receipt.json"
    _registry: ClassVar[dict[str, "ExecutionReceipt"]] = {}

    @property
    def receipt_id(self) -> str:
        return self._data["receipt_id"]

    @classmethod
    def issue(cls, settlement: Any, platform_private_key: str) -> "ExecutionReceipt":
        settlement_data = settlement.to_dict() if hasattr(settlement, "to_dict") else deep_copy(settlement)
        event_chain = deep_copy(getattr(settlement, "event_chain", settlement_data.get("event_chain", [])))

        # Support both v0.1 and v0.2 settlement field names
        payer = settlement_data.get("payer_agent") or settlement_data.get("payer_agent_id", "")
        payee_agents = settlement_data.get("payee_agents")
        if payee_agents:
            payee = payee_agents[0]["agent_id"]
        else:
            payee = settlement_data.get("payee_agent_id", "")

        state = settlement_data["state"]

        receipt_data: dict[str, Any] = {
            "xap_version": "0.1",
            "receipt_id": generate_prefixed_id("rcpt_"),
            "receipt_type": _resolve_receipt_type(state),
            "settlement_id": settlement_data["settlement_id"],
            "negotiation_id": settlement_data["negotiation_id"],
            "payer_agent_id": payer,
            "payee_agent_id": payee,
            "event_chain": event_chain,
            "final_state": _build_final_state(settlement_data),
            "amounts_settled": _build_amounts_settled(settlement_data),
            "created_at": utc_now_iso(),
        }

        receipt_event = {
            "event_id": generate_prefixed_id("evt_"),
            "event_type": "RECEIPT_ISSUED",
            "timestamp": receipt_data["created_at"],
            "agent_id": "xap_platform",
            "event_data": {"receipt_id": receipt_data["receipt_id"]},
            "previous_event_hash": _event_hash(receipt_data["event_chain"][-1]) if receipt_data["event_chain"] else "",
        }
        receipt_event["signature"] = sign_payload(receipt_event, platform_private_key, exclude_fields=["signature"])
        receipt_data["event_chain"].append(receipt_event)

        receipt_hash = sha256(canonical_json_bytes(receipt_data, exclude_fields=["receipt_signature", "receipt_hash"]))
        receipt_data["receipt_hash"] = receipt_hash.hexdigest()
        receipt_data["receipt_signature"] = sign_payload(
            {"receipt_hash": receipt_data["receipt_hash"]},
            platform_private_key,
        )

        validate_against_schema(cls.SCHEMA, receipt_data)
        obj = cls(receipt_data)
        cls._registry[obj.receipt_id] = obj
        return obj

    def verify(self, platform_public_key: str) -> bool:
        expected_hash = sha256(canonical_json_bytes(self._data, exclude_fields=["receipt_signature", "receipt_hash"]))
        if self._data.get("receipt_hash") != expected_hash.hexdigest():
            return False
        return verify_payload(
            {"receipt_hash": self._data["receipt_hash"]},
            self._data["receipt_signature"],
            platform_public_key,
        )

    def to_dict(self) -> dict[str, Any]:
        return deep_copy(self._data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionReceipt":
        validate_against_schema(cls.SCHEMA, data)
        obj = cls(deep_copy(data))
        cls._registry[obj.receipt_id] = obj
        return obj

    @classmethod
    def query(
        cls,
        settlement_id: str | None = None,
        negotiation_id: str | None = None,
    ) -> list["ExecutionReceipt"]:
        results = list(cls._registry.values())
        if settlement_id is not None:
            results = [item for item in results if item._data.get("settlement_id") == settlement_id]
        if negotiation_id is not None:
            results = [item for item in results if item._data.get("negotiation_id") == negotiation_id]
        return results


def _resolve_receipt_type(state: str) -> str:
    mapping = {
        "SETTLED": "FULL_RELEASE",
        "RELEASED": "FULL_RELEASE",
        "PARTIAL": "PARTIAL_RELEASE",
        "PARTIAL_RELEASED": "PARTIAL_RELEASE",
        "REFUNDED": "FULL_ROLLBACK",
        "ROLLED_BACK": "FULL_ROLLBACK",
        "DISPUTED": "DISPUTE_RESOLVED",
    }
    return mapping.get(state, "FULL_RELEASE")


def _map_state_to_receipt(state: str) -> str:
    """Map v0.2 settlement states to v0.1 receipt final_state enum."""
    mapping = {
        "SETTLED": "RELEASED",
        "REFUNDED": "ROLLED_BACK",
        "PARTIAL": "PARTIAL_RELEASED",
        "DISPUTED": "DISPUTE_RESOLVED",
        # v0.1 states pass through
        "RELEASED": "RELEASED",
        "PARTIAL_RELEASED": "PARTIAL_RELEASED",
        "ROLLED_BACK": "ROLLED_BACK",
    }
    return mapping.get(state, state)


def _build_final_state(settlement_data: dict[str, Any]) -> dict[str, Any]:
    state = settlement_data["state"]
    receipt_state = _map_state_to_receipt(state)
    verification = settlement_data.get("verification_result", {})

    condition_met = verification.get("all_required_met", verification.get("condition_met", False))

    return {
        "state": receipt_state,
        "resolved_at": settlement_data.get("settled_at", utc_now_iso()),
        "resolution_method": "automatic_condition_met" if condition_met else "automatic_condition_failed",
        "condition_met": condition_met,
        "completion_percentage": settlement_data.get("execution_result", {}).get("completion_percentage", 100),
    }


def _build_amounts_settled(settlement_data: dict[str, Any]) -> dict[str, Any]:
    # Support both v0.1 and v0.2 field names
    locked = settlement_data.get("total_amount_minor_units") or settlement_data.get("locked_amount", 0)
    currency = settlement_data.get("currency") or settlement_data.get("settlement_unit", "USD")

    state = settlement_data["state"]
    if state in {"REFUNDED", "ROLLED_BACK"}:
        released = 0
    else:
        distributions = settlement_data.get("split_distributions", [])
        released = sum(
            item.get("amount_minor_units", item.get("amount", 0))
            for item in distributions
        )

    # Normalize distributions to v0.1 receipt schema format
    # Map v0.2 roles to v0.1 receipt role enum
    role_map = {
        "primary_executor": "subagent",
        "sub_executor": "subagent",
        "data_provider": "subagent",
        "tool_provider": "tool",
        "orchestrator": "orchestrator",
        "verifier": "custom",
        "platform": "platform",
    }

    normalized_distributions = []
    for d in settlement_data.get("split_distributions", []):
        raw_role = d.get("role", "custom")
        normalized_distributions.append({
            "recipient_agent_id": d.get("recipient_agent_id") or d.get("agent_id", ""),
            "amount": d.get("amount") if "amount" in d else d.get("amount_minor_units", 0),
            "role": role_map.get(raw_role, raw_role),
            "distribution_timestamp": d.get("distribution_timestamp"),
            "distribution_signature": d.get("distribution_signature"),
        })

    return {
        "total_locked": locked,
        "total_released": released,
        "total_rolled_back": max(0, locked - released),
        "settlement_unit": currency,
        "split_distributions": normalized_distributions,
    }


def _event_hash(event: dict[str, Any]) -> str:
    return sha256(canonical_json_bytes(event, exclude_fields=["signature"])).hexdigest()
