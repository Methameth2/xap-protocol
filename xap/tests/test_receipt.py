import uuid

from xap import ExecutionReceipt, NegotiationContract, SettlementIntent, generate_keypair
from xap.settlement import PLATFORM_PUBLIC_KEY


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


def _released_settlement():
    priv_a, _ = generate_keypair()
    priv_b, _ = generate_keypair()

    negotiation = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    negotiation.accept("agent_bbbb2222", priv_b)

    settlement = SettlementIntent.create(negotiation, idempotency_key=f"idemp-r1-{uuid.uuid4()}")
    settlement.start_execution()
    settlement.submit_result(output={"completion_percentage": 100}, quality_score=0.9, latency_ms=800, agent_private_key=priv_b)
    settlement.verify_condition()
    settlement.release()
    return settlement


def test_receipt_signature_verification_and_tamper_detection():
    settlement = _released_settlement()
    receipt = settlement.execution_receipt

    assert receipt is not None
    assert receipt.verify(PLATFORM_PUBLIC_KEY)

    payload = receipt.to_dict()
    payload["final_state"]["state"] = "ROLLED_BACK"
    tampered = ExecutionReceipt.from_dict(payload)
    assert not tampered.verify(PLATFORM_PUBLIC_KEY)


def test_receipt_query_by_settlement_id():
    settlement = _released_settlement()
    matches = ExecutionReceipt.query(settlement_id=settlement.settlement_id)
    assert any(item.to_dict()["settlement_id"] == settlement.settlement_id for item in matches)
