# agentreceipts

Two-line drop-in for any Anthropic or OpenAI client. Every API call, tool use, and agent action produces an Ed25519-signed, tamper-evident receipt. Nothing leaves your machine.

```bash
pip install agentreceipts
```

```python
import agentreceipts
client = agentreceipts.wrap(anthropic.Anthropic())
```

<!-- TODO(gabe): repoint to live successor -->

---

## Quickstart

```python
import anthropic
import agentreceipts

# Optional: configure where receipts are written (default: ~/.agentreceipts/)
agentreceipts.init(out_dir="./observations")

# Drop-in replacement for your existing client
client = agentreceipts.wrap(anthropic.Anthropic())

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Summarize this contract..."}],
)
```

Every call writes a signed receipt to `./observations/`. OpenAI works the same way.

---

## Verify a receipt

```bash
receipts verify ar_obs_a1b2c3d4e5f6g7h8
```

```
receipt_id:   ar_obs_a1b2c3d4e5f6g7h8
event_type:   obs.llm.call.v1
observed_at:  2026-06-15T14:23:01.123456+00:00
backfilled:   False
hash_valid:   True
sig_valid:    True

VERIFIED
```

`hash_valid: True` + `sig_valid: True` + `backfilled: False` — cryptographic proof the call happened, independently verifiable offline.

---

## Track a multi-step run

```python
with agentreceipts.run("intake-run-001") as run_id:
    r1 = client.messages.create(...)   # receipt tagged with run_id
    r2 = client.messages.create(...)   # same run_id
```

---

## Observe a tool call or action

```python
agentreceipts.tool("obs.tool.database_query.v1", {
    "query_type": "SELECT",
    "table": "leads",
    "row_count": 47,
    "duration_ms": 12,
})
```

---

## OpenAI

```python
import openai
import agentreceipts

client = agentreceipts.wrap(openai.OpenAI())
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
)
```

---

## Privacy guarantees

- Prompts and outputs are **never stored** — only their SHA-256 hashes
- All payload fields are scrubbed for secrets before signing (bearer tokens, JWTs, API keys, connection strings, PEM blocks)
- Receipts are **local-only** — nothing reaches any server
- You own the signing key (`~/.agentreceipts/witness-key.pem`)
- Receipts are immutable — altering one breaks verification

---

## Receipt format

```json
{
  "schema_version": "agentreceipts.observation.v1",
  "receipt_id": "ar_obs_a1b2c3d4e5f6g7h8",
  "event_type": "obs.llm.call.v1",
  "observed_at": "2026-06-15T14:23:01.123456+00:00",
  "payload": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "prompt_anchor": "sha256:4a7b...",
    "output_anchor": "sha256:9f2c...",
    "stop_reason": "end_turn",
    "usage": { "input_tokens": 312, "output_tokens": 88 }
  },
  "backfilled": false,
  "public_key_id": "sdk-key-v1",
  "public_key_b64": "...",
  "receipt_hash": "sha256:...",
  "signature": "ed25519:..."
}
```

