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
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol, runtime_checkable

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

SIGNER_CMD_ENV = "THREEPOWERS_SIGNER_CMD"
ORACLE_SIGNER_CMD_ENV = "THREEPOWERS_ORACLE_SIGNER_CMD"


def _raw_public(pk: Ed25519PublicKey) -> bytes:
    return pk.public_bytes(Encoding.Raw, PublicFormat.Raw)


def key_id_of(raw_public: bytes) -> str:
    """Stable short identifier for a public key: ``ed25519:<16 hex>``."""
    return "ed25519:" + hashlib.sha256(raw_public).hexdigest()[:16]


@runtime_checkable
class Signer(Protocol):
    """Anything that can sign ledger bytes: a software key or an external signer (HARDN-FR-006)."""

    @property
    def key_id(self) -> str: ...

    def sign(self, data: bytes) -> bytes: ...


class ExternalSignerError(ValueError):
    """A configured external signer failed — loudly, never falling back (HARDN-FR-006)."""


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
    # cryptography>=42 (a hard dependency) always provides private_bytes_raw().
    return SigningKey(seed=Ed25519PrivateKey.generate().private_bytes_raw())


def write_public(path: Path, vk: VerifyKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(vk.to_line() + "\n", encoding="utf-8")


def write_private(path: Path, sk: SigningKey) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sk.to_line() + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def load_public(path: Path) -> VerifyKey:
    return VerifyKey.from_line(path.read_text(encoding="utf-8"))


@dataclass
class CommandSigner:
    """Delegate signing to an external process boundary (HARDN-FR-006).

    The command receives the canonical bytes to sign on **stdin** and must print the
    base64 Ed25519 signature on **stdout**. The private-key material lives wherever the
    command keeps it — an agent, a hardware token, an enclave — and is never present in a
    file or environment variable readable by the engine process. Verification is unchanged:
    every signature is checked against the committed public key, here at signing time too,
    so a misconfigured signer fails immediately and never silently.
    """

    cmd: str
    public: VerifyKey

    @property
    def key_id(self) -> str:
        return self.public.key_id

    def sign(self, data: bytes) -> bytes:
        # argv-style, never a shell (a signer needing pipes/expansion wraps them in a script).
        argv = shlex.split(self.cmd)
        if not argv:
            raise ExternalSignerError("external signer command is empty (HARDN-FR-006)")
        try:
            res = subprocess.run(argv, input=data, capture_output=True, timeout=120)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExternalSignerError(
                f"external signer could not run ({self.cmd!r}): {exc} — refusing to fall "
                "back to a software key (HARDN-FR-006)"
            ) from exc
        if res.returncode != 0:
            err = res.stderr.decode(errors="replace").strip()
            raise ExternalSignerError(
                f"external signer exited {res.returncode}: {err or 'no diagnostics'} — "
                "refusing to fall back to a software key (HARDN-FR-006)"
            )
        try:
            sig = base64.b64decode(res.stdout.strip(), validate=True)
        except (ValueError, TypeError) as exc:
            raise ExternalSignerError(
                "external signer output is not base64 — expected the Ed25519 signature "
                "of stdin on stdout (HARDN-FR-006)"
            ) from exc
        if len(sig) != 64 or not self.public.verify(sig, data):
            raise ExternalSignerError(
                "external signer produced a signature that does not verify against the "
                f"committed public key {self.public.key_id} — misconfigured signer or "
                "wrong key (HARDN-FR-006)"
            )
        return sig


def _committed_pubkey_path(repo_root: Path, role: str) -> Path:
    name = "oracle.pub" if role == "oracle" else "ledger.pub"
    return repo_root / ".3powers" / "keys" / name


def _command_signer(cmd: str, pub_path: Path, env_name: str) -> CommandSigner:
    if not pub_path.exists():
        raise ExternalSignerError(
            f"${env_name} is set but no committed public key exists at {pub_path} — "
            "install the external signer's public key there first (HARDN-FR-006)"
        )
    return CommandSigner(cmd=cmd, public=load_public(pub_path))


def default_private_path(repo_root: Path) -> Path:
    base = Path(os.path.expanduser("~")) / ".config" / "3powers"
    return base / (repo_root.name + ".key")


def default_oracle_private_path(repo_root: Path) -> Path:
    """The distinct judiciary (oracle) signer's default path — also OUTSIDE the repo (3PWR-NFR-005)."""
    base = Path(os.path.expanduser("~")) / ".config" / "3powers"
    return base / (repo_root.name + ".oracle.key")


def _resolve(file_env: str, seed_env: str, default_path: Path) -> Optional[SigningKey]:
    """Custody resolution: env file → env seed → default path (outside the repo). None if none set."""
    env_file = os.environ.get(file_env)
    if env_file:
        return SigningKey.from_line(Path(env_file).read_text(encoding="utf-8"))
    env_seed = os.environ.get(seed_env)
    if env_seed:
        return SigningKey(seed=base64.b64decode(env_seed))
    if default_path.exists():
        return SigningKey.from_line(default_path.read_text(encoding="utf-8"))
    return None


def inside_working_tree(repo_root: Path, path: Path) -> bool:
    """True iff ``path`` resolves inside the repository working tree (HARDN-FR-002)."""
    try:
        path.resolve().relative_to(repo_root.resolve())
        return True
    except ValueError:
        return False


def _mode_too_open(path: Path) -> bool:
    """True iff the file grants any group/other permission bits (broader than owner-only)."""
    try:
        return bool(path.stat().st_mode & 0o077)
    except OSError:
        return False


def custody_findings(repo_root: Path) -> list[str]:
    """Deterministic key-custody preflight (HARDN-FR-002).

    Reports a ``key_custody`` finding when a resolved private-key file lives inside the
    repository working tree, or when its permissions are broader than owner-only. A
    compliant setup — no key configured, or an owner-only key outside the tree — emits
    nothing. Purely local: stat calls only, no key material is ever read.
    """
    findings: list[str] = []
    candidates: list[tuple[str, Path]] = []
    for env, default in (
        ("THREEPOWERS_SIGNING_KEY_FILE", default_private_path(repo_root)),
        ("THREEPOWERS_ORACLE_SIGNING_KEY_FILE", default_oracle_private_path(repo_root)),
    ):
        env_file = os.environ.get(env)
        if env_file:
            candidates.append((f"${env} → {env_file}", Path(env_file)))
        elif default.exists():
            candidates.append((str(default), default))
    for label, path in candidates:
        if inside_working_tree(repo_root, path):
            findings.append(
                f"key_custody: private key at {label} resolves INSIDE the working tree — "
                "an executive agent with repo access can read it; move it outside the "
                "repository (3PWR-NFR-005)"
            )
        if path.exists() and _mode_too_open(path):
            findings.append(
                f"key_custody: private key file {path} is readable by other users "
                f"(mode {oct(path.stat().st_mode & 0o777)}) — run `chmod 600 {path}`"
            )
    return findings


def resolve_signing_key(repo_root: Path, role: str = "ledger") -> SigningKey:
    """Load the private signing key from outside the repository (3PWR-NFR-005).

    ``role="oracle"`` prefers a distinct judiciary identity
    (``$THREEPOWERS_ORACLE_SIGNING_KEY_FILE`` / ``$THREEPOWERS_ORACLE_SIGNING_KEY`` /
    ``~/.config/3powers/<repo>.oracle.key``), **falling back to the primary signer** when unset — so
    a distinct oracle key is optional and fully backward-compatible (3PWR-FR-039)."""
    if role == "oracle":
        sk = _resolve(
            "THREEPOWERS_ORACLE_SIGNING_KEY_FILE",
            "THREEPOWERS_ORACLE_SIGNING_KEY",
            default_oracle_private_path(repo_root),
        )
        if sk is not None:
            return sk
        # fall through to the primary signer (a distinct oracle identity is optional)
    sk = _resolve(
        "THREEPOWERS_SIGNING_KEY_FILE",
        "THREEPOWERS_SIGNING_KEY",
        default_private_path(repo_root),
    )
    if sk is not None:
        return sk
    raise FileNotFoundError(
        "No signing key found. Run `3pwr keygen` or set $THREEPOWERS_SIGNING_KEY_FILE. "
        "The private key must live OUTSIDE the repository (3PWR-NFR-005)."
    )


def resolve_signer(repo_root: Path, role: str = "ledger") -> Signer:
    """Resolve the signer: an external signer where configured, else the software key.

    Where ``$THREEPOWERS_SIGNER_CMD`` (or ``$THREEPOWERS_ORACLE_SIGNER_CMD`` for the
    judiciary identity) is set, signing is delegated to that process boundary and the
    private seed is never readable by the engine (HARDN-FR-006). A configured-but-broken
    external signer raises — it never silently falls back to a software key. With no
    external configuration the existing software-key custody chain applies unchanged.
    """
    if role == "oracle":
        cmd = os.environ.get(ORACLE_SIGNER_CMD_ENV)
        if cmd:
            return _command_signer(
                cmd, _committed_pubkey_path(repo_root, "oracle"), ORACLE_SIGNER_CMD_ENV
            )
        sk = _resolve(
            "THREEPOWERS_ORACLE_SIGNING_KEY_FILE",
            "THREEPOWERS_ORACLE_SIGNING_KEY",
            default_oracle_private_path(repo_root),
        )
        if sk is not None:
            return sk
        # fall through to the primary signer (a distinct oracle identity is optional)
    cmd = os.environ.get(SIGNER_CMD_ENV)
    if cmd:
        return _command_signer(cmd, _committed_pubkey_path(repo_root, "ledger"), SIGNER_CMD_ENV)
    return resolve_signing_key(repo_root)
