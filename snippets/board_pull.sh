#!/usr/bin/env bash
# Read the board in lane mode: fetch the coordination branch and copy its board into the records folder.
# (PLAN-lanes §3: in lane mode the branch foreman-lanes holds the board's one true copy; every reader pulls first.)
#
#   bash board_pull.sh <remote> <board path>
#
# <board path> is the local BOARD.json, e.g. foreman/projects/<slug>/BOARD.json. Its path inside the branch is the
# same path relative to the repo root. The script fetches <remote>'s foreman-lanes into
# refs/remotes/<remote>/foreman-lanes, then copies that tip's BOARD.json and its page (publish.local_html,
# default board.html) beside <board path>. It never touches the checkout's index or HEAD; the two copied files
# show as changed in git status until a records push commits them, which is meant.
#
# Exit codes: 0 copied · 2 bad usage · 3 the branch foreman-lanes does not exist on <remote> (lane mode is not
# switched on: board_push.sh --init creates it) · 4 git failed (fetch, the remote unreachable, a file missing
# on the branch) or a file could not be written.
set -u
BRANCH=foreman-lanes
remote=${1:-}; board=${2:-}
if [ -z "$remote" ] || [ -z "$board" ] || [ $# -ne 2 ]; then
  echo "usage: board_pull.sh <remote> <board path>"; exit 2
fi
name=$(basename "$board")
dir=$(cd "$(dirname "$board")" 2>/dev/null && pwd) || { echo "the records folder does not exist: $(dirname "$board")"; exit 2; }
git -C "$dir" rev-parse --git-dir >/dev/null 2>&1 || { echo "not inside a git repository: $dir"; exit 2; }
git -C "$dir" remote get-url "$remote" >/dev/null 2>&1 || { echo "no remote named $remote in this repository"; exit 2; }
prefix=$(git -C "$dir" rev-parse --show-prefix) || exit 4
for p in python3 python; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
    PY=$p; break
  fi
done
[ -n "${PY:-}" ] || { echo "no Python 3.9+ found (tried python3, python)"; exit 4; }

ref="refs/remotes/$remote/$BRANCH"
if ! out=$(git -C "$dir" fetch -q "$remote" "+refs/heads/$BRANCH:$ref" 2>&1); then
  git -C "$dir" ls-remote --exit-code "$remote" "refs/heads/$BRANCH" >/dev/null 2>&1; code=$?
  if [ "$code" -eq 0 ]; then
    echo "fetch from $remote failed:"; echo "$out"; exit 4
  elif [ "$code" -eq 2 ]; then
    echo "no branch $BRANCH on $remote: lane mode is not switched on (board_push.sh $remote $board --init creates it)"; exit 3
  fi
  echo "cannot reach $remote:"; echo "$out"; exit 4
fi
tip=$(git -C "$dir" rev-parse --verify -q "$ref^{commit}") || { echo "fetched, but $ref is missing"; exit 4; }

tmp=$(mktemp -d) || exit 4
trap 'rm -rf "$tmp"' EXIT
git -C "$dir" cat-file blob "$tip:$prefix$name" > "$tmp/$name" 2>/dev/null \
  || { echo "the branch $BRANCH (tip ${tip:0:7}) has no $prefix$name"; exit 4; }
html=$("$PY" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("publish", {}).get("local_html") or "board.html")' "$tmp/$name" 2>/dev/null | tr -d '\r') \
  || { echo "$prefix$name on the branch is not valid JSON"; exit 4; }
case $html in */*|*\\*|"") echo "publish.local_html must be a plain file name, not '$html'"; exit 4 ;; esac
git -C "$dir" cat-file blob "$tip:$prefix$html" > "$tmp/$html" 2>/dev/null \
  || { echo "the branch $BRANCH (tip ${tip:0:7}) has no $prefix$html"; exit 4; }

for f in "$name" "$html"; do
  cp "$tmp/$f" "$dir/$f.pull-tmp" && mv -f "$dir/$f.pull-tmp" "$dir/$f" || { rm -f "$dir/$f.pull-tmp"; echo "could not write $dir/$f"; exit 4; }
done
echo "PULLED $BRANCH ${tip:0:7}: $prefix$name and $prefix$html copied into $dir"
exit 0
