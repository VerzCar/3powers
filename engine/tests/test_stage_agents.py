"""Per-stage agent templates + the headless-CLI / role→model setup (AGENTX-FR-001…018, NFR-001…005).

Spec: specs-src/016-stage-agents-and-role-setup/spec.md (Spec ID AGENTX, Standard tier). Everything here
runs offline and deterministically (AGENTX-NFR-001): templates are plain files, the catalog is data,
and the setup is driven headlessly (pytest has no TTY, so init/setup are non-interactive and apply
the documented defaults — AGENTX-NFR-004).
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from threepowers import catalog, prompts, scaffold, style
from threepowers.cli import main
from threepowers.config import Settings

REPO = Path(__file__).resolve().parents[2]
ENGINE_SRC = REPO / "engine" / "src" / "threepowers"
BUNDLED = ENGINE_SRC / "scaffold" / "templates" / "agents"

STAGES = (
    "discovery",
    "specify",
    "clarify",
    "plan",
    "tasks",
    "oracle",
    "implement",
    "review",
    "characterize",
)

# Substrate machinery no shipped template may carry (AGENTX-FR-002).
FORBIDDEN = (".specify/", "$ARGUMENTS", "handoffs:", "extensions.yml", "before_specify")


def _init(root, *extra, key=None):
    argv = ["--root", str(root), "init", "--yes"]
    if key is not None:
        argv += ["--key-path", str(key)]
    return main(argv + list(extra))


def _proj(tmp_path) -> Settings:
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", key=tmp_path / "k.key") == 0
    return Settings(root=root)


def _front_matter(text: str) -> dict:
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---", "template must open with a metadata header"
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    return yaml.safe_load("\n".join(lines[1:end])) or {}


# --------------------------------------------------------------------------- AGENTX-FR-001 (the set)
def test_one_agent_template_per_dispatched_stage(tmp_path):
    """AGENTX-FR-001: after init, one readable markdown agent template exists per dispatched stage."""
    s = _proj(tmp_path)
    for step in STAGES:
        p = prompts.template_path(s.stage_templates_dir, step)
        assert p.is_file(), f"missing stage template {p.name}"
        assert prompts.template_body(p.read_text(encoding="utf-8")), f"{p.name} has no body"
    assert prompts.TEMPLATE_STEPS == STAGES


# --------------------------------------------------------------------------- AGENTX-FR-002 (the merge)
def test_templates_carry_merged_structure_and_no_substrate_machinery():
    """AGENTX-FR-002: the plan/tasks templates carry the merged reference structure; no shipped
    template contains a .specify/ script call, an extension-hook block, $ARGUMENTS, or handoffs:."""
    plan = (BUNDLED / "plan.agent.md").read_text(encoding="utf-8")
    # merged from the reference plan agent + the native planning agent:
    for token in ("Risk tier & gates", "context budget", "[P]", "file scope", "Think first"):
        assert token.lower() in plan.lower(), f"plan template lost merged structure: {token!r}"
    tasks = (BUNDLED / "implementation-plan.agent.md").read_text(encoding="utf-8")
    # merged from the reference implementation-plan agent + the tasks-checklist template:
    for token in ("- [ ] T###", "[REQ-ID]", "Depends on", "HANDOFF", "checklist"):
        assert token in tasks, f"tasks template lost merged structure: {token!r}"
    for p in sorted(BUNDLED.glob("*.agent.md")):
        text = p.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            assert token not in text, f"{p.name} carries substrate machinery {token!r}"


# --------------------------------------------------------------------------- AGENTX-FR-003 (discipline)
def test_templates_preserve_threepowers_discipline():
    """AGENTX-FR-003: each template states the discipline (directly and via the standing preamble
    the executive always prepends): spec is the law / no gate weakening / file scope / traceability."""
    for step in STAGES:
        body = prompts.template_body(
            prompts.template_path(BUNDLED, step).read_text(encoding="utf-8")
        )
        assert "spec" in body.lower(), f"{step} template never mentions the spec"
        assert "requirement" in body.lower() or "law" in body.lower() or "scope" in body.lower()
        # the assembled prompt always carries the standing discipline preamble:
        assembled = prompts.assemble(step, intent="x", body=body)
        assert "The spec is the law" in assembled
        assert "never weaken a gate" in assembled
        assert "declared file scope" in assembled
        assert "requirement id" in assembled


# --------------------------------------------------------------------------- AGENTX-FR-004 (header + context blocks)
def test_templates_declare_stage_artifact_role_and_reference_context_blocks():
    """AGENTX-FR-004: each template's header names its stage, artifact, and role; its body refers to
    the supplied run-context blocks and no external argument/script input channel."""
    for step in STAGES:
        text = prompts.template_path(BUNDLED, step).read_text(encoding="utf-8")
        fm = _front_matter(text)
        assert fm.get("stage") == step
        assert str(fm.get("artifact") or "").strip(), f"{step} declares no artifact"
        assert fm.get("role") in ("planner", "coder", "oracle", "reviewer")
        body = prompts.template_body(text)
        assert "run-context blocks" in body, f"{step} body never references the context blocks"


# --------------------------------------------------------------------------- AGENTX-FR-005 (resolution)
def test_repo_local_template_body_wins_and_fallback_is_builtin(tmp_path):
    """AGENTX-FR-005: a repo-local stage template supplies the instruction body; absent, empty, or
    unreadable falls back to the built-in instruction unchanged."""
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "plan.agent.md").write_text(
        "---\nstage: plan\nartifact: plan.md\nrole: planner\n---\n\nCUSTOM PLAN INSTRUCTIONS\n",
        encoding="utf-8",
    )
    body = prompts.stage_template_body(tdir, "plan")
    assert body == "CUSTOM PLAN INSTRUCTIONS"
    with_tpl = prompts.assemble("plan", intent="i", spec_text="S", body=body)
    assert "CUSTOM PLAN INSTRUCTIONS" in with_tpl
    assert prompts.stage_prompt_body("plan") not in with_tpl
    # absent → built-in
    assert prompts.stage_template_body(tdir, "tasks") == ""
    assert prompts.assemble("tasks", intent="i") == prompts.assemble("tasks", intent="i", body="")
    # empty (header only, no body) → built-in
    (tdir / "oracle.agent.md").write_text("---\nstage: oracle\n---\n", encoding="utf-8")
    assert prompts.stage_template_body(tdir, "oracle") == ""
    # unreadable (a directory at the template path) → built-in, no crash
    (tdir / "implement.agent.md").mkdir()
    assert prompts.stage_template_body(tdir, "implement") == ""
    assert prompts.resolve_body("implement", tdir) == prompts.stage_prompt_body("implement")


def test_template_resolution_is_deterministic_and_changes_only_the_body(tmp_path):
    """AGENTX-FR-005 (property): identical template bytes + identical run context yield identical
    prompt bytes; a template changes only the instruction body, never the context blocks or order."""
    tdir = tmp_path / "t"
    tdir.mkdir()
    (tdir / "plan.agent.md").write_text("---\nstage: plan\n---\nBODY X\n", encoding="utf-8")
    body = prompts.stage_template_body(tdir, "plan")
    a = prompts.assemble("plan", intent="i", spec_text="S", context="C", file_scope="F", body=body)
    b = prompts.assemble("plan", intent="i", spec_text="S", context="C", file_scope="F", body=body)
    assert a == b
    builtin = prompts.assemble("plan", intent="i", spec_text="S", context="C", file_scope="F")
    # the surrounding context blocks are byte-identical — only the body differs:
    assert a.split("BODY X", 1)[1] == builtin.split(prompts.stage_prompt_body("plan"), 1)[1]
    assert a.split("BODY X", 1)[0] == builtin.split(prompts.stage_prompt_body("plan"), 1)[0]


# --------------------------------------------------------------------------- AGENTX-FR-006/007 (phases + [P])
def test_plan_and_tasks_templates_demand_context_budgeted_phases():
    """AGENTX-FR-006: the plan/tasks templates decompose work into ordered phases with file scope,
    dependencies, and an estimated context size against the configured budget."""
    for name in ("plan.agent.md", "implementation-plan.agent.md"):
        text = (BUNDLED / name).read_text(encoding="utf-8").lower()
        assert "phase" in text
        assert "file scope" in text
        assert "depend" in text
        assert "context" in text and "budget" in text, f"{name} never references the budget"


def test_tasks_template_binds_parallel_marker_to_disjoint_scope_and_no_dependency():
    """AGENTX-FR-007: the tasks template allows [P] only for disjoint, dependency-free phases and
    forbids reading it as a licence to run overlapping/dependent phases concurrently."""
    text = (BUNDLED / "implementation-plan.agent.md").read_text(encoding="utf-8")
    assert "[P]" in text
    assert "disjoint" in text
    assert "dependency" in text.lower()
    assert "never a licence" in text


def test_implementation_plan_template_mandates_per_phase_gates_and_final_verification():
    """AGENTX-FR-006 (extension): every generated implementation plan runs the coding-section gates
    per phase over its file scope, and its LAST phase is always a dedicated Verification phase
    depending on all prior phases whose goal is a fully green build — named in the shipped agent
    template and its .3powers mirror, with the concrete gate command."""
    for base in (BUNDLED, REPO / ".3powers" / "templates" / "agents"):
        text = (base / "implementation-plan.agent.md").read_text(encoding="utf-8")
        assert "coding-section gates" in text or "coding gate" in text.lower(), base
        assert "3pwr gate run --path" in text, base
        assert "Verification" in text and "all prior phases" in text, base
        assert "fully green build" in text, base
        # the output skeleton itself carries the final Verification phase depending on all others
        assert "## Phase N: Verification" in text, base
        assert "**Depends on**: all prior phases" in text, base


def test_implement_template_makes_the_coding_gate_mandatory():
    """AGENTX-FR-008 (extension): the implement template promotes validate-as-you-go to a mandatory
    per-phase coding gate — run the gates after each phase, fix everything before reporting done;
    a phase with a red coding gate is not complete — and asks for the per-change summary the engine
    folds into changelog.md."""
    for base in (BUNDLED, REPO / ".3powers" / "templates" / "agents"):
        text = (base / "implement.agent.md").read_text(encoding="utf-8")
        assert "coding gate" in text.lower(), base
        assert "mandatory" in text.lower(), base
        assert "A phase with a red coding gate" in text, base
        assert "changelog.md" in text, base
        assert "Change summary" in text, base


def test_plan_surfaces_carry_no_judicial_label_or_model_family_table():
    """AGENTX-FR-002 (de-judicialized plan doc): the plan agent template (both copies), the built-in
    plan prompt body, and the plan document template carry no "Judicial" label and no
    role→model-family table — tier→gates and requirement→phase coverage stay. roles.yaml diversity
    enforcement is untouched by this (it was never parsed from the plan doc)."""
    surfaces = [
        (BUNDLED / "plan.agent.md").read_text(encoding="utf-8"),
        (REPO / ".3powers" / "templates" / "agents" / "plan.agent.md").read_text(encoding="utf-8"),
        (REPO / ".3powers" / "templates" / "plan-template.md").read_text(encoding="utf-8"),
        prompts.stage_prompt_body("plan"),
    ]
    for text in surfaces:
        assert "Judicial" not in text
        assert "model-family" not in text and "model family" not in text.lower()
        assert "Risk tier & gates" in text or "risk tier" in text.lower()


# --------------------------------------------------------------------------- AGENTX-FR-008 (implement discipline)
def test_implement_template_batches_independent_tasks_and_stops_out_of_scope():
    """AGENTX-FR-008: the implement template states the batch-independent / serialize-dependencies
    discipline and the file-scope stop condition (3PWR-FR-017)."""
    text = (BUNDLED / "implement.agent.md").read_text(encoding="utf-8")
    assert "independent" in text.lower() and "proceed together" in text
    assert "serialized" in text or "serialize" in text
    assert "STOP" in text and "re-spec" in text


def test_implement_template_mandates_subagents_for_parallel_tasks():
    """Plan 033 Track G (RUNVIS): both implement.agent.md copies state plainly that [P]-marked
    tasks MUST run via the agent's own sub-agents, and that the engine's concurrent dispatch of
    disjoint [P] phases is separate and not the agent's to manage."""
    for base in (BUNDLED, REPO / ".3powers" / "templates" / "agents"):
        text = (base / "implement.agent.md").read_text(encoding="utf-8")
        assert "MUST be executed via your own sub-agents" in text, base
        assert "one sub-agent per" in text, base
        assert "already dispatched by the engine as separate fresh sessions" in text, base


