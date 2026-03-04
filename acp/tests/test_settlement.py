import pytest

from acp import ACPSplitError, ACPStateError, NegotiationContract, SettlementIntent, generate_keypair


def _offer(rate=3.5):
    return {
        "offered_rate": rate,
        "settlement_unit": "USD",
        "payment_condition": {
            "condition_type": "probabilistic",
            "description": "quality >= 0.8",
            "probabilistic_check": {"score_field": "quality_score", "minimum_score": 0.8},
        },
    }


def _sla():
    return {
        "max_latency_ms": 2000,
        "quality_threshold": 0.8,
        "retry_allowed": True,
        "max_retries": 1,
        "partial_completion_policy": "pro_rata",
    }


def _accepted_negotiation():
    initiator_priv, _ = generate_keypair()
    counterparty_priv, _ = generate_keypair()

    contract = NegotiationContract.create(
        initiator_id="acp_initiator_123",
        counterparty_id="acp_counterparty_123",
        capability_id="cap_data_enrich",
        offer=_offer(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    contract.counter(_offer(rate=3.1), proposed_by="acp_counterparty_123")
    contract.accept("acp_initiator_123", initiator_priv)
    contract.accept("acp_counterparty_123", counterparty_priv)
    return contract


def test_settlement_idempotency_and_happy_path_release():
    payee_priv, _ = generate_keypair()
    negotiation = _accepted_negotiation()

    intent_a = SettlementIntent.create(negotiation, idempotency_key="idemp-1")
    intent_b = SettlementIntent.create(negotiation, idempotency_key="idemp-1")
    assert intent_a is intent_b

    intent_a.start_execution()
    intent_a.submit_result(output={"completion_percentage": 100}, quality_score=0.91, latency_ms=900, agent_private_key=payee_priv)
    assert intent_a.verify_condition()
    intent_a.release()

    assert intent_a.to_dict()["state"] == "RELEASED"
    assert intent_a.execution_receipt is not None


def test_settlement_invalid_state_transition_raises_state_error():
    negotiation = _accepted_negotiation()
    intent = SettlementIntent.create(negotiation, idempotency_key="idemp-2")

    with pytest.raises(ACPStateError):
        intent.release()


def test_settlement_invalid_split_rules_raise_split_error():
    payee_priv, _ = generate_keypair()
    negotiation = _accepted_negotiation()
    intent = SettlementIntent.create(negotiation, idempotency_key="idemp-3")

    payload = intent.to_dict()
    payload["split_rules"] = [
        {
            "recipient_agent_id": "acp_counterparty_123",
            "share_type": "percentage",
            "percentage": 70,
            "role": "subagent",
            "partial_completion_eligible": True,
        },
        {
            "recipient_agent_id": "acp_platform_123",
            "share_type": "percentage",
            "percentage": 20,
            "role": "platform",
            "partial_completion_eligible": False,
        },
    ]
    intent = SettlementIntent.from_dict(payload)

    intent.start_execution()
    intent.submit_result(output={"completion_percentage": 100}, quality_score=0.95, latency_ms=500, agent_private_key=payee_priv)
    intent.verify_condition()

    with pytest.raises(ACPSplitError):
        intent.release()


def test_end_to_end_register_negotiate_lock_execute_verify_release_receipt():
    initiator_priv, initiator_pub = generate_keypair()
    counterparty_priv, counterparty_pub = generate_keypair()

    from acp import AgentIdentity

    initiator = AgentIdentity.create(
        capabilities=[
            {
                "capability_id": "cap_orchestrate",
                "name": "Orchestrate",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            }
        ],
        pricing={"model": "fixed", "base_rate": 5, "settlement_unit": "USD"},
        sla={"max_latency_ms": 2000, "quality_threshold": 0.8},
        risk_profile={"max_transaction_value": 1000},
        public_key=initiator_pub,
    )
    initiator.sign(initiator_priv)

    counterparty = AgentIdentity.create(
        capabilities=[
            {
                "capability_id": "cap_data_enrich",
                "name": "Data Enrichment",
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
            }
        ],
        pricing={"model": "fixed", "base_rate": 3.5, "settlement_unit": "USD"},
        sla={"max_latency_ms": 1500, "quality_threshold": 0.85},
        risk_profile={"max_transaction_value": 1000},
        public_key=counterparty_pub,
    )
    counterparty.sign(counterparty_priv)

    negotiation = NegotiationContract.create(
        initiator_id=initiator.agent_id,
        counterparty_id=counterparty.agent_id,
        capability_id="cap_data_enrich",
        offer=_offer(rate=3.5),
        sla=_sla(),
        expires_in_seconds=300,
    )
    negotiation.counter(_offer(rate=3.2), proposed_by=counterparty.agent_id)
    negotiation.accept(initiator.agent_id, initiator_priv)
    negotiation.accept(counterparty.agent_id, counterparty_priv)

    settlement = SettlementIntent.create(negotiation, idempotency_key="idemp-e2e")
    settlement.start_execution()
    settlement.submit_result(
        output={"completion_percentage": 100, "result": {"ok": True}},
        quality_score=0.92,
        latency_ms=700,
        agent_private_key=counterparty_priv,
    )
    assert settlement.verify_condition()
    settlement.release()

    receipt = settlement.execution_receipt
    assert receipt is not None
    assert receipt.to_dict()["final_state"]["state"] == "RELEASED"
