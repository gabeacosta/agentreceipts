"""receipts verify <receipt_id_or_path> CLI entry point."""

import argparse
import json
import sys
from pathlib import Path

from ._canon import canonical_json, sha256_str
from ._sign import verify_signature


def _find_receipt(target: str, out_dir: Path) -> Path:
    p = Path(target)
    if p.exists():
        return p
    candidate = out_dir / f"{target}.json"
    if candidate.exists():
        return candidate
    raise FileNotFoundError(f"Receipt not found: {target}")


def cmd_verify(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir).expanduser()
    try:
        receipt_path = _find_receipt(args.receipt, out_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    body = json.loads(receipt_path.read_text())

    stored_hash = body.get("receipt_hash", "")
    stored_sig = body.get("signature", "")
    pub_b64 = body.get("public_key_b64", "")

    body_for_hash = {k: v for k, v in body.items() if k not in ("receipt_hash", "signature")}
    computed_hash = sha256_str(canonical_json(body_for_hash))
    hash_valid = computed_hash == stored_hash

    body_for_sig = {k: v for k, v in body.items() if k != "signature"}
    sig_valid = verify_signature(pub_b64, stored_sig, canonical_json(body_for_sig))

    print(f"receipt_id:   {body.get('receipt_id')}")
    print(f"event_type:   {body.get('event_type')}")
    print(f"observed_at:  {body.get('observed_at')}")
    print(f"backfilled:   {body.get('backfilled')}")
    print(f"hash_valid:   {hash_valid}")
    print(f"sig_valid:    {sig_valid}")

    if hash_valid and sig_valid and body.get("backfilled") is False:
        print("\nVERIFIED")
        return 0
    else:
        print("\nFAILED", file=sys.stderr)
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="receipts", description="Agent Receipts — verify tamper-proof AI action receipts")
    sub = parser.add_subparsers(dest="command")

    verify_p = sub.add_parser("verify", help="Verify a signed receipt")
    verify_p.add_argument("receipt", help="receipt_id or path to .json file")
    verify_p.add_argument(
        "--out-dir",
        default="~/.agentreceipts/observations",
        help="Directory containing receipts (default: ~/.agentreceipts/observations)",
    )

    args = parser.parse_args()
    if args.command == "verify":
        sys.exit(cmd_verify(args))
    else:
        parser.print_help()
        sys.exit(1)