# --------------------------------------------------------------------------- AGENTX-FR-009 / NFR-003 (seeding)
def test_seeding_is_idempotent_and_never_clobbers_a_hand_edited_template(tmp_path):
    """AGENTX-FR-009 / AGENTX-NFR-003: init seeds the templates when absent, preserves hand-edits,
    and re-running converges to the same on-disk state."""
    s = _proj(tmp_path)
    edited = s.stage_templates_dir / "plan.agent.md"
    edited.write_text("---\nstage: plan\n---\nMY TUNED PLAN\n", encoding="utf-8")
    # a removed template is re-seeded:
    (s.stage_templates_dir / "implementation-plan.agent.md").unlink()
    out = scaffold.seed_stage_templates(s)
    assert out["plan.agent.md"] == "kept"
    assert out["implementation-plan.agent.md"] == "created"
    assert edited.read_text(encoding="utf-8").endswith("MY TUNED PLAN\n")
    again = scaffold.seed_stage_templates(s)
    assert all(v == "kept" for v in again.values())


# --------------------------------------------------------------------------- AGENTX-FR-010 (retirement)
def test_example_templates_reference_set_is_retired():
    """AGENTX-FR-010: the curated example-templates folder is gone and nothing in the engine or the
    docs references it as a runtime input (a docs mention of the retirement itself is not an input)."""
    assert not (REPO / ".3powers" / "templates" / "example-templates").exists()
    for f in ENGINE_SRC.rglob("*"):
        if f.is_file() and f.suffix in (".py", ".md", ".yaml", ".yml"):
            assert "example-templates" not in f.read_text(encoding="utf-8", errors="ignore"), (
                f"engine still references example-templates: {f}"
            )
    for f in (REPO / "docs").rglob("*"):
        if f.is_file() and f.suffix == ".md":
            for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "example-templates" in line and "retire" not in line:
                    raise AssertionError(f"{f} references example-templates as an input: {line!r}")


