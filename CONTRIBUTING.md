# Contributing to XAP

Thank you for your interest in contributing to the eXchange Agent Protocol.

XAP is early-stage. The protocol is in draft. The schemas are being hardened. The most impactful contributions right now are feedback and thinking, not code.

## How to Contribute

### 1. Read first

Start with the schemas in `/xap/schemas/`. They are the source of truth. Then read the open issues and discussions to understand what is already being explored.

### 2. Open an issue before writing anything substantial

XAP is a protocol. Changing a field name or adding a required property can break every implementation. All significant changes start as a discussion, not a pull request.

### 3. Use the right label

| Label | Use for |
|---|---|
| `schema-feedback` | Feedback on the five XAP schemas |
| `edge-case` | A scenario the protocol does not handle correctly |
| `vertical-schema` | Domain-specific capability definitions (finance, healthcare, legal, etc.) |
| `implementation-feedback` | Problems encountered while implementing XAP |
| `dispute-resolution` | Ideas for deterministic dispute resolution rules |
| `security` | Security vulnerabilities (see SECURITY.md for responsible disclosure) |

### 4. Edge Case Submissions

Edge cases are especially valuable. Every edge case found before v1.0 prevents a breaking change later.

When submitting an edge case, include:

- **Category**: Negotiation, Settlement, Split, Identity, Time, Adapter, Security, or Verity
- **Severity**: S1 (funds at risk), S2 (incorrect behavior), S3 (unexpected but workable), S4 (inconvenient)
- **Description**: What happens, step by step
- **Expected behavior**: What should happen
- **Proposed resolution**: Your suggestion (optional but appreciated)

### What We Are Not Looking For Right Now

- Pull requests that change core protocol objects without a prior discussion
- Implementation code (implementations belong in separate repos)
- Marketing or copy edits

## Code of Conduct

All participants are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
