#!/usr/bin/env bash
# Tests for board_pull.sh and board_push.sh (METHOD.md §13, two lanes). Self-contained: temp folders only, a bare repo as
# the remote, two clones (two lanes), the v1 board template as the fixture.
#
#   bash snippets/test_board_push.sh
#
# Prints PASS or FAIL per case; exit 0 only when every case passes.
set -u
here=$(cd "$(dirname "$0")" && pwd)
pkg=$(cd "$here/.." && pwd)
PUSH="$here/board_push.sh"; PULL="$here/board_pull.sh"
REAL_TOOL="$pkg/skills/f-board/render_board.py"
FIXTURE="$pkg/skills/f-schedule/templates/BOARD.json"
for p in python3 python; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >/dev/null 2>&1; then
    PY=$p; break
  fi
done
[ -n "${PY:-}" ] || { echo "FAIL: no Python 3.9+"; exit 1; }

root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
fails=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; shift; for m in "$@"; do echo "  $m"; done; fails=$((fails + 1)); }

# A fake tool that records the FOREMAN_BOARD_NO_OPEN it was given, then runs the real one.
TOOL="$root/tool.py"
native() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }  # paths Python can open
cat > "$TOOL" <<EOF
import os, runpy, sys
with open(r"$(native "$root")/no_open.log", "a", encoding="utf-8") as f:
    f.write(repr(os.environ.get("FOREMAN_BOARD_NO_OPEN")) + "\n")
sys.argv = [r"$(native "$REAL_TOOL")"] + sys.argv[1:]
sys.path.insert(0, os.path.dirname(sys.argv[0]))
runpy.run_path(sys.argv[0], run_name="__main__")
EOF
export BOARD_TOOL="$TOOL"
# the scripts must override this: =dry would print "would open" if the tool were let open a browser
export FOREMAN_BOARD_NO_OPEN=dry

REC=foreman/projects/example-project
B="$REC/BOARD.json"
setup_clone() {  # <dir>
  git clone -q "$root/remote.git" "$1" 2>/dev/null
  git -C "$1" config user.name "Test Lane"; git -C "$1" config user.email "lane@example.invalid"
  git -C "$1" config commit.gpgsign false
}
git init -q --bare "$root/remote.git"
git init -q "$root/seed"
git -C "$root/seed" config user.name "Test Lane"; git -C "$root/seed" config user.email "lane@example.invalid"
git -C "$root/seed" config commit.gpgsign false
mkdir -p "$root/seed/$REC"
cp "$FIXTURE" "$root/seed/$B"
(cd "$root/seed" && FOREMAN_BOARD_NO_OPEN=1 "$PY" "$REAL_TOOL" "$B" render >/dev/null) || { echo "FAIL setup: render"; exit 1; }
echo "product" > "$root/seed/app.txt"
git -C "$root/seed" add -A 2>/dev/null && git -C "$root/seed" commit -q -m "Seed" && git -C "$root/seed" branch -M main
git -C "$root/seed" push -q "$root/remote.git" main 2>/dev/null
git --git-dir="$root/remote.git" symbolic-ref HEAD refs/heads/main
setup_clone "$root/A"; setup_clone "$root/B"
A="$root/A"; BB="$root/B"
rtip() { git --git-dir="$root/remote.git" rev-parse -q --verify refs/heads/foreman-lanes; }
rjson() { git --git-dir="$root/remote.git" cat-file blob "foreman-lanes:$B"; }
jfield() {  # <json file or -> <job> <field>
  "$PY" -c 'import json, sys; d = json.load(sys.stdin if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8")); print([j for j in d["jobs"] if j["id"] == sys.argv[2]][0].get(sys.argv[3]))' "$@" | tr -d '\r'
}
snapshot() {  # <clone>: HEAD, branch, index, and status outside the two board files
  local c=$1
  git -C "$c" rev-parse HEAD
  git -C "$c" symbolic-ref HEAD
  git -C "$c" ls-files --stage
  git -C "$c" status --porcelain -- . ":!$REC/BOARD.json" ":!$REC/board.html"
}
# leave unrelated work in clone A: a staged change and an unstaged one, to see they survive
echo "staged" > "$A/staged.txt"; git -C "$A" add staged.txt 2>/dev/null
echo "dirty" >> "$A/app.txt"
before=$(snapshot "$A")
log="$root/all-output.txt"; : > "$log"
run() {  # <clone> <script> <args...>: runs in the clone; output in $out, exit in $rc
  local c=$1; shift
  out=$(cd "$c" && bash "$@" 2>&1); rc=$?
  printf '%s\n' "$out" >> "$log"
}

