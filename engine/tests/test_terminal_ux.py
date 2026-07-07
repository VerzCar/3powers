"""Terminal UX on Rich (TRIX, spec 026) — the renderer rebuilt behind the existing APIs.

These tests prove the Rich swap is contract-transparent: `--json` is byte-identical to a golden
capture taken BEFORE the rewrite, `NO_COLOR`/piped output carries no escapes, the `Styler` and
`LiveFrame` public APIs are unchanged (import-and-call smoke over every public method), a narrow
terminal degrades to plain text, and no raw ANSI escape construction survives in the renderer
modules.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from threepowers import frame, orchestrate, style
from threepowers.cli import main

GOLDEN = Path(__file__).parent / "golden"
_SRC = Path(__file__).resolve().parents[1] / "src" / "threepowers"


@pytest.fixture()
def repo(tmp_path):
    """A freshly initialized repo, isolated from this repository's own config."""
    root = tmp_path / "proj"
    root.mkdir()
    args = ["--root", str(root), "init", "--yes", "--language", "python"]
    assert main([*args, "--key-path", str(tmp_path / "k.key")]) == 0
    return root


class _FakeTty(io.StringIO):
    def isatty(self) -> bool:
        return True


# --------------------------------------------------------------------------- TRIX-FR-006 json bytes
def test_json_output_byte_identical_to_pre_trix_golden(repo, capsys):
    """TRIX-FR-006: a representative command's --json bytes equal the golden capture taken before
    the Rich rewrite — the JSON serialization path never passes through Rich formatting."""
    assert main(["--root", str(repo), "classify", "fix a crash", "--json"]) == 0
    out = capsys.readouterr().out
    assert out == (GOLDEN / "classify_fix_a_crash.json").read_text(encoding="utf-8")


def test_plain_text_output_byte_identical_to_pre_trix_golden(repo, capsys, monkeypatch):
    """TRIX-FR-002 / TRIX-FR-007: representative plain (piped, color-off) human output is
    byte-identical to its pre-rewrite golden capture — the toolkit's structure is unchanged."""
    monkeypatch.delenv("THREEPOWERS_FORCE_COLOR", raising=False)
    assert main(["--root", str(repo), "classify", "fix a crash"]) == 0
    assert capsys.readouterr().out == (GOLDEN / "classify_fix_a_crash.txt").read_text(
        encoding="utf-8"
    )
    assert main(["--root", str(repo), "run", "--status", "--spec-id", "NOPE"]) == 0
    assert capsys.readouterr().out == (GOLDEN / "run_status_nope.txt").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- TRIX-FR-007 degradation
def test_no_color_and_piped_output_contain_no_ansi(repo, capsys, monkeypatch):
    """TRIX-FR-007: under NO_COLOR and on a piped (non-TTY) stream the human output carries no
    ANSI escape — plain sequential text, exactly the pre-rewrite degradation contract."""
    monkeypatch.setenv("NO_COLOR", "1")
    assert main(["--root", str(repo), "status"]) == 0
    assert "\033[" not in capsys.readouterr().out
    monkeypatch.delenv("NO_COLOR")
    # piped (capsys IS a pipe — non-TTY): still plain
    assert main(["--root", str(repo), "classify", "add a feature"]) == 0
    assert "\033[" not in capsys.readouterr().out
    # --yes forces the non-interactive plain path too
    assert style.color_enabled(_FakeTty(), assume_yes=True) is False


def test_narrow_terminal_degrades_to_plain_text():
    """TRIX-FR-007 / TRIX-SC-003: a 40-column (or smaller) terminal cannot carry the live bar —
    `build` yields no frame and the tracker falls back to the plain sequential log."""
    env = {"TERM": "xterm-256color"}
    assert frame.build(_FakeTty(), st=style.Styler(), env=env, size=(39, 24)) is None
    buf = _FakeTty()
    tr = orchestrate.Tracker(
        buf,
        "auto",
        tty=True,
        st=style.Styler(),
        frame_view=frame.build(buf, st=style.Styler(), env=env, size=(39, 24)),
    )
    tr.on_event(orchestrate.Event("step", "plan", "Plan"))
    out = buf.getvalue()
    assert "plan" in out and "\033" not in out and "\r" not in out
    tr.close()
    # at exactly the 40-col minimum the bar IS supported — the boundary is unchanged
    assert frame.supported(_FakeTty(), env=env, size=(40, 24))


