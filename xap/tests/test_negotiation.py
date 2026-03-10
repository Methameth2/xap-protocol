import pytest

from xap import XAPExpiredError, XAPStateError, NegotiationContract, generate_keypair


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


def test_negotiation_happy_path_offer_counter_accept():
    initiator_priv, _ = generate_keypair()
    counterparty_priv, _ = generate_keypair()

    contract = NegotiationContract.create(
        initiator_id="xap_initiator_123",
        counterparty_id="xap_counterparty_123",
        capability_id="cap_data_enrich",
        offer=_offer(),
        sla=_sla(),
        expires_in_seconds=300,
    )

    contract.counter(_offer(rate=3.0), proposed_by="xap_counterparty_123")
    contract.counter(_offer(rate=2.9), proposed_by="xap_initiator_123")
    contract.accept("xap_initiator_123", initiator_priv)
    contract.accept("xap_counterparty_123", counterparty_priv)

    assert contract.to_dict()["state"] == "ACCEPT"


def test_negotiation_invalid_transition_raises_state_error():
    initiator_priv, _ = generate_keypair()

    contract = NegotiationContract.create(
        initiator_id="xap_initiator_123",
        counterparty_id="xap_counterparty_123",
        capability_id="cap_data_enrich",
        offer=_offer(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    contract.accept("xap_initiator_123", initiator_priv)

    with pytest.raises(XAPStateError):
        contract.counter(_offer(rate=2.8), proposed_by="xap_counterparty_123")


def test_expired_negotiation_raises_expired_error():
    contract = NegotiationContract.create(
        initiator_id="xap_initiator_123",
        counterparty_id="xap_counterparty_123",
        capability_id="cap_data_enrich",
        offer=_offer(),
        sla=_sla(),
        expires_in_seconds=-1,
    )

    with pytest.raises(XAPExpiredError):
        contract.counter(_offer(rate=2.8), proposed_by="xap_counterparty_123")
