"""``3pwr`` — the 3Powers command line: parser assembly and entry point.

The command overview and shared helpers live in :mod:`._common`; each command group
owns its subparsers via per-command ``_register_*`` functions, driven here in the
exact registration order so help output is stable. Collaborator seams the command
modules resolve late through this package namespace (``run_gates``,
``detect_adapter``, …) are defined below before the command modules load.
"""

from __future__ import annotations

import argparse
import sys
from typing import Callable, Optional

from .. import __version__
from ..adapters import detect_adapter
from ..gates import run_gates
from ._common import (
    EXIT_FAIL,
    EXIT_OK,
    EXIT_PAUSED,
    EXIT_SETUP,
    EXIT_USAGE,
    _ask_multi,
    _resolve_ui,
)
from . import (
    bootstrap,
    brownfield,
    exceptions,
    gate,
    keys,
    observe,
    oracle,
    run,
    supply,
    trust,
)
from .bootstrap import _notifications_setup_flow, _roles_setup_flow, _warn_diversity
from .run import (
    _dispatch_spec_text,
    _make_agent_runner,
    _progress_safe,
    _resolve_runner_kind,
    _run_feature_dir_from_ledger,
    _run_make_runner,
)

__all__ = [
    "EXIT_FAIL",
    "EXIT_OK",
    "EXIT_PAUSED",
    "EXIT_SETUP",
    "EXIT_USAGE",
    "build_parser",
    "detect_adapter",
    "main",
    "run_gates",
    "_ask_multi",
    "_dispatch_spec_text",
    "_make_agent_runner",
    "_notifications_setup_flow",
    "_progress_safe",
    "_resolve_runner_kind",
    "_roles_setup_flow",
    "_run_feature_dir_from_ledger",
    "_run_make_runner",
    "_warn_diversity",
]

# One registrar per subcommand, in the exact order the subcommands are registered —
# argparse lists subcommands in registration order, so this table IS the help order.
_REGISTRARS: tuple[Callable[..., None], ...] = (
    keys._register_keygen,
    keys._register_rotate_key,
    bootstrap._register_init,
    bootstrap._register_commit_stage,
    gate._register_gate,
    gate._register_conformance,
    trust._register_verify,
    trust._register_anchor,
    trust._register_signoff,
    trust._register_advance,
    exceptions._register_deviation,
    exceptions._register_emergency,
    run._register_status,
    run._register_git,
    gate._register_classify,
    run._register_run,
    trust._register_revert,
    run._register_abort,
    gate._register_coverage_check,
    gate._register_scope_check,
    supply._register_provenance,
    supply._register_deploy_gate,
    supply._register_residual,
    brownfield._register_characterize,
    brownfield._register_eval,
    brownfield._register_deps_check,
    brownfield._register_ready,
    trust._register_ledger,
    oracle._register_roles_check,
    oracle._register_oracle,
    observe._register_observe,
    trust._register_spec,
    bootstrap._register_config,
)


# --------------------------------------------------------------------------- parser
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="3pwr", description="3Powers judiciary engine.")
    p.add_argument("--version", action="version", version=f"3pwr {__version__}")
    p.add_argument("--root", help="repository root (defaults to discovery from cwd)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--json", action="store_true", help="machine-readable output")
        v = sp.add_mutually_exclusive_group()
        v.add_argument(
            "--quiet", action="store_true", help="terser human output — result and failures only"
        )
        v.add_argument(
            "--verbose", action="store_true", help="richer human output — extra per-step detail"
        )
        return sp

    for register in _REGISTRARS:
        register(sub, common)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _, ui_malformed = _resolve_ui(args)
    if ui_malformed and not getattr(args, "json", False):
        print(
            "warning: .3powers/config/ui.yaml is malformed — using default output preferences",
            file=sys.stderr,
        )
    try:
        return int(args.func(args))
    except (FileNotFoundError, LookupError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
