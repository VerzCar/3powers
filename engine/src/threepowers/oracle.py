"""Structural oracle independence — Phase A/B, anchored in the signed ledger.

The oracle is the answer key the coder never authored. This module makes
that independence **structural and traceable** rather than merely procedural:

* ``seal`` extracts a spec-only bundle — requirement IDs and their acceptance-criterion text,
  with **no** implementation, plan, tasks, or contracts — and records its content hash in the
  ledger. The judiciary authors the oracle *from this bundle*.
* ``record`` captures the authoring event: the bundle hash authored against, the model family
  that actually authored, the oracle test files and their content hashes, and (via the ledger)
  the signer identity. It refuses when the oracle resolves to the coder's model family
  (judged on the *actual* model — not just the declared config).
* ``dispatch`` authors the oracle *headlessly* under a non-coder agent backend (dispatched
  natively by the engine) inside a **sanitized git worktree** from which the implementation, plan,
  tasks, and contracts are physically **absent**. It attests the isolation
  with a worktree manifest hash recorded in the ledger, and records the actual agent + model.
* ``independence`` proves, from the ledger's monotonic signed ``seq`` (never from spoofable git
  timestamps), that Phase A preceded Phase B, the oracle was bound to the active
  seal, the families diverge, and every acceptance criterion has
  an oracle test. When a dispatch attestation is present (or required by the tier
  policy) it also proves **physical read-path isolation**. These bind at ``advance``
  at the High-risk tier.

The worktree makes read-path isolation *physical*, not merely policy: the dispatched agent's cwd
does not contain the implementation. The advisory peek/touch signals remain **advisory,
non-blocking** (that heuristic is input-dependent and must not perturb the deterministic verdict);
network egress from the dispatched agent is out of scope here (read-path isolation only).
"""

from __future__ import annotations

import fnmatch
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import canonical
from .conformance import _TEST_GLOBS, _iter_req_ids, extract_spec, referenced_ids

ORACLE_ENTRY = "oracle"


# --------------------------------------------------------------------------- sealed bundle
def extract_criteria(spec_path: Path) -> tuple[str, dict[str, str]]:
    """Return ``(spec_id, {requirement_id: acceptance-criterion text})`` from a spec.

    The criterion text is the spec line that declares the requirement — the only content the
    judiciary is meant to author against. Reuses the conformance spec parser so
    the same requirement-ID grammar governs everywhere.
    """
    spec_id, ids = extract_spec(spec_path)
    criteria: dict[str, str] = {}
    for line in spec_path.read_text(encoding="utf-8").splitlines():
        line_ids = {f"{s}-{k}-{n}" for s, k, n in _iter_req_ids(line)} & ids
        for rid in line_ids:
            criteria.setdefault(rid, line.strip())
    return spec_id, criteria


def bundle_hash(spec_id: str, source: str, criteria: dict[str, str]) -> str:
    """Content hash of the sealed bundle — deliberately excludes any timestamp so that
    re-sealing an unchanged spec yields an identical hash (deterministic binding)."""
    return canonical.hash_payload(
        {
            "spec_id": spec_id,
            "source": source,
            "criteria": [{"id": rid, "text": criteria[rid]} for rid in sorted(criteria)],
        }
    )


def build_bundle(spec_id: str, source: str, criteria: dict[str, str], sealed_at: str) -> dict:
    """The on-disk sealed bundle (``.3powers/oracle/<spec-id>/sealed.json``). ``sealed_at`` is
    informational and is *not* part of ``bundle_hash``."""
    return {
        "spec_id": spec_id,
        "source": source,
        "requirement_ids": sorted(criteria),
        "criteria": [{"id": rid, "text": criteria[rid]} for rid in sorted(criteria)],
        "bundle_hash": bundle_hash(spec_id, source, criteria),
        "sealed_at": sealed_at,
    }


def seal_payload(spec_id: str, source: str, criteria: dict[str, str]) -> dict:
    return {
        "kind": "seal",
        "bundle_hash": bundle_hash(spec_id, source, criteria),
        "source": source,
        "requirement_ids": sorted(criteria),
    }


# --------------------------------------------------------------------------- authoring record
def family_of(model: str) -> str:
    """The model *family* — the part before the first ``/`` in ``<family>/<model>``."""
    return model.split("/", 1)[0].strip() if model else ""


def coder_family(roles: dict) -> str:
    return ((roles.get("roles") or {}).get("coder") or {}).get("model_family", "") or ""


