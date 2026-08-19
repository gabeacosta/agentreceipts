# agentreceipts

Local Ed25519-signed **observation receipts** for LLM calls, tool calls, and agent actions.

This project records a canonical, secret-scrubbed observation locally, hashes it, and signs it with a key controlled by the operator. A later verifier can detect whether that signed record was altered after it was produced.

> **Scope boundary:** a locally signed receipt is evidence about what the local observer recorded. It is **not** provider attestation, authorization to perform an action, proof that an action was correct, or proof that an external side effect actually occurred.

That distinction is intentional. In a governed agent system, receipts are an **evidence input**; policy, authority, sink effects, and verifier acceptance are separate concerns.

---

## Quickstart

```bash
git clone https://github.com/gabeacosta/agentreceipts.git
cd agentreceipts
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[all]'
```

```python
import anthropic
import agentreceipts

agentreceipts.init(out_dir="./observations")
client = agentreceipts.wrap(anthropic.Anthropic())

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Summarize this contract."}],
)
```

The wrapper records a local signed observation without storing raw prompt/output text in the receipt payload.

---

## Verify a receipt

```bash
receipts verify <receipt-id>
```

Verification checks the receipt's canonical hash and Ed25519 signature against the public key embedded/referenced by the local observation format. If either check fails, the record has not preserved its signed integrity.

What verification **does establish**:

- the receipt body matches its recorded hash;
- the signature matches the corresponding signing key;
- fields covered by the signature have not been silently edited since signing.

What verification **does not establish**:

- that Anthropic/OpenAI or another provider attested to the event;
- that the underlying tool or external system actually completed the claimed side effect;
- that the action was authorized by policy;
- that the result was correct, safe, or accepted by an independent verifier.

---

## Track a multi-step run

```python
with agentreceipts.run("intake-run-001") as run_id:
    r1 = client.messages.create(...)
    r2 = client.messages.create(...)
```

Receipts created inside the context carry the same run identifier so observations can be grouped without turning the receipt layer into a workflow runtime.

---

## Record a tool observation

```python
agentreceipts.tool("obs.tool.database_query.v1", {
    "query_type": "SELECT",
    "table": "leads",
    "row_count": 47,
    "duration_ms": 12,
})
```

Again, this records what the observer was told about the tool event. For consequential effects, pair the observation with an authority boundary and independent sink/verifier evidence.

---

## Privacy properties

The public implementation is designed so that:

- prompt/output content is represented by hashes rather than stored verbatim in the receipt payload;
- common secret-shaped fields are scrubbed before signing;
- receipts are written locally by default;
- the operator owns the signing key;
- modifying signed fields invalidates hash/signature verification.

These are implementation properties, not a claim that the receipt layer alone provides end-to-end system security.

---

## Where this fits

```text
model / tool observation
        ↓
 local signed receipt       ← this repo
        ↓
 authority / policy         ← separate boundary
        ↓
 external effect
        ↓
 independent verification   ← separate boundary
```

For the larger execution-governance and runtime-evaluation story, see:

- [governed-mcp-spine](https://github.com/gabeacosta/governed-mcp-spine)
- [Public Runtime Wind Tunnel](https://github.com/gabeacosta/ai-portfolio/tree/main/specimens/agent-runtime-wind-tunnel)
- [Forward Deployed Engineering portfolio](https://github.com/gabeacosta/ai-portfolio)

## License

MIT
