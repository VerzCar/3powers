"""The bundled-default template tier, the closed-vocabulary substitution helper, and the
prompt-fragment resolution.

Everything here runs offline and deterministically: bundled templates are package data,
substitution is ``string.Template.safe_substitute`` over a closed variable vocabulary, and body
resolution is a pure three-tier fallback (repo-local → bundled → generic fragment).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

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


# --------------------------------------------------------------------------- assembly
def test_assemble_is_byte_deterministic():
    """The same inputs always assemble byte-identical prompts — template-file sourcing adds no
    run-to-run variance."""
    a = prompts.assemble("implement", intent="add x", spec_text="S", context="C", file_scope="F")
    b = prompts.assemble("implement", intent="add x", spec_text="S", context="C", file_scope="F")
    assert a == b


def test_untrusted_dollar_in_context_blocks_survives_verbatim():
    """A literal $ in the run-context blocks (untrusted text) is never substituted — the blocks
    are appended verbatim, only template-sourced pieces pass through substitution."""
    spec = "price is $5, keep $STEP and $$ and a lone $ exactly"
    out = prompts.assemble("plan", intent="do $GATE things", spec_text=spec)
    assert spec in out
    assert "do $GATE things" in out


def test_cli_and_hosted_dispatch_assemble_identical_prompts(tmp_path):
    """The CLI runner and the hosted runner dispatch the byte-identical assembled prompt for the
    same inputs — one assembly path, two transports."""
    from threepowers.config import Settings
    from threepowers.hosted import HostedAgentRunner
    from threepowers.runner import CliAgentRunner

    s = Settings(root=tmp_path)
    seen_cli: list[str] = []

    def fake_dispatch(argv, **kw):
        seen_cli.append(argv[-1])
        return (0, "", "")

    cli = CliAgentRunner(
        s,
        {"command": "agent", "prompt_flag": "-p"},
        intent="add x",
        spec_text="S",
        dispatcher=fake_dispatch,
    )
    cli.dispatch("implement", "Build", context="C", file_scope="F")

    seen_hosted: list[str] = []

    def fake_run(argv, cwd):
        if argv[0] == "trigger":
            seen_hosted.append(argv[-1])
            return (0, "run-1", "")
        if argv[0] == "poll":
            return (0, '{"status": "completed"}', "")
        return (0, "", "")

    manifest = {
        "mode": "async-hosted",
        "trigger_command": ["trigger", "{prompt}"],
        "poll_command": ["poll", "{run_id}"],
        "poll_status_field": "status",
    }
    hosted_runner = HostedAgentRunner(
        s,
        manifest,
        intent="add x",
        spec_text="S",
        command_runner=fake_run,
        sleep=lambda _s: None,
    )
    hosted_runner.dispatch("implement", "Build", context="C", file_scope="F")
    assert seen_cli and seen_hosted
    assert seen_cli[-1] == seen_hosted[-1]


# --------------------------------------------------------------------------- no inline literals
_SRC_DIR = Path(prompts.__file__).resolve().parent
# Names that historically carried inline dispatched-prompt text; reintroducing prose under any
# matching name fails this guard.
_FORBIDDEN_NAMES = re.compile(r"PROMPT|PREAMBLE|GENERIC|COMMIT_NOTE|REVISION", re.IGNORECASE)
# Prose markers unique to the dispatched prompts — they may live only in template files.
_PROMPT_MARKERS = ("STAGE:", "COMMIT MESSAGE:", "REVISION REQUESTED", "spec is the law")


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """The ids of the Constant nodes that are module/class/function docstrings."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def test_no_inline_dispatched_prompt_literal_remains_in_source():
    """Every dispatched-prompt body lives in a template file: the prompts and steering sources
    carry no multi-line/concatenated prompt literal — no prose assigned to a prompt-ish name
    (_STAGE_PROMPTS, _PREAMBLE, _GENERIC, _COMMIT_NOTE, REVISION…) and no non-docstring string
    with dispatched-prompt prose. Reintroducing an inline body fails here."""
    for module in ("prompts", "steering"):
        src = (_SRC_DIR / f"{module}.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        doc_ids = _docstring_nodes(tree)
        for node in ast.walk(tree):
            value: ast.expr | None = None
            names: list[str] = []
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
                value = node.value
            if value is not None and any(_FORBIDDEN_NAMES.search(n) for n in names):
                prose = [
                    c.value
                    for c in ast.walk(value)
                    if isinstance(c, ast.Constant)
                    and isinstance(c.value, str)
                    and len(c.value) >= 40
                ]
                assert not prose, f"{module}.py: {names} carries inline prompt text: {prose[:1]}"
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in doc_ids
            ):
                for marker in _PROMPT_MARKERS:
                    assert marker not in node.value, (
                        f"{module}.py line {node.lineno}: inline dispatched-prompt prose "
                        f"({marker!r}) — move it into a template file"
                    )