# ---- (a) init creates the branch with only the two files --------------------------------------------
run "$A" "$PULL" origin "$B"; rc_pull_before=$rc; out_pull_before=$out
run "$A" "$PUSH" origin "$B" --init; rc_init=$rc; out_init=$out
run "$BB" "$PUSH" origin "$B" --init; rc_init2=$rc
files=$(git --git-dir="$root/remote.git" ls-tree -r --name-only foreman-lanes 2>/dev/null | tr '\n' ' ')
parents=$(git --git-dir="$root/remote.git" rev-list --parents -n1 foreman-lanes 2>/dev/null | wc -w | tr -d ' ')
same=$(cmp -s <(rjson) "$A/$B" && echo yes)
if [ "$rc_pull_before" -eq 3 ] && [ "$rc_init" -eq 0 ] && [ "$files" = "$REC/BOARD.json $REC/board.html " ] \
   && [ "$parents" = 1 ] && [ "$same" = yes ] && [ "$rc_init2" -eq 3 ]; then
  pass "(a) init creates foreman-lanes as a root commit with only $REC/BOARD.json and board.html; pull before it exits 3; a second init is refused"
else
  fail "(a) init" "pull before init rc=$rc_pull_before ($out_pull_before)" "init rc=$rc_init ($out_init)" "files: $files" "words in parent line: $parents" "same bytes: $same" "second init rc=$rc_init2"
fi

# ---- (a2) a later head's board is added beside the first; read-only commands are not pushed -------------
REC2=foreman/projects/second-head
mkdir -p "$BB/$REC2" && cp "$FIXTURE" "$BB/$REC2/BOARD.json"
(cd "$BB" && FOREMAN_BOARD_NO_OPEN=1 "$PY" "$REAL_TOOL" "$REC2/BOARD.json" render >/dev/null)
first_before=$(git --git-dir="$root/remote.git" rev-parse "foreman-lanes:$B")
run "$BB" "$PUSH" origin "$REC2/BOARD.json" --init; rc_add=$rc; out_add=$out
run "$BB" "$PUSH" origin "$REC2/BOARD.json" --init; rc_add2=$rc
first_after=$(git --git-dir="$root/remote.git" rev-parse "foreman-lanes:$B")
n=$(git --git-dir="$root/remote.git" ls-tree -r --name-only foreman-lanes | grep -c .)
tip_before=$(rtip)
run "$BB" "$PUSH" origin "$REC2/BOARD.json" -- check; rc_check=$rc
if [ "$rc_add" -eq 0 ] && [ "$rc_add2" -eq 3 ] && [ "$n" = 4 ] && [ "$first_before" = "$first_after" ] && [ "$rc_check" -eq 2 ] && [ "$tip_before" = "$(rtip)" ]; then
  pass "(a2) a second head's board is added beside the first (the first untouched), added once only; '-- check' is refused and pushes nothing"
else
  fail "(a2) second board" "add rc=$rc_add ($out_add)" "again rc=$rc_add2" "files $n" "first same: $([ "$first_before" = "$first_after" ] && echo yes)" "check rc=$rc_check"
fi
rm -rf "$BB/$REC2"

# ---- (b) an event lands and both clones see it after pull -------------------------------------------
tip0=$(rtip)
run "$A" "$PUSH" origin "$B" -- start 01 --run J2; rc_b=$rc; out_b=$out
run "$A" "$PULL" origin "$B"; rc_pa=$rc
run "$BB" "$PULL" origin "$B"; rc_pb=$rc
sa=$(jfield "$A/$B" 01 state); sb=$(jfield "$BB/$B" 01 state); runb=$(jfield "$BB/$B" 01 run)
parent=$(git --git-dir="$root/remote.git" rev-parse "foreman-lanes^" 2>/dev/null)
htmlsame=$(cmp -s <(git --git-dir="$root/remote.git" cat-file blob "foreman-lanes:$REC/board.html") "$BB/$REC/board.html" && echo yes)
if [ "$rc_b" -eq 0 ] && [ "$rc_pa" -eq 0 ] && [ "$rc_pb" -eq 0 ] && [ "$sa" = in-progress ] && [ "$sb" = in-progress ] \
   && [ "$runb" = J2 ] && [ "$parent" = "$tip0" ] && [ "$htmlsame" = yes ]; then
  pass "(b) start 01 --run J2 lands on foreman-lanes on top of the old tip; both clones see job 01 in progress after pull"
