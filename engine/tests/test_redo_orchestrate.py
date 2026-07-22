"""Redo rewind math — the pure resolution + resume-index helpers (spec 039).

These exercise the deterministic pieces `3pwr run --redo` stands on, with no I/O, no signing, and no
CLI: stage/step → target resolution (REQ-002), the latest-redo-wins marker read (REQ-008), and the
redo-aware re-entry index that treats the newest rewind marker as the completion floor
(REQ-008/REQ-011). Every case runs against hand-built ledger-entry dicts of the same shape
`Ledger.append("run", …)` writes.
"""

from __future__ import annotations

import pytest

from threepowers import orchestrate


def _run_entry(
    seq: int, kind: str, *, step: str = "", target: str = "", spec_id: str = "RUN"
) -> dict:
    """A minimal signed-ledger-shaped ``run`` entry — only the fields the helpers read."""
    payload: dict[str, object] = {"kind": kind}
    if step:
        payload["step"] = step
    if target:
        payload["target_step"] = target
    return {"seq": seq, "spec_id": spec_id, "type": "run", "payload": payload}


# --------------------------------------------------------------------------- resolve_redo_target
@pytest.mark.parametrize(
    "name,expected",
    [
        # stage labels resolve to the EARLIEST producing step of the stage
        ("discovery", ("discovery", "Discovery")),
        ("spec", ("specify", "Spec")),
        ("plan", ("plan", "Plan")),
        ("build", ("oracle", "Build")),
        # casing is irrelevant for a stage label
        ("SPEC", ("specify", "Spec")),
        ("Build", ("oracle", "Build")),
        # a bare step id resolves to itself when it is redo-eligible
        ("specify", ("specify", "Spec")),
        ("oracle", ("oracle", "Build")),
        ("implement", ("implement", "Build")),
    ],
)
def test_resolve_redo_target_maps_labels_and_steps(name, expected):
    """Covers: REQ-002 — every rewind-able stage label and step id resolves to its `(step, stage)`,
    a stage label always landing on the stage's earliest producing step."""
    assert orchestrate.resolve_redo_target(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "",  # empty
        "frobnicate",  # unknown
        "review-spec",  # a human gate step
        "review-plan",  # a human gate step
        "verify",  # the deterministic verdict step
        "clarify",  # a producing action, but not redo-eligible
        "tasks",  # a producing action, but not redo-eligible
        "advance",  # Ship — a shipped run is reverted, never rewound
        "ship",  # the Ship stage label has no rewind-able producing step
    ],
)
def test_resolve_redo_target_refuses_non_redoable(name):
    """Covers: REQ-002/CON-002 — unknown input, gate/verdict steps, non-eligible producing steps,
    and `advance`/Ship all resolve to `("", "")` so the CLI can refuse them."""
    assert orchestrate.resolve_redo_target(name) == ("", "")


# --------------------------------------------------------------------------- last_redo_target
def test_last_redo_target_picks_the_latest_marker():
    """Covers: REQ-008 — with several rewind markers the LATEST wins; earlier ones stay history."""
    entries = [
        _run_entry(0, "start"),
        _run_entry(3, "redo", target="specify"),
        _run_entry(7, "stage", step="specify"),
        _run_entry(9, "redo", target="plan"),
    ]
    assert orchestrate.last_redo_target(entries, "RUN") == (9, "plan")


def test_last_redo_target_none_when_no_marker():
    """Covers: REQ-008 — no rewind marker for the spec yields `(-1, "")`."""
    entries = [_run_entry(0, "start"), _run_entry(1, "stage", step="specify")]
    assert orchestrate.last_redo_target(entries, "RUN") == (-1, "")


def test_last_redo_target_ignores_other_specs_and_targetless_markers():
    """Covers: REQ-008 — a marker for another spec, and a malformed marker with no target, are
    both ignored."""
    entries = [
        _run_entry(2, "redo", target="plan", spec_id="OTHER"),
        _run_entry(4, "redo"),  # no target_step
    ]
    assert orchestrate.last_redo_target(entries, "RUN") == (-1, "")


# --------------------------------------------------------------------------- redo_start_index
@pytest.mark.parametrize(
    "target,expected_step",
    [("specify", "specify"), ("plan", "plan"), ("oracle", "oracle")],
)
def test_redo_start_index_rewinds_to_the_target(target, expected_step):
    """Covers: REQ-008 — with pre-rewind completions of every producing stage, a fresh marker with
    no post-marker progress re-enters exactly at the target step."""
    entries = [
        _run_entry(0, "start"),
        _run_entry(1, "stage", step="specify"),
        _run_entry(2, "stage", step="plan"),
        _run_entry(3, "stage", step="oracle"),
        _run_entry(4, "stage", step="implement"),
        _run_entry(5, "redo", target=target),
    ]
    assert orchestrate.redo_start_index(entries, "RUN") == orchestrate.step_index(expected_step)


def test_redo_start_index_ignores_completions_before_the_marker():
    """Covers: REQ-008/REQ-011 — a pre-rewind `implement` completion no longer counts once a later
    marker rewinds to `specify`; re-entry lands at `specify`, not past `implement`."""
    entries = [
        _run_entry(0, "start"),
        _run_entry(1, "stage", step="specify"),
        _run_entry(2, "stage", step="plan"),
        _run_entry(3, "stage", step="oracle"),
        _run_entry(4, "stage", step="implement"),
        _run_entry(9, "redo", target="specify"),
    ]
    assert orchestrate.redo_start_index(entries, "RUN") == orchestrate.step_index("specify")


def test_redo_start_index_advances_past_re_run_stages_after_the_marker():
    """Covers: REQ-008 — only completions recorded AFTER the marker advance the re-entry point, so a
    re-flow that already re-ran `specify` resumes past it (never re-running a re-completed stage)."""
    entries = [
        _run_entry(0, "start"),
        _run_entry(1, "stage", step="specify"),
        _run_entry(5, "redo", target="specify"),
        _run_entry(6, "stage", step="specify"),  # the re-run completion, after the marker
    ]
    assert orchestrate.redo_start_index(entries, "RUN") == orchestrate.step_index("specify") + 1


def test_redo_start_index_never_rewinds_to_or_past_ship():
    """Covers: REQ-008/CON-002 — the last rewind-able step is `implement`; a marker there re-enters
    at `implement` and never at Ship (`advance`), so a rewind cannot cross into the shipped stage."""
    entries = [
        _run_entry(0, "start"),
        _run_entry(1, "stage", step="implement"),
        _run_entry(2, "stage", step="advance"),  # a prior Ship completion, pre-rewind
        _run_entry(5, "redo", target="implement"),
    ]
    idx = orchestrate.redo_start_index(entries, "RUN")
    assert idx == orchestrate.step_index("implement")
    assert idx < orchestrate.step_index("advance")


def test_redo_start_index_defers_to_resume_when_no_marker():
    """Covers: REQ-008 — with no rewind marker the index is exactly `resume_start_index` (a redo
    changes resume math only when a marker is present)."""
    entries = [
        _run_entry(0, "start"),
        _run_entry(1, "stage", step="specify"),
        _run_entry(2, "stage", step="plan"),
    ]
    assert orchestrate.redo_start_index(entries, "RUN") == orchestrate.resume_start_index(
        entries, "RUN"
    )
