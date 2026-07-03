# Agent Receipts — Onboarding

Three steps. No infrastructure required. Receipts stay in your environment.

---

## Step 1 — Install

```bash
pip install agentreceipts
```

Requires Python 3.11+. No cloud dependency. Key generated locally on first use.

---

## Step 2 — Wrap your agent

```python
import anthropic
import agentreceipts

# One-time init (optional — defaults write to ~/.agentreceipts/)
agentreceipts.init(out_dir="./observations")

# Two-line wrap — drop-in replacement for your existing client
client = agentreceipts.wrap(anthropic.Anthropic())

# Your existing code unchanged
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Summarize the following contract..."}],
)
```

Every API call produces a signed receipt in `./observations/`. Prompts and outputs are
stored as SHA-256 anchors — never raw content. No secrets reach the receipt.

---

## Step 3 — Verify

```bash
receipts verify ar_obs_<receipt_id>
```

Expected output:

```
receipt_id:   ar_obs_a1b2c3d4e5f6g7h8
event_type:   obs.llm.call.v1
observed_at:  2026-06-15T14:23:01.123456+00:00
backfilled:   False
hash_valid:   True
sig_valid:    True

VERIFIED
```

`hash_valid=True` + `sig_valid=True` + `backfilled=False` = tamper-evident proof the call happened.

---

## Advanced usage

**Track a multi-step run:**
```python
with agentreceipts.run("intake-run-001") as run_id:
    r1 = client.messages.create(...)   # receipt tagged with run_id
    r2 = client.messages.create(...)   # same run_id
```

**Observe a tool call or action:**
```python
agentreceipts.tool("obs.tool.database_query.v1", {
    "query_type": "SELECT",
    "table": "leads",
    "row_count": 47,
    "duration_ms": 12,
})
```

**OpenAI:**
```python
import openai
client = agentreceipts.wrap(openai.OpenAI())
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "..."}],
)
```

---

## Privacy guarantees

- Prompts and outputs are never stored — only their SHA-256 hashes.
- All payload fields are scrubbed for secrets before signing (bearer tokens, JWTs, API keys,
  connection strings, PEM blocks). Matches are replaced with `[REDACTED:<type>]`.
- Receipts are local-only. Nothing leaves your environment.
- Ed25519 signatures are generated with a key you own (`~/.agentreceipts/witness-key.pem`).
- Receipts are immutable. Once written, they cannot be altered without breaking verification.

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
    "usage": {"input_tokens": 312, "output_tokens": 88}
  },
  "backfilled": false,
  "public_key_id": "sdk-key-v1",
  "public_key_b64": "...",
  "receipt_hash": "sha256:...",
  "signature": "ed25519:..."
}
```
