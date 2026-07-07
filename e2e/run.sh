#!/bin/sh
# One-command runner for the 3pwr end-to-end notebook kit.
#
#   ./e2e/run.sh <typescript|python|go> [--intent "…"] [--integration NAME]
#                                       [--approver NAME] [--keep] [--check]
#
# Maps a language to its fixed notebook and executes it headlessly with papermill
# from the pinned harness environment. The executed notebook (with outputs) and a
# run log are written to the sandbox's artifact directory — never back into this
# repo. The wrapper exits with papermill's status.
#
#   --check   deterministic, zero-credential path: baseline gates + `3pwr run
#             --dry-run`, no live agent dispatch (sets DRY_RUN=true).
#   --keep    keep the sandbox after the run for inspection (sets KEEP_SANDBOX).
set -eu

usage() {
  cat >&2 <<'EOF'
usage: ./e2e/run.sh <typescript|python|go> [options]

options:
  --intent "<text>"     override the notebook's canned INTENT
  --integration NAME    override the headless agent backend (e.g. copilot)
  --approver NAME       recorded approver for the two human gates (default: e2e-harness)
  --keep                keep the sandbox after the run (default: teardown)
  --check               deterministic no-agent path: baseline gates + dry-run
  -h, --help            show this help
EOF
}

if [ "$#" -eq 0 ]; then
  usage
  exit 2
fi

LANG_ARG=""
INTENT=""
INTEGRATION=""
APPROVER="e2e-harness"
KEEP_SANDBOX="false"
DRY_RUN="false"

while [ "$#" -gt 0 ]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --intent)
      INTENT="${2:?--intent needs a value}"
      shift 2
      ;;
    --integration)
      INTEGRATION="${2:?--integration needs a value}"
      shift 2
      ;;
    --approver)
      APPROVER="${2:?--approver needs a value}"
      shift 2
      ;;
    --keep)
      KEEP_SANDBOX="true"
      shift
      ;;
    --check)
      DRY_RUN="true"
      shift
      ;;
    typescript|python|go)
      LANG_ARG="$1"
      shift
      ;;
    *)
      echo "error: unknown argument '$1'" >&2
      usage
      exit 2
      ;;
  esac
done

if [ -z "$LANG_ARG" ]; then
  echo "error: a language (typescript|python|go) is required" >&2
  usage
  exit 2
fi

# Locate the kit relative to this script so it runs from any working directory.
E2E_DIR=$(cd "$(dirname "$0")" && pwd)

case "$LANG_ARG" in
  typescript) PROJECT_DIR="$E2E_DIR/typescript-orders" ;;
  python)     PROJECT_DIR="$E2E_DIR/python-inventory" ;;
  go)         PROJECT_DIR="$E2E_DIR/go-ratelimit" ;;
esac

NOTEBOOK="$PROJECT_DIR/run.ipynb"
if [ ! -f "$NOTEBOOK" ]; then
  echo "error: notebook not found: $NOTEBOOK" >&2
  exit 1
fi

# The executed notebook + log land beside the sandbox, discovered by the notebook
# itself at teardown. We stage them under a per-run temp dir the notebook reports;
# until then, keep a local run log next to a throwaway executed copy in the system
# temp area so nothing is written into the repo.
RUN_STAMP=$(date +%Y%m%d-%H%M%S)
OUT_DIR="${TMPDIR:-/tmp}/3pwr-e2e-run-$LANG_ARG-$RUN_STAMP"
mkdir -p "$OUT_DIR"
EXECUTED="$OUT_DIR/executed.ipynb"
RUN_LOG="$OUT_DIR/run.log"

echo "e2e: running $LANG_ARG notebook (dry_run=$DRY_RUN, keep=$KEEP_SANDBOX)" >&2
echo "e2e: executed notebook -> $EXECUTED" >&2
echo "e2e: run log           -> $RUN_LOG" >&2

set -- \
  "$NOTEBOOK" "$EXECUTED" \
  --log-output \
  -p LANGUAGE "$LANG_ARG" \
  -p APPROVER "$APPROVER" \
  -p KEEP_SANDBOX "$KEEP_SANDBOX" \
  -p DRY_RUN "$DRY_RUN"

if [ -n "$INTENT" ]; then
  set -- "$@" -p INTENT "$INTENT"
fi
if [ -n "$INTEGRATION" ]; then
  set -- "$@" -p INTEGRATION "$INTEGRATION"
fi

# Run papermill from the pinned harness environment; tee output to the run log.
status=0
uv run --project "$E2E_DIR/harness" papermill "$@" 2>&1 | tee "$RUN_LOG" || status=$?

echo "e2e: papermill exited $status" >&2
exit "$status"