def diverse(coder: str, oracle: str, level: str) -> bool:
    """True iff ``coder`` and ``oracle`` are diverse enough at ``level``.

    ``level='family'`` (the recommended posture): different model *families* (the part before ``/``).
    ``level='model'``: a different *model* qualifies (e.g. ``anthropic/opus`` vs ``anthropic/sonnet``),
    but only when both sides name a full ``<family>/<model>``; otherwise it falls back to comparing
    families. Empty inputs are never diverse — independence cannot be proven."""
    c, o = (coder or "").strip(), (oracle or "").strip()
    if not c or not o:
        return False
    if level == "model" and "/" in c and "/" in o:
        return c != o
    return family_of(c) != family_of(o)


def record_payload(
    bound_bundle_hash: str,
    model: str,
    test_paths: list[str],
    test_hashes: dict[str, str],
    advisory: list[str],
    diversity_deviation: Optional[int] = None,
) -> dict:
    payload: dict = {
        "kind": "record",
        "bundle_hash": bound_bundle_hash,
        "model": model,
        "model_family": family_of(model),
        "test_paths": sorted(test_paths),
        "test_hashes": {p: test_hashes[p] for p in sorted(test_hashes)},
        "advisory_findings": advisory,
    }
    if diversity_deviation is not None:  # same-family authoring sanctioned by a signed deviation
        payload["diversity_deviation"] = diversity_deviation
    return payload


# --------------------------------------------------------------------------- ledger-derived queries
def _oracle_entries(entries: list[dict], spec_id: str, kind: str) -> list[dict]:
    return [
        e
        for e in entries
        if e.get("type") == ORACLE_ENTRY
        and (e.get("payload") or {}).get("kind") == kind
        and (not spec_id or e.get("spec_id") == spec_id)
    ]


def active_seal(entries: list[dict], spec_id: str) -> Optional[dict]:
    seals = _oracle_entries(entries, spec_id, "seal")
    return seals[-1] if seals else None


def authoring_record(entries: list[dict], spec_id: str) -> Optional[dict]:
    recs = _oracle_entries(entries, spec_id, "record")
    return recs[-1] if recs else None


def _latest_impl_verdict(entries: list[dict], spec_id: str) -> Optional[dict]:
    """The latest *enforced* (non report-only) verdict for the spec — Phase B's marker."""
    verdicts = [
        e
        for e in entries
        if e.get("type") == "verdict"
        and not (e.get("payload") or {}).get("report_only")
        and (not spec_id or e.get("spec_id") == spec_id)
    ]
    return verdicts[-1] if verdicts else None


# --------------------------------------------------------------------------- advisory scanners (pure, non-blocking)
# Source-file extensions used to guess "an implementation file was touched". Advisory only, so a
# coarse guess is fine — this never blocks (read-path isolation is enforced structurally, not here).
_SOURCE_EXT = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".cc",
    ".cpp",
    ".cs",
)
# Leading-underscore identifiers — a private/internal symbol the spec would not name.
_PRIVATE_SYMBOL = re.compile(r"(?<![\w.])_[A-Za-z]\w*")
# A relative import reaches into the implementation package's internals.
_INTERNAL_IMPORT = re.compile(r"^\s*from\s+\.\S*\s+import\s", re.MULTILINE)


def is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, glob) for glob in _TEST_GLOBS)


def looks_like_impl(path: str) -> bool:
    return path.endswith(_SOURCE_EXT) and not is_test_file(path)


def scan_touched_impl(changed: set[str], oracle_paths: set[str]) -> list[str]:
    """Advisory: implementation files the oracle author also modified (non-blocking)."""
    hits = sorted(f for f in changed if looks_like_impl(f) and f not in oracle_paths)
    return [f"oracle author also modified implementation file: {f}" for f in hits]


def scan_symbol_leakage(test_texts: dict[str, str], criteria_text: str) -> list[str]:
    """Advisory: oracle tests referencing implementation internals absent from the sealed spec.

    A relative import, or a leading-underscore symbol the spec never names, suggests the author
    read the implementation. Heuristic and input-dependent — hence advisory, never a gate."""
    findings: list[str] = []
    for path in sorted(test_texts):
        text = test_texts[path]
        if _INTERNAL_IMPORT.search(text):
            findings.append(f"oracle test imports internal implementation modules: {path}")
        privs = {m.group(0) for m in _PRIVATE_SYMBOL.finditer(text)} - {"__init__", "__main__"}
        leaked = sorted(s for s in privs if s not in criteria_text)
        if leaked:
            findings.append(
                f"oracle test references implementation-internal symbol(s) not in the spec "
                f"({path}): {', '.join(leaked[:5])}"
            )
    return findings


