#!/usr/bin/env bash
# Every board event in lane mode goes through this helper (METHOD.md §13, two lanes): the event runs against the newest board
# on the coordination branch foreman-lanes and lands there by a push git can refuse, never by force.
#
#   bash board_push.sh [--tool <render_board.py>] <remote> <board path> -- <event args...>
#   bash board_push.sh [--tool <render_board.py>] <remote> <board path> --init
#
# <board path> is the local BOARD.json, e.g. foreman/projects/<slug>/BOARD.json; its path inside the branch is the
# same path relative to the repo root. The page beside it is publish.local_html (default board.html).
#
# An event, e.g. `-- start 02 --lane B --run J52`:
#   1. git fetch <remote> foreman-lanes; its tip is the base;
#   2. copy the base's BOARD.json and page to a temp folder and run the board tool there with
#      FOREMAN_BOARD_NO_OPEN=1 (the tool checks the event against the newest state, so a job another lane just
#      took is refused);
#   3. build the commit without touching the checkout: a temporary index (GIT_INDEX_FILE), read-tree <base>,
#      hash-object -w, update-index --cacheinfo, write-tree, commit-tree -p <base>; the message is one subject
#      line and nothing else, e.g. "Board: start 02 (Lane B, J52)";
#   4. git push <remote> <commit>:refs/heads/foreman-lanes, never force. Refused: back to step 1, at most 3
#      attempts in all, then stop and report. A push whose reply was lost (the push failed, but the branch tip
#      now is our commit or has it in its history) counts as landed (an identical BOARD.json is not proof: another
#      session may have pushed the same event, and then ours was refused);
#   5. on success, copy the two files into the local records folder (uncommitted: the job's records push
#      commits them).
# --init puts a board on foreman-lanes when lanes are switched on for its head: the first one creates the branch
# (a root commit holding only that BOARD.json and page), a later head's board is added on top. It refuses if the
# branch already holds that board. Only lifecycle events are pushed; read-only commands are refused.
#
# The board tool: --tool, else $BOARD_TOOL, else .claude/skills/f-board/render_board.py, else
# skills/f-board/render_board.py (both from the repo root).
# Test hooks (snippets/test_board_push.sh only): BOARD_PUSH_TEST_HOOK is run before the first push attempt;
# BOARD_PUSH_TEST_LOSE_REPLY=1 makes the first push report failure after it has pushed.
#
# Exit codes: 0 landed (or the branch created) · 1 the board tool refused the event (its exit 1 or 2; its
# message is shown; nothing pushed) · 2 bad usage · 3 no branch foreman-lanes on <remote> (lane mode is not on),
# or with --init: the branch already exists · 4 git failed (fetch, building the commit, a file missing) ·
# 5 the board tool failed (crash, or exit 4: page not written; nothing pushed) · 6 the push was refused
# 3 times: stop and report.
set -u
BRANCH=foreman-lanes
ATTEMPTS=3
usage() { echo "usage: board_push.sh [--tool <render_board.py>] <remote> <board path> (-- <event args...> | --init)"; exit 2; }

