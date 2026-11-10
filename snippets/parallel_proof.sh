#!/usr/bin/env bash
# The parallel proof: does a suite give the same verdicts with several workers as with one?
# (templates/TEST-ADAPTERS.md, "Speed: one suite at a time, several workers in it")
#
#   bash parallel_proof.sh <adapter file> <workers> <test paths...>
#
# Run it from the worktree, when no other session is running tests. It sources the repo's test adapter, runs the
# given tests once with TEST_WORKERS empty (one process), then three times with TEST_WORKERS=<workers>, each into
# its own files under $PROOF_DIR (default: a new temp folder), and prints one line per run, then the verdict:
#   PROVED <date>: <w> workers, one process <s>s, workers <a>/<b>/<c>s (<x>x faster), identical failing IDs (<n>) in 4 runs
#   NOT PROVED <date>: <why>
# PROVED needs: every run really ran (ran_ok), the four failing-ID lists identical, the workers really started
# (pytest-xdist reports them), and the slowest parallel run at least twice as fast as the single-process one.
# Exit 0 only on PROVED. A difference is a finding: never re-run it until it agrees.
set -u
adapter=${1:-}; workers=${2:-}
if [ -z "$adapter" ] || [ -z "$workers" ] || [ $# -lt 3 ]; then
  echo "usage: parallel_proof.sh <adapter file> <workers> <test paths...>"; exit 2
fi
shift 2
case $workers in *[!0-9]*|0|1) echo "workers must be a whole number of 2 or more"; exit 2 ;; esac
# shellcheck disable=SC1090
source "$adapter" || { echo "cannot source the adapter: $adapter"; exit 2; }
for f in run_tests failed_ids ran_ok; do
  declare -F "$f" >/dev/null || { echo "the adapter has no $f function"; exit 2; }
done
paths=("$@")
dir=${PROOF_DIR:-$(mktemp -d)}
mkdir -p "$dir" || exit 2
today=$(date +%Y-%m-%d)
why=""
declare -A secs

one() {  # <label> <workers or empty>
  local label=$1 s e ok
  TEST_WORKERS=$2
  s=$(date +%s)
  run_tests "$dir/$label.txt" "$dir/$label.exit" "${paths[@]}"
  e=$(date +%s)
  TEST_WORKERS=""
  secs[$label]=$((e - s))
  if ran_ok "$dir/$label.txt" "$dir/$label.exit"; then ok=yes; else ok=NO; why=${why:-"$label did not really run (exit $(cat "$dir/$label.exit")); see $dir/$label.txt"}; fi
  failed_ids "$dir/$label.txt" > "$dir/$label.ids"
  echo "$label: ran_ok=$ok exit=$(cat "$dir/$label.exit") failing=$(wc -l < "$dir/$label.ids" | tr -d ' ') seconds=${secs[$label]}"
}

one single ""
for k in 1 2 3; do one "workers$k" "$workers"; done

if [ -z "$why" ]; then
  for k in 1 2 3; do
    if ! cmp -s "$dir/single.ids" "$dir/workers$k.ids"; then
      why="workers$k failed different tests from the single-process run:"$'\n'"$(diff "$dir/single.ids" "$dir/workers$k.ids")"
      break
    fi
  done
fi
if [ -z "$why" ] && grep -q -- "-- Python" "$dir/single.txt"; then   # pytest: the workers must have started
  for k in 1 2 3; do
    grep -qE '(created: |^)[0-9]+(/[0-9]+)? workers' "$dir/workers$k.txt" || { why="workers$k ran in one process (is pytest-xdist installed?)"; break; }
  done
fi
slow=0
for k in 1 2 3; do [ "${secs[workers$k]}" -gt "$slow" ] && slow=${secs[workers$k]}; done
if [ -z "$why" ] && [ "${secs[single]}" -lt 10 ]; then
  why="not needed: one process takes ${secs[single]}s"
elif [ -z "$why" ] && [ $((2 * slow)) -gt "${secs[single]}" ]; then
  why="not worth it: one process ${secs[single]}s, slowest parallel run ${slow}s (needs at least 2x)"
fi

if [ -z "$why" ]; then
  x=$(awk -v a="${secs[single]}" -v b="$slow" 'BEGIN { printf "%.1f", (b > 0 ? a / b : 0) }')
  echo "PROVED $today: $workers workers, one process ${secs[single]}s, workers ${secs[workers1]}/${secs[workers2]}/${secs[workers3]}s (${x}x faster), identical failing IDs ($(wc -l < "$dir/single.ids" | tr -d ' ')) in 4 runs"
  exit 0
fi
echo "NOT PROVED $today: $why"
exit 1
