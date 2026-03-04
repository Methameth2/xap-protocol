# ACP v0.1 Reference Implementation (Python)

This repository contains a lightweight Python implementation of ACP v0.1 with four core objects:

- `AgentIdentity`
- `NegotiationContract`
- `SettlementIntent`
- `ExecutionReceipt`

## Install

```bash
python -m pip install cryptography>=41.0.0 jsonschema>=4.0.0 pytest
```

## Quickstart

```python
from acp import AgentIdentity, NegotiationContract, SettlementIntent, generate_keypair
from acp.settlement import PLATFORM_PUBLIC_KEY

# 1) Register identities
initiator_priv, initiator_pub = generate_keypair()
counterparty_priv, counterparty_pub = generate_keypair()

initiator = AgentIdentity.create(
    capabilities=[{
        "capability_id": "cap_orchestrate",
        "name": "Orchestrate",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }],
    pricing={"model": "fixed", "base_rate": 5, "settlement_unit": "USD"},
    sla={"max_latency_ms": 2000, "quality_threshold": 0.8},
    risk_profile={"max_transaction_value": 1000},
    public_key=initiator_pub,
)
initiator.sign(initiator_priv)

counterparty = AgentIdentity.create(
    capabilities=[{
        "capability_id": "cap_data_enrich",
        "name": "Data Enrichment",
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
    }],
    pricing={"model": "fixed", "base_rate": 3.5, "settlement_unit": "USD"},
    sla={"max_latency_ms": 1500, "quality_threshold": 0.85},
    risk_profile={"max_transaction_value": 1000},
    public_key=counterparty_pub,
)
counterparty.sign(counterparty_priv)

# 2) Negotiate
contract = NegotiationContract.create(
    initiator_id=initiator.agent_id,
    counterparty_id=counterparty.agent_id,
    capability_id="cap_data_enrich",
    offer={
        "offered_rate": 3.2,
        "settlement_unit": "USD",
        "payment_condition": {
            "condition_type": "probabilistic",
            "description": "quality >= 0.8",
            "probabilistic_check": {
                "score_field": "quality_score",
                "minimum_score": 0.8,
            },
        },
    },
    sla={
        "max_latency_ms": 2000,
        "quality_threshold": 0.8,
        "retry_allowed": True,
        "max_retries": 1,
        "partial_completion_policy": "pro_rata",
    },
    expires_in_seconds=300,
)
contract.accept(initiator.agent_id, initiator_priv)
contract.accept(counterparty.agent_id, counterparty_priv)

# 3) Lock + execute + settle
intent = SettlementIntent.create(contract, idempotency_key="demo-1")
intent.start_execution()
intent.submit_result(
    output={"completion_percentage": 100, "payload": {"ok": True}},
    quality_score=0.91,
    latency_ms=900,
    agent_private_key=counterparty_priv,
)
intent.verify_condition()
intent.release()

# 4) Audit with receipt
receipt = intent.execution_receipt
assert receipt is not None
assert receipt.verify(PLATFORM_PUBLIC_KEY)
```

## Run Tests

```bash
pytest -q
```
