"""Spec-integrity (spec-lock) — protect the approved spec against silent mutation.

The spec is the law. After a human approves it (``signoff --stage spec``)
nothing should be able to alter, add, or delete requirements unnoticed. At
the approval moment the full document's raw-bytes SHA-256 is recorded *inside the signed
sign-off ledger entry* — so tampering with the recorded hash is caught by
the existing ``verify`` with no new trust primitive or entry kind.
Thereafter the ``spec_integrity`` gate and ``advance``
re-hash the file and fail on a mismatch; a fresh Spec-stage sign-off supersedes the old
hash. Everything here is deterministic — bytes on disk plus committed
ledger state, no model call, no network.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from . import canonical
from .verdict import STATUS_FAIL, STATUS_PASS, STATUS_SKIP, GateResult

GATE_NAME = "spec_integrity"

# Integrity states. ``no_approval`` and ``match`` are OK; the rest block.
NO_APPROVAL = "no_approval"
MATCH = "match"
MISMATCH = "mismatch"
MISSING_FILE = "missing_file"


def spec_file_hash(path: Path) -> str:
    """Raw-bytes SHA-256 of the full spec document.

    Byte-for-byte on purpose — no whitespace or formatting normalization: a deliberate
    edit of any kind is a change and must be re-approved.
    """
    return canonical.sha256_hex(path.read_bytes())


def approval_fields(root: Path, spec_path: Path, commit: str = "") -> dict[str, Any]:
    """The extra payload recorded on a Spec-stage sign-off.

    ``spec_path`` is stored root-relative so the check is reproducible from any clone;
    ``commit`` (when known) lets ``3pwr spec diff`` show a textual diff.
    """
    try:
        rel = str(spec_path.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = str(spec_path)
    fields: dict[str, Any] = {"spec_hash": spec_file_hash(spec_path), "spec_path": rel}
    if commit:
        fields["commit"] = commit
    return fields


def spec_approval(entries: list[dict[str, Any]], spec_id: str) -> Optional[dict[str, Any]]:
    """The latest Spec-stage sign-off carrying a spec hash for ``spec_id``.

    Ledger-only — no file I/O. A later approval supersedes an earlier one.
    Sign-offs for other stages, for other specs, or without a
    ``spec_hash`` (older entries) never match, so a never-approved spec yields
    ``None`` and the gate skips rather than blocks.
    """
    result: Optional[dict[str, Any]] = None
    for e in entries:
        if e.get("type") != "signoff":
            continue
        if (e.get("spec_id") or "") != (spec_id or ""):
            continue
        payload = e.get("payload") or {}
        if str(payload.get("stage", "")).lower() != "spec":
            continue
        if not payload.get("spec_hash"):
            continue
        result = e
    return result


@dataclass
class SpecIntegrity:
    """Result of comparing the current spec against its recorded approval."""

    status: str  # no_approval | match | mismatch | missing_file
    approval_seq: Optional[int] = None
    approver: str = ""
    approved_hash: str = ""
    current_hash: str = ""
    spec_path: str = ""  # root-relative path recorded at approval
    commit: str = ""  # commit recorded at approval (for `spec diff`)

    @property
    def ok(self) -> bool:
        return self.status in (NO_APPROVAL, MATCH)


def check(
    entries: list[dict[str, Any]],
    spec_id: str,
    root: Path,
    spec_path: Optional[Path] = None,
) -> SpecIntegrity:
    """Compare the current spec bytes against the recorded approval hash.

    The ledger is consulted FIRST: with no approval the file is never read and the
    check is O(1). When ``spec_path`` is not given, the path recorded
    at approval (root-relative) locates the document — which is how ``advance``
    re-executes the check with no ``--spec`` argument.
    """
    approval = spec_approval(entries, spec_id)
    if approval is None:
        return SpecIntegrity(status=NO_APPROVAL)
    payload = approval.get("payload") or {}
    res = SpecIntegrity(
        status=MISMATCH,
        approval_seq=approval.get("seq"),
        approver=str(payload.get("approver", "")),
        approved_hash=str(payload.get("spec_hash", "")),
        spec_path=str(payload.get("spec_path", "")),
        commit=str(payload.get("commit", "")),
    )
    target = spec_path if spec_path is not None else resolve_target(root, res)
    if target is None or not target.exists():
        res.status = MISSING_FILE
        return res
    res.current_hash = spec_file_hash(target)
    res.status = MATCH if res.current_hash == res.approved_hash else MISMATCH
    return res


def resolve_target(root: Path, res: SpecIntegrity) -> Optional[Path]:
    """The on-disk document an approval points at (root-relative recorded path)."""
    return (root / res.spec_path) if res.spec_path else None


def integrity_gate(
    entries: list[dict[str, Any]], spec_id: str, root: Path, spec_path: Path
) -> GateResult:
    """The ``spec_integrity`` gate — pass / fail(spec_modified) / skip.

    Skips (never blocks) a spec with no recorded approval hash; fails fast — before
    any test executes — when the document changed after approval.
    """
    res = check(entries, spec_id, root, spec_path=spec_path)
    if res.status == NO_APPROVAL:
        return GateResult(
            gate=GATE_NAME,
            status=STATUS_SKIP,
            findings=[
                f"no Spec-stage sign-off with a spec hash recorded for '{spec_id}' — "
                "gate skipped (a not-yet-approved spec is never blocked)"
            ],
        )
    if res.status == MATCH:
        return GateResult(
            gate=GATE_NAME,
            status=STATUS_PASS,
            details={"approval_seq": res.approval_seq, "spec_hash": res.approved_hash},
        )
    finding = (
        f"spec file recorded at approval is missing: {res.spec_path}"
        if res.status == MISSING_FILE
        else (
            f"spec modified after approval (ledger seq={res.approval_seq}, approver={res.approver})"
        )
    )
    return GateResult(
        gate=GATE_NAME,
        status=STATUS_FAIL,
        details={
            "approval_seq": res.approval_seq,
            "approved_hash": res.approved_hash,
            "current_hash": res.current_hash,
        },
        findings=[
            finding,
            "review with `3pwr spec diff`, re-approve via `3pwr signoff --stage spec`, "
            "or record a signed `3pwr deviation --gate spec_integrity`",
        ],
    )
