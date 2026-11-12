#!/usr/bin/env bash
# land_tested.sh: lane mode's landing (METHOD.md §10, "In lane mode"): main only ever gets the exact tree that
# was proven, and a push git refuses when main moved closes the race between two lanes.
#
#   land_tested.sh moved  <remote> <main> <base>
#       Has <remote>/<main> moved since <base> (the base the final checks ran on)? Fetches first. Prints one word:
#         same          main is still <base>
#         records-only  only records moved, so land as today
#         product       product code moved: merge main into the job branch and prove that commit again
#       Inside the records folders, code still counts as product: foreman/test-adapter.sh (it runs every test)
#       and any .py, .sh, .mjs, .js or .ts file (a repo's own tools that CI runs).
#   land_tested.sh land   <remote> <main> <proven head> "<subject>"
#       Make the merge commit in a throwaway worktree of <remote>/<main> (git merge --no-ff, subject only, no
#       trailer), refuse unless its tree is the proven head's (records aside), and push it as a fast-forward,
#       never force. Exit 6: main moved (by product code, or since the fetch): go back to `moved`. A push whose
#       reply was lost is recognised: main's first-parent history already holds a merge of <proven head>.
#   land_tested.sh verify <remote> <main> <proven head>
#       The tree check: M = the merge on main's first-parent line whose second parent is the proven head (main
#       may have moved on since, by records or the other lane); M's tree equals the proven head's, records aside.
#
# RECORDS_DIRS (default "foreman work-sessions") names the records folders, from the repo profile's records root.
# With a separate records repo, product main never moves by records, so `moved` never prints records-only.
# Paths are always taken from the repository's top, whatever folder this runs in.
# Exit codes: 0 ok · 1 verify failed · 2 bad usage · 4 git failure · 6 the push was refused (main moved).
set -u

die() { echo "land_tested: $2" >&2; exit "$1"; }
[ $# -ge 1 ] || die 2 "usage: land_tested.sh moved|land|verify ..."
cmd="$1"; shift
top=$(git rev-parse --show-toplevel 2>/dev/null) || die 2 "not inside a git repository"
cd "$top" || die 4 "cannot enter $top"
RECORDS_DIRS="${RECORDS_DIRS:-foreman work-sessions}"
ADAPTER="foreman/test-adapter.sh"

trees_match() {   # $1 $2: commits; the same tree once the records folders are left out, code inside them counted in.
  # Two diffs, not one pathspec: in git an exclude beats an include, so "-- . ':!foreman' foreman/test-adapter.sh"
  # would never see a change to the adapter. Every pathspec is anchored at the top (":(top)").
  local d spec=(":(top)") code=(":(top)$ADAPTER")
  for d in $RECORDS_DIRS; do
    spec+=(":(top,exclude)$d")
    code+=(":(top,glob)$d/**/*.py" ":(top,glob)$d/**/*.sh" ":(top,glob)$d/**/*.mjs" ":(top,glob)$d/**/*.js" ":(top,glob)$d/**/*.ts")
  done
  git diff --quiet "$1" "$2" -- "${spec[@]}" && git diff --quiet "$1" "$2" -- "${code[@]}"
}

landing_of() {   # $1 the ref of main, $2 the proven head: the merge on main's first-parent line whose ^2 is it
  git log --first-parent --merges --format='%H %P' "$1" 2>/dev/null | awk -v h="$2" '$3 == h { print $1; exit }'
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
    done_m=$(landing_of "$remote/$main" "$h")
    if [ -n "$done_m" ]; then echo "already landed: $done_m on $remote/$main is the merge of $h"; exit 0; fi
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
    done_m=$(landing_of "$remote/$main" "$h")
    if [ -n "$done_m" ]; then
      echo "landed (the push's reply was lost): $done_m on $remote/$main"; exit 0
    fi
    die 6 "the push was refused: $remote/$main moved since the fetch; run moved again"
    ;;
  verify)
    [ $# -eq 3 ] || die 2 "usage: land_tested.sh verify <remote> <main> <proven head>"
    remote="$1" main="$2" head="$3"
    git fetch -q "$remote" "$main" || die 4 "git fetch failed"
    h=$(git rev-parse "$head^{commit}") || die 2 "proven head $head is not a commit"
    m=$(landing_of "$remote/$main" "$h")
    [ -n "$m" ] || die 1 "no merge of the proven head $h on $remote/$main's first-parent line"
    trees_match "$m" "$h" || die 1 "M $m's tree differs from the proven head's outside the records folders"
    echo "VERIFIED: M $m, M^2 = proven head, trees equal outside the records folders"
    ;;
  *) die 2 "unknown command $cmd (moved, land, verify)";;
esac
