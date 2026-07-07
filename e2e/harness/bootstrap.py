#!/usr/bin/env python3
"""Shared sandbox provisioning for the 3pwr end-to-end notebook kit.

Every per-language notebook calls :func:`provision` (or this file's ``__main__``
entry point) to stand up a throwaway sandbox before any ``3pwr`` command runs. A
sandbox is a copy of a committed ``e2e/<name>/project/`` template turned into a
real git repository with its dependencies installed, a sandbox-scoped signing
identity, and the shared headless-integration config seeded in.

The module is deliberately stdlib-only — it imports nothing from the harness
virtual environment (papermill/jupyter) and nothing from the 3powers engine. That
keeps provisioning independent of both, so a notebook can drive it under any
kernel and the harness venv stays papermill-only.

Provisioning steps (one implementation, three thin call sites):

1. Copy ``e2e/<name>/project/`` to a fresh temp workspace, excluding any inner
   ``.git``, installed dependencies, or coverage artifacts.
2. ``git init`` + an initial commit, so ``3pwr`` has a clean substrate.
3. Install project dependencies from the committed lockfile for the language.
4. Run ``3pwr init --yes --language <lang> --key-path <key>`` to lay down the
   ``.3powers/`` tree and mint a sandbox-scoped signing key outside the repo.
5. Export ``THREEPOWERS_SIGNING_KEY_FILE`` so every later ``3pwr`` command
   resolves that key.
6. Overlay the single shared ``e2e/config/roles.yaml`` onto the initialized
   ``.3powers/config/roles.yaml``.

The executed notebook and run logs are written to the returned ``artifact_dir``,
which lives beside the sandbox (never inside the git repo, never back in this
source tree).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

# Language → sample project directory under e2e/. The one place the mapping lives.
PROJECTS: dict[str, str] = {
    "typescript": "typescript-orders",
    "python": "python-inventory",
    "go": "go-ratelimit",
}

# Per-language dependency install from the committed lockfile. Runs inside the
# sandbox copy only — the templates never carry installed dependencies.
INSTALL_COMMANDS: dict[str, list[str]] = {
    "typescript": ["npm", "ci"],
    "python": ["uv", "sync"],
    "go": ["go", "mod", "download"],
}

# Copy filter: template trees are committed source + lockfiles only, but guard
# against a locally dirty checkout leaking installed deps or run artifacts.
_COPY_IGNORE = shutil.ignore_patterns(
    ".git",
    "node_modules",
    ".venv",
    "coverage",
    "cover.out",
    "__pycache__",
    ".stryker-tmp",
    "reports",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
)


@dataclass(frozen=True)
class Sandbox:
    """The result of provisioning: where the run happens and where outputs go."""

    language: str
    project: str
    sandbox_dir: str  # the git repo 3pwr drives (holds the project + run artifacts)
    artifact_dir: str  # beside the sandbox; executed notebook + logs land here
    key_file: str  # sandbox-scoped signing key (outside the sandbox git repo)


def _log(message: str) -> None:
    """Progress output — to stderr, so ``--json`` stdout stays machine-parseable."""
    print(message, file=sys.stderr, flush=True)


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    """Run a command, streaming output, and raise with context on failure."""
    printable = " ".join(cmd)
    _log(f"  $ {printable}")
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {printable}")


def _e2e_root() -> Path:
    """The ``e2e/`` directory — this file lives at ``e2e/harness/bootstrap.py``."""
    return Path(__file__).resolve().parent.parent


def _git_env() -> dict[str, str]:
    """A committer identity so ``git commit`` never fails on an unconfigured host."""
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", "e2e-harness")
    env.setdefault("GIT_AUTHOR_EMAIL", "e2e-harness@3powers.local")
    env.setdefault("GIT_COMMITTER_NAME", "e2e-harness")
    env.setdefault("GIT_COMMITTER_EMAIL", "e2e-harness@3powers.local")
    return env


def provision(
    language: str,
    *,
    e2e_root: Path | None = None,
    install_deps: bool = True,
) -> Sandbox:
    """Provision a fresh sandbox for ``language`` and return its paths.

    Set ``install_deps=False`` to skip the dependency install step (useful when a
    caller only needs the scaffolded git repo). All other steps always run.
    """
    if language not in PROJECTS:
        raise ValueError(
            f"unknown language {language!r}; expected one of {sorted(PROJECTS)}"
        )

    root = e2e_root or _e2e_root()
    project_name = PROJECTS[language]
    template = root / project_name / "project"
    if not template.is_dir():
        raise FileNotFoundError(f"sample project template not found: {template}")

    config_roles = root / "config" / "roles.yaml"
    if not config_roles.is_file():
        raise FileNotFoundError(f"shared headless config not found: {config_roles}")

    workspace = Path(tempfile.mkdtemp(prefix=f"3pwr-e2e-{language}-"))
    sandbox_dir = workspace / "project"
    artifact_dir = workspace / "artifacts"
    key_file = workspace / "signing.key"
    artifact_dir.mkdir(parents=True, exist_ok=True)

    _log(f"[bootstrap] provisioning {project_name} sandbox at {sandbox_dir}")

    # 1. Copy the template (source + lockfiles only).
    shutil.copytree(template, sandbox_dir, ignore=_COPY_IGNORE)

    # The adapter tests gate writes coverage to `coverage/lcov.info`. Node/pytest
    # coverage reporters create that directory themselves, but Go's gcov2lcov does
    # not — it fails if the parent is missing. The directory is gitignored in every
    # template, so pre-creating it here is invisible to git and safe for all
    # languages.
    (sandbox_dir / "coverage").mkdir(exist_ok=True)

    git_env = _git_env()

    # 2. git init + initial commit.
    _log("[bootstrap] initializing git substrate")
    _run(["git", "init", "-q", "-b", "main"], cwd=sandbox_dir, env=git_env)
    _run(["git", "add", "-A"], cwd=sandbox_dir, env=git_env)
    _run(
        ["git", "commit", "-q", "-m", "chore: sandbox baseline"],
        cwd=sandbox_dir,
        env=git_env,
    )

    # 3. Install dependencies from the committed lockfile.
    if install_deps:
        _log(f"[bootstrap] installing {language} dependencies")
        _run(INSTALL_COMMANDS[language], cwd=sandbox_dir, env=git_env)

    # 4. Make the sandbox 3Powers-ready. `init` lays down the `.3powers/` tree and
    #    mints the sandbox-scoped signing identity at --key-path (outside the repo).
    _log("[bootstrap] running 3pwr init")
    _run(
        ["3pwr", "init", "--yes", "--language", language, "--key-path", str(key_file)],
        cwd=sandbox_dir,
        env=git_env,
    )

    # 5. Export the signing key for every later 3pwr command in this process and in
    #    the sandbox git environment.
    os.environ["THREEPOWERS_SIGNING_KEY_FILE"] = str(key_file)
    git_env["THREEPOWERS_SIGNING_KEY_FILE"] = str(key_file)

    # 6. Overlay the single shared headless-integration config.
    _log("[bootstrap] seeding shared headless config")
    target_roles = sandbox_dir / ".3powers" / "config" / "roles.yaml"
    target_roles.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(config_roles, target_roles)

    # Commit the 3Powers scaffold so the sandbox starts from a clean tree.
    _run(["git", "add", "-A"], cwd=sandbox_dir, env=git_env)
    _run(
        ["git", "commit", "-q", "-m", "chore: 3powers init + shared config"],
        cwd=sandbox_dir,
        env=git_env,
    )

    sandbox = Sandbox(
        language=language,
        project=project_name,
        sandbox_dir=str(sandbox_dir),
        artifact_dir=str(artifact_dir),
        key_file=str(key_file),
    )
    _log(f"[bootstrap] sandbox ready: {sandbox.sandbox_dir}")
    return sandbox


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="bootstrap.py",
        description=(
            "Provision a throwaway 3pwr sandbox from a committed e2e sample "
            "project (copy → git init → deps → keygen → init → config overlay)."
        ),
    )
    parser.add_argument(
        "language",
        choices=sorted(PROJECTS),
        help="which sample project / language adapter to provision",
    )
    parser.add_argument(
        "--no-install",
        action="store_true",
        help="skip the dependency install step (git scaffold only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the sandbox paths as a single JSON object on stdout",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    sandbox = provision(args.language, install_deps=not args.no_install)
    if args.json:
        print(json.dumps(asdict(sandbox)))
    else:
        print(f"SANDBOX_DIR={sandbox.sandbox_dir}")
        print(f"ARTIFACT_DIR={sandbox.artifact_dir}")
        print(f"SIGNING_KEY_FILE={sandbox.key_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
