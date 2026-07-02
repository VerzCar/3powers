"""External anchoring of the ledger head — opt-in (HARDN-FR-005).

Unit layer: the anchor module's pure functions, the ``3pwr anchor`` command against a real
local git repo, and the ``verify --anchored`` divergence checks — including the one attack
plain verify cannot see: a key holder regenerating the whole ledger (SC-003).
"""

from __future__ import annotations

import subprocess

import pytest

from threepowers import anchor
from threepowers.cli import main
from threepowers.ledger import Ledger


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    """A real git repo with a 3Powers ledger and an outside-tree signer."""
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(root), "keygen", "--out", str(key)]) == 0
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "README.md").write_text("x\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")
    assert main(["--root", str(root), "signoff", "--approver", "c", "--stage", "review"]) == 0
    return root


# --------------------------------------------------------------------------- pure functions
def test_head_of_and_anchor_message_are_deterministic():
    """HARDN-NFR-001: the witness payload is a pure function of the head."""
    entries = [{"seq": 0, "entry_hash": "sha256:aa"}, {"seq": 1, "entry_hash": "sha256:bb"}]
    assert anchor.head_of(entries) == (1, "sha256:bb")
    assert anchor.head_of([]) is None
    assert anchor.anchor_message(1, "sha256:bb") == anchor.anchor_message(1, "sha256:bb")


def test_check_anchored_divergence_classes():
    """HARDN-FR-005: truncation, rewrite, extension, and missing anchor are each distinct."""
    entries = [{"seq": 0, "entry_hash": "sha256:aa"}, {"seq": 1, "entry_hash": "sha256:bb"}]
    assert anchor.check_anchored(entries, (1, "sha256:bb")).ok  # exact head
    assert anchor.check_anchored(entries, (0, "sha256:aa")).ok  # chain extends the anchor
    trunc = anchor.check_anchored([entries[0]], (1, "sha256:bb"))
    assert not trunc.ok and any("truncated" in p for p in trunc.problems)
    rewrite = anchor.check_anchored(entries, (1, "sha256:EVIL"))
    assert not rewrite.ok and any("diverges" in p for p in rewrite.problems)
    missing = anchor.check_anchored(entries, None)
    assert not missing.ok and any("no anchor" in p for p in missing.problems)


# --------------------------------------------------------------------------- CLI
def test_anchor_creates_tag_and_receipt(repo, capsys):
    """HARDN-FR-005: `3pwr anchor` tags the head and appends a local anchor receipt."""
    assert main(["--root", str(repo), "anchor"]) == 0
    out = capsys.readouterr().out
    assert "anchored ledger head seq=0" in out
    tags = _git(repo, "tag", "-l", "3powers/anchor/*").stdout
    assert "3powers/anchor/0" in tags
    entries = Ledger(repo / ".3powers" / "ledger.jsonl").entries()
    receipts = [e for e in entries if e["type"] == "anchor"]
    assert len(receipts) == 1
    assert receipts[0]["payload"]["anchored_seq"] == 0
    assert receipts[0]["payload"]["pushed"] is False


def test_verify_anchored_passes_when_chain_extends_the_anchor(repo):
    """HARDN-FR-005: appending after the anchor is fine — the anchored head is intact."""
    assert main(["--root", str(repo), "anchor"]) == 0
    assert main(["--root", str(repo), "signoff", "--approver", "c", "--stage", "review"]) == 0
    assert main(["--root", str(repo), "verify", "--anchored"]) == 0


def test_verify_anchored_catches_wholesale_regeneration(repo, monkeypatch, tmp_path, capsys):
    """HARDN-FR-005 + SC-003: a key holder regenerating the ledger passes plain verify but
    fails --anchored."""
    assert main(["--root", str(repo), "anchor"]) == 0
    # The adversary holds the signing key: wipe the ledger and re-sign a fresh history.
    ledger_path = repo / ".3powers" / "ledger.jsonl"
    ledger_path.write_text("", encoding="utf-8")
    assert main(["--root", str(repo), "signoff", "--approver", "evil", "--stage", "review"]) == 0
    assert main(["--root", str(repo), "verify"]) == 0  # tamper-evidence alone sees nothing
    capsys.readouterr()
    assert main(["--root", str(repo), "verify", "--anchored"]) == 1  # the anchor does
    assert "diverges" in capsys.readouterr().out


def test_verify_anchored_catches_truncation(repo, capsys):
    """HARDN-FR-005: a ledger cut behind the anchored head fails --anchored."""
    assert main(["--root", str(repo), "signoff", "--approver", "c", "--stage", "review"]) == 0
    assert main(["--root", str(repo), "anchor"]) == 0  # anchors head seq=1
    ledger_path = repo / ".3powers" / "ledger.jsonl"
    first_line = ledger_path.read_text(encoding="utf-8").splitlines()[0]
    ledger_path.write_text(first_line + "\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["--root", str(repo), "verify", "--anchored"]) == 1
    assert "truncated" in capsys.readouterr().out


def test_verify_anchored_fails_without_any_anchor(repo, capsys):
    """HARDN-FR-005: the opt-in mode fails closed when no anchor exists."""
    capsys.readouterr()
    assert main(["--root", str(repo), "verify", "--anchored"]) == 1
    assert "no anchor" in capsys.readouterr().out


def test_plain_verify_is_unchanged_and_offline(repo):
    """HARDN-FR-005 + HARDN-NFR-001: plain verify never consults an anchor."""
    assert main(["--root", str(repo), "verify"]) == 0  # no anchor exists; nothing changes


def test_anchor_refuses_empty_ledger(tmp_path, monkeypatch, capsys):
    """HARDN-FR-005: nothing to anchor is an actionable usage error."""
    root = tmp_path / "repo"
    (root / ".3powers" / "config").mkdir(parents=True)
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(root), "keygen", "--out", str(key)]) == 0
    assert main(["--root", str(root), "anchor"]) == 2
    assert "empty" in capsys.readouterr().err


def test_anchor_outside_git_fails_actionably(tmp_path, monkeypatch, capsys):
    """HARDN-FR-005: the reference witness is a git tag — no repo, no witness, loud error."""
    root = tmp_path / "not-git"
    (root / ".3powers" / "config").mkdir(parents=True)
    key = tmp_path / "signer.key"
    monkeypatch.setenv("THREEPOWERS_SIGNING_KEY_FILE", str(key))
    assert main(["--root", str(root), "keygen", "--out", str(key)]) == 0
    assert main(["--root", str(root), "signoff", "--approver", "c", "--stage", "review"]) == 0
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    rc = main(["--root", str(root), "anchor"])
    assert rc == 1
    assert "could not create anchor tag" in capsys.readouterr().err
