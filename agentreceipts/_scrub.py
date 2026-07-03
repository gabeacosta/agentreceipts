"""Redact-before-sign scrubber — same patterns as actions/observe.py (L15)."""

import copy
import re
from typing import Any

_SECRET_PATTERNS: list[tuple] = [
    (re.compile(r'Bearer\s+\S+'), 'Bearer [REDACTED:token]'),
    (re.compile(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+'), '[REDACTED:jwt]'),
    (re.compile(r'pat[A-Za-z0-9]{14,}'), '[REDACTED:token]'),
    (re.compile(r'sk_[a-zA-Z0-9_]{20,}'), '[REDACTED:token]'),
    (re.compile(r'xoxb-[0-9A-Za-z-]+'), '[REDACTED:token]'),
    (re.compile(r'ghp_[A-Za-z0-9]{36}'), '[REDACTED:token]'),
    (re.compile(r'\b(?:ak|pk)_[a-zA-Z0-9_]{20,}'), '[REDACTED:token]'),
    (re.compile(r'(postgres|mysql|mongodb|redis)://[^@\s]+@'), None),
    (re.compile(r'-----BEGIN [A-Z ]+ KEY-----[\s\S]*?-----END [A-Z ]+ KEY-----'), '[REDACTED:private_key]'),
]


def _scrub_str(s: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        if replacement is None:
            s = pattern.sub(lambda m: m.group(1) + '://[REDACTED:connection_string]@', s)
        else:
            s = pattern.sub(replacement, s)
    return s


def _scrub_inplace(obj: Any) -> None:
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if isinstance(obj[k], str):
                obj[k] = _scrub_str(obj[k])
            else:
                _scrub_inplace(obj[k])
    elif isinstance(obj, list):
        for i in range(len(obj)):
            if isinstance(obj[i], str):
                obj[i] = _scrub_str(obj[i])
            else:
                _scrub_inplace(obj[i])


def scrub_payload(payload: dict) -> dict:
    """Return a deep copy of payload with secret patterns replaced. Raises on error."""
    clean = copy.deepcopy(payload)
    _scrub_inplace(clean)
    return clean