tool=${BOARD_TOOL:-}; init=0; pos=(); event=()
while [ $# -gt 0 ]; do
  case $1 in
    --tool) [ $# -ge 2 ] || usage; tool=$2; shift 2 ;;
    --init) init=1; shift ;;
    --) shift; event=("$@"); break ;;
    -*) echo "unknown option $1"; usage ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ ${#pos[@]} -eq 2 ] || usage
remote=${pos[0]}; board=${pos[1]}
if [ "$init" -eq 1 ] && [ ${#event[@]} -gt 0 ]; then echo "--init takes no event"; usage; fi
if [ "$init" -eq 0 ] && [ ${#event[@]} -eq 0 ]; then echo "no event given after --"; usage; fi

name=$(basename "$board")
dir=$(cd "$(dirname "$board")" 2>/dev/null && pwd) || { echo "the records folder does not exist: $(dirname "$board")"; exit 2; }
git -C "$dir" rev-parse --git-dir >/dev/null 2>&1 || { echo "not inside a git repository: $dir"; exit 2; }
git -C "$dir" remote get-url "$remote" >/dev/null 2>&1 || { echo "no remote named $remote in this repository"; exit 2; }
prefix=$(git -C "$dir" rev-parse --show-prefix) || exit 4
top=$(git -C "$dir" rev-parse --show-toplevel) || exit 4
for p in python3 python; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
    PY=$p; break
  fi
done
[ -n "${PY:-}" ] || { echo "no Python 3.9+ found (tried python3, python)"; exit 4; }
if [ -z "$tool" ]; then
  for t in "$top/.claude/skills/f-board/render_board.py" "$top/skills/f-board/render_board.py"; do
    [ -f "$t" ] && { tool=$t; break; }
  done
fi
[ -n "$tool" ] && [ -f "$tool" ] || { echo "board tool not found (give --tool or BOARD_TOOL)"; exit 2; }

ref="refs/remotes/$remote/$BRANCH"
tmp=$(mktemp -d) || exit 4
trap 'rm -rf "$tmp"' EXIT
export FOREMAN_BOARD_NO_OPEN=1

html_name() {  # <BOARD.json>: the page's file name
  local h
  h=$("$PY" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("publish", {}).get("local_html") or "board.html")' "$1" 2>/dev/null | tr -d '\r') \
    || { echo "$1 is not valid JSON"; return 1; }
  case $h in */*|*\\*|"") echo "publish.local_html must be a plain file name, not '$h'"; return 1 ;; esac
  echo "$h"
}
remote_has_branch() {  # 0 yes, 2 no, other: cannot tell
  git -C "$dir" ls-remote --exit-code "$remote" "refs/heads/$BRANCH" >/dev/null 2>&1
}
fetch_tip() {  # sets $base, or exits
  local out code
  if ! out=$(git -C "$dir" fetch -q "$remote" "+refs/heads/$BRANCH:$ref" 2>&1); then
    remote_has_branch; code=$?
    if [ "$code" -eq 2 ]; then
      echo "no branch $BRANCH on $remote: lane mode is not switched on (board_push.sh $remote $board --init creates it)"; exit 3
    fi
    echo "fetch from $remote failed:"; echo "$out"; exit 4
  fi
  base=$(git -C "$dir" rev-parse --verify -q "$ref^{commit}") || { echo "fetched, but $ref is missing"; exit 4; }
}
build_commit() {  # <parent or empty> <subject> <folder holding the two files>: prints the commit
  local parent=$1 subject=$2 src=$3 idx="$tmp/index" f blob tree
  rm -f "$idx"
  if [ -n "$parent" ]; then
    GIT_INDEX_FILE="$idx" git -C "$dir" read-tree "$parent" || return 1
  else
    GIT_INDEX_FILE="$idx" git -C "$dir" read-tree --empty || return 1
  fi
  for f in "$name" "$html"; do
    blob=$(git -C "$dir" hash-object -w --no-filters "$src/$f") || return 1
    GIT_INDEX_FILE="$idx" git -C "$dir" update-index --add --cacheinfo "100644,$blob,$prefix$f" || return 1
  done
  tree=$(GIT_INDEX_FILE="$idx" git -C "$dir" write-tree) || return 1
  if [ -n "$parent" ]; then
    git -C "$dir" commit-tree "$tree" -p "$parent" -m "$subject"
  else
    git -C "$dir" commit-tree "$tree" -m "$subject"
  fi
}
push_commit() {  # <commit>: the push's exit code; its output in $tmp/push.txt
  git -C "$dir" push "$remote" "$1:refs/heads/$BRANCH" > "$tmp/push.txt" 2>&1
}
install_local() {  # <folder>: copy the two files into the records folder
  local f
  for f in "$name" "$html"; do
    cp "$1/$f" "$dir/$f.push-tmp" && mv -f "$dir/$f.push-tmp" "$dir/$f" \
      || { rm -f "$dir/$f.push-tmp"; echo "landed, but could not write $dir/$f (run board_pull.sh)"; exit 4; }
  done
}

# ---- --init: create the branch from the local board -----------------------------------------------
if [ "$init" -eq 1 ]; then
  remote_has_branch; code=$?
  [ "$code" -eq 0 ] || [ "$code" -eq 2 ] || { echo "cannot reach $remote to check for $BRANCH"; exit 4; }
  parent=""
  if [ "$code" -eq 0 ]; then   # the branch exists (another head's board): add this board to it, never replace one
    fetch_tip
    if git -C "$dir" cat-file -e "$base:$prefix$name" 2>/dev/null; then
      echo "$BRANCH already holds $prefix$name: --init only adds a board that isn't there (use board_pull.sh)"; exit 3
    fi
    parent=$base
  fi
  [ -f "$board" ] || { echo "no local board: $board"; exit 2; }
  html=$(html_name "$board") || exit 4
  [ -f "$dir/$html" ] || { echo "no local page: $dir/$html (run render_board.py $board render first)"; exit 2; }
  out=$("$PY" "$tool" "$board" check 2>&1); code=$?
  [ "$code" -eq 0 ] || { echo "the local board does not pass check (exit $code):"; echo "$out"; exit 1; }
  version=$("$PY" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("version"))' "$board" | tr -d '\r')
  commit=$(build_commit "$parent" "Board: lanes switched on for $prefix$name (version $version)" "$dir") || { echo "could not build the commit"; exit 4; }
  if ! push_commit "$commit"; then
    cat "$tmp/push.txt"; echo "push refused: did another lane change $BRANCH meanwhile? Run --init again"; exit 6
  fi
  echo "CREATED $BRANCH on $remote at ${commit:0:7}: $prefix$name and $prefix$html (version $version)"
  exit 0
fi

# ---- an event --------------------------------------------------------------------------------------
lane=""; run=""; i=0
while [ $i -lt ${#event[@]} ]; do
  case ${event[$i]} in
    --lane) lane=${event[$((i + 1))]:-} ;;
    --run) run=${event[$((i + 1))]:-} ;;
  esac
  i=$((i + 1))
done
case ${event[0]} in
  start|close|halt|decided|add|split|covered|summary|topout|promote|footprint-check|reserve|unreserve|requires|footprint) ;;
  *) echo "'${event[0]}' is not a board event (read-only commands like check, next and width run on the pulled board)"; exit 2 ;;
esac
subject="Board: ${event[0]}"
case ${event[1]:-} in -*|"") ;; *) subject="$subject ${event[1]}" ;; esac
paren=""
[ -n "$lane" ] && paren="Lane $lane"
[ -n "$run" ] && paren="${paren:+$paren, }$run"
[ -n "$paren" ] && subject="$subject ($paren)"
subject=$(printf '%s' "$subject" | tr '\r\n' '  ')

attempt=1
while :; do
  fetch_tip                                                                                   # step 1
  work="$tmp/work$attempt"; mkdir -p "$work"                                                  # step 2
  git -C "$dir" cat-file blob "$base:$prefix$name" > "$work/$name" 2>/dev/null \
    || { echo "the branch $BRANCH (tip ${base:0:7}) has no $prefix$name"; exit 4; }
  html=$(html_name "$work/$name") || exit 4
  git -C "$dir" cat-file blob "$base:$prefix$html" > "$work/$html" 2>/dev/null || rm -f "$work/$html"
  "$PY" "$tool" "$work/$name" "${event[@]}" > "$tmp/tool.txt" 2>&1; code=$?
  cat "$tmp/tool.txt"
  case $code in
    0) ;;
    1|2) echo "REFUSED by the board tool (exit $code) against $BRANCH ${base:0:7}: nothing pushed"; exit 1 ;;
    *) echo "the board tool failed (exit $code): nothing pushed"; exit 5 ;;
  esac
  [ -f "$work/$html" ] || { echo "the board tool did not write $html: nothing pushed"; exit 5; }
  commit=$(build_commit "$base" "$subject" "$work") || { echo "could not build the commit"; exit 4; }   # step 3
  if [ "$attempt" -eq 1 ] && [ -n "${BOARD_PUSH_TEST_HOOK:-}" ]; then
    ( h=$BOARD_PUSH_TEST_HOOK; unset BOARD_PUSH_TEST_HOOK BOARD_PUSH_TEST_LOSE_REPLY; eval "$h" ) >> "$tmp/hook.txt" 2>&1
  fi
  # Two sessions making the same event in the same second build the very same commit (same tree, parent,
  # message, author and time), so a push of ours would "succeed" as a no-op on the other's. If the tip is
  # already exactly our commit before we push, it is theirs: replay, and the tool refuses the repeat.
  pre=$(git -C "$dir" ls-remote "$remote" "refs/heads/$BRANCH" 2>/dev/null | cut -f1)
  if [ "$pre" = "$commit" ]; then
    echo "the branch already holds this exact event from another session: replaying"
    attempt=$((attempt + 1)); [ "$attempt" -gt "$ATTEMPTS" ] && { echo "STOPPED after $ATTEMPTS attempts"; exit 6; }
    continue
  fi
  push_commit "$commit"; code=$?                                                              # step 4
  if [ "$attempt" -eq 1 ] && [ "${BOARD_PUSH_TEST_LOSE_REPLY:-}" = 1 ] && [ "$code" -eq 0 ]; then
    echo "(test: the push's reply is treated as lost)" > "$tmp/push.txt"; code=1
  fi
  if [ "$code" -eq 0 ]; then
    install_local "$work"                                                                     # step 5
    echo "LANDED $BRANCH ${commit:0:7}: $subject (attempt $attempt)"
    exit 0
  fi
  # the push failed: was it refused, or did only its reply get lost?
  if git -C "$dir" fetch -q "$remote" "+refs/heads/$BRANCH:$ref" >/dev/null 2>&1; then
    tip=$(git -C "$dir" rev-parse --verify -q "$ref^{commit}")
    if [ "$tip" = "$commit" ] || git -C "$dir" merge-base --is-ancestor "$commit" "$tip" 2>/dev/null; then
      install_local "$work"
      echo "LANDED $BRANCH ${commit:0:7}: $subject (the push's reply was lost; the branch already holds it)"
      exit 0
    fi
  fi
  if [ "$attempt" -ge "$ATTEMPTS" ]; then
    cat "$tmp/push.txt"
    echo "STOPPED: the push to $BRANCH was refused $ATTEMPTS times; nothing more pushed. Report it and pull the board."
    exit 6
  fi
  echo "push refused (attempt $attempt of $ATTEMPTS): replaying the event on the new tip"
  attempt=$((attempt + 1))
done
