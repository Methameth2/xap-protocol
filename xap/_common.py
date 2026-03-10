"""Common XAP helpers for IDs, timestamps and schema validation."""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .errors import XAPValidationError

SCHEMA_DIR = Path(__file__).parent / "schemas"


@lru_cache(maxsize=None)
def _load_schema(schema_name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / schema_name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_against_schema(schema_name: str, payload: dict[str, Any]) -> None:
    schema = _load_schema(schema_name)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.absolute_path))
    if errors:
        first = errors[0]
        path = ".".join(str(part) for part in first.absolute_path) or "<root>"
        raise XAPValidationError(f"Schema validation failed for {schema_name} at {path}: {first.message}")


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def parse_utc(ts: str) -> datetime:
    if ts.endswith("Z"):
        return datetime.fromisoformat(ts[:-1])
    return datetime.fromisoformat(ts)


def generate_prefixed_id(prefix: str) -> str:
    while True:
        token = secrets.token_urlsafe(24)
        cleaned = "".join(ch for ch in token if ch.isalnum())
        if len(cleaned) >= 32:
            return f"{prefix}{cleaned[:32]}"


def deep_copy(data: Any) -> Any:
    return json.loads(json.dumps(data))
