# Security Policy

## Reporting a Vulnerability

XAP is a financial protocol. Security is not a feature. It is a requirement.

If you discover a security vulnerability in the XAP specification, schemas, or reference implementations, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Email: **security@agentralabs.tech**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)

We will acknowledge receipt within 48 hours and provide an initial assessment within 7 days.

## Scope

This policy covers:
- The XAP protocol specification
- JSON schemas in this repository
- Cryptographic design (Ed25519 signing, hash chains, Merkle proofs)
- The negotiation state machine
- The settlement flow and condition verification logic
- The Verity truth engine design

## Recognition

We recognize security researchers who report valid vulnerabilities. With your permission, we will credit you in the CHANGELOG and in any related security advisory.

## Supported Versions

| Version | Supported |
|---|---|
| v0.1 (current draft) | Yes |
