"""CLI experience — the structured-output toolkit, consistent vocabulary, the auto-mode stage
header, verbosity, and ui.yaml preferences (CLIUX-FR-001…015, NFR-001…005).

Presentation is a human-output-only layer: these tests prove it degrades to plain, alignment-
preserving text with color off, never touches the ``--json`` payload or exit codes, stays
dependency-free, and resolves its preferences deterministically.
"""

from __future__ import annotations

import io
import json
import tomllib
from pathlib import Path

import pytest

from threepowers import orchestrate, style
from threepowers.cli import main
from threepowers.config import Settings

# --------------------------------------------------------------------------- fixtures


@pytest.fixture()
def repo(tmp_path):
    """A freshly initialized repo (seeds .3powers, ui.yaml, keys) — isolated from this repo's config."""
    root = tmp_path / "proj"
    root.mkdir()
    assert (
        main(
            [
                "--root",
                str(root),
                "init",
                "--yes",
                "--language",
                "python",
                "--key-path",
                str(tmp_path / "k.key"),
            ]
        )
        == 0
    )
    return root


# --------------------------------------------------------------------------- CLIUX-FR-001/002 toolkit
def test_toolkit_primitives_degrade_to_stripped_plain():
    """CLIUX-FR-001 / CLIUX-FR-002: every primitive with color off equals the colored output stripped."""
    on = style.Styler(enabled=True, ascii_only=False)
    off = style.Styler(enabled=False, ascii_only=False)
    renderers = [
        lambda st: st.header("Title", "subject"),
        lambda st: st.status_row("pass", "all good", "detail"),
        lambda st: st.kv([("a", "1"), ("bbb", "22")]),
        lambda st: st.table([["a", "short"], ["bbbb", "x"]], headers=["c1", "c2"]),
        lambda st: st.rule(12),
        lambda st: st.bullet(["one", "two three four"]),
    ]
    for render in renderers:
        assert style.strip_ansi(render(on)) == render(off)  # color adds only ANSI, never structure
    # the colorizing primitives emit ANSI when enabled (bullet stays plain — coloring its glyph would
    # corrupt textwrap's width math, so it carries meaning by structure alone).
    for render in renderers[:-1]:
        assert "\033[" in render(on)


def test_toolkit_avoids_run_on_lines():
    """CLIUX-FR-004: a multi-field result renders as aligned rows, not one run-on line."""
    st = style.Styler(enabled=False)
    out = st.table([["a", "1"], ["bbbb", "2"]])
    l1, l2 = out.splitlines()
    assert l1.index("1") == l2.index("2")  # the second column is vertically aligned


# --------------------------------------------------------------------------- CLIUX-NFR-004 accessibility
def test_ascii_glyph_fallback_and_unicode_default():
    """CLIUX-NFR-004: an ascii-only styler swaps the Unicode marks; the default keeps them."""
    a = style.Styler(enabled=False, ascii_only=True)
    assert a.mark("pass") == "v" and a.mark("fail") == "x"
    assert "•" not in a.bullet(["x"])  # ascii bullet
    assert style.Styler(enabled=False).mark("pass") == "✓"  # default unchanged (INITX contract)


def test_status_meaning_never_carried_by_color_alone():
    """CLIUX-NFR-004: with color off, a glyph + words still convey the status."""
    off = style.Styler(enabled=False)
    row = off.status_row("fail", "boom", "seq=3")
    assert "✗" in row and "boom" in row and "\033" not in row


# --------------------------------------------------------------------------- CLIUX-FR-003/NFR-003 no deps
def test_no_third_party_rendering_dependency():
    """CLIUX-FR-003 / CLIUX-NFR-003: no rendering library is a runtime dependency (ANSI only)."""
    data = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8"))
    deps = " ".join(data["project"]["dependencies"]).lower()
    for banned in ("rich", "curses", "colorama", "blessed", "termcolor"):
        assert banned not in deps


# --------------------------------------------------------------------------- CLIUX-FR-005 vocabulary
def test_consistent_status_vocabulary():
    """CLIUX-FR-005: a given status always maps to the same glyph, everywhere."""
    st = style.Styler(enabled=False)
    assert st.status_row("pass", "x").strip().startswith("✓")
    assert st.status_row("fail", "x").strip().startswith("✗")
    assert st.status_row("warn", "x").strip().startswith("⚠")


