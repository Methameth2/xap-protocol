from acp import AgentIdentity, generate_keypair


def _capabilities():
    return [
        {
            "capability_id": "cap_data_enrich",
            "name": "Data Enrichment",
            "input_schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"enriched": {"type": "boolean"}}},
        }
    ]


def _pricing():
    return {"model": "fixed", "base_rate": 1.0, "settlement_unit": "USD"}


def _sla():
    return {"max_latency_ms": 1500, "quality_threshold": 0.9}


def test_identity_roundtrip_and_signature_verification():
    private_key, public_key = generate_keypair()
    identity = AgentIdentity.create(
        capabilities=_capabilities(),
        pricing=_pricing(),
        sla=_sla(),
        risk_profile={"max_transaction_value": 1000},
        public_key=public_key,
    )

    signature = identity.sign(private_key)
    assert isinstance(signature, str)
    assert identity.verify(public_key)

    clone = AgentIdentity.from_dict(identity.to_dict())
    assert clone.verify(public_key)

    tampered = clone.to_dict()
    tampered["pricing"]["base_rate"] = 99.9
    tampered_identity = AgentIdentity.from_dict(tampered)
    assert not tampered_identity.verify(public_key)