# --------------------------------------------------------------------------- AGENTX-FR-011/012/013 (setup writes)
def test_roles_setup_writes_full_blocks_for_every_role(tmp_path):
    """AGENTX-FR-011/012: the setup binds each role to the declared integration with a complete
    block — model_family, model, integration, label — and require_dispatch present for the oracle."""
    s = _proj(tmp_path)
    rc = main(
        [
            "--root",
            str(s.root),
            "config",
            "roles",
            "setup",
            "--yes",
            "--integration",
            "copilot",
            "--planner",
            "claude-opus-4.8",
            "--coder",
            "gpt-5.5",
            "--oracle",
            "claude-opus-4.8",
            "--reviewer",
            "gpt-5.5",
        ]
    )
    assert rc == 0
    roles = (yaml.safe_load(s.roles_path.read_text(encoding="utf-8")) or {}).get("roles") or {}
    assert roles["planner"] == {
        "model_family": "anthropic",
        "model": "claude-opus-4.8",
        "integration": "copilot",
        "label": "Claude Opus 4.8",
    }
    assert roles["coder"]["model_family"] == "openai"
    assert roles["coder"]["model"] == "gpt-5.5"
    assert roles["coder"]["integration"] == "copilot"
    assert roles["coder"]["label"] == "GPT 5.5"
    assert roles["oracle"]["model_family"] == "anthropic"
    assert roles["oracle"]["require_dispatch"] is False  # present, documented default
    assert roles["reviewer"]["label"] == "GPT 5.5"


