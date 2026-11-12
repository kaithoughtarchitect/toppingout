#!/usr/bin/env bash
# land_tested.sh: lane mode's landing (PLAN-lanes §5, METHOD.md §10): main only ever gets the exact tree that
# was proven, and a push git refuses when main moved closes the race between two lanes.
#
#   land_tested.sh moved  <remote> <main> <base>
#       Has <remote>/<main> moved since <base> (the base the final checks ran on)? Fetches first. Prints one word:
#         same          main is still <base>
#         records-only  only records moved (nothing outside the records folders), so land as today
#         product       product code moved: merge main into the job branch and prove that commit again
#       foreman/test-adapter.sh counts as product: it runs every test.
#   land_tested.sh land   <remote> <main> <proven head> "<subject>"
#       Make the merge commit in a throwaway worktree of <remote>/<main> (git merge --no-ff, subject only, no
#       trailer) and push it as a fast-forward, never force. Exit 6: main moved since the fetch (git refused the
#       push): go back to `moved`. A push whose reply was lost is recognised: if <remote>/<main>'s second parent
#       is already <proven head>, it landed.
#   land_tested.sh verify <remote> <main> <proven head>
#       The tree check: M = <remote>/<main>; M^2 is the proven head, and M's tree equals the proven head's with
#       the records folders left out.
#
# RECORDS_DIRS (default "foreman work-sessions") names the records folders, from the repo profile's records root.
# With a separate records repo, product main never moves by records, so `moved` never prints records-only.
# Exit codes: 0 ok · 1 verify failed · 2 bad usage · 4 git failure · 6 the push was refused (main moved).
set -u

die() { echo "land_tested: $2" >&2; exit "$1"; }
[ $# -ge 1 ] || die 2 "usage: land_tested.sh moved|land|verify ..."
cmd="$1"; shift
RECORDS_DIRS="${RECORDS_DIRS:-foreman work-sessions}"
ADAPTER="foreman/test-adapter.sh"

trees_match() {   # $1 $2: commits; same tree once the records folders are left out, the adapter counted in.
  # Two diffs, not one pathspec: in git an exclude beats an include, so "-- . ':!foreman' foreman/test-adapter.sh"
  # would never see a change to the adapter.
  local d spec=(".")
  for d in $RECORDS_DIRS; do spec+=(":(exclude)$d"); done
  git diff --quiet "$1" "$2" -- "${spec[@]}" && git diff --quiet "$1" "$2" -- "$ADAPTER"
}

case "$cmd" in
  moved)
    [ $# -eq 3 ] || die 2 "usage: land_tested.sh moved <remote> <main> <base>"
    remote="$1" main="$2" base="$3"
    git fetch -q "$remote" "$main" || die 4 "git fetch $remote $main failed"
    tip=$(git rev-parse "$remote/$main") || die 4 "no $remote/$main"
    b=$(git rev-parse "$base^{commit}") || die 2 "base $base is not a commit"
    if [ "$tip" = "$b" ]; then echo same; exit 0; fi
    git merge-base --is-ancestor "$b" "$tip" || die 4 "$remote/$main does not contain the base $base (history rewritten?)"
    if trees_match "$b" "$tip"; then echo records-only; else echo product; fi
    ;;
  land)
    [ $# -eq 4 ] || die 2 "usage: land_tested.sh land <remote> <main> <proven head> \"<subject>\""
    remote="$1" main="$2" head="$3" subject="$4"
    case "$subject" in *$'\n'*) die 2 "the merge message is a subject only, one line";; esac
    git fetch -q "$remote" "$main" || die 4 "git fetch failed"
    h=$(git rev-parse "$head^{commit}") || die 2 "proven head $head is not a commit"
    if [ "$(git rev-parse -q --verify "$remote/$main^2" 2>/dev/null)" = "$h" ]; then
      echo "already landed: $remote/$main is the merge of $h"; exit 0
    fi
    wt=$(mktemp -d "${TMPDIR:-/tmp}/land-XXXXXX") && rmdir "$wt"
    git worktree add -q --detach "$wt" "$remote/$main" || die 4 "could not make a worktree of $remote/$main"
    cleanup() { git worktree remove --force "$wt" >/dev/null 2>&1; }
    trap cleanup EXIT
    if ! git -C "$wt" merge -q --no-ff --no-edit -m "$subject" "$h"; then
      git -C "$wt" merge --abort >/dev/null 2>&1
      die 4 "the merge of $h onto $remote/$main conflicts: it was not the proven tree; go back to moved"
    fi
    m=$(git -C "$wt" rev-parse HEAD)
    # the invariant: what lands is the proven tree. If main moved by product code since the proof, the merge's
    # tree differs from the proven head's: refuse before pushing anything.
    trees_match "$m" "$h" || die 6 "main moved by product code since $h was proven: the merge would land a tree nobody proved; run moved, merge main in and prove it again"
    if git -C "$wt" push -q "$remote" "HEAD:refs/heads/$main" 2>/dev/null && [ -z "${LAND_TEST_LOSE_REPLY:-}" ]; then
      echo "landed: $m on $remote/$main"; exit 0
    fi
    git fetch -q "$remote" "$main" || die 4 "git fetch after the push failed"
    if [ "$(git rev-parse -q --verify "$remote/$main^2" 2>/dev/null)" = "$h" ] \
       || { git merge-base --is-ancestor "$m" "$remote/$main" 2>/dev/null; }; then
      echo "landed (the push's reply was lost): $(git rev-parse "$remote/$main") on $remote/$main"; exit 0
    fi
    die 6 "the push was refused: $remote/$main moved since the fetch; run moved again"
    ;;
  verify)
    [ $# -eq 3 ] || die 2 "usage: land_tested.sh verify <remote> <main> <proven head>"
    remote="$1" main="$2" head="$3"
    git fetch -q "$remote" "$main" || die 4 "git fetch failed"
    m=$(git rev-parse "$remote/$main") || die 4 "no $remote/$main"
    h=$(git rev-parse "$head^{commit}") || die 2 "proven head $head is not a commit"
    p2=$(git rev-parse -q --verify "$m^2" 2>/dev/null) || die 1 "M $m is not a merge commit"
    [ "$p2" = "$h" ] || die 1 "M^2 is $p2, not the proven head $h"
    trees_match "$m" "$h" || die 1 "M's tree differs from the proven head's outside the records folders"
    echo "VERIFIED: M $m, M^2 = proven head, trees equal outside the records folders"
    ;;
  *) die 2 "unknown command $cmd (moved, land, verify)";;
esac
