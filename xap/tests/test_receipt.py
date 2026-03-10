import uuid

from xap import ExecutionReceipt, NegotiationContract, SettlementIntent, generate_keypair
from xap.settlement import PLATFORM_PUBLIC_KEY


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


def _released_settlement():
    initiator_priv, _ = generate_keypair()
    counterparty_priv, _ = generate_keypair()

    negotiation = NegotiationContract.create(
        initiator_id="xap_initiator_123",
        counterparty_id="xap_counterparty_123",
        capability_id="cap_data_enrich",
        offer=_offer(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    negotiation.accept("xap_initiator_123", initiator_priv)
    negotiation.accept("xap_counterparty_123", counterparty_priv)

    settlement = SettlementIntent.create(negotiation, idempotency_key=f"idemp-r1-{uuid.uuid4()}")
    settlement.start_execution()
    settlement.submit_result(output={"completion_percentage": 100}, quality_score=0.9, latency_ms=800, agent_private_key=counterparty_priv)
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
