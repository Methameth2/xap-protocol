import pytest

from xap import XAPSplitError, XAPStateError, NegotiationContract, SettlementIntent, generate_keypair


def _task():
    return {
        "type": "data_enrichment",
        "input_spec": {"format": "json"},
        "output_spec": {"format": "json"},
    }


def _pricing(amount=500):
    return {
        "amount_minor_units": amount,
        "currency": "USD",
        "model": "fixed",
        "per": "request",
    }


def _sla():
    return {
        "max_latency_ms": 2000,
        "min_quality_score_bps": 8000,
    }


def _accepted_negotiation():
    priv_a, _ = generate_keypair()
    priv_b, _ = generate_keypair()

    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    contract.counter(_pricing(amount=400), proposed_by="agent_bbbb2222", private_key=priv_b)
    contract.accept("agent_aaaa1111", priv_a)
    return contract


def test_settlement_idempotency_and_happy_path_release():
    payee_priv, _ = generate_keypair()
    negotiation = _accepted_negotiation()

    intent_a = SettlementIntent.create(negotiation, idempotency_key="idemp-v2-1")
    intent_b = SettlementIntent.create(negotiation, idempotency_key="idemp-v2-1")
    assert intent_a is intent_b

    intent_a.start_execution()
    intent_a.submit_result(output={"completion_percentage": 100}, quality_score=0.91, latency_ms=900, agent_private_key=payee_priv)
    assert intent_a.verify_condition()
    intent_a.release()

    assert intent_a.to_dict()["state"] == "RELEASED"
    assert intent_a.execution_receipt is not None


def test_settlement_invalid_state_transition_raises_state_error():
    negotiation = _accepted_negotiation()
    intent = SettlementIntent.create(negotiation, idempotency_key="idemp-v2-2")

    with pytest.raises(XAPStateError):
        intent.release()


def test_settlement_invalid_split_rules_raise_split_error():
    payee_priv, _ = generate_keypair()
    negotiation = _accepted_negotiation()
    intent = SettlementIntent.create(negotiation, idempotency_key="idemp-v2-3")

    payload = intent.to_dict()
    payload["split_rules"] = [
        {
            "recipient_agent_id": "agent_bbbb2222",
            "share_type": "percentage",
            "percentage": 70,
            "role": "subagent",
            "partial_completion_eligible": True,
        },
        {
            "recipient_agent_id": "agent_cccc3333",
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

    with pytest.raises(XAPSplitError):
        intent.release()


def test_end_to_end_register_negotiate_lock_execute_verify_release_receipt():
    initiator_priv, initiator_pub = generate_keypair()
    counterparty_priv, counterparty_pub = generate_keypair()

    from xap import AgentIdentity

    initiator = AgentIdentity.create(
        capabilities=[
            {
                "name": "orchestrate",
                "version": "1.0.0",
                "pricing": {"model": "fixed", "amount_minor_units": 500, "currency": "USD", "per": "request"},
                "sla": {"max_latency_ms": 2000, "availability_bps": 9900},
            }
        ],
        risk_profile={"risk_tier": "low"},
        public_key=initiator_pub,
    )
    initiator.sign(initiator_priv)

    counterparty = AgentIdentity.create(
        capabilities=[
            {
                "name": "data_enrichment",
                "version": "1.0.0",
                "pricing": {"model": "fixed", "amount_minor_units": 350, "currency": "USD", "per": "request"},
                "sla": {"max_latency_ms": 1500, "availability_bps": 9950},
            }
        ],
        risk_profile={"risk_tier": "low"},
        public_key=counterparty_pub,
    )
    counterparty.sign(counterparty_priv)

    negotiation = NegotiationContract.create(
        from_agent=initiator.agent_id,
        to_agent=counterparty.agent_id,
        task=_task(),
        pricing=_pricing(amount=350),
        sla=_sla(),
        expires_in_seconds=300,
    )
    negotiation.counter(_pricing(amount=300), proposed_by=counterparty.agent_id, private_key=counterparty_priv)
    negotiation.accept(initiator.agent_id, initiator_priv)

    settlement = SettlementIntent.create(negotiation, idempotency_key="idemp-e2e-v2")
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