def test_setup_leaves_the_project_run_ready(tmp_path):
    """AGENTX-FR-013: after the setup, every configurable role has a concrete pin and the coder
    integration resolves — no manual role editing is required before `3pwr run`."""
    from threepowers import runpreflight

    s = _proj(tmp_path)
    assert (
        main(
            ["--root", str(s.root), "config", "roles", "setup", "--yes", "--integration", "claude"]
        )
        == 0
    )
    for role in ("planner", "coder", "oracle", "reviewer"):
        pin = s.role_model_pin(role)
        assert pin is not None and pin["integration"], f"{role} not run-ready"
    # the roles that had no binding were filled with the declared integration's default:
    assert s.role_model_pin("planner")["integration"] == "claude"
    assert s.role_model_pin("coder")["integration"] == "claude"
    assert runpreflight.resolve_coder_integration(s, None) == "claude"


# --------------------------------------------------------------------------- AGENTX-FR-014 (re-runnable, non-destructive)
def test_config_roles_setup_updates_only_reconfigured_roles(tmp_path):
    """AGENTX-FR-014 / AGENTX-NFR-003: the standalone command reconfigures only the named roles and
    preserves every unrelated roles.yaml field."""
    s = _proj(tmp_path)
    data = yaml.safe_load(s.roles_path.read_text(encoding="utf-8")) or {}
    data["custom_note"] = "hands off"  # an unrelated, hand-edited field
    baseline_reviewer = dict((data.get("roles") or {}).get("reviewer") or {})
    s.roles_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    rc = main(
        [
            "--root",
            str(s.root),
            "config",
            "roles",
            "setup",
            "--yes",
            "--integration",
            "codex",
            "--planner",
            "openai/gpt-5.5",
        ]
    )
    assert rc == 0
    after = yaml.safe_load(s.roles_path.read_text(encoding="utf-8")) or {}
    assert after["custom_note"] == "hands off"
    assert after["diversity_level"] == "family"
    assert after["roles"]["planner"]["model"] == "openai/gpt-5.5"
    # roles already bound and not named stay untouched (the documented non-interactive default):
    assert after["roles"]["reviewer"] == baseline_reviewer


