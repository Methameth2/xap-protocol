"""Ed25519 helpers and canonical JSON utilities for XAP."""

from __future__ import annotations

import base64
import json
from hashlib import sha256
from typing import Any, Iterable

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


def canonical_json_bytes(payload: Any, exclude_fields: Iterable[str] | None = None) -> bytes:
    if exclude_fields and isinstance(payload, dict):
        payload = {k: v for k, v in payload.items() if k not in set(exclude_fields)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_json_hash(payload: Any, exclude_fields: Iterable[str] | None = None) -> str:
    return sha256(canonical_json_bytes(payload, exclude_fields=exclude_fields)).hexdigest()


def generate_keypair() -> tuple[str, str]:
    """Returns (private_key_b64url, public_key_b64url)."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64url_encode(private_bytes), _b64url_encode(public_bytes)


def sign_payload(payload: Any, private_key_b64url: str, exclude_fields: Iterable[str] | None = None) -> str:
    private_key = Ed25519PrivateKey.from_private_bytes(_b64url_decode(private_key_b64url))
    signature = private_key.sign(canonical_json_bytes(payload, exclude_fields=exclude_fields))
    return _b64url_encode(signature)


def verify_payload(
    payload: Any,
    signature_b64url: str,
    public_key_b64url: str,
    exclude_fields: Iterable[str] | None = None,
) -> bool:
    try:
        public_key = Ed25519PublicKey.from_public_bytes(_b64url_decode(public_key_b64url))
        public_key.verify(
            _b64url_decode(signature_b64url),
            canonical_json_bytes(payload, exclude_fields=exclude_fields),
        )
        return True
    except Exception:
        return False