else
  fail "(b) event lands" "push rc=$rc_b ($out_b)" "pull rcs $rc_pa $rc_pb" "states A=$sa B=$sb run=$runb" "parent ok: $([ "$parent" = "$tip0" ] && echo yes)" "html same: $htmlsame"
fi
subject_b=$(git --git-dir="$root/remote.git" log -1 --format=%B foreman-lanes)

# ---- (c) two clones race to start the same job: exactly one wins ------------------------------------
# B reads the tip, then (by the hook) A starts 02 and pushes first; B's push is refused, its replay is refused
# by the tool, and B pushes nothing. First move the board so 02 is startable: close 01.
run "$A" "$PUSH" origin "$B" -- close 01 --pr "#2" --merge abc9999 --next 02; rc_close=$rc
tip1=$(rtip)
hook="cd '$A' && bash '$PUSH' origin '$B' -- start 02 --run J3"
out=$(cd "$BB" && BOARD_PUSH_TEST_HOOK="$hook" bash "$PUSH" origin "$B" -- start 02 --run J4 2>&1); rc_c=$?
printf '%s\n' "$out" >> "$log"; out_c=$out
commits=$(git --git-dir="$root/remote.git" rev-list --count "$tip1..foreman-lanes")
runc=$(rjson | jfield - 02 run); localb=$(jfield "$BB/$B" 02 state)
if [ "$rc_close" -eq 0 ] && [ "$rc_c" -eq 1 ] && [ "$commits" = 1 ] && [ "$runc" = J3 ] && [ "$localb" = open ] \
   && printf '%s' "$out_c" | grep -q "replaying" && printf '%s' "$out_c" | grep -q "REFUSED by the board tool"; then
  pass "(c) race to start 02: lane A's start lands (J3), lane B's push is refused, its replay is refused by the tool (exit 1), B pushes nothing and its local board is unchanged"
else
  fail "(c) race" "close rc=$rc_close" "B rc=$rc_c" "new commits=$commits run on branch=$runc B local state=$localb" "B said: $out_c"
fi

# ---- (c2) two sessions push the very same event: the second is refused, never "landed" ---------------
tip2=$(rtip)
hook="cd '$A' && bash '$PUSH' origin '$B' -- add 09 --title Same > '$root/hook-c2.txt' 2>&1"
out=$(cd "$BB" && BOARD_PUSH_TEST_HOOK="$hook" bash "$PUSH" origin "$B" -- add 09 --title Same 2>&1); rc_c2=$?
printf '%s
' "$out" >> "$log"
n2=$(git --git-dir="$root/remote.git" rev-list --count "$tip2..foreman-lanes")
if [ "$rc_c2" -eq 1 ] && [ "$n2" = 1 ] && ! printf '%s' "$out" | grep -q "LANDED"; then
  pass "(c2) the same event pushed twice: one lands, the second is refused (exit 1), not read as a lost reply"
else
  fail "(c2) same event" "rc=$rc_c2 commits=$n2" "said: $out" "the other session said: $(cat "$root/hook-c2.txt" 2>/dev/null)"
fi

