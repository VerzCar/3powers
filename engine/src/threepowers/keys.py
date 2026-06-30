"""Ed25519 signer / verifier identity for the trust spine.

The **signer identity is independent of the executive agents**: the private key is
never stored in the repository and never appears in the ledger (3PWR-FR-039,
3PWR-NFR-005). Only the *public* key is committed (``.3powers/keys/ledger.pub``) so
that ``verify`` is fully local and offline (3PWR-NFR-004).

Key custody (private key) is resolved, in order:
  1. ``$THREEPOWERS_SIGNING_KEY_FILE`` — path to a private-key file;
  2. ``$THREEPOWERS_SIGNING_KEY`` — base64 raw 32-byte seed (for CI/secret stores);
  3. the default user path ``~/.config/3powers/<repo>.key`` — *outside* the repo.

File formats (deliberately simple and self-describing; minisign interop is a
documented follow-up, not required for local verification):
  * public  : one line ``ed25519 <base64-raw-32> <key_id>``
  * private : one line ``ed25519-priv <base64-raw-seed-32>``
"""

from __future__ import annotations

import base64
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)

PUBLIC_PREFIX = "ed25519"
PRIVATE_PREFIX = "ed25519-priv"


def _raw_public(pk: Ed25519PublicKey) -> bytes:
    return pk.public_bytes(Encoding.Raw, PublicFormat.Raw)


def key_id_of(raw_public: bytes) -> str:
    """Stable short identifier for a public key: ``ed25519:<16 hex>``."""
    return "ed25519:" + hashlib.sha256(raw_public).hexdigest()[:16]


@dataclass
class VerifyKey:
    raw: bytes

    @property
    def key_id(self) -> str:
        return key_id_of(self.raw)

    def verify(self, signature: bytes, data: bytes) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(self.raw).verify(signature, data)
            return True
        except InvalidSignature:
            return False

    def to_line(self) -> str:
        return f"{PUBLIC_PREFIX} {base64.b64encode(self.raw).decode()} {self.key_id}"

    @classmethod
    def from_line(cls, line: str) -> "VerifyKey":
        parts = line.strip().split()
        if len(parts) < 2 or parts[0] != PUBLIC_PREFIX:
            raise ValueError("malformed public key line")
        return cls(raw=base64.b64decode(parts[1]))


@dataclass
class SigningKey:
    seed: bytes  # raw 32-byte Ed25519 private seed

    @property
    def _key(self) -> Ed25519PrivateKey:
        return Ed25519PrivateKey.from_private_bytes(self.seed)

    @property
    def verify_key(self) -> VerifyKey:
        return VerifyKey(raw=_raw_public(self._key.public_key()))

    @property
    def key_id(self) -> str:
        return self.verify_key.key_id

    def sign(self, data: bytes) -> bytes:
        return self._key.sign(data)

    def to_line(self) -> str:
        return f"{PRIVATE_PREFIX} {base64.b64encode(self.seed).decode()}"

    @classmethod
    def from_line(cls, line: str) -> "SigningKey":
        parts = line.strip().split()
        if len(parts) != 2 or parts[0] != PRIVATE_PREFIX:
            raise ValueError("malformed private key line")
        return cls(seed=base64.b64decode(parts[1]))


def generate() -> SigningKey:
    pk = Ed25519PrivateKey.generate()
    seed = pk.private_bytes_raw() if hasattr(pk, "private_bytes_raw") else _seed_compat(pk)
    return SigningKey(seed=seed)


def _seed_compat(pk: Ed25519PrivateKey) -> bytes:  # pragma: no cover - old cryptography
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    return pk.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def write_public(path: Path, vk: VerifyKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(vk.to_line() + "\n", encoding="utf-8")


def write_private(path: Path, sk: SigningKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sk.to_line() + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def load_public(path: Path) -> VerifyKey:
    return VerifyKey.from_line(path.read_text(encoding="utf-8"))


def default_private_path(repo_root: Path) -> Path:
    base = Path(os.path.expanduser("~")) / ".config" / "3powers"
    return base / (repo_root.name + ".key")


def resolve_signing_key(repo_root: Path) -> SigningKey:
    """Load the private signing key from outside the repository (3PWR-NFR-005)."""
    env_file = os.environ.get("THREEPOWERS_SIGNING_KEY_FILE")
    if env_file:
        return SigningKey.from_line(Path(env_file).read_text(encoding="utf-8"))
    env_seed = os.environ.get("THREEPOWERS_SIGNING_KEY")
    if env_seed:
        return SigningKey(seed=base64.b64decode(env_seed))
    default = default_private_path(repo_root)
    if default.exists():
        return SigningKey.from_line(default.read_text(encoding="utf-8"))
    raise FileNotFoundError(
        "No signing key found. Run `3pwr keygen` or set $THREEPOWERS_SIGNING_KEY_FILE. "
        "The private key must live OUTSIDE the repository (3PWR-NFR-005)."
    )
