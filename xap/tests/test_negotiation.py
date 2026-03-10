import pytest

from xap import XAPExpiredError, XAPStateError, NegotiationContract, generate_keypair


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


def test_negotiation_happy_path_offer_counter_accept():
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
    assert contract.to_dict()["state"] == "OFFER"
    assert contract.to_dict()["round_number"] == 1

    contract.counter(_pricing(amount=400), proposed_by="agent_bbbb2222", private_key=priv_b)
    assert contract.to_dict()["state"] == "COUNTER"
    assert contract.to_dict()["round_number"] == 2
    assert "previous_state_hash" in contract.to_dict()

    contract.accept("agent_aaaa1111", priv_a)
    assert contract.to_dict()["state"] == "ACCEPT"


def test_negotiation_invalid_transition_raises_state_error():
    priv_a, _ = generate_keypair()

    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    contract.accept("agent_bbbb2222", priv_a)

    with pytest.raises(XAPStateError):
        contract.counter(_pricing(amount=300), proposed_by="agent_aaaa1111")


def test_expired_negotiation_raises_expired_error():
    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=-1,
    )

    with pytest.raises(XAPExpiredError):
        contract.counter(_pricing(amount=300), proposed_by="agent_bbbb2222")


def test_negotiation_reject():
    priv_a, _ = generate_keypair()

    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    contract.reject("agent_bbbb2222", priv_a)
    assert contract.to_dict()["state"] == "REJECT"

    with pytest.raises(XAPStateError):
        contract.reject("agent_aaaa1111")


def test_negotiation_self_withdrawal():
    priv_a, _ = generate_keypair()

    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
    )
    contract.reject("agent_aaaa1111", priv_a)
    assert contract.to_dict()["state"] == "REJECT"


def test_negotiation_max_rounds():
    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
        max_rounds=2,
    )
    contract.counter(_pricing(amount=400), proposed_by="agent_bbbb2222")

    with pytest.raises(XAPStateError, match="Maximum negotiation rounds"):
        contract.counter(_pricing(amount=350), proposed_by="agent_aaaa1111")


def test_negotiation_state_chain_hashes():
    priv_a, _ = generate_keypair()

    contract = NegotiationContract.create(
        from_agent="agent_aaaa1111",
        to_agent="agent_bbbb2222",
        task=_task(),
        pricing=_pricing(),
        sla=_sla(),
        expires_in_seconds=300,
    )

    data_before = contract.to_dict()
    contract.counter(_pricing(amount=400), proposed_by="agent_bbbb2222")
    data_after = contract.to_dict()

    assert data_after["previous_state_hash"].startswith("sha256:")
    assert len(data_after["previous_state_hash"]) == 71  # "sha256:" + 64 hex chars
