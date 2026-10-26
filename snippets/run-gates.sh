#!/usr/bin/env bash
# Per-task gate capture for one job. Copy it into the day folder as run-gates-<ticket>.sh,
# fill in the CONFIG block and the GATES block, then call it with a task label:
#   bash run-gates-<ticket>.sh t0      (then t1, t2, ... so captures never overwrite each other)
#
# What it guarantees (SETUP.md section 3):
#   - one <gate>.txt (full output) and one <gate>.exit (the exit code) per gate, in LOG;
#   - a summary.txt with every gate's result, ending "ALL DONE";
#   - every run strips the paid API keys first, and gates run one at a time.
# A code area that no gate covers gets its own copy of this file, with gates that name
# that area's tests by explicit path.
set +e

# ---- CONFIG: fill these in for the job -------------------------------------------------
TASK="${1:?task label required, e.g. t0}"
WT="<absolute path to the job's worktree>"
LOG="<absolute path to the day folder>/${TASK}-<ticket>-gates"
MAIN_REF="origin/main"                 # the repo profile's remote and main branch
PAID_KEYS=(OPENROUTER_API_KEY OPENAI_API_KEY ANTHROPIC_API_KEY)   # every paid key the tests could reach
# -----------------------------------------------------------------------------------------

# a label names one capture: refuse to reuse it, so earlier evidence is never overwritten
if [ -e "$LOG" ]; then echo "capture folder already exists: $LOG (choose a new label)"; exit 3; fi
mkdir -p "$(dirname "$LOG")" && mkdir "$LOG" || { echo "could not create $LOG"; exit 3; }
cd "$WT" || { echo "worktree not found: $WT"; exit 1; }
SUMMARY="$LOG/summary.txt"
: > "$SUMMARY"
STRIP=()
for k in "${PAID_KEYS[@]}"; do STRIP+=(-u "$k"); done

{
  echo "GATE CAPTURE - <ticket> / $TASK"
  echo "worktree: $WT"
  echo "HEAD:     $(git rev-parse --short HEAD)  $(git rev-parse HEAD)"
  echo "$MAIN_REF: $(git rev-parse --short "$MAIN_REF")  $(git rev-parse "$MAIN_REF")"
  echo "started:  $(date -Iseconds)"
  echo "====="
} | tee -a "$SUMMARY"

# run_gate <name> <command...>: capture one gate; never stops the run on a red gate.
run_gate() {
  local name="$1"
  shift
  local start end rc
  start=$(date +%s)
  echo "START $name $(date -Iseconds)" | tee -a "$SUMMARY"
  env "${STRIP[@]}" "$@" > "$LOG/${name}.txt" 2>&1
  rc=$?
  end=$(date +%s)
  echo "$rc" > "$LOG/${name}.exit"
  echo "END $name rc=$rc elapsed=$((end - start))s" | tee -a "$SUMMARY"
  tail -n 20 "$LOG/${name}.txt" | tee -a "$SUMMARY"
  echo "-----" | tee -a "$SUMMARY"
  return 0
}

# ---- GATES: the repo profile's documented gates, one line each, in order -----------------
# Examples (replace with the profile's own commands):
#   run_gate g1_unit         python -m pytest tests/unit -q -p no:cacheprovider
#   run_gate g2_integration  env TEST_DB_URL="<disposable database only>" python -m pytest tests/integration -q
#   run_gate g3_lint         ruff check src tests
#   run_gate g4_types        mypy src
#   run_gate g5_js           npm test --silent
run_gate g1_example echo "replace the GATES block with the profile's gates"
# -----------------------------------------------------------------------------------------

# Say plainly what these gates do NOT cover, so green is never read as more than it is.
echo "COVERAGE NOTE: <the code areas and test folders no gate above runs>" | tee -a "$SUMMARY"
echo "ALL DONE $(date -Iseconds)" | tee -a "$SUMMARY"
echo "=====" | tee -a "$SUMMARY"
git status --short | tee -a "$SUMMARY"
echo "HEAD after: $(git rev-parse --short HEAD) $(git rev-parse HEAD)" | tee -a "$SUMMARY"
