"""The bundled-default template tier, the closed-vocabulary substitution helper, and the
prompt-fragment resolution.

Everything here runs offline and deterministically: bundled templates are package data,
substitution is ``string.Template.safe_substitute`` over a closed variable vocabulary, and body
resolution is a pure three-tier fallback (repo-local → bundled → generic fragment).
"""

from __future__ import annotations

from threepowers import prompts


# --------------------------------------------------------------------------- bundled tier
def test_bundled_template_body_returns_stripped_body():
    """bundled_template_body reads a shipped stage template and strips its metadata header."""
    body = prompts.bundled_template_body("specify.agent.md")
    assert body, "the bundled specify template must ship a non-empty body"
    assert not body.startswith("---"), "the metadata header must be stripped"
    assert "spec" in body.lower()


def test_bundled_template_body_missing_file_is_empty():
    """An absent bundled template resolves to '' — fall-through, never an exception."""
    assert prompts.bundled_template_body("missing.agent.md") == ""


# --------------------------------------------------------------------------- substitution
def test_substitute_fills_supplied_variable():
    """A supplied closed-vocabulary variable renders its value."""
    assert prompts.substitute("STAGE: $STEP.", {"STEP": "plan"}) == "STAGE: plan."


def test_substitute_unfilled_defined_variable_renders_empty():
    """A defined variable left unfilled renders empty, never verbatim."""
    assert prompts.substitute("STAGE: $STEP.") == "STAGE: ."


def test_substitute_double_dollar_renders_literal_dollar():
    """A $$ in the body renders a single literal $."""
    assert prompts.substitute("costs $$5") == "costs $5"


def test_substitute_lone_malformed_dollar_never_raises():
    """A lone malformed $ is left verbatim — safe_substitute never raises."""
    assert prompts.substitute("a lone $ sign") == "a lone $ sign"


def test_substitute_unknown_variable_left_verbatim():
    """A $name outside the closed vocabulary is left verbatim."""
    assert prompts.substitute("keep $UNKNOWN as-is") == "keep $UNKNOWN as-is"


# --------------------------------------------------------------------------- fragments
def test_fragment_body_answers_bundled_when_no_templates_dir():
    """With no repo-local templates dir, the bundled fragment body answers."""
    body = prompts.fragment_body("preamble.agent.md", None)
    assert body
    assert "spec is the law" in body.lower()


def test_fragment_body_repo_local_override_wins(tmp_path):
    """A repo-local fragment override takes precedence over the bundled default; an absent
    override falls back to the bundled body."""
    (tmp_path / "preamble.agent.md").write_text(
        "---\nname: preamble.agent\nrole: fragment\n---\n\nMY PREAMBLE\n", encoding="utf-8"
    )
    assert prompts.fragment_body("preamble.agent.md", tmp_path) == "MY PREAMBLE"
    assert prompts.fragment_body("generic.agent.md", tmp_path) == prompts.bundled_template_body(
        "generic.agent.md"
    )


# --------------------------------------------------------------------------- three-tier resolve
def test_resolve_body_unseeded_returns_bundled_stage_body():
    """With no repo-local templates dir, resolve_body answers the bundled stage template body —
    not the generic fragment."""
    body = prompts.resolve_body("plan", None)
    assert body == prompts.bundled_template_body("plan.agent.md")
    assert body, "the bundled plan template ships non-empty"


def test_resolve_body_unknown_step_falls_through_to_generic_fragment():
    """A step with neither a repo-local nor a bundled template resolves to the generic fragment
    with $STEP filled with the step's name."""
    body = prompts.resolve_body("unknown-step", None)
    assert body.startswith("STAGE: unknown-step.")
    assert "$STEP" not in body
