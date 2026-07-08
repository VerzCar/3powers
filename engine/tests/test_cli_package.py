"""CLI package split — structural and behavior-identity tests for threepowers/cli/.

The single-module ``cli.py`` became the ``threepowers/cli/`` package: one module per
command group, each owning its ``cmd_*`` handlers and registering its own subparsers
via ``_register_*`` hooks, assembled by ``cli/__init__.py`` in a fixed registrar-table
order. These tests pin the enduring properties of that split — the module map, the
registrar/handler binding, the re-export surface, the help-order stability, and the
unchanged entry point — hermetically (parser introspection, importlib, pathlib; no
subprocess).
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import tomllib
from pathlib import Path

import threepowers.cli as cli

ENGINE_DIR = Path(__file__).resolve().parents[1]
CLI_DIR = ENGINE_DIR / "src" / "threepowers" / "cli"

# The module map the spec fixes: command module → the registrar hooks it must own.
_MODULE_MAP: dict[str, set[str]] = {
    "keys": {"_register_keygen", "_register_rotate_key"},
    "bootstrap": {"_register_init", "_register_commit_stage", "_register_config"},
    "gate": {
        "_register_gate",
        "_register_conformance",
        "_register_classify",
        "_register_coverage_check",
        "_register_scope_check",
    },
    "trust": {
        "_register_verify",
        "_register_anchor",
        "_register_signoff",
        "_register_advance",
        "_register_revert",
        "_register_ledger",
        "_register_spec",
    },
    "exceptions": {"_register_deviation", "_register_emergency"},
    "oracle": {"_register_roles_check", "_register_oracle"},
    "observe": {"_register_observe"},
    "run": {"_register_status", "_register_git", "_register_run", "_register_abort"},
    "supply": {"_register_provenance", "_register_deploy_gate", "_register_residual"},
    "brownfield": {
        "_register_characterize",
        "_register_eval",
        "_register_deps_check",
        "_register_ready",
    },
}

_COMMAND_MODULES = {f"threepowers.cli.{name}" for name in _MODULE_MAP}


def _subparsers_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    """The parser's subparsers action, if it has one."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _passthrough_common(sp: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """A stub for the shared-flags helper: registration-order probes need no real flags."""
    return sp


def _leaf_handlers(parser: argparse.ArgumentParser) -> list[object]:
    """Every ``func`` default reachable from ``parser``, walking nested subparsers.

    A leaf subcommand must carry a callable ``func``; a group subcommand may instead
    carry nested subparsers whose leaves do.
    """
    handlers: list[object] = []
    sub = _subparsers_action(parser)
    assert sub is not None, "parser has no subcommands"
    for name, child in sub.choices.items():
        func = child.get_default("func")
        nested = _subparsers_action(child)
        if nested is None:
            assert callable(func), f"leaf subcommand {name!r} has no func default"
            handlers.append(func)
        else:
            handlers.extend(_leaf_handlers(child))
    return handlers


def test_cli_package_module_map_matches_the_spec():
    """CLIPKG-FR-001: the cli/ package carries exactly the documented command modules, each
    importable and owning its registrar hooks; assembly and shared helpers own no commands."""
    py_modules = {p.stem for p in CLI_DIR.glob("*.py")}
    assert py_modules == {"__init__", "__main__", "_common", *_MODULE_MAP}
    for name, registrars in _MODULE_MAP.items():
        mod = importlib.import_module(f"threepowers.cli.{name}")
        for hook in registrars:
            assert callable(getattr(mod, hook, None)), f"{name} is missing {hook}"
        assert any(n.startswith("cmd_") for n in vars(mod)), f"{name} owns no cmd_* handler"
    for owner in ("threepowers.cli", "threepowers.cli._common"):
        mod = importlib.import_module(owner)
        owned = [n for n, v in vars(mod).items() if n.startswith("cmd_") and callable(v)]
        assert not owned, f"{owner} must not define command handlers, found {owned}"