# --------------------------------------------------------------------------- TRIX-FR-002/003 api smoke
def test_styler_public_api_unchanged_smoke():
    """TRIX-FR-002: every public Styler method and module function keeps its signature and its
    plain/colored contract — the call sites in orchestrate/cli/gates compile untouched."""
    on = style.Styler(enabled=True, ascii_only=False)
    off = style.Styler(enabled=False, ascii_only=True)
    for st in (on, off):
        assert isinstance(st.paint("x", "bold", "cyan"), str)
        for meth in (st.ok, st.err, st.warn, st.head, st.bold, st.dim):
            assert "x" in meth("x")
        assert st.mark("pass") and st.mark("fail") and st.mark("bogus")
        assert "T" in st.header("T", "subject")
        assert st.rule(10)
        assert "text" in st.status_row("warn", "text", "detail", indent=4)
        assert "k" in st.kv([("k", "v")]) and st.kv([]) == ""
        assert "h" in st.table([["a", "b"]], headers=["h", "i"], indent=2)
        assert "one" in st.bullet(["one", "two"], indent=2, width=30)
    # the exact SGR byte contract the pre-Rich implementation emitted is preserved
    assert on.ok("x") == "\033[32mx\033[0m" and on.err("x") == "\033[31mx\033[0m"
    assert on.warn("x") == "\033[33mx\033[0m" and on.head("x") == "\033[1;36mx\033[0m"
    assert on.bold("x") == "\033[1mx\033[0m" and on.dim("x") == "\033[2mx\033[0m"
    assert on.paint("x", "gray") == "\033[90mx\033[0m"
    assert on.paint("x") == "x" and on.paint("x", "unknown") == "x"
    # module functions unchanged
    assert style.strip_ansi(on.ok("x")) == "x" and style.visible_len(on.ok("x")) == 1
    assert style.term_width(default=80) >= 20
    assert style.resolve_verbosity(verbose=True) == "verbose"
    assert style.styler(io.StringIO(), as_json=True).enabled is False


def test_liveframe_public_api_unchanged_smoke():
    """TRIX-FR-003: the LiveFrame public API — supported/build/open/close/emit/note/heartbeat/
    retitle/resize and the idempotent teardown — is exercised end-to-end with zero call-site
    changes; the bar stays visible and the cursor is restored exactly once."""
    env = {"TERM": "xterm-256color"}
    assert frame.supported(_FakeTty(), env=env, size=(100, 24))
    buf = _FakeTty()
    lf = frame.build(buf, st=style.Styler(), subject="RUN", env=env, size=(100, 24), heartbeat=0)
    assert isinstance(lf, frame.LiveFrame)
    lf.open()
    lf.note(kind="step", step="plan", stage="Plan", detail="", reached="Plan", spec_id="RUN")
    lf.emit("hello above the bar")
    lf.heartbeat()
    lf.retitle("030")
    lf.resize()
    lf.close()
    lf.close()  # idempotent
    out = buf.getvalue()
    assert "hello above the bar" in out and "running plan" in style.strip_ansi(out)
    assert "030" in out  # the retitled subject reached the bar
    assert out.count("\033[?25h") == 1  # cursor restored exactly once
    # a closed frame degrades emit to a plain write
    lf.emit("after close")
    assert buf.getvalue().endswith("after close\n")


# --------------------------------------------------------------------------- TRIX-FR-008 source scan
def test_no_raw_ansi_escape_construction_in_renderer_sources():
    """TRIX-FR-008: style.py and frame.py construct no ANSI escape by hand — every escape literal
    left in those sources sits inside a re.compile strip/sanitize matcher; all emission is Rich's."""
    for name in ("style.py", "frame.py"):
        src = (_SRC / name).read_text(encoding="utf-8")
        for lineno, line in enumerate(src.splitlines(), start=1):
            if "\\033" in line or "\\x1b" in line or "\x1b" in line:
                assert "re.compile(" in line, (
                    f"{name}:{lineno} carries an escape literal outside a strip/sanitize "
                    f"matcher: {line.strip()!r}"
                )
        assert "rich" in src  # the renderer is Rich-backed


# --------------------------------------------------------------------------- TRIX-NFR-001 determinism
def test_rich_backed_rendering_stays_deterministic():
    """TRIX-NFR-001: identical state renders identical bytes through the Rich-backed pipeline."""
    st = style.Styler(enabled=True)
    state = frame.FrameState(reached="Build", status="running", activity="implement")
    assert frame.frame_lines(state, 90, st, "X") == frame.frame_lines(state, 90, st, "X")
    assert st.table([["a", "1"]], headers=["h"]) == st.table([["a", "1"]], headers=["h"])