# --------------------------------------------------------------------------- the binding predicate
@dataclass
class Independence:
    ok: bool
    reasons: list[str] = field(default_factory=list)  # blocking, structural
    advisory: list[str] = field(default_factory=list)  # non-blocking, surfaced for review
    covered: list[str] = field(default_factory=list)
    model_family: Optional[str] = None
    bundle_hash: Optional[str] = None
    dispatch_ok: Optional[bool] = (
        None  # None = no dispatch attestation; True/False = isolation proof
    )
    isolation_method: Optional[str] = None


def independence(
    entries: list[dict],
    roles: dict,
    spec_id: str,
    *,
    repo_root: Path,
    test_roots: list[Path],
    require_dispatch: bool = False,
    diversity_relaxed: bool = False,
    diversity_level: str = "family",
    coder_model: str = "",
) -> Independence:
    """Prove oracle independence from the ledger + roles + the recorded oracle tests.

    Structural (blocking) facts: an active seal exists; the authoring record is bound to it;
    the recorded oracle is diverse from the coder at ``diversity_level``; the
    record precedes the implementation verdict by ledger ``seq``; every sealed acceptance
    criterion has an oracle test. When a dispatch attestation is present — or when
    ``require_dispatch`` is set (the High-risk tier policy) — physical read-path isolation is also
    proven. A same-family/same-model finding is blocking **unless** ``diversity_relaxed``
    (a signed ``model_diversity`` deviation), in which case it is advisory — never a silent
    drop. Advisory findings never enter ``reasons``.
    """
    reasons: list[str] = []
    covered: list[str] = []
    seal = active_seal(entries, spec_id)
    rec = authoring_record(entries, spec_id)
    coder = coder_family(roles)
    coder_side = coder_model or coder  # full model at model-level, else the family
    label = spec_id or "(spec)"

    if seal is None:
        reasons.append(f"no sealed oracle bundle for {label} — run `3pwr oracle seal`")
    if rec is None:
        reasons.append(f"no oracle authoring record for {label} — run `3pwr oracle record`")

    advisory = list((rec or {}).get("payload", {}).get("advisory_findings", []))
    seal_hash = (seal or {}).get("payload", {}).get("bundle_hash")
    model_family: Optional[str] = None

    if seal is not None and rec is not None:
        rp = rec["payload"]
        model_family = rp.get("model_family")

        # seal-binding: the oracle was authored against the active spec-only bundle.
        if rp.get("bundle_hash") != seal_hash:
            reasons.append(
                "oracle authored against a stale/mismatched bundle — re-seal or re-record"
            )

        # diversity on the ACTUAL model used, at the configured granularity. A same
        # family/model is blocking unless a signed model_diversity deviation relaxes it.
        oracle_model = rp.get("model") or ""
        if not model_family:
            reasons.append("oracle authoring record has no model family")
        elif not coder:
            reasons.append("coder model family is unset in roles.yaml")
        elif not diverse(coder_side, oracle_model or model_family, diversity_level):
            model_lvl = diversity_level == "model" and "/" in oracle_model and "/" in coder_side
            msg = (
                f"oracle model '{oracle_model}' equals the coder model"
                if model_lvl
                else f"oracle model family '{model_family}' equals the coder family"
            )
            if diversity_relaxed:
                advisory.append(msg + " — relaxed by an active model_diversity deviation")
            else:
                reasons.append(msg)

        # ordering: Phase A must precede Phase B, proven by ledger seq (not git time).
        impl = _latest_impl_verdict(entries, spec_id)
        if impl is not None and rec.get("seq", -1) >= impl.get("seq", 0):
            reasons.append(
                "oracle authored at or after the implementation verdict — "
                "Phase A must precede Phase B"
            )

        # coverage: each sealed acceptance criterion has ≥1 oracle test.
        req_ids = set(seal["payload"].get("requirement_ids", []))
        refs = referenced_ids(test_roots, spec_id) if test_roots else {}
        covered = sorted(req_ids & set(refs))
        missing = sorted(req_ids - set(refs))
        if missing:
            reasons.append(f"acceptance criteria without an oracle test: {', '.join(missing)}")

    # physical read-path isolation via headless dispatch. Advisory→blocking when a
    # dispatch attestation exists, or when the tier policy requires one (require_dispatch). Every
    # fact is ledger-derived, so this stays deterministic.
    disp = active_dispatch(entries, spec_id)
    dispatch_ok: Optional[bool] = None
    isolation_method: Optional[str] = None
    if require_dispatch and disp is None:
        reasons.append(
            f"no isolated oracle dispatch recorded for {label} — run `3pwr oracle dispatch`"
        )
    if disp is not None:
        dp = disp["payload"]
        iso = dp.get("isolation") or {}
        isolation_method = iso.get("method")
        dispatch_ok = True
        if seal is not None and dp.get("bundle_hash") != seal_hash:
            reasons.append("oracle dispatch bound to a stale/mismatched bundle")
            dispatch_ok = False
        if not iso.get("excluded_absent") or not iso.get("manifest_hash"):
            reasons.append("oracle dispatch did not prove read-path isolation")
            dispatch_ok = False
        disp_family = dp.get("model_family")
        disp_model = dp.get("model") or ""
        if (
            disp_family
            and coder
            and not diverse(coder_side, disp_model or disp_family, diversity_level)
        ):
            model_lvl = diversity_level == "model" and "/" in disp_model and "/" in coder_side
            msg = (
                f"oracle dispatch model '{disp_model}' equals the coder model"
                if model_lvl
                else f"oracle dispatch model family '{disp_family}' equals the coder family"
            )
            if diversity_relaxed:
                advisory.append(msg + " — relaxed by an active model_diversity deviation")
            else:
                reasons.append(msg)
                dispatch_ok = False

        # model attestation: the self-reported record model must not contradict
        # the ledger-attested dispatch. Deterministic cross-check at family granularity; an
        # integration with an unknown family ('', e.g. copilot's in-IDE picker) cannot contradict.
        attested = integration_family(dp.get("integration") or "") or (disp_family or "")
        if rec is not None and model_family and attested and model_family != attested:
            reasons.append(
                f"self-reported oracle model family '{model_family}' contradicts the "
                f"ledger-attested dispatch (integration '{dp.get('integration')}' → "
                f"'{attested}') — the model claim is not what actually ran"
            )
            dispatch_ok = False
    elif rec is not None and model_family:
        # No dispatch attestation exists: say so honestly — the claim is self-reported and
        # nothing binds it to the process that ran. Advisory, never blocking.
        advisory.append(
            f"oracle model claim '{rec['payload'].get('model')}' is self-reported — "
            "no dispatch attestation binds it to the process that authored the oracle"
        )

    return Independence(
        ok=not reasons,
        reasons=reasons,
        advisory=advisory,
        covered=covered,
        model_family=model_family,
        bundle_hash=seal_hash,
        dispatch_ok=dispatch_ok,
        isolation_method=isolation_method,
    )