def test_every_subcommand_binds_a_handler_from_its_owning_module():
    """CLIPKG-FR-002: every leaf subcommand reachable from the assembled parser resolves to a
    cmd_* handler via set_defaults(func=…), and each handler lives in a command module — help
    and implementation stay together."""
    handlers = _leaf_handlers(cli.build_parser())
    assert handlers, "no subcommand handlers found"
    for func in handlers:
        assert func.__name__.startswith("cmd_"), f"handler {func.__name__!r} is not a cmd_*"
        assert func.__module__ in _COMMAND_MODULES, (
            f"{func.__module__}.{func.__name__} lives outside the command modules"
        )


def test_init_reexports_the_public_surface_and_preserves_help_order():
    """CLIPKG-FR-003: cli/__init__.py re-exports the documented surface (main, build_parser,
    the exit-code constants, and the helper seams tests import), and the assembled parser's
    subcommand order equals the registrar table's order exactly."""
    for name in (
        "main",
        "build_parser",
        "EXIT_OK",
        "EXIT_FAIL",
        "EXIT_USAGE",
        "EXIT_PAUSED",
        "EXIT_SETUP",
        "run_gates",
        "detect_adapter",
    ):
        assert name in cli.__all__ and hasattr(cli, name), f"missing re-export {name!r}"
    for name in cli.__all__:
        assert hasattr(cli, name), f"__all__ names {name!r} but it is not defined"

    # Replay each registrar on a fresh parser to learn which subcommands it registers,
    # then require the assembled parser to list them in exactly that concatenated order.
    expected: list[str] = []
    for register in cli._REGISTRARS:
        probe = argparse.ArgumentParser(prog="probe")
        register(probe.add_subparsers(dest="cmd"), _passthrough_common)
        probe_sub = _subparsers_action(probe)
        assert probe_sub is not None
        expected.extend(probe_sub.choices)
    assembled = _subparsers_action(cli.build_parser())
    assert assembled is not None
    assert list(assembled.choices) == expected, "help order diverged from the registrar-table order"


def test_command_surface_behavior_identity_smoke():
    """CLIPKG-FR-004: one uniform surface — --help names every subcommand, the entry callable
    resolves, and the exit-code constants keep their documented values."""
    parser = cli.build_parser()
    top = _subparsers_action(parser)
    assert top is not None
    help_text = parser.format_help()
    for name in top.choices:
        assert name in help_text, f"--help does not name subcommand {name!r}"
    assert callable(cli.main)
    assert (cli.EXIT_OK, cli.EXIT_FAIL, cli.EXIT_USAGE, cli.EXIT_PAUSED, cli.EXIT_SETUP) == (
        0,
        1,
        2,
        3,
        4,
    )


def test_single_module_is_gone_and_the_entry_point_is_unchanged():
    """CLIPKG-FR-005: the old cli.py single module no longer exists, and pyproject.toml still
    targets threepowers.cli:main — the script resolves to the package with zero config change."""
    assert not (ENGINE_DIR / "src" / "threepowers" / "cli.py").exists()
    cfg = tomllib.loads((ENGINE_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    assert cfg["project"]["scripts"]["3pwr"] == "threepowers.cli:main"
    entry_module, _, entry_attr = "threepowers.cli:main".partition(":")
    resolved = getattr(importlib.import_module(entry_module), entry_attr)
    assert resolved is cli.main


def test_package_imports_cleanly_with_no_circular_imports():
    """CLIPKG-NFR-001: every submodule of threepowers.cli imports on its own — no circular
    imports across the new package boundaries."""
    found = {m.name for m in pkgutil.iter_modules(cli.__path__)}
    assert {"_common", *_MODULE_MAP} <= found
    for name in sorted(found):
        mod = importlib.import_module(f"threepowers.cli.{name}")
        assert mod is not None
