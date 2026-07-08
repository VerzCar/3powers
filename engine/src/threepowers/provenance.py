"""Build provenance + SBOM + deploy-gate verification.

A signed, verifiable record binding an artifact (by hash) to its source commit, repo,
producing run, and dependency list (SBOM). It is signed with the **same independent
Ed25519 identity as the verdict ledger** — so provenance is produced and
verified with no hosted CI/CD pipeline, fully offline. The deploy gate
refuses any artifact whose provenance is missing or fails verification.
"""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import SCHEMA_VERSION
from .adapters import run_cmd
from .canonical import canonical_bytes
from .keys import Signer, VerifyKey

_DERIVED = ("signer_key_id", "signature")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sbom(target: Path) -> dict:
    """Minimal SBOM from lockfiles; richer via syft when it is installed."""
    if shutil.which("syft"):
        res = run_cmd(f"syft {target} -o cyclonedx-json --quiet", cwd=target)
        if res.ok and res.stdout.strip():
            try:
                doc = json.loads(res.stdout)
                comps = [
                    {"name": c.get("name", "?"), "version": c.get("version", "")}
                    for c in doc.get("components", [])
                ]
                return {"format": "cyclonedx (syft)", "components": comps}
            except ValueError:
                pass

    components: list[dict] = []
    lock = target / "package-lock.json"
    if lock.exists():
        try:
            for name, meta in (json.loads(lock.read_text()).get("packages") or {}).items():
                if name and isinstance(meta, dict) and meta.get("version"):
                    components.append(
                        {"name": name.split("node_modules/")[-1], "version": meta["version"]}
                    )
        except (ValueError, OSError):
            pass
    ulock = target / "uv.lock"
    if ulock.exists():
        try:
            import tomllib

            for p in tomllib.loads(ulock.read_text()).get("package", []):
                if p.get("name") and p.get("version"):
                    components.append({"name": p["name"], "version": p["version"]})
        except (ValueError, OSError):
            pass
    return {"format": "minimal", "components": components}


def build_record(repo_root: Path, target: Path, artifact: Path) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact": {"path": artifact.name, "sha256": sha256_file(artifact)},
        "source_commit": _git(repo_root, ["rev-parse", "HEAD"]).strip(),
        "repository": _repo_name(repo_root),
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sbom": sbom(target),
    }


def sign_record(record: dict, signer: Signer) -> dict:
    out = dict(record)
    out["signer_key_id"] = signer.key_id
    out["signature"] = base64.b64encode(signer.sign(canonical_bytes(record))).decode()
    return out


def verify_record(record: dict, vk: VerifyKey) -> bool:
    core = {k: v for k, v in record.items() if k not in _DERIVED}
    try:
        return vk.verify(base64.b64decode(record["signature"]), canonical_bytes(core))
    except (KeyError, ValueError):
        return False


def _git(repo_root: Path, args: list[str]) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return ""


def _repo_name(repo_root: Path) -> str:
    origin = _git(repo_root, ["config", "--get", "remote.origin.url"]).strip()
    return origin or repo_root.name