# --------------------------------------------------------------------------- headless dispatch
def active_dispatch(entries: list[dict], spec_id: str) -> Optional[dict]:
    """The latest isolated-dispatch attestation for the spec, if any."""
    recs = _oracle_entries(entries, spec_id, "dispatch")
    return recs[-1] if recs else None


# Best-effort model *family* for an agent-backend key — the fast-fail diversity precheck only.
# The authoritative family is the resolved model recorded post-dispatch; "" means "unknown, skip".
INTEGRATION_FAMILY = {
    "claude": "anthropic",
    "gemini": "google",
    "codex": "openai",
    "copilot": "",  # depends on the chosen model / BYOK, not the backend
    "opencode": "",
    "aider": "",  # any OpenAI-compatible model
}


def integration_family(integration: str) -> str:
    return INTEGRATION_FAMILY.get(integration, "")


def parse_dispatched_model(stdout: str) -> Optional[str]:
    """Best-effort ``<family>/<model>`` the dispatch reported (schema-tolerant). Unknown → None,
    and the caller falls back to the integration's declared model."""
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return None
    stack = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            m = cur.get("model")
            if isinstance(m, str) and "/" in m:
                return m
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None


# What the oracle author must never see: the implementation, the plan, contracts, and
# source code. Named planning/design docs + any non-test source file + contracts/.
_EXCLUDED_BASENAMES = ("plan.md", "tasks.md", "research.md", "data-model.md")


def _is_excluded_path(rel: str) -> bool:
    """True iff a repo-relative path is implementation / plan / contracts / source."""
    parts = rel.split("/")
    if parts[-1] in _EXCLUDED_BASENAMES:
        return True
    if "contracts" in parts[:-1]:  # any directory named `contracts` on the path
        return True
    return looks_like_impl(rel)  # a source-code file that is not a test (the advisory predicate)


