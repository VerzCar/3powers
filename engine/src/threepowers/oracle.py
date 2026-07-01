"""Structural oracle independence — Phase A/B, anchored in the signed ledger.

The oracle is the answer key the coder never authored (3PWR-FR-020, §7). This module makes
that independence **structural and traceable** rather than merely procedural:

* ``seal`` extracts a spec-only bundle — requirement IDs and their acceptance-criterion text,
  with **no** implementation, plan, tasks, or contracts — and records its content hash in the
  ledger. The judiciary authors the oracle *from this bundle* (3PWR-FR-020).
* ``record`` captures the authoring event: the bundle hash authored against, the model family
  that actually authored, the oracle test files and their content hashes, and (via the ledger)
  the signer identity. It refuses when the oracle resolves to the coder's model family
  (3PWR-FR-022, on the *actual* model — not just the declared config).
* ``independence`` proves, from the ledger's monotonic signed ``seq`` (never from spoofable git
  timestamps), that Phase A preceded Phase B (3PWR-FR-062), the oracle was bound to the active
  seal (3PWR-FR-020/021), the families diverge (3PWR-FR-022), and every acceptance criterion has
  an oracle test (3PWR-FR-023). These bind at ``advance`` at the High-risk tier (spec §4).

Physically preventing the oracle author from *reading* the implementation — the full letter of
3PWR-FR-021 — requires isolated headless dispatch (3PWR-A3) and is out of reach in a Copilot-only
setting. Here we (a) narrow the read path with the spec-only bundle and (b) surface **advisory,
non-blocking** signals when the author appears to have touched the implementation — flagged for
human review, never a gate (that heuristic is input-dependent and must not perturb the
deterministic verdict, 3PWR-NFR-001).
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import canonical
from .conformance import _TEST_GLOBS, _iter_req_ids, extract_spec, referenced_ids

ORACLE_ENTRY = "oracle"


# --------------------------------------------------------------------------- sealed bundle (FR-020)
def extract_criteria(spec_path: Path) -> tuple[str, dict[str, str]]:
    """Return ``(spec_id, {requirement_id: acceptance-criterion text})`` from a spec.

    The criterion text is the spec line that declares the requirement — the only content the
    judiciary is meant to author against (3PWR-FR-020). Reuses the conformance spec parser so
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
    re-sealing an unchanged spec yields an identical hash (deterministic binding, 3PWR-FR-020)."""
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


# --------------------------------------------------------------------------- authoring record (FR-022/062)
def family_of(model: str) -> str:
    """The model *family* — the part before the first ``/`` in ``<family>/<model>``."""
    return model.split("/", 1)[0].strip() if model else ""


def coder_family(roles: dict) -> str:
    return ((roles.get("roles") or {}).get("coder") or {}).get("model_family", "") or ""


def record_payload(
    bound_bundle_hash: str,
    model: str,
    test_paths: list[str],
    test_hashes: dict[str, str],
    advisory: list[str],
) -> dict:
    return {
        "kind": "record",
        "bundle_hash": bound_bundle_hash,
        "model": model,
        "model_family": family_of(model),
        "test_paths": sorted(test_paths),
        "test_hashes": {p: test_hashes[p] for p in sorted(test_hashes)},
        "advisory_findings": advisory,
    }


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
# coarse guess is fine — this never blocks (3PWR-FR-021 is enforced structurally, not here).
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
    """Advisory: implementation files the oracle author also modified (3PWR-FR-021, non-blocking)."""
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


def independence(
    entries: list[dict],
    roles: dict,
    spec_id: str,
    *,
    repo_root: Path,
    test_roots: list[Path],
) -> Independence:
    """Prove oracle independence from the ledger + roles + the recorded oracle tests.

    Structural (blocking) facts: an active seal exists; the authoring record is bound to it
    (FR-020/021); the recorded oracle family differs from the coder's (FR-022); the record
    precedes the implementation verdict by ledger ``seq`` (FR-062); every sealed acceptance
    criterion has an oracle test (FR-023). Advisory (non-blocking) findings come from the record.
    """
    reasons: list[str] = []
    covered: list[str] = []
    seal = active_seal(entries, spec_id)
    rec = authoring_record(entries, spec_id)
    label = spec_id or "(spec)"

    if seal is None:
        reasons.append(f"no sealed oracle bundle for {label} — run `3pwr oracle seal` (FR-020)")
    if rec is None:
        reasons.append(
            f"no oracle authoring record for {label} — run `3pwr oracle record` (FR-062)"
        )

    advisory = list((rec or {}).get("payload", {}).get("advisory_findings", []))
    seal_hash = (seal or {}).get("payload", {}).get("bundle_hash")
    model_family: Optional[str] = None

    if seal is not None and rec is not None:
        rp = rec["payload"]
        model_family = rp.get("model_family")

        # seal-binding (FR-020/021): the oracle was authored against the active spec-only bundle.
        if rp.get("bundle_hash") != seal_hash:
            reasons.append(
                "oracle authored against a stale/mismatched bundle — re-seal or re-record (FR-020/021)"
            )

        # model-family diversity on the ACTUAL model used (FR-022).
        coder = coder_family(roles)
        if not model_family:
            reasons.append("oracle authoring record has no model family (FR-022)")
        elif not coder:
            reasons.append("coder model family is unset in roles.yaml (FR-022)")
        elif model_family == coder:
            reasons.append(f"oracle model family '{model_family}' equals the coder family (FR-022)")

        # ordering (FR-062): Phase A must precede Phase B, proven by ledger seq (not git time).
        impl = _latest_impl_verdict(entries, spec_id)
        if impl is not None and rec.get("seq", -1) >= impl.get("seq", 0):
            reasons.append(
                "oracle authored at or after the implementation verdict — "
                "Phase A must precede Phase B (FR-062)"
            )

        # coverage (FR-023): each sealed acceptance criterion has ≥1 oracle test.
        req_ids = set(seal["payload"].get("requirement_ids", []))
        refs = referenced_ids(test_roots, spec_id) if test_roots else {}
        covered = sorted(req_ids & set(refs))
        missing = sorted(req_ids - set(refs))
        if missing:
            reasons.append(
                f"acceptance criteria without an oracle test: {', '.join(missing)} (FR-023)"
            )

    return Independence(
        ok=not reasons,
        reasons=reasons,
        advisory=advisory,
        covered=covered,
        model_family=model_family,
        bundle_hash=seal_hash,
    )
