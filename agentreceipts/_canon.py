"""Vendored canonical JSON + sha256 — no dependency on trace-zero core."""

import hashlib
import json
from typing import Any


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def sha256_str(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()