@dataclass
class WorktreeInfo:
    path: Path
    manifest: list[dict]
    manifest_hash: str

    @property
    def file_count(self) -> int:
        return len(self.manifest)


def worktree_manifest(root: Path) -> list[dict]:
    """Sorted ``[{"path": rel, "hash": sha256}]`` of every file under ``root`` (excluding ``.git``).
    Deterministic — the evidence the implementation was absent at authoring time."""
    items: list[dict] = []
    for p in sorted(root.rglob("*")):
        rel_parts = p.relative_to(root).parts
        if p.is_dir() or ".git" in rel_parts:
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        items.append({"path": p.relative_to(root).as_posix(), "hash": canonical.sha256_hex(data)})
    return items


def manifest_hash(manifest: list[dict]) -> str:
    return canonical.hash_payload(manifest)


def isolation_violations(manifest: list[dict]) -> list[str]:
    """Excluded (implementation/plan/contracts/source) paths still present — must be empty."""
    return sorted(m["path"] for m in manifest if _is_excluded_path(m["path"]))


def _git_worktree(repo_root: Path, args: list[str]) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["git", "worktree", *args], cwd=repo_root, capture_output=True, text=True, check=False
        )
        return proc.returncode, (proc.stderr or proc.stdout)
    except OSError as exc:
        return 1, str(exc)


def teardown_worktree(repo_root: Path, worktree_dir: Path) -> None:
    """Remove the ephemeral worktree (best-effort; always safe to call)."""
    if worktree_dir.exists():
        _git_worktree(repo_root, ["remove", "--force", str(worktree_dir)])
    _git_worktree(repo_root, ["prune"])
    if worktree_dir.exists():
        shutil.rmtree(worktree_dir, ignore_errors=True)


def build_sanitized_worktree(
    repo_root: Path,
    worktree_dir: Path,
    sealed_bundle_path: Path,
    *,
    base_ref: Optional[str] = None,
) -> WorktreeInfo:
    """Create an ephemeral git worktree pruned of implementation/plan/contracts/source.

    The dispatched oracle runs with ``cwd=worktree_dir``; it cannot read the implementation because it
    is not on disk there. The sealed bundle is copied in (it may be uncommitted) as
    ``ORACLE_BUNDLE.json`` and an empty ``oracle-tests/`` output dir is created. Returns the manifest
    computed *after* pruning — the isolation evidence recorded in the ledger. Raises ``RuntimeError``
    if the worktree cannot be created."""
    ref = base_ref or "HEAD"  # current state minus the implementation; --base for a specific ref
    teardown_worktree(repo_root, worktree_dir)  # clear any stale worktree at this path
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)
    rc, err = _git_worktree(repo_root, ["add", "--detach", "--force", str(worktree_dir), ref])
    if rc != 0:
        raise RuntimeError(f"git worktree add failed: {err.strip() or rc}")
    # Prune the implementation / plan / contracts / source.
    for p in sorted(worktree_dir.rglob("*")):
        rel_parts = p.relative_to(worktree_dir).parts
        if p.is_dir() or ".git" in rel_parts:
            continue
        if _is_excluded_path(p.relative_to(worktree_dir).as_posix()):
            p.unlink()
    # The judiciary authors from the sealed bundle only (copied in — it may be uncommitted).
    if sealed_bundle_path.exists():
        (worktree_dir / "ORACLE_BUNDLE.json").write_bytes(sealed_bundle_path.read_bytes())
    (worktree_dir / "oracle-tests").mkdir(exist_ok=True)
    manifest = worktree_manifest(worktree_dir)
    return WorktreeInfo(path=worktree_dir, manifest=manifest, manifest_hash=manifest_hash(manifest))


def dispatch_payload(bound_bundle_hash: str, integration: str, model: str, isolation: dict) -> dict:
    """The ledger attestation for an isolated headless oracle dispatch."""
    return {
        "kind": "dispatch",
        "bundle_hash": bound_bundle_hash,
        "integration": integration,
        "model": model,
        "model_family": family_of(model),
        "isolation": {
            "method": isolation.get("method", "git-worktree"),
            "manifest_hash": isolation["manifest_hash"],
            "file_count": int(isolation.get("file_count", 0)),
            "excluded_absent": bool(isolation.get("excluded_absent")),
        },
    }
