from xap import AgentIdentity, generate_keypair


def _capabilities():
    return [
        {
            "name": "data_enrichment",
            "version": "1.0.0",
            "description": "Enriches company data",
            "pricing": {
                "model": "fixed",
                "amount_minor_units": 300,
                "currency": "USD",
                "per": "request",
            },
            "sla": {
                "max_latency_ms": 1500,
                "availability_bps": 9900,
                "min_quality_score_bps": 9000,
            },
        }
    ]


def test_identity_roundtrip_and_signature_verification():
    private_key, public_key = generate_keypair()
    identity = AgentIdentity.create(
        capabilities=_capabilities(),
        risk_profile={"risk_tier": "low", "jurisdiction": "US"},
        public_key=public_key,
    )

    signature = identity.sign(private_key)
    assert isinstance(signature, str)
    assert identity.verify(public_key)

    clone = AgentIdentity.from_dict(identity.to_dict())
    assert clone.verify(public_key)

    tampered = clone.to_dict()
    tampered["capabilities"][0]["pricing"]["amount_minor_units"] = 99999
    tampered_identity = AgentIdentity.from_dict(tampered)
    assert not tampered_identity.verify(public_key)


def test_identity_with_org_hierarchy():
    private_key, public_key = generate_keypair()
    identity = AgentIdentity.create(
        capabilities=_capabilities(),
        public_key=public_key,
        org_id="org_a1b2c3d4",
        team_id="team_e5f6a7b8",
    )
    identity.sign(private_key)

    data = identity.to_dict()
    assert data["org_id"] == "org_a1b2c3d4"
    assert data["team_id"] == "team_e5f6a7b8"
    assert data["key_version"] == 1
    assert data["key_status"] == "active"
    assert data["status"] == "active"
    assert data["xap_version"] == "0.2.0"


def test_identity_agent_id_format():
    identity = AgentIdentity.create(capabilities=_capabilities())
    assert identity.agent_id.startswith("agent_")
    assert len(identity.agent_id) == 14  # "agent_" + 8 hex chars
