"""SettlementIntent implementation for ACP v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from hashlib import sha256
from typing import Any, ClassVar

from ._common import (
    deep_copy,
    generate_prefixed_id,
    parse_utc,
    utc_now_iso,
    validate_against_schema,
)
from .crypto import canonical_json_bytes, generate_keypair, sign_payload
from .errors import ACPExpiredError, ACPSplitError, ACPStateError
from .receipt import ExecutionReceipt

_PLATFORM_PRIVATE_KEY, PLATFORM_PUBLIC_KEY = generate_keypair()


@dataclass
class SettlementIntent:
    _data: dict[str, Any]
    event_chain: list[dict[str, Any]] = field(default_factory=list)

    SCHEMA: ClassVar[str] = "settlement-intent.json"
    _idempotency_registry: ClassVar[dict[str, "SettlementIntent"]] = {}
    _terminal_states: ClassVar[set[str]] = {"RELEASED", "PARTIAL_RELEASED", "ROLLED_BACK", "DISPUTED"}

    @property
    def settlement_id(self) -> str:
        return self._data["settlement_id"]

    @property
    def execution_receipt(self) -> ExecutionReceipt | None:
        return getattr(self, "_execution_receipt", None)

    @classmethod
    def create(cls, negotiation: Any, idempotency_key: str) -> "SettlementIntent":
        if idempotency_key in cls._idempotency_registry:
            return cls._idempotency_registry[idempotency_key]

        negotiation_data = negotiation.to_dict() if hasattr(negotiation, "to_dict") else deep_copy(negotiation)

        if negotiation_data.get("state") != "ACCEPT":
            raise ACPStateError("SettlementIntent can only be created from an ACCEPT negotiation")
        if parse_utc(utc_now_iso()) > parse_utc(negotiation_data["expires_at"]):
            raise ACPExpiredError("Cannot create settlement from an expired negotiation")

        created_at = parse_utc(utc_now_iso())
        max_latency_ms = negotiation_data.get("sla_declaration", {}).get("max_latency_ms", 60000)
        execution_deadline = created_at + timedelta(milliseconds=max_latency_ms * 2)

        split_rules = negotiation_data.get("split_rules") or [
            {
                "recipient_agent_id": negotiation_data["counterparty_agent_id"],
                "share_type": "percentage",
                "percentage": 100,
                "role": "subagent",
                "partial_completion_eligible": True,
            }
        ]

        partial_policy = negotiation_data.get("sla_declaration", {}).get("partial_completion_policy", "pro_rata")
        policy_map = {
            "pro_rata": "pro_rata_release",
            "full_release": "full_release",
            "full_rollback": "full_rollback",
        }

        data: dict[str, Any] = {
            "acp_version": "0.1",
            "settlement_id": generate_prefixed_id("stl_"),
            "state": "LOCKED",
            "negotiation_id": negotiation_data["negotiation_id"],
            "payer_agent_id": negotiation_data["initiator_agent_id"],
            "payee_agent_id": negotiation_data["counterparty_agent_id"],
            "locked_amount": negotiation_data["offer"]["offered_rate"],
            "settlement_unit": negotiation_data["offer"]["settlement_unit"],
            "condition": deep_copy(negotiation_data["offer"]["payment_condition"]),
            "split_rules": split_rules,
            "failure_handling": {
                "on_full_failure": "full_rollback",
                "on_partial_completion": policy_map.get(partial_policy, "pro_rata_release"),
                "on_timeout": "full_rollback",
                "on_verification_ambiguity": "automatic_arbitration",
            },
            "idempotency_key": idempotency_key,
            "created_at": created_at.isoformat() + "Z",
            "execution_deadline": execution_deadline.isoformat() + "Z",
            "declared_sla": deep_copy(negotiation_data.get("sla_declaration", {})),
        }

        validate_against_schema(cls.SCHEMA, data)
        obj = cls(data)
        obj.event_chain = _build_initial_event_chain(negotiation_data, data["settlement_id"])
        cls._idempotency_registry[idempotency_key] = obj
        return obj

    def start_execution(self) -> "SettlementIntent":
        self._transition("LOCKED", "EXECUTING")
        self._append_event("EXECUTION_STARTED", self._data["payee_agent_id"], {"state": "EXECUTING"})
        return self

    def submit_result(
        self,
        output: dict[str, Any],
        quality_score: float,
        latency_ms: int,
        agent_private_key: str,
    ) -> "SettlementIntent":
        self._transition("EXECUTING", "VERIFYING")

        result = {
            "submitted_by": self._data["payee_agent_id"],
            "submitted_at": utc_now_iso(),
            "output": output,
            "quality_score": quality_score,
            "latency_ms": latency_ms,
            "completion_percentage": output.get("completion_percentage", 100),
        }
        result["execution_signature"] = sign_payload(result, agent_private_key, exclude_fields=["execution_signature"])
        self._data["execution_result"] = result
        self._append_event("EXECUTION_COMPLETED", self._data["payee_agent_id"], result, signer_key=agent_private_key)
        validate_against_schema(self.SCHEMA, self._data)
        return self

    def verify_condition(self) -> bool:
        if self._data["state"] != "VERIFYING":
            raise ACPStateError("Condition verification requires VERIFYING state")

        result = self._data.get("execution_result", {})
        output = result.get("output", {})
        condition = self._data["condition"]
        condition_type = condition.get("condition_type")

        condition_met = False
        detail = ""

        if condition_type == "probabilistic":
            minimum_score = condition.get("probabilistic_check", {}).get("minimum_score", 0)
            actual_score = result.get("quality_score", 0)
            condition_met = actual_score >= minimum_score
            detail = f"quality_score={actual_score} minimum_score={minimum_score}"
        elif condition_type == "deterministic":
            deterministic = condition.get("deterministic_check", {})
            expected = deterministic.get("expected_value")
            check_path = deterministic.get("check_path")
            value = _extract_path(output, check_path) if check_path else output
            condition_met = value == expected if expected is not None else bool(value)
            detail = f"value={value} expected={expected}"
        elif condition_type == "human_verified":
            condition_met = bool(output.get("human_verified"))
            detail = "human verification flag checked"

        self._data["verification_result"] = {
            "verified_at": utc_now_iso(),
            "condition_met": condition_met,
            "verification_method": condition_type,
            "verification_detail": detail,
            "resulting_state": "RELEASED" if condition_met else "ROLLED_BACK",
        }

        self._append_event(
            "CONDITION_VERIFIED" if condition_met else "CONDITION_FAILED",
            self._data["payer_agent_id"],
            {"condition_met": condition_met, "detail": detail},
        )
        validate_against_schema(self.SCHEMA, self._data)
        return condition_met

    def release(self) -> "SettlementIntent":
        if self._data["state"] != "VERIFYING":
            raise ACPStateError("Release requires VERIFYING state")

        if "verification_result" not in self._data:
            self.verify_condition()
        if not self._data["verification_result"]["condition_met"]:
            raise ACPStateError("Cannot release settlement when condition is not met")

        distributions = self.apply_splits()
        completion = self._data.get("execution_result", {}).get("completion_percentage", 100)
        target_state = "PARTIAL_RELEASED" if completion < 100 else "RELEASED"

        self._data["state"] = target_state
        self._data["settled_at"] = utc_now_iso()
        self._data["split_distributions"] = distributions

        self._append_event("FUNDS_RELEASED", self._data["payer_agent_id"], {"state": target_state})
        self._append_event("SPLIT_DISTRIBUTED", "acp_platform", {"count": len(distributions)})
        self._issue_receipt()
        validate_against_schema(self.SCHEMA, self._data)
        return self

    def rollback(self) -> "SettlementIntent":
        if self._data["state"] != "VERIFYING":
            raise ACPStateError("Rollback requires VERIFYING state")

        self._data["state"] = "ROLLED_BACK"
        self._data["settled_at"] = utc_now_iso()
        if "verification_result" not in self._data:
            self._data["verification_result"] = {
                "verified_at": utc_now_iso(),
                "condition_met": False,
                "verification_method": self._data["condition"].get("condition_type", "deterministic"),
                "verification_detail": "rollback requested",
                "resulting_state": "ROLLED_BACK",
            }

        self._append_event("FUNDS_ROLLED_BACK", self._data["payer_agent_id"], {"state": "ROLLED_BACK"})
        self._issue_receipt()
        validate_against_schema(self.SCHEMA, self._data)
        return self

    def apply_splits(self) -> list[dict[str, Any]]:
        split_rules = self._data.get("split_rules", [])
        fixed_total = 0.0
        percentage_total = 0.0

        for rule in split_rules:
            share_type = rule.get("share_type")
            if share_type == "fixed":
                if "fixed_amount" not in rule:
                    raise ACPSplitError("Fixed split rule missing fixed_amount")
                fixed_total += float(rule["fixed_amount"])
            elif share_type == "percentage":
                if "percentage" not in rule:
                    raise ACPSplitError("Percentage split rule missing percentage")
                percentage_total += float(rule["percentage"])
            else:
                raise ACPSplitError(f"Unsupported share_type: {share_type}")

        if round(percentage_total, 10) != 100.0:
            raise ACPSplitError("Percentage split rules must sum to 100")

        locked_amount = float(self._data["locked_amount"])
        if fixed_total > locked_amount:
            raise ACPSplitError("Fixed split amounts exceed locked amount")

        remaining = locked_amount - fixed_total
        now = utc_now_iso()
        distributions: list[dict[str, Any]] = []

        for rule in split_rules:
            if rule["share_type"] == "fixed":
                amount = float(rule["fixed_amount"])
            else:
                amount = remaining * float(rule["percentage"]) / 100.0

            record = {
                "recipient_agent_id": rule["recipient_agent_id"],
                "amount": amount,
                "role": rule.get("role", "custom"),
                "distribution_timestamp": now,
            }
            record["distribution_signature"] = sign_payload(
                record,
                _PLATFORM_PRIVATE_KEY,
                exclude_fields=["distribution_signature"],
            )
            distributions.append(record)

        return distributions

    def to_dict(self) -> dict[str, Any]:
        data = deep_copy(self._data)
        data["event_chain"] = deep_copy(self.event_chain)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SettlementIntent":
        event_chain = deep_copy(data.get("event_chain", []))
        payload = deep_copy(data)
        payload.pop("event_chain", None)
        validate_against_schema(cls.SCHEMA, payload)
        return cls(payload, event_chain=event_chain)

    def _transition(self, expected_state: str, next_state: str) -> None:
        current = self._data["state"]
        if current != expected_state:
            raise ACPStateError(f"Invalid state transition from {current} to {next_state}")
        self._data["state"] = next_state

    def _append_event(
        self,
        event_type: str,
        agent_id: str,
        event_data: dict[str, Any],
        signer_key: str | None = None,
    ) -> None:
        previous_hash = _event_hash(self.event_chain[-1]) if self.event_chain else ""
        event = {
            "event_id": generate_prefixed_id("evt_"),
            "event_type": event_type,
            "timestamp": utc_now_iso(),
            "agent_id": agent_id,
            "event_data": event_data,
            "previous_event_hash": previous_hash,
        }
        event["signature"] = sign_payload(event, signer_key or _PLATFORM_PRIVATE_KEY, exclude_fields=["signature"])
        self.event_chain.append(event)

    def _issue_receipt(self) -> None:
        if self._data["state"] not in self._terminal_states:
            return
        self._execution_receipt = ExecutionReceipt.issue(self, _PLATFORM_PRIVATE_KEY)
        self._data["execution_receipt_id"] = self._execution_receipt.receipt_id


def _event_hash(event: dict[str, Any]) -> str:
    return sha256(canonical_json_bytes(event, exclude_fields=["signature"])).hexdigest()


def _build_initial_event_chain(negotiation_data: dict[str, Any], settlement_id: str) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    first_event = {
        "event_id": generate_prefixed_id("evt_"),
        "event_type": "NEGOTIATION_INITIATED",
        "timestamp": negotiation_data["created_at"],
        "agent_id": negotiation_data["initiator_agent_id"],
        "event_data": {"negotiation_id": negotiation_data["negotiation_id"]},
        "previous_event_hash": "",
    }
    first_event["signature"] = sign_payload(first_event, _PLATFORM_PRIVATE_KEY, exclude_fields=["signature"])
    chain.append(first_event)

    for history_item in negotiation_data.get("negotiation_history", []):
        state = history_item.get("state", "OFFER")
        if state == "OFFER":
            event_type = "OFFER_MADE"
        elif state == "COUNTER":
            event_type = "COUNTER_MADE"
        elif state == "ACCEPT":
            event_type = "CONTRACT_ACCEPTED"
        else:
            event_type = "OFFER_MADE"

        event = {
            "event_id": generate_prefixed_id("evt_"),
            "event_type": event_type,
            "timestamp": history_item.get("timestamp", utc_now_iso()),
            "agent_id": history_item.get("proposed_by", negotiation_data["initiator_agent_id"]),
            "event_data": {"state": state, "offered_rate": history_item.get("offered_rate")},
            "previous_event_hash": _event_hash(chain[-1]),
        }
        event["signature"] = history_item.get("signature") or sign_payload(
            event,
            _PLATFORM_PRIVATE_KEY,
            exclude_fields=["signature"],
        )
        chain.append(event)

    lock_event = {
        "event_id": generate_prefixed_id("evt_"),
        "event_type": "FUNDS_LOCKED",
        "timestamp": utc_now_iso(),
        "agent_id": negotiation_data["initiator_agent_id"],
        "event_data": {"settlement_id": settlement_id},
        "previous_event_hash": _event_hash(chain[-1]),
    }
    lock_event["signature"] = sign_payload(lock_event, _PLATFORM_PRIVATE_KEY, exclude_fields=["signature"])
    chain.append(lock_event)
    return chain


def _extract_path(data: Any, path: str | None) -> Any:
    if not path:
        return data
    # Minimal JSONPath-like support: $.a.b.c
    normalized = path.strip()
    if normalized.startswith("$"):
        normalized = normalized[1:]
    normalized = normalized.lstrip(".")

    value = data
    for part in normalized.split("."):
        if not part:
            continue
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value
