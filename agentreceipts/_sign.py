"""Vendored Ed25519 signing — no dependency on trace-zero core."""

import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
    load_pem_private_key,
)


def load_or_create_key(key_path: Path, key_id: str) -> tuple[Ed25519PrivateKey, str]:
    key_path = Path(key_path).expanduser()
    if key_path.exists():
        private_key = load_pem_private_key(key_path.read_bytes(), password=None)
    else:
        private_key = Ed25519PrivateKey.generate()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(
            private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )
        key_path.chmod(0o600)
    pub_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, base64.b64encode(pub_bytes).decode()


def sign_bytes(private_key: Ed25519PrivateKey, data: bytes) -> str:
    sig = private_key.sign(data)
    return "ed25519:" + base64.b64encode(sig).decode()


def verify_signature(pub_b64: str, signature: str, data: bytes) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    pub_bytes = base64.b64decode(pub_b64)
    pub_key = Ed25519PublicKey.from_public_bytes(pub_bytes)
    sig_b64 = signature.removeprefix("ed25519:")
    try:
        pub_key.verify(base64.b64decode(sig_b64), data)
        return True
    except InvalidSignature:
        return False
