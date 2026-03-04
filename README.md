# ACP — Agent Commerce Protocol

**The open economic protocol for autonomous agents.**

[![License: MIT](https://img.shields.io/badge/License-MIT-white.svg)](https://opensource.org/licenses/MIT)
[![Status: Draft v0.1](https://img.shields.io/badge/Status-Draft%20v0.1-yellow.svg)](#project-status)
[![Maintained by: Agentra Labs](https://img.shields.io/badge/Maintained%20by-Agentra%20Labs-blue.svg)](https://www.agentralabs.tech)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2.svg)](https://discord.gg/agentralabs)

---

## Public Position
ACP is currently in **Introduction, Planning, and Validation**.

This repository exists to:
- Define the open protocol primitives for agent-to-agent commerce
- Establish public claim of origin for the protocol design
- Gather rigorous community feedback before protocol lock-in

This repository does **not** claim production readiness yet.

---

## What Is ACP?
ACP (Agent Commerce Protocol) is an open standard for how autonomous agents:
- identify themselves,
- negotiate terms,
- lock/release value against explicit conditions,
- and produce signed, replayable audit records.

ACP is the interoperability layer above settlement rails. It does not replace payment systems; it standardizes coordination and accountability between agents.

---

## The Primitives

```
AgentIdentity        →  who the agent is and what it can do
NegotiationContract  →  what two agents agreed to
SettlementIntent     →  what value is locked and under what condition
ExecutionReceipt     →  what happened and what was paid
VerityReceipt        →  why it happened and whether it can be replayed/proven
```

---

## Project Status

| Area | Status |
|---|---|
| Protocol narrative | Draft v0.1 |
| Core schemas (`AgentIdentity`, `NegotiationContract`, `SettlementIntent`, `ExecutionReceipt`) | Draft v0.1 |
| `VerityReceipt` schema | In progress |
| Governance policy | Drafting |
| Conformance test suite | Planned |
| Reference code artifacts in `/acp` | Experimental, non-normative |
| Production settlement engine | Not started in this repo |

Detailed stage notes: [`docs/STAGE.md`](/docs/STAGE.md)

---

## Schema Reference
All schema source-of-truth files live in [`/acp/schemas`](/acp/schemas).

| Schema | File | Status |
|---|---|---|
| `AgentIdentity` | [`/acp/schemas/agent-identity.json`](/acp/schemas/agent-identity.json) | ✅ v0.1 Draft |
| `NegotiationContract` | [`/acp/schemas/negotiation-contract.json`](/acp/schemas/negotiation-contract.json) | ✅ v0.1 Draft |
| `SettlementIntent` | [`/acp/schemas/settlement-intent.json`](/acp/schemas/settlement-intent.json) | ✅ v0.1 Draft |
| `ExecutionReceipt` | [`/acp/schemas/execution-receipt.json`](/acp/schemas/execution-receipt.json) | ✅ v0.1 Draft |
| `VerityReceipt` | [`/acp/schemas/verity-receipt.json`](/acp/schemas/verity-receipt.json) | 🔄 In Progress |

---

## Lifecycle Model

```
REGISTER → NEGOTIATE → EXECUTE → SETTLE → AUDIT
```

Negotiation state model:

```
OFFER ↔ COUNTER → ACCEPT or REJECT
```

Settlement design principle:
- no ambiguous terminal outcome,
- no money in limbo,
- deterministic failure handling declared up front.

---

## Why This Matters For The Agent Economy
Without common economic primitives, agent ecosystems fragment into incompatible one-off integrations.

ACP targets a shared baseline for:
- autonomous contracting semantics,
- conditional settlement behavior,
- reproducible audit and dispute evidence,
- interoperable trust signals across unknown counterparties.

---

## Validation Artifacts
This repo now includes explicit validation/planning artifacts:

- Stage definition: [`docs/STAGE.md`](/docs/STAGE.md)
- Validation hypotheses and exit criteria: [`docs/VALIDATION-PLAN.md`](/docs/VALIDATION-PLAN.md)
- Phase roadmap: [`docs/ROADMAP.md`](/docs/ROADMAP.md)
- Early adoption strategy: [`docs/ADOPTION-PLAYBOOK.md`](/docs/ADOPTION-PLAYBOOK.md)

---

## Contributing (Current Priority)
At this phase, the most valuable contributions are:
- Schema ambiguity reports
- Edge-case settlement/dispute scenarios
- Independent implementer feedback
- Critiques on protocol governance and compatibility policy

Use issue labels:
- `schema-feedback`
- `edge-case`
- `implementation-feedback`
- `dispute-resolution`
- `monetary-policy`
- `verity-legal`

---

## Relationship To Agentra Labs And Agentra Rail
- **ACP (this repo):** open protocol specification.
- **Agentra Labs:** broader cognitive substrate work.
- **Agentra Rail:** intended production implementation path.

ACP remains open and MIT-licensed regardless of implementation choices.

---

## Community
- Discord: [Join @agentralabs](https://discord.gg/agentralabs)
- X: [@agentralab](https://x.com/agentralab)
- Email: [hello@agentralabs.tech](mailto:hello@agentralabs.tech)

---

## License
MIT: [`LICENSE`](/LICENSE)

---

*ACP is maintained by Agentra Labs as an open protocol effort for interoperable agent commerce.*
