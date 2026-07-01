"""Integration layer: the conformance + coverage trace through the CLI (3PWR-FR-026, 3PWR-FR-030).

An **integration-layer** test (its path is ``tests/integration/``). It wires the CLI, the
conformance/coverage trace, and the verdict together on a fixture — exercising the engine's change at
the integration layer, dogfooding tier-required layers (3PWR-FR-064/065).
"""

from __future__ import annotations

from threepowers.cli import main


def test_two_way_coverage_integration(tmp_path):
    """3PWR-FR-030-adjacent: the CLI coverage trace passes when every requirement maps to a task and
    every task to a requirement (exercises cli + conformance + verdict together)."""
    (tmp_path / ".3powers").mkdir()
    spec = tmp_path / "spec.md"
    spec.write_text(
        "**Spec ID**: INTG\n\n- **INTG-FR-001**: The system shall work.\n", encoding="utf-8"
    )
    tasks = tmp_path / "tasks.md"
    tasks.write_text("- T001 implement INTG-FR-001\n", encoding="utf-8")
    assert (
        main(
            ["--root", str(tmp_path), "coverage-check", "--spec", str(spec), "--tasks", str(tasks)]
        )
        == 0
    )
