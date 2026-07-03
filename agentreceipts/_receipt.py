"""Core receipt issuance — emit_observation() adapted for SDK use."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._canon import canonical_json, sha256_str
from ._scrub import scrub_payload
from ._sign import load_or_create_key, sign_bytes

DEFAULT_KEY_PATH = Path("~/.agentreceipts/witness-key.pem")
DEFAULT_OUT_DIR = Path("~/.agentreceipts/observations")
DEFAULT_KEY_ID = "sdk-key-v1"


def emit_observation(
    event_type: str,
    payload: dict[str, Any],
    observed_at: str | None = None,
    key_path: Path = DEFAULT_KEY_PATH,
    key_id: str = DEFAULT_KEY_ID,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict:
    """
    Build, sign, and persist an agentreceipts.observation.v1 receipt.
    Payload is scrubbed before hashing (redact-before-sign).
    Raises on signing or I/O failure — never emits a bad receipt.
    Returns the signed receipt dict.
    """
    out_dir = Path(out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    receipt_id = "ar_obs_" + uuid.uuid4().hex[:16]
    ts = observed_at or datetime.now(timezone.utc).isoformat()

    private_key, pub_b64 = load_or_create_key(Path(key_path), key_id)

    clean_payload = scrub_payload(payload)  # redact-before-sign

    body: dict[str, Any] = {
        "schema_version": "agentreceipts.observation.v1",
        "receipt_id": receipt_id,
        "event_type": event_type,
        "observed_at": ts,
        "payload": clean_payload,
        "backfilled": False,
        "public_key_id": key_id,
        "public_key_b64": pub_b64,
    }

    body["receipt_hash"] = sha256_str(canonical_json(body))
    body["signature"] = sign_bytes(private_key, canonical_json(body))

    out_path = out_dir / f"{receipt_id}.json"
    out_path.write_text(json.dumps(body, indent=2, ensure_ascii=False))
    out_path.chmod(0o644)

    return body
