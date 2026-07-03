"""
agentreceipts — Tamper-proof signed receipts for every AI agent action.

Public API:

    init(key_path, out_dir, key_id)  → configure once per process
    run(run_id, metadata)            → context manager; sets active run context
    wrap(client)                     → wrap Anthropic/OpenAI client; observe-fails-open
    tool(event_type, payload)        → emit a one-off receipt (tool call, action, etc.)
    verify(receipt_id_or_path)       → returns dict with hash_valid, sig_valid, backfilled

Constraints:
    - redact-before-sign enforced on all payloads
    - anchor-not-content: prompt/output stored as sha256 hashes only
    - observe-fails-open: capture failures never break host calls
    - immutable: receipts are never mutated after signing
"""

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from ._receipt import emit_observation, DEFAULT_KEY_PATH, DEFAULT_OUT_DIR, DEFAULT_KEY_ID
from ._context import set_run, clear_run, get_run
from ._clients import wrap_client
from ._canon import canonical_json
from ._sign import verify_signature

import json
import uuid

_config: dict[str, Any] = {
    "key_path": DEFAULT_KEY_PATH,
    "out_dir": DEFAULT_OUT_DIR,
    "key_id": DEFAULT_KEY_ID,
}


def init(
    key_path: str | Path = DEFAULT_KEY_PATH,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    key_id: str = DEFAULT_KEY_ID,
) -> None:
    """Configure SDK-wide key path and output directory. Call once at startup."""
    _config["key_path"] = Path(key_path)
    _config["out_dir"] = Path(out_dir)
    _config["key_id"] = key_id


@contextmanager
def run(run_id: str | None = None, metadata: dict[str, Any] | None = None) -> Generator[str, None, None]:
    """
    Context manager. Sets active run ID so all receipts within the block share it.

        with agentreceipts.run("my-agent-run-001") as rid:
            client.messages.create(...)   # receipt tagged with rid
    """
    rid = run_id or ("ar_run_" + uuid.uuid4().hex[:12])
    set_run(rid, metadata or {})
    try:
        yield rid
    finally:
        clear_run()


def wrap(client: Any) -> Any:
    """
    Wrap an Anthropic or OpenAI client. Returns a drop-in replacement that emits
    receipts on every API call. Observe-fails-open: host call never broken.

        client = agentreceipts.wrap(anthropic.Anthropic())
        resp = client.messages.create(model=..., messages=...)
    """
    return wrap_client(client, dict(_config))


def tool(event_type: str, payload: dict[str, Any], observed_at: str | None = None) -> dict:
    """
    Emit a one-off observation receipt (for tool calls, actions, decisions, etc.).
    Payload is scrubbed before signing. Returns the signed receipt dict.

        agentreceipts.tool("obs.tool.web_search.v1", {"query": "...", "result_count": 5})
    """
    run_ctx = get_run()
    if run_ctx:
        payload = {"run_id": run_ctx["run_id"], **payload}
    return emit_observation(
        event_type=event_type,
        payload=payload,
        observed_at=observed_at,
        key_path=_config["key_path"],
        key_id=_config["key_id"],
        out_dir=_config["out_dir"],
    )


def verify(receipt: str | Path) -> dict:
    """
    Verify a receipt by receipt_id or file path. Returns:
        {"hash_valid": bool, "sig_valid": bool, "backfilled": bool, "receipt": dict}
    Raises FileNotFoundError if the receipt doesn't exist.
    """
    out_dir = Path(_config["out_dir"]).expanduser()
    p = Path(receipt)
    if not p.exists():
        candidate = out_dir / f"{receipt}.json"
        if candidate.exists():
            p = candidate
        else:
            raise FileNotFoundError(f"Receipt not found: {receipt}")

    body = json.loads(p.read_text())

    stored_hash = body.get("receipt_hash", "")
    stored_sig = body.get("signature", "")
    pub_b64 = body.get("public_key_b64", "")

    body_for_hash = {k: v for k, v in body.items() if k not in ("receipt_hash", "signature")}
    from ._canon import sha256_str
    computed_hash = sha256_str(canonical_json(body_for_hash))
    hash_valid = computed_hash == stored_hash

    body_for_sig = {k: v for k, v in body.items() if k != "signature"}
    sig_valid = verify_signature(pub_b64, stored_sig, canonical_json(body_for_sig))

    return {
        "hash_valid": hash_valid,
        "sig_valid": sig_valid,
        "backfilled": body.get("backfilled"),
        "receipt": body,
    }


__all__ = ["init", "run", "wrap", "tool", "verify"]
