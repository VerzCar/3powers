"""Locate the 3Powers root and load the single-source-of-truth configuration.

Every gate threshold (diff-coverage, mutation score, model diversity, verification
spend) is read from one risk-tier table. Roles are bound to model *families* so the
engine can refuse to run when judicial independence is violated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

THREEPOWERS_DIRNAME = ".3powers"

# The scanner gates that honor scan.yaml exclusions — the loader always returns these keys.
_SCAN_TOOLS = ("secret_scan", "dependency_scan", "sast")


@dataclass(frozen=True)
class AutoFixPrefs:
    """The resolved auto-fix loop preferences (``auto-fix.yaml``).

    ``enabled`` gates the run-path loop (a red Verify in ``3pwr run`` auto mode); a standalone
    ``3pwr gate fix`` runs the loop regardless. ``max_attempts`` bounds the coder attempts before
    the loop gives up to the human summary. ``scope_to_failed`` optionally narrows each coder
    dispatch to the failed gates' files. Never a gate, verdict, or ledger input."""

    enabled: bool
    max_attempts: int
    scope_to_failed: bool


@dataclass
class Settings:
    root: Path

    @property
    def dir(self) -> Path:
        return self.root / THREEPOWERS_DIRNAME

    @property
    def ledger_path(self) -> Path:
        return self.dir / "ledger.jsonl"

    @property
    def pubkey_path(self) -> Path:
        return self.dir / "keys" / "ledger.pub"

    @property
    def oracle_pubkey_path(self) -> Path:
        """The distinct judiciary (oracle) public key, if one was minted."""
        return self.dir / "keys" / "oracle.pub"

    @property
    def verdicts_dir(self) -> Path:
        return self.dir / "verdicts"

    @property
    def risk_tiers_path(self) -> Path:
        return self.dir / "config" / "risk-tiers.yaml"

    @property
    def roles_path(self) -> Path:
        return self.dir / "config" / "roles.yaml"

    @property
    def design_oracles_path(self) -> Path:
        return self.dir / "config" / "design-oracles.yaml"

    @property
    def adapters_dir(self) -> Path:
        return self.dir / "adapters"

    @property
    def agents_dir(self) -> Path:
        """Declarative agent-backend manifests for the native executive."""
        return self.dir / "agents"

    @property
    def onboarding_path(self) -> Path:
        """Advisory onboarding preferences written by ``3pwr init``."""
        return self.dir / "config" / "onboarding.yaml"

    @property
    def context_config_path(self) -> Path:
        """The advisory per-model context-budget configuration."""
        return self.dir / "config" / "context.yaml"

    @property
    def ui_config_path(self) -> Path:
        """Optional human-output preferences — color mode, verbosity, layout.

        Presentation only: never a gate, verdict, or ledger input. A missing or malformed file falls
        back to the shipped defaults, so its absence changes nothing."""
        return self.dir / "config" / "ui.yaml"

    @property
    def git_config_path(self) -> Path:
        """The git-integration preferences — branch prefix, base branch, 3pwr author.

        Applied to the run's git handling only; a missing or malformed file falls back to the
        documented defaults with at most one warning (see :mod:`threepowers.gitflow`)."""
        return self.dir / "config" / "git.yaml"

    @property
    def scan_config_path(self) -> Path:
        """The auditable per-tool scanner-exclusion preferences (``scan.yaml``).

        Committed team configuration for the scanner gates only. A missing or malformed file
        yields no exclusions; the core private-key check can never be disabled here."""
        return self.dir / "config" / "scan.yaml"

    @property
    def notifications_config_path(self) -> Path:
        """The opt-in notification channels for a paused/failed/completed run.

        Convenience only — never a trust or enforcement channel: a missing file disables
        notifications; a malformed file warns once and falls back (see
        :mod:`threepowers.notify`). Secrets are referenced from the environment."""
        return self.dir / "config" / "notifications.yaml"

    @property
    def constitution_path(self) -> Path:
        """The project constitution — part of every phase's reload set."""
        return self.dir / "memory" / "constitution.md"

    @property
    def stage_templates_dir(self) -> Path:
        """The per-stage agent templates — one editable markdown per dispatched stage.

        A repo-local ``<step>.agent.md`` here (``implementation-plan.agent.md`` for the tasks step)
        supplies that stage's instruction body; an absent, empty, or unreadable file falls back to
        the engine's built-in instruction."""
        return self.dir / "templates" / "agents"

    @property
    def models_catalog_path(self) -> Path:
        """The per-integration model/label catalog — editable data, not code.

        Read by init and ``3pwr config roles setup`` to offer per-role model choices; a missing or
        malformed file falls back to the shipped catalog defaults plus free-form entry."""
        return self.dir / "config" / "models.yaml"

    @property
    def auto_fix_config_path(self) -> Path:
        """The auto-fix loop preferences (``auto-fix.yaml``).

        Governs the harness's bounded, code-only remediation loop — whether the run-path loop is on,
        the coder-attempt budget, and whether to scope a dispatch to the failed gates' files. A
        missing or malformed file falls back to the shipped defaults; never a gate or ledger input."""
        return self.dir / "config" / "auto-fix.yaml"

    def context_budget(self, model: str = "") -> int:
        """The advisory context budget in tokens for ``model``.

        Read from ``context.yaml``: a per-model entry under ``models:`` wins, else the file's
        ``budget_tokens``, else the shipped default (~110k). Deterministic — the same config bytes
        always resolve the same budget — and strictly advisory: exceeding it warns and advises a
        split, never a failed gate."""
        from .phases import DEFAULT_BUDGET_TOKENS

        data = _load_yaml(self.context_config_path)
        candidate: Any = None
        models = data.get("models") or {}
        if model and isinstance(models, dict) and model in models:
            candidate = models[model]
        if candidate is None:
            candidate = data.get("budget_tokens")
        try:
            n = int(candidate) if candidate is not None else 0
        except (TypeError, ValueError):
            n = 0
        return n if n > 0 else DEFAULT_BUDGET_TOKENS

    def default_mode(self) -> str:
        """The recorded ``3pwr run`` autonomy default (advisory): ``auto`` | ``commit``.

        Defaults to ``auto`` when no preference was recorded. Advisory only: it selects the *default*
        mode when ``--mode`` is omitted and never suppresses a mandatory human gate."""
        auto = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("auto_mode")
        if auto is None:
            return "auto"
        return "auto" if bool(auto) else "commit"

    def auto_commit(self) -> bool:
        """Whether per-stage auto-commit is enabled. Defaults to True (the wanted workflow).

        Advisory: it commits each successful lifecycle stage; it never touches the ledger or a gate."""
        v = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("auto_commit")
        return True if v is None else bool(v)

    def auto_fix(self) -> AutoFixPrefs:
        """The resolved auto-fix loop preferences — tolerant, deterministic, never raises.

        Read from ``auto-fix.yaml``: ``enabled`` (default True — the run-path loop is on for
        ``3pwr run`` auto mode), ``max_attempts`` (default 3, clamped to at least 1), and
        ``scope_to_failed`` (default False). A missing or malformed file, or an out-of-shape value,
        falls back to the shipped default for that field. Advisory only — it steers the code-only
        remediation loop and is never a gate, verdict, or ledger input."""
        data = _load_yaml(self.auto_fix_config_path)
        enabled = data.get("enabled")
        raw_max = data.get("max_attempts")
        try:
            max_attempts = int(raw_max) if raw_max is not None else 3
        except (TypeError, ValueError):
            max_attempts = 3
        return AutoFixPrefs(
            enabled=True if enabled is None else bool(enabled),
            max_attempts=max_attempts if max_attempts >= 1 else 3,
            scope_to_failed=bool(data.get("scope_to_failed", False)),
        )

    def dispatch_timeout(self) -> int:
        """The per-stage dispatch timeout in seconds. Defaults to 1800 (30 min).

        Advisory config only: it bounds how long one agent dispatch may run before it is terminated and
        reported as a dispatch failure. Never affects a gate, verdict, or the ledger."""
        v = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("dispatch_timeout_s")
        if not isinstance(v, (int, str)):
            return 1800
        try:
            n = int(v)
        except ValueError:
            return 1800
        return n if n > 0 else 1800

    def dispatch_retries(self) -> int:
        """How many times a *failed* dispatch is retried before the stage is reported failed.

        Defaults to 1 (one retry on a transient failure). A stage is attempted at most ``retries + 1`` times;
        a successful stage is never retried. Advisory config only — never a gate or verdict."""
        v = (_load_yaml(self.onboarding_path).get("defaults") or {}).get("dispatch_retries")
        if not isinstance(v, (int, str)):
            return 1
        try:
            n = int(v)
        except ValueError:
            return 1
        return n if n >= 0 else 1

    def default_tier(self) -> str:
        """The recorded default risk tier a new spec starts at (advisory).

        Defaults to ``Standard`` when no preference was recorded. Advisory only: it never lowers a
        threshold or removes a gate; it seeds the tier a fresh spec is authored at."""
        tier = str(
            (_load_yaml(self.onboarding_path).get("defaults") or {}).get("tier") or ""
        ).strip()
        return tier or "Standard"

    def load_ui(self) -> tuple[dict[str, str], bool]:
        """Resolved UI preferences from ``ui.yaml`` + whether the file was malformed.

        Human-output presentation only — never a gate or ledger input. Tolerant and never raises: a
        missing file yields the shipped defaults with ``malformed=False``; a file that is not valid
        YAML (or not a mapping) yields the defaults with ``malformed=True`` so the caller can warn
        once. Deterministic and pure in the file bytes. Only recognized keys/values are honored;
        anything else falls back to its default."""
        defaults = {"color_mode": "auto", "verbosity": "normal", "layout": "normal"}
        allowed = {
            "color_mode": ("auto", "always", "never"),
            "verbosity": ("quiet", "normal", "verbose"),
            "layout": ("normal", "compact"),
        }
        path = self.ui_config_path
        if not path.exists():
            return defaults, False
        data: Any = {}
        malformed = False
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            malformed = True
            data = {}
        if data is None:
            data = {}  # an empty file is valid — use the defaults
        elif not isinstance(data, dict):
            malformed = True  # a scalar/list is not a preferences mapping
            data = {}
        prefs = dict(defaults)
        for key, choices in allowed.items():
            val = str(data.get(key) or "").strip().lower()
            if val in choices:
                prefs[key] = val
        return prefs, malformed

    def ui_preferences(self) -> dict[str, str]:
        """The resolved UI preferences; shorthand for ``load_ui()[0]``."""
        return self.load_ui()[0]

    def load_risk_tiers(self) -> dict[str, Any]:
        return _load_yaml(self.risk_tiers_path)

    def _scan_config(self) -> dict[str, Any]:
        """The parsed ``scan.yaml`` mapping — ``{}`` when the file is absent or malformed."""
        path = self.scan_config_path
        if not path.exists():
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return {}
        return data if isinstance(data, dict) else {}

    def load_scan_ignores(self) -> dict[str, dict[str, list[str]]]:
        """Per-tool scanner exclusions from ``scan.yaml`` — tolerant, deterministic, never raises.

        Returns ``{tool: {"ignore": [globs], "ignore_rules": [rule ids]}}`` for each scanner
        gate (``secret_scan``, ``dependency_scan``, ``sast``), with empty lists when the file,
        a tool's section, or a key is missing or malformed — mirroring the ``git.yaml``
        handling. Only non-empty string entries are honored. The exclusions shape what the
        scanners read — and are always reported in their gate output — never whether they run.
        """
        out: dict[str, dict[str, list[str]]] = {
            tool: {"ignore": [], "ignore_rules": []} for tool in _SCAN_TOOLS
        }
        data = self._scan_config()
        for tool in _SCAN_TOOLS:
            section = data.get(tool)
            if not isinstance(section, dict):
                continue
            for key in ("ignore", "ignore_rules"):
                vals = section.get(key)
                if isinstance(vals, list):
                    out[tool][key] = [v for v in vals if isinstance(v, str) and v.strip()]
        return out

    def load_scan_advisories(self) -> list[dict[str, str]]:
        """The ``dependency_scan`` advisory allowlist from ``scan.yaml`` — tolerant, never raises.

        Returns the ``dependency_scan.advisories`` entries normalized to
        ``{"id": str, "reason": str, "until": str}`` — only mapping entries carrying a
        non-empty string ``id`` are kept, and ``until`` is stringified so an unquoted YAML
        date still round-trips as an ISO date. Whether an entry actually suppresses a
        finding (non-empty reason, unexpired ``until``) is enforced by the scanner itself,
        fail-closed — this loader only shapes the data.
        """
        section = self._scan_config().get("dependency_scan")
        if not isinstance(section, dict):
            return []
        raw = section.get("advisories")
        if not isinstance(raw, list):
            return []
        out: list[dict[str, str]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            vid = entry.get("id")
            if not isinstance(vid, str) or not vid.strip():
                continue
            reason = entry.get("reason")
            until = entry.get("until")
            out.append(
                {
                    "id": vid.strip(),
                    "reason": str(reason).strip() if reason is not None else "",
                    "until": str(until).strip() if until is not None else "",
                }
            )
        return out

    def load_roles(self) -> dict[str, Any]:
        return _load_yaml(self.roles_path)

    def oracle_require_dispatch(self) -> bool:
        """Policy: require an isolated headless-dispatch attestation at High-risk.

        Default False — the manual/in-IDE oracle flow (model-switch in the agent window) stays valid;
        a repo opts in by setting ``roles.oracle.require_dispatch: true`` once it adopts the workflow."""
        roles = self.load_roles()
        oracle = (roles.get("roles") or {}).get("oracle") or {}
        return bool(oracle.get("require_dispatch", False))

    def diversity_level(self) -> str:
        """How strictly model diversity is compared: ``family`` (default) or ``model``.

        ``family`` — the oracle and coder must be different model *families*.
        ``model``  — a different *model* in the same family qualifies (e.g. opus vs sonnet)."""
        level = str(self.load_roles().get("diversity_level", "family")).strip().lower()
        return level if level in ("family", "model") else "family"

    def coder_model(self) -> str:
        """The coder's full ``<family>/<model>`` if declared (for model-level diversity); else ''."""
        return ((self.load_roles().get("roles") or {}).get("coder") or {}).get("model", "") or ""

    def role(self, name: str) -> dict[str, Any]:
        """The raw configuration block for one role (empty dict when absent)."""
        return (self.load_roles().get("roles") or {}).get(name) or {}

    def coder_family(self) -> str:
        """The coder's model *family* — the explicit ``model_family`` when declared, else derived
        from its full ``model`` id. The explicit field wins because catalog-listed bindings may use
        bare, integration-native model ids (e.g. Copilot's ``claude-opus-4.8``) whose family the id
        does not encode."""
        from .oracle import family_of

        c = self.role("coder")
        return (str(c.get("model_family") or "") or family_of(str(c.get("model") or ""))).strip()

    def role_model_pin(self, name: str) -> dict[str, str] | None:
        """The concrete model pin for a role — ``{model, integration, label}`` — or ``None``.

        Reading a roles configuration that predates this feature (family-only, no ``model``) simply
        yields ``None`` here and never fails — the concrete-model fields are additive. ``label``
        falls back to the model id, so a pin always renders as ``<label> (<integration>)``."""
        r = self.role(name)
        model = str(r.get("model") or "").strip()
        if not model:
            return None
        return {
            "model": model,
            "integration": str(r.get("integration") or "").strip(),
            "label": str(r.get("label") or "").strip() or model,
        }

    def subagent_models(self) -> dict[str, str]:
        """The optional per-stage sub-agent model overrides — ``{step: model}``.

        Additive and off by default: an absent (or non-mapping) ``subagent_models`` block yields an
        empty map and changes nothing about dispatch. Each value is the model id the resolved
        integration expects for that stage's *sub-agents*; the main stage agent keeps its role
        model. Blank keys/values are dropped. A value absent from the ``models.yaml`` catalog stays
        usable (BYOK), matching the role model-pin tolerance — :meth:`subagent_model_warnings`
        surfaces the likely-typo case advisorily; it is never a gate."""
        raw = self.load_roles().get("subagent_models")
        if not isinstance(raw, dict):
            return {}
        out: dict[str, str] = {}
        for step, model in raw.items():
            key = str(step or "").strip()
            val = str(model or "").strip()
            if key and val:
                out[key] = val
        return out

    def subagent_model_warnings(self) -> list[str]:
        """Advisory warnings for ``subagent_models`` entries whose model is not in the catalog.

        A stage's dispatching integration is the oracle's for the ``oracle`` step, else the coder's.
        When that integration has a curated catalog and the pinned sub-agent model is not listed, one
        warning names the likely typo — the model is still used as-is (BYOK), never blocked. Empty
        when every entry resolves, when no ``subagent_models`` block is set, or when the integration
        is a free-form BYOK backend with no curated list. Never raises, never a gate."""
        from . import catalog as _catalog  # local import avoids a config↔catalog import cycle

        overrides = self.subagent_models()
        if not overrides:
            return []
        cat = _catalog.load_catalog(self)
        coder_intg = str(self.role("coder").get("integration") or "").strip()
        oracle_intg = str(self.role("oracle").get("integration") or "").strip()
        warnings: list[str] = []
        for step, model in overrides.items():
            integration = oracle_intg if step == "oracle" else coder_intg
            if not integration:
                continue
            listed = {e["model"] for e in _catalog.models_for(cat, integration)}
            if listed and model not in listed:
                warnings.append(
                    f"subagent_models.{step}: '{model}' is not in the {integration} catalog "
                    f"(models.yaml) — used as-is (BYOK); check for a typo"
                )
        return warnings


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_root(start: Path | None = None) -> Path:
    """Walk up from ``start`` (default cwd) to the directory holding ``.3powers/``."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / THREEPOWERS_DIRNAME).is_dir():
            return candidate
    raise FileNotFoundError(
        f"no {THREEPOWERS_DIRNAME}/ directory found from {cur} upward — run `3pwr init`"
    )


def tier_config(tiers: dict[str, Any], tier: str) -> dict[str, Any]:
    table = tiers.get("tiers", {})
    if tier not in table:
        raise KeyError(f"unknown risk tier {tier!r}; known: {sorted(table)}")
    return table[tier]


def model_diversity_ok(
    roles: dict[str, Any], role_a: str, role_b: str, level: str = "family"
) -> bool:
    """True iff two roles are *diverse enough* at ``level``.

    Compares each role's declared ``model`` (full ``<family>/<model>``) when present, else its
    ``model_family``. Delegates to ``oracle.diverse`` for a single source of truth."""
    from .oracle import diverse  # local import avoids any import cycle at module load

    table = roles.get("roles", {})
    a = table.get(role_a) or {}
    b = table.get(role_b) or {}
    a_id = (a.get("model") or a.get("model_family") or "").strip()
    b_id = (b.get("model") or b.get("model_family") or "").strip()
    return diverse(a_id, b_id, level)