# --------------------------------------------------------------------------- AGENTX-FR-015/016 (the catalog)
def test_catalog_offers_models_per_integration_and_fills_fields_consistently(tmp_path):
    """AGENTX-FR-015: the catalog is keyed by integration; a listed selection fills model_family/
    model/label exactly from the entry."""
    s = _proj(tmp_path)
    cat = catalog.load_catalog(s)
    assert "copilot" in catalog.integrations(cat)
    entries = catalog.models_for(cat, "copilot")
    assert entries, "the copilot integration offers no models"
    entry = catalog.entry_for(cat, "copilot", "gpt-5.5")
    assert entry == {"model": "gpt-5.5", "family": "openai", "label": "GPT 5.5"}
    default = catalog.default_for(cat, "copilot")
    assert default is not None and default["model"]


def test_catalog_is_editable_data_and_freeform_models_stay_selectable(tmp_path):
    """AGENTX-FR-016: editing the catalog data offers a new model with no engine change; a model
    absent from the catalog is accepted free-form with a derived family."""
    s = _proj(tmp_path)
    data = yaml.safe_load(s.models_catalog_path.read_text(encoding="utf-8"))
    data["integrations"]["copilot"]["models"].append(
        {"model": "brandnew-9", "family": "acme", "label": "Brand New 9"}
    )
    s.models_catalog_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    cat = catalog.load_catalog(s)
    assert catalog.entry_for(cat, "copilot", "brandnew-9") == {
        "model": "brandnew-9",
        "family": "acme",
        "label": "Brand New 9",
    }
    # free-form fallback: not listed anywhere, family derived where the value encodes it
    assert catalog.entry_for(cat, "copilot", "acme/unlisted-1") is None
    assert catalog.derive_family("acme/unlisted-1") == "acme"
    assert catalog.derive_family("claude-next-1") == "anthropic"
    assert catalog.derive_family("gpt-7") == "openai"
    assert catalog.derive_family("mystery-model") == ""
    # slugify-style purity: deriving twice is stable
    assert catalog.derive_family(catalog.derive_family("acme/unlisted-1") + "/x") == "acme"