# --------------------------------------------------------------------------- CLIUX-FR-014 color precedence
def test_color_enabled_precedence(monkeypatch):
    """CLIUX-FR-014: flag(--json) > env(NO_COLOR/FORCE) > file(color_mode) > default(tty)."""
    monkeypatch.delenv("THREEPOWERS_FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    class FakeTTY(io.StringIO):
        def isatty(self):
            return True

    assert style.color_enabled(FakeTTY(), color_mode="never") is False  # file overrides tty default
    assert style.color_enabled(io.StringIO(), color_mode="always") is True  # file overrides default
    monkeypatch.setenv("NO_COLOR", "1")
    assert style.color_enabled(io.StringIO(), color_mode="always") is False  # env beats file
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("THREEPOWERS_FORCE_COLOR", "1")
    assert (
        style.color_enabled(io.StringIO(), as_json=True, color_mode="always") is False
    )  # json wins


# --------------------------------------------------------------------------- CLIUX-FR-013 verbosity
def test_resolve_verbosity_precedence():
    """CLIUX-FR-013/014: an explicit flag wins over the ui.yaml default; verbose beats quiet."""
    assert style.resolve_verbosity(quiet=True, file_default="verbose") == "quiet"
    assert style.resolve_verbosity(verbose=True, file_default="quiet") == "verbose"
    assert style.resolve_verbosity(file_default="verbose") == "verbose"
    assert style.resolve_verbosity() == "normal"
    assert style.resolve_verbosity(file_default="bogus") == "normal"


# --------------------------------------------------------------------------- CLIUX-FR-014/015 ui.yaml
def test_load_ui_defaults_valid_and_malformed(tmp_path):
    """CLIUX-FR-014/015: missing → defaults; valid → honored; malformed/unknown → defaults + flag."""
    (tmp_path / ".3powers" / "config").mkdir(parents=True)
    s = Settings(root=tmp_path)
    prefs, malformed = s.load_ui()
    assert prefs == {"color_mode": "auto", "verbosity": "normal", "layout": "normal"}
    assert malformed is False

    s.ui_config_path.write_text("color_mode: never\nverbosity: verbose\nlayout: compact\n")
    prefs, malformed = s.load_ui()
    assert prefs == {"color_mode": "never", "verbosity": "verbose", "layout": "compact"}
    assert malformed is False

    s.ui_config_path.write_text("color_mode: [unterminated\n")  # not valid YAML
    prefs, malformed = s.load_ui()
    assert prefs["color_mode"] == "auto" and malformed is True

    s.ui_config_path.write_text("- a\n- b\n")  # valid YAML but not a mapping
    prefs, malformed = s.load_ui()
    assert prefs["color_mode"] == "auto" and malformed is True

    s.ui_config_path.write_text("color_mode: rainbow\n")  # unknown value → per-key default
    prefs, _ = s.load_ui()
    assert prefs["color_mode"] == "auto"


def test_init_seeds_documented_ui_yaml(repo):
    """CLIUX-FR-015: `3pwr init` seeds ui.yaml, and its defaults reproduce today's behavior."""
    s = Settings(root=repo)
    assert s.ui_config_path.exists()
    prefs, malformed = s.load_ui()
    assert prefs == {"color_mode": "auto", "verbosity": "normal", "layout": "normal"}
    assert malformed is False


def test_malformed_ui_warns_once_on_stderr_not_json(repo, capsys):
    """CLIUX-FR-015: a malformed ui.yaml warns once on stderr, never on the --json path."""
    Settings(root=repo).ui_config_path.write_text("color_mode: [bad\n")
    assert main(["--root", str(repo), "status"]) == 0
    assert "ui.yaml is malformed" in capsys.readouterr().err
    assert main(["--root", str(repo), "status", "--json"]) == 0
    assert "malformed" not in capsys.readouterr().err  # --json output stays clean


# --------------------------------------------------------------------------- CLIUX-FR-007/NFR-002 json
def test_json_never_colored_even_when_forced(repo, capsys, monkeypatch):
    """CLIUX-FR-007 / CLIUX-NFR-002: --json is clean JSON with no ANSI, even under FORCE_COLOR + always."""
    monkeypatch.setenv("THREEPOWERS_FORCE_COLOR", "1")
    Settings(root=repo).ui_config_path.write_text("color_mode: always\n")
    assert main(["--root", str(repo), "classify", "fix a crash", "--json"]) == 0
    out = capsys.readouterr().out
    assert "\033[" not in out
    assert json.loads(out)["kinds"]  # still valid, populated JSON


def test_verbosity_never_changes_json_or_exit(repo, capsys):
    """CLIUX-FR-013: --quiet/--verbose leave the --json payload and exit code byte/behavior identical."""
    results = []
    for flag in ([], ["--quiet"], ["--verbose"]):
        rc = main(["--root", str(repo), "classify", "add a feature", "--json", *flag])
        results.append((rc, capsys.readouterr().out))
    assert results[0][0] == results[1][0] == results[2][0]
    assert results[0][1] == results[1][1] == results[2][1]


def test_verbosity_monotonically_increases_human_detail(repo, capsys, monkeypatch):
    """CLIUX-FR-013: human detail grows quiet ⊆ normal ⊆ verbose (header, then per-item detail)."""
    monkeypatch.delenv("THREEPOWERS_FORCE_COLOR", raising=False)
    seen = {}
    for level, flag in [("quiet", ["--quiet"]), ("normal", []), ("verbose", ["--verbose"])]:
        main(["--root", str(repo), "verify", *flag])
        seen[level] = capsys.readouterr().out
    assert "verify" not in seen["quiet"]  # header suppressed at quiet
    assert "verify" in seen["normal"]  # header shown at normal
    assert "entries checked" in seen["verbose"]  # verbose-only detail
    assert "entries checked" not in seen["normal"]


# --------------------------------------------------------------------------- CLIUX-FR-006 self-identifying
def test_commands_open_with_a_self_identifying_header(repo, capsys):
    """CLIUX-FR-006: a command's human output names the operation (a header)."""
    main(["--root", str(repo), "classify", "add a login form"])
    assert "classify" in capsys.readouterr().out
    main(["--root", str(repo), "status"])
    assert "status" in capsys.readouterr().out


# --------------------------------------------------------------------------- CLIUX-FR-008/009/012 stage header
def test_render_tracker_colorized_and_plain_stable():
    """CLIUX-FR-008/012: the tracker colorizes with a styler and is byte-stable plain without one."""
    colored = orchestrate.render_tracker("Plan", style.Styler(enabled=True))
    assert "\033[" in colored
    assert style.strip_ansi(colored) == orchestrate.render_tracker("Plan")
    assert "▶ Plan" in orchestrate.render_tracker(
        "Plan"
    ) and "✓ Spec" in orchestrate.render_tracker("Plan")


def test_format_event_states_are_distinct_when_colored():
    """CLIUX-FR-009: running/paused/failed render with distinct color; the plain path is unchanged."""
    on = style.Styler(enabled=True)
    gate = orchestrate.format_event(
        orchestrate.Event("gate-stop", "review-spec", "Spec"), "auto", on
    )
    failed = orchestrate.format_event(
        orchestrate.Event("failed", "gate_red", "Verify", "fail"), "auto", on
    )
    assert "\033[33m" in gate  # a paused human gate is warn-colored (yellow)
    assert "\033[31m" in failed  # a failure is red
    # the no-styler path is byte-identical to before (tests elsewhere depend on it)
    assert orchestrate.format_event(orchestrate.Event("step", "plan", "Plan"), "auto") == (
        "  ▶ Plan     plan"
    )


# --------------------------------------------------------------------------- CLIUX-FR-011 off-tty plain
def test_offtty_stage_view_is_plain_even_with_enabled_styler():
    """CLIUX-FR-011: the off-TTY run log carries no ANSI/control codes, even if handed an enabled styler."""
    buf = io.StringIO()
    tr = orchestrate.Tracker(buf, "auto", tty=False, st=style.Styler(enabled=True))
    tr.on_event(orchestrate.Event("step", "specify", "Spec"))
    tr.on_event(orchestrate.Event("done"))
    out = buf.getvalue()
    assert "specify" in out and "\033" not in out and "\r" not in out


def test_run_status_renders_structured_snapshot(repo, capsys):
    """CLIUX-FR-012: `3pwr run --status` renders the same vocabulary as a live run (a static snapshot)."""
    assert main(["--root", str(repo), "run", "--status", "--spec-id", "NOPE"]) == 0
    assert "no run recorded for NOPE" in capsys.readouterr().out


def test_auto_run_pauses_prominently_at_human_gate(repo, capsys, tmp_path, monkeypatch):
    """CLIUX-FR-010: at a human gate the run marks it prominently and names the exact resume command."""
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(tmp_path / "k.key"))
    rc = main(
        ["--root", str(repo), "run", "add a thing", "--dry-run", "--no-input", "--spec-id", "DEMO"]
    )
    assert rc == 3  # paused at a human gate (AUTOX-FR-009 exit contract, unchanged)
    out = capsys.readouterr().out
    assert "HUMAN GATE" in out and "review-spec" in out
    assert "3pwr run --resume --spec-id DEMO" in out  # the exact resume command


# --------------------------------------------------------------------------- CLIUX-NFR-001/005
def test_rendering_is_deterministic():
    """CLIUX-NFR-001: identical inputs render identical bytes (deterministic, fully offline).

    The engine also stays green under its own gates across this presentation layer, with STATUS.md the
    single home of status (CLIUX-NFR-005) — proven by the whole suite passing under self-application."""
    st = style.Styler(enabled=True)
    assert st.table([["a", "1"]], headers=["h"]) == st.table([["a", "1"]], headers=["h"])
    assert orchestrate.render_tracker("Build", st) == orchestrate.render_tracker("Build", st)
