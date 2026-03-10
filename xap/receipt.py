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

        receipt_data: dict[str, Any] = {
            "xap_version": "0.1",
            "receipt_id": generate_prefixed_id("rcpt_"),
            "receipt_type": _resolve_receipt_type(settlement_data["state"]),
            "settlement_id": settlement_data["settlement_id"],
            "negotiation_id": settlement_data["negotiation_id"],
            "payer_agent_id": settlement_data["payer_agent_id"],
            "payee_agent_id": settlement_data["payee_agent_id"],
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
    if state == "RELEASED":
        return "FULL_RELEASE"
    if state == "PARTIAL_RELEASED":
        return "PARTIAL_RELEASE"
    if state == "ROLLED_BACK":
        return "FULL_ROLLBACK"
    if state == "DISPUTED":
        return "DISPUTE_RESOLVED"
    return "SPLIT_CASCADE"


def _build_final_state(settlement_data: dict[str, Any]) -> dict[str, Any]:
    state = settlement_data["state"]
    final_state = {
        "state": "DISPUTE_RESOLVED" if state == "DISPUTED" else state,
        "resolved_at": settlement_data.get("settled_at", utc_now_iso()),
        "resolution_method": "automatic_condition_met",
        "condition_met": settlement_data.get("verification_result", {}).get("condition_met", False),
        "completion_percentage": settlement_data.get("execution_result", {}).get("completion_percentage", 100),
    }

    if state in {"ROLLED_BACK", "DISPUTED"}:
        final_state["resolution_method"] = "automatic_condition_failed"
    if settlement_data.get("verification_result", {}).get("verification_method") == "human_verified":
        final_state["resolution_method"] = "human_approved" if final_state["condition_met"] else "human_rejected"

    return final_state


def _build_amounts_settled(settlement_data: dict[str, Any]) -> dict[str, Any]:
    locked = settlement_data["locked_amount"]
    if settlement_data["state"] == "ROLLED_BACK":
        released = 0.0
    else:
        released = sum(item["amount"] for item in settlement_data.get("split_distributions", []))

    return {
        "total_locked": locked,
        "total_released": released,
        "total_rolled_back": max(0.0, locked - released),
        "settlement_unit": settlement_data["settlement_unit"],
        "split_distributions": settlement_data.get("split_distributions", []),
    }


def _event_hash(event: dict[str, Any]) -> str:
    return sha256(canonical_json_bytes(event, exclude_fields=["signature"])).hexdigest()