def test_malformed_catalog_falls_back_to_shipped_defaults(tmp_path):
    """AGENTX-FR-016 (edge): a malformed models.yaml degrades to the shipped catalog, never a crash."""
    s = _proj(tmp_path)
    s.models_catalog_path.write_text(":: not yaml ::\n- broken", encoding="utf-8")
    cat = catalog.load_catalog(s)
    assert "claude" in catalog.integrations(cat)  # the bundled fallback answered


# --------------------------------------------------------------------------- AGENTX-FR-017 (require_dispatch explained)
def test_require_dispatch_is_explained_where_the_config_lives(tmp_path):
    """AGENTX-FR-017: the shipped roles.yaml and the rewritten roles.yaml both explain
    require_dispatch — meaning, default, and when to enable it — and the docs carry it too."""
    shipped = (ENGINE_SRC / "scaffold" / "config" / "roles.yaml").read_text(encoding="utf-8")
    assert "require_dispatch" in shipped and "read-path-isolation" in shipped
    s = _proj(tmp_path)
    scaffold.set_role_model(s, "oracle", model="anthropic/claude-opus-4-8", integration="claude")
    rewritten = s.roles_path.read_text(encoding="utf-8")
    assert "require_dispatch" in rewritten
    assert "default false" in rewritten
    assert "oracle dispatch" in rewritten  # what it enforces
    docs = (REPO / "docs" / "cli-reference.md").read_text(encoding="utf-8")
    assert "require_dispatch" in docs


# --------------------------------------------------------------------------- AGENTX-FR-018 (diversity warns, never blocks)
def test_same_family_judiciary_warns_and_names_the_deviation_path(tmp_path, capsys):
    """AGENTX-FR-018: a setup where the oracle resolves to the coder's family warns, names the
    signed deviation path, and still completes."""
    s = _proj(tmp_path)
    capsys.readouterr()  # drain init's output
    rc = main(
        [
            "--root",
            str(s.root),
            "config",
            "roles",
            "setup",
            "--yes",
            "--integration",
            "copilot",
            "--coder",
            "claude-opus-4.8",
            "--oracle",
            "claude-opus-4.8",
        ]
    )
    assert rc == 0  # recommended, never forced
    err = capsys.readouterr().err
    assert "anthropic" in err and "model diversity is recommended" in err
    assert "3pwr deviation --gate model_diversity" in err


# --------------------------------------------------------------------------- AGENTX-NFR-001 (deterministic, offline)
def test_setup_and_resolution_are_deterministic(tmp_path):
    """AGENTX-NFR-001: identical inputs yield identical written role config and identical
    assembled prompts — no network, no model call."""
    s = _proj(tmp_path)
    args = [
        "--root",
        str(s.root),
        "config",
        "roles",
        "setup",
        "--yes",
        "--integration",
        "copilot",
        "--planner",
        "gpt-5.5",
    ]
    assert main(args) == 0
    first = s.roles_path.read_bytes()
    assert main(args) == 0
    assert s.roles_path.read_bytes() == first  # converges — same bytes on re-run
    body = prompts.stage_template_body(s.stage_templates_dir, "specify")
    assert prompts.assemble("specify", intent="i", body=body) == prompts.assemble(
        "specify", intent="i", body=body
    )