# ---- (d) a refused push replays and lands when the event is still valid -----------------------------
tip2=$(rtip)
hook="cd '$A' && bash '$PUSH' origin '$B' -- add 05 --title 'Job five' --needs 00"
out=$(cd "$BB" && BOARD_PUSH_TEST_HOOK="$hook" bash "$PUSH" origin "$B" -- add 06 --title 'Job six' --needs 00 2>&1); rc_d=$?
printf '%s\n' "$out" >> "$log"; out_d=$out
commits=$(git --git-dir="$root/remote.git" rev-list --count "$tip2..foreman-lanes")
t5=$(rjson | jfield - 05 title); t6=$(rjson | jfield - 06 title)
l5=$(jfield "$BB/$B" 05 title); l6=$(jfield "$BB/$B" 06 title)
if [ "$rc_d" -eq 0 ] && [ "$commits" = 2 ] && [ "$t5" = "Job five" ] && [ "$t6" = "Job six" ] \
   && [ "$l5" = "Job five" ] && [ "$l6" = "Job six" ] && printf '%s' "$out_d" | grep -q "attempt 2"; then
  pass "(d) add 05 (lane A) and add 06 (lane B) at once: B's first push is refused, the replay lands on attempt 2, both jobs on the branch and in B's records folder"
else
  fail "(d) replay" "B rc=$rc_d" "new commits=$commits" "branch 05=$t5 06=$t6 B local 05=$l5 06=$l6" "B said: $out_d"
fi

# ---- (e) a lost reply is recognised as success -------------------------------------------------------
tip3=$(rtip)
out=$(cd "$A" && BOARD_PUSH_TEST_LOSE_REPLY=1 bash "$PUSH" origin "$B" -- summary 05 --text "Builds the fifth thing." 2>&1); rc_e=$?
printf '%s\n' "$out" >> "$log"; out_e=$out
commits=$(git --git-dir="$root/remote.git" rev-list --count "$tip3..foreman-lanes")
s5=$(rjson | jfield - 05 summary); l5=$(jfield "$A/$B" 05 summary)
if [ "$rc_e" -eq 0 ] && [ "$commits" = 1 ] && [ "$s5" = "Builds the fifth thing." ] && [ "$l5" = "$s5" ] \
   && printf '%s' "$out_e" | grep -q "reply was lost"; then
  pass "(e) a push whose reply is lost is recognised as landed: exit 0, exactly one commit, no replay"
else
  fail "(e) lost reply" "rc=$rc_e" "new commits=$commits" "summary branch=$s5 local=$l5" "said: $out_e"
fi

# ---- (f) the clone's checkout, index and HEAD are untouched ------------------------------------------
after=$(snapshot "$A")
if [ "$before" = "$after" ] && [ -n "$(git -C "$A" diff --cached --name-only -- staged.txt)" ] && grep -q dirty "$A/app.txt"; then
  pass "(f) clone A after init and five events: HEAD, branch, index and git status (beside the two board files) identical; its staged and unstaged work kept"
else
  fail "(f) checkout touched" "$(diff <(echo "$before") <(echo "$after"))"
fi

# ---- (g) no browser opens ------------------------------------------------------------------------------
seen=$(tr -d '\r' < "$root/no_open.log" | sort -u | tr '\n' ' ')
if [ "$seen" = "'1' " ] && ! grep -qE "would open|opened .* in the browser" "$log"; then
  pass "(g) every board tool run had FOREMAN_BOARD_NO_OPEN=1 (the caller's =dry overridden); nothing tried to open a browser"
else
  fail "(g) browser" "values seen: $seen" "$(grep -E "would open|opened" "$log")"
fi

# ---- (h) subject-only messages, no trailer ---------------------------------------------------------------
bad=""
for c in $(git --git-dir="$root/remote.git" rev-list foreman-lanes); do
  msg=$(git --git-dir="$root/remote.git" cat-file commit "$c" | sed '1,/^$/d')
  lines=$(printf '%s\n' "$msg" | wc -l | tr -d ' ')
  trailers=$(printf '%s\n' "$msg" | git interpret-trailers --parse)
  case $msg in Board:*) ;; *) bad="$bad $c:not-Board" ;; esac
  [ "$lines" = 1 ] || bad="$bad ${c:0:7}:$lines-lines"
  [ -z "$trailers" ] || bad="$bad ${c:0:7}:trailer"
done
if [ -z "$bad" ] && [ "$subject_b" = "Board: start 01 (J2)" ]; then
  pass "(h) every commit on foreman-lanes has a one-line subject and no trailer, e.g. \"$subject_b\""
else
  fail "(h) messages" "problems:$bad" "subject of (b): $subject_b"
fi

[ "$fails" -eq 0 ] && { echo "ALL PASS"; exit 0; }
echo "$fails case(s) failed"; exit 1
