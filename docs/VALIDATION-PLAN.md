# Validation Plan

## Validation Goal
Prove ACP can become a practical interoperability standard for autonomous agent commerce.

## Core Hypotheses
1. A small set of primitives can represent most agent-to-agent economic flows.
2. Deterministic state machines reduce settlement ambiguity.
3. Signed, replayable records improve trust across unknown counterparties.
4. Schema-first protocol design lowers integration cost across stacks.

## Validation Tracks
- **Schema Fitness**: check whether fields are sufficient, minimal, and unambiguous.
- **State-Machine Safety**: test invalid transitions, timeout behavior, and rollback outcomes.
- **Economic Correctness**: validate split distribution, idempotency, and dispute edge cases.
- **Implementation Clarity**: measure time-to-first-integration for external teams.

## Success Criteria (Pre-v1.0)
- At least 3 independent teams can implement ACP objects from the spec without private guidance.
- No unresolved ambiguity in terminal settlement outcomes.
- All required fields in v1.0 have explicit rationale and migration policy.
- Conformance test suite scope agreed and published.

## Evidence To Collect
- Issue reports tagged `schema-feedback`, `edge-case`, `implementation-feedback`
- Integration notes from external implementers
- Change log of schema updates with rationale
- Decision records for disputed design choices

## Exit Criteria For v1.0 Freeze
- Schema churn rate meaningfully drops
- Open critical ambiguities are resolved
- Governance and compatibility policy finalized
- Conformance suite is published and runnable
