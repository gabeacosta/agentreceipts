"""
sdk/tests/test_sdk.py — SDK acceptance tests

Covers: scrubber, wrap (Anthropic stub), tool(), verify(), run context, fails-open.
No real API keys required — uses local stubs.
"""

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import agentreceipts
from agentreceipts._scrub import scrub_payload
from agentreceipts._receipt import emit_observation

TMP_KEY = Path("/tmp/ar_sdk_test_key.pem")
TMP_OUT = Path("/tmp/ar_sdk_test_obs")


@pytest.fixture(autouse=True)
def configure_sdk(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    yield
    # reset to defaults
    agentreceipts.init()


# ---------------------------------------------------------------------------
# Scrubber
# ---------------------------------------------------------------------------

def test_scrubber_bearer():
    fake = "sk_" + "test_abc1234567890123456789012"  # not a real key
    clean = scrub_payload({"auth": f"Bearer {fake}"})
    assert "sk_test_abc" not in clean["auth"]
    assert "[REDACTED:" in clean["auth"]


def test_scrubber_no_mutation():
    original = {"key": "ghp_" + "X" * 36}  # not a real key
    copy_val = original["key"]
    scrub_payload(original)
    assert original["key"] == copy_val


# ---------------------------------------------------------------------------
# tool() — one-off receipt
# ---------------------------------------------------------------------------

def test_tool_emits_receipt(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    r = agentreceipts.tool("obs.test.unit.v1", {"status": "ok", "count": 3})
    assert r["backfilled"] is False
    out_file = tmp_path / "obs" / f"{r['receipt_id']}.json"
    assert out_file.exists()


def test_tool_scrubs_payload(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    fake_key = "sk_" + "live_abcdefghijklmnopqrstu"  # not a real key
    r = agentreceipts.tool(
        "obs.test.unit.v1",
        {"root_cause": f"Error: Bearer {fake_key} rejected"},
    )
    out_file = tmp_path / "obs" / f"{r['receipt_id']}.json"
    text = out_file.read_text()
    assert "sk_live_abcdefghijklmnopqrstu" not in text  # gitleaks:allow
    assert "[REDACTED:" in text


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------

def test_verify_valid_receipt(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    r = agentreceipts.tool("obs.test.verify.v1", {"x": 1})
    result = agentreceipts.verify(r["receipt_id"])
    assert result["hash_valid"] is True
    assert result["sig_valid"] is True
    assert result["backfilled"] is False


def test_verify_missing_receipt(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    with pytest.raises(FileNotFoundError):
        agentreceipts.verify("ar_obs_doesnotexist")


def test_verify_tampered_receipt(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    r = agentreceipts.tool("obs.test.tamper.v1", {"data": "original"})
    out_file = tmp_path / "obs" / f"{r['receipt_id']}.json"
    body = json.loads(out_file.read_text())
    body["payload"]["data"] = "tampered"
    out_file.write_text(json.dumps(body))
    result = agentreceipts.verify(r["receipt_id"])
    assert result["hash_valid"] is False


# ---------------------------------------------------------------------------
# run() context manager
# ---------------------------------------------------------------------------

def test_run_context_sets_run_id(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    with agentreceipts.run("test-run-001") as rid:
        assert rid == "test-run-001"
        r = agentreceipts.tool("obs.test.run_ctx.v1", {"step": "a"})
        assert r["payload"]["run_id"] == "test-run-001"


def test_run_context_clears_after_exit(tmp_path):
    from agentreceipts._context import get_run
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    with agentreceipts.run("test-run-002"):
        pass
    assert get_run() is None


def test_run_auto_generates_id(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    with agentreceipts.run() as rid:
        assert rid.startswith("ar_run_")


# ---------------------------------------------------------------------------
# wrap() — Anthropic stub
# ---------------------------------------------------------------------------

def _make_anthropic_stub():
    """Return a mock that looks like anthropic.Anthropic()."""
    client = MagicMock()
    client.__class__.__name__ = "Anthropic"
    client.__class__.__module__ = "anthropic"

    msg = MagicMock()
    msg.content = [MagicMock(text="Hello, world!")]
    msg.stop_reason = "end_turn"
    msg.usage = MagicMock(input_tokens=10, output_tokens=5)
    client.messages.create.return_value = msg

    return client


def test_wrap_anthropic_returns_response(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    stub = _make_anthropic_stub()
    wrapped = agentreceipts.wrap(stub)
    resp = wrapped.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hi"}],
    )
    assert resp.content[0].text == "Hello, world!"


def test_wrap_anthropic_emits_receipt(tmp_path):
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    stub = _make_anthropic_stub()
    wrapped = agentreceipts.wrap(stub)
    wrapped.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hi"}],
    )
    receipt_files = list((tmp_path / "obs").glob("*.json"))
    assert len(receipt_files) == 1
    body = json.loads(receipt_files[0].read_text())
    assert body["event_type"] == "obs.llm.call.v1"
    assert body["payload"]["provider"] == "anthropic"
    assert "prompt_anchor" in body["payload"]
    assert body["payload"]["prompt_anchor"].startswith("sha256:")


def test_wrap_fails_open(tmp_path):
    """If emit_observation raises, the host call result is still returned."""
    agentreceipts.init(key_path=tmp_path / "key.pem", out_dir=tmp_path / "obs")
    stub = _make_anthropic_stub()
    wrapped = agentreceipts.wrap(stub)

    with patch("agentreceipts._clients.emit_observation", side_effect=RuntimeError("disk full")):
        resp = wrapped.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hi"}],
        )
    assert resp.content[0].text == "Hello, world!"


def test_wrap_unknown_client_raises():
    class FakeClient:
        pass

    with pytest.raises(TypeError, match="Unsupported client type"):
        agentreceipts.wrap(FakeClient())
