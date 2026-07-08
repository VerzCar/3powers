"""Per-stage artifact contracts — each executive action stage declares what it must produce.

An earlier native runner treated *"agent exited 0"* as success and never checked that the stage
actually produced the right thing. These contracts close that: an action stage declares the artifact
it is responsible for (a spec file at Specify, oracle tests at Oracle, an implementation change at
Implement), and after dispatch the runner verifies that artifact was produced *before advancing*. A
stage that produced nothing — or only an off-target change — is a **dispatch/artifact failure naming
the stage**, distinct from a gate-red verdict and never a silent pass.

Verification is a **pure function** of the contract and the set of paths the stage produced, so it
is fully deterministic and unit-testable with a fake agent and no network. The engine-owned
contract table below is provider-, model-, and language-agnostic: it names *kinds* of
artifact by path shape, not any vendor, stack, or file. A stage with no declared contract falls back
to the lenient prior behavior so unconfigured stages still run — but the hard contracts extend to
every artifact-producing action stage: ``plan`` and ``tasks`` declare theirs, so the
committed artifact trail in the feature workspace is checked at every stage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArtifactContract:
    """What one action stage must produce.

    ``kind`` is either ``"path"`` — at least one produced path must match one of ``patterns`` (each an
    anchored-anywhere regex over the repo-relative POSIX path) — or ``"change"`` — the stage must produce a
    non-empty change (any produced path). ``expected`` is the human description named in a failure
    message, so it must read as *what was expected*, including the location.
    """

    step: str
    kind: str  # "path" | "change"
    expected: str
    patterns: tuple[str, ...] = ()


@dataclass
class ArtifactCheck:
    """The result of verifying a stage's produced paths against its contract (pure)."""

    ok: bool
    expected: str
    matched: list[str] = field(default_factory=list)  # produced paths that satisfied the contract
    produced: list[str] = field(
        default_factory=list
    )  # everything the stage produced (for diagnostics)

    @property
    def summary(self) -> str:
        """A short artifact summary for the per-stage result."""
        if self.matched:
            head = ", ".join(self.matched[:3])
            more = f" (+{len(self.matched) - 3})" if len(self.matched) > 3 else ""
            return f"{head}{more}"
        return f"{len(self.produced)} file(s) changed"

    @property
    def message(self) -> str:
        """The failure message naming the stage and the expected artifact.

        When the stage produced *something* but nothing on target (the "right artifact, wrong location"
        edge case), the message also names what was produced so the location mismatch is diagnosable."""
        if self.ok:
            return ""
        if self.produced:
            off = ", ".join(self.produced[:3])
            more = f" (+{len(self.produced) - 3} more)" if len(self.produced) > 3 else ""
            return (
                f"expected {self.expected}, but the stage produced only off-target changes: "
                f"{off}{more}"
            )
        return f"expected {self.expected}, but the stage produced no change"


# The engine-owned per-stage contracts. Every lifecycle *action* stage that produces a
# committed artifact carries a hard contract: specify/oracle/implement plus plan/tasks — removed
# from the lenient fallback, so a plan or tasks dispatch that writes no
# artifact is a named failure, never a silent pass. Remaining steps (clarify/…) still fall back leniently.
# The spec/plan/tasks patterns accept the canonical FLAT layout (specs-src/<f>/<step>.md), the
# legacy base folder (specs/<f>/…), and the legacy split layout (spec/spec.md,
# artifacts/<step>.md) — signed ledger history keeps its recorded specs/… paths, so the
# patterns must keep matching both bases forever.
STAGE_ARTIFACTS: dict[str, ArtifactContract] = {
    "discovery": ArtifactContract(
        step="discovery",
        kind="path",
        expected="a discovery note (specs-src/<feature>/discovery.md)",
        patterns=(r"(^|/)specs(-src)?/.+/discovery\.md$",),
    ),
    "specify": ArtifactContract(
        step="specify",
        kind="path",
        expected="a spec file (specs-src/<feature>/spec.md, or the legacy specs/<feature>/…)",
        patterns=(r"(^|/)specs(-src)?/.+/spec\.md$",),
    ),
    "plan": ArtifactContract(
        step="plan",
        kind="path",
        expected="a plan artifact (specs-src/<feature>/plan.md, or the legacy specs/<feature>/…)",
        patterns=(r"(^|/)specs(-src)?/.+/plan\.md$",),
    ),
    "tasks": ArtifactContract(
        step="tasks",
        kind="path",
        expected=(
            "an implementation-plan artifact (specs-src/<feature>/implementation-plan.md, or the "
            "legacy tasks.md)"
        ),
        patterns=(
            r"(^|/)specs(-src)?/.+/implementation-plan\.md$",
            r"(^|/)specs(-src)?/.+/tasks\.md$",
        ),
    ),
    "oracle": ArtifactContract(
        step="oracle",
        kind="path",
        expected="oracle tests (tests/oracle/<spec>/… or oracle-tests/…)",
        # Match the collected location, the sanitized-worktree location, and a generic oracle test file.
        patterns=(
            r"(^|/)tests/oracle/",
            r"(^|/)oracle-tests/",
            r"(^|/)[^/]*oracle[^/]*test[^/]*",
            r"(^|/)test[^/]*oracle[^/]*",
        ),
    ),
    "implement": ArtifactContract(
        step="implement",
        kind="change",
        expected="an implementation change (a non-empty diff)",
    ),
}


def contract_for(step: str) -> ArtifactContract | None:
    """The artifact contract for an action step, or ``None`` when the step declares none."""
    return STAGE_ARTIFACTS.get(step)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    p = path.replace("\\", "/")
    return any(re.search(rx, p) for rx in patterns)


def verify(contract: ArtifactContract | None, produced: list[str]) -> ArtifactCheck:
    """Verify a stage's ``produced`` paths against its ``contract`` — pure and deterministic.

    ``produced`` is the set of repo-relative paths the stage created or modified. When ``contract``
    is ``None`` the stage declared no artifact, so the check is lenient and always passes — an
    unconfigured stage still runs. For a ``path`` contract the check passes iff at least one produced
    path matches a pattern; for a ``change`` contract it passes iff anything was produced. The
    returned :class:`ArtifactCheck` carries the matched/produced paths for the per-stage summary and
    the named failure message.
    """
    produced = sorted(set(produced))
    if contract is None:  # no declared contract → never block
        return ArtifactCheck(ok=True, expected="", matched=produced, produced=produced)
    if contract.kind == "path":
        matched = [p for p in produced if _matches(p, contract.patterns)]
        return ArtifactCheck(
            ok=bool(matched), expected=contract.expected, matched=matched, produced=produced
        )
    # kind == "change": any produced path satisfies the contract.
    return ArtifactCheck(
        ok=bool(produced), expected=contract.expected, matched=produced, produced=produced
    )