# --------------------------------------------------------------------------- AGENTX-NFR-002 (authoring layer only)
def test_role_and_template_changes_never_touch_verdict_or_ledger(tmp_path):
    """AGENTX-NFR-002: a role-config or template change produces no change in any verdict or ledger
    record — the trust spine never reads templates or the catalog."""
    from threepowers.verdict import GateResult, Verdict

    def fixed_verdict() -> dict:
        v = Verdict(spec_id="AGENTX", tier="Standard", adapter="python")
        v.verdict_id = "fixed"
        v.created_at = "2026-07-05T00:00:00Z"
        v.add(GateResult(gate="tests", status="pass"))
        return v.finalize().to_dict()

    s = _proj(tmp_path)
    before = json.dumps(fixed_verdict(), sort_keys=True)
    (s.stage_templates_dir / "implement.agent.md").write_text(
        "---\nstage: implement\n---\nTOTALLY DIFFERENT\n", encoding="utf-8"
    )
    scaffold.set_role_model(s, "coder", model="x/y", integration="copilot", label="X Y")
    after = json.dumps(fixed_verdict(), sort_keys=True)
    assert before == after
    # and no trust-spine module imports the authoring layer:
    for mod in ("canonical", "keys", "ledger", "verify", "verdict", "gates"):
        text = (ENGINE_SRC / f"{mod}.py").read_text(encoding="utf-8")
        for token in ("from .catalog", "import catalog", "stage_template", "models_catalog"):
            assert token not in text, f"{mod} reads authoring data ({token})"


# --------------------------------------------------------------------------- AGENTX-NFR-004 (non-interactive, byte-stable)
def test_non_interactive_setup_is_promptless_and_json_byte_stable(tmp_path, capsys):
    """AGENTX-NFR-004: a --json setup prompts for nothing and the same run twice yields
    byte-identical stdout."""
    s = _proj(tmp_path)
    capsys.readouterr()  # drain init's output
    args = [
        "--root",
        str(s.root),
        "config",
        "roles",
        "setup",
        "--json",
        "--integration",
        "copilot",
        "--planner",
        "gpt-5.5",
        "--coder",
        "gpt-5.5",
        "--oracle",
        "claude-opus-4.8",
        "--reviewer",
        "gemini-2.5-pro",
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert "\033[" not in first
    payload = json.loads(first)
    assert payload["integration"] == "copilot"
    assert payload["roles"]["oracle"]["model_family"] == "anthropic"
    assert main(args) == 0
    assert capsys.readouterr().out == first


# --------------------------------------------------------------------------- AGENTX-NFR-005 (no new dependency)
def test_no_new_runtime_dependency():
    """AGENTX-NFR-005: the stage-agent layer added no runtime dependency — the set is exactly
    {cryptography, PyYAML, rich} (rich being the rendering dependency TRIX-FR-001 permits)."""
    text = (REPO / "engine" / "pyproject.toml").read_text(encoding="utf-8")
    block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    deps = {ln.strip().strip('",') for ln in block.splitlines() if ln.strip()}
    assert deps == {"cryptography>=42", "PyYAML>=6", "rich>=13.7,<15"}


# --------------------------------------------------------------------------- init integration (AGENTX-FR-009/011)
def test_init_reports_seeded_templates_and_stays_promptless(tmp_path, capsys):
    """AGENTX-FR-009/NFR-004: a non-interactive init seeds the stage templates (reported in --json)
    and prompts for nothing."""
    root = tmp_path / "proj"
    root.mkdir()
    assert _init(root, "--language", "python", "--json", key=tmp_path / "k.key") == 0
    payload = json.loads(capsys.readouterr().out)
    seeded = payload["stage_templates"]
    assert set(seeded) == {prompts.template_name(s) for s in STAGES}
    assert all(v == "created" for v in seeded.values())


def test_diversity_warning_helper_is_stderr_only(tmp_path, capsys):
    """AGENTX-FR-018 (property): the warning goes to stderr, never stdout, keeping --json stable."""
    from threepowers.cli import _warn_diversity

    s = _proj(tmp_path)
    scaffold.set_role_model(s, "coder", model="anthropic/claude-opus-4-8", integration="claude")
    scaffold.set_role_model(s, "oracle", model="anthropic/claude-opus-4-8", integration="claude")
    capsys.readouterr()  # drain init's output
    warned = _warn_diversity(s, style.Styler(enabled=False))
    out, err = capsys.readouterr()
    assert warned == ["oracle"]
    assert out == ""
    assert "model_diversity" in err
