#!/usr/bin/env bash
# Tests for land_tested.sh: a bare repo as the remote, two clones as the two lanes. bash snippets/test_land_tested.sh
set -u
here="$(cd "$(dirname "$0")" && pwd)"
tool="$here/land_tested.sh"
root=$(mktemp -d "${TMPDIR:-/tmp}/landtest-XXXXXX")
trap 'rm -rf "$root"' EXIT
fails=0
pass() { echo "PASS $1"; }
fail() { echo "FAIL $1"; fails=$((fails + 1)); }
id() { git -C "$1" config user.name "Test Lane"; git -C "$1" config user.email "lane@example.invalid"; }

git init -q --bare -b main "$root/remote.git"
git clone -q "$root/remote.git" "$root/a" 2>/dev/null; id "$root/a"
mkdir -p "$root/a/src" "$root/a/foreman"
echo one > "$root/a/src/app.txt"; echo rec > "$root/a/foreman/notes.md"; echo adapter > "$root/a/foreman/test-adapter.sh"
git -C "$root/a" add -A && git -C "$root/a" commit -qm base && git -C "$root/a" push -q origin main
git clone -q "$root/remote.git" "$root/b" 2>/dev/null; id "$root/b"
base=$(git -C "$root/a" rev-parse HEAD)

# lane A: a job branch proven at its head
git -C "$root/a" switch -qc job-a && echo a > "$root/a/src/a.txt" && git -C "$root/a" add -A && git -C "$root/a" commit -qm "job a"
headA=$(git -C "$root/a" rev-parse HEAD)
out=$(cd "$root/a" && bash "$tool" moved origin main "$base"); [ "$out" = same ] && pass "(a) main unmoved reads same" || fail "(a) got $out"

# a records-only push lands on main
(cd "$root/b" && echo rec2 >> foreman/notes.md && git commit -qam records && git push -q origin main)
out=$(cd "$root/a" && bash "$tool" moved origin main "$base"); [ "$out" = records-only ] && pass "(b) records moved reads records-only" || fail "(b) got $out"

# the adapter counts as product
(cd "$root/b" && echo adapter2 > foreman/test-adapter.sh && git commit -qam adapter && git push -q origin main)
out=$(cd "$root/a" && bash "$tool" moved origin main "$base"); [ "$out" = product ] && pass "(c) the test adapter counts as product" || fail "(c) got $out"

# product moved: A merges main into its branch (the caller proves that commit again), then lands it
git -C "$root/a" fetch -q origin && git -C "$root/a" merge -q --no-edit origin/main
headA=$(git -C "$root/a" rev-parse HEAD)
out=$(cd "$root/a" && bash "$tool" land origin main "$headA" "Merge job a" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "(d) land makes a merge commit and pushes it: $out" || fail "(d) rc $rc $out"
msg=$(git -C "$root/remote.git" log -1 --format=%B main)
[ "$msg" = "Merge job a" ] && pass "(e) the merge commit's message is the subject only" || fail "(e) message: $msg"
out=$(cd "$root/a" && bash "$tool" verify origin main "$headA" 2>&1) && pass "(f) verify: $out" || fail "(f) $out"

# lane B lands second: its fetch is stale, so git refuses its push (exit 6)
git -C "$root/b" fetch -q && git -C "$root/b" switch -qc job-b origin/main~1 2>/dev/null || git -C "$root/b" switch -qc job-b
echo b > "$root/b/src/b.txt" && git -C "$root/b" add -A && git -C "$root/b" commit -qm "job b"
headB=$(git -C "$root/b" rev-parse HEAD)
(cd "$root/a" && git switch -q main && git pull -q origin main && echo c > src/c.txt && git add -A && git commit -qm "lane a again" && git push -q origin main)
# simulate the race: B fetched before A's push; make B's push see a stale tip by pushing from A between B's fetch and push
cat > "$root/racehook.sh" <<EOF
cd "$root/a" && echo d > src/d.txt && git add -A && git commit -qm "lane a races" && git push -q origin main
EOF
out=$(cd "$root/b" && GIT_TRACE=0 bash -c "git fetch -q origin main; bash '$root/racehook.sh'; git -c advice.detachedHead=false worktree add -q --detach '$root/wtb' origin/main && git -C '$root/wtb' merge -q --no-ff -m 'Merge job b' $headB && git -C '$root/wtb' push -q origin HEAD:refs/heads/main" 2>&1); rc=$?
[ $rc -ne 0 ] && pass "(g) a push built on a stale main is refused by git (never forced)" || fail "(g) the stale push landed"
git -C "$root/b" worktree remove --force "$root/wtb" >/dev/null 2>&1
out=$(cd "$root/b" && bash "$tool" land origin main "$headB" "Merge job b" 2>&1); rc=$?
[ $rc -eq 6 ] && pass "(h0) B's head was proven before A's landing: land refuses it" || fail "(h0) rc $rc $out"
git -C "$root/b" fetch -q origin && git -C "$root/b" merge -q --no-edit origin/main   # B merges main in and proves it again
headB=$(git -C "$root/b" rev-parse HEAD)
out=$(cd "$root/b" && bash "$tool" land origin main "$headB" "Merge job b" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "(h) after merging main in, the new proven head lands" || fail "(h) rc $rc $out"

# a lost reply is recognised as landed
git -C "$root/a" fetch -q && git -C "$root/a" switch -qc job-e origin/main && echo e > "$root/a/src/e.txt" && git -C "$root/a" add -A && git -C "$root/a" commit -qm "job e"
headE=$(git -C "$root/a" rev-parse HEAD)
out=$(cd "$root/a" && LAND_TEST_LOSE_REPLY=1 bash "$tool" land origin main "$headE" "Merge job e" 2>&1); rc=$?
case "$out" in *"reply was lost"*) [ $rc -eq 0 ] && pass "(i) a lost reply reads as landed" || fail "(i) rc $rc";; *) fail "(i) $out";; esac
n=$(git -C "$root/remote.git" log --oneline --merges main | grep -c "Merge job e")
[ "$n" = 1 ] && pass "(j) landed exactly once" || fail "(j) $n merges"

# the critical race: "same" was true when A checked, then the other lane landed product code before A's land
git -C "$root/a" fetch -q && git -C "$root/a" switch -qc job-f origin/main && echo f > "$root/a/src/f.txt" && git -C "$root/a" add -A && git -C "$root/a" commit -qm "job f"
headF=$(git -C "$root/a" rev-parse HEAD); baseF=$(git -C "$root/a" rev-parse origin/main)
out=$(cd "$root/a" && bash "$tool" moved origin main "$baseF"); [ "$out" = same ] || fail "(m0) expected same, got $out"
(cd "$root/b" && git switch -q main && git pull -q origin main && echo g > src/g.txt && git add -A && git commit -qm "other lane product" && git push -q origin main)
before=$(git -C "$root/remote.git" rev-parse main)
out=$(cd "$root/a" && bash "$tool" land origin main "$headF" "Merge job f" 2>&1); rc=$?
after=$(git -C "$root/remote.git" rev-parse main)
[ $rc -eq 6 ] && [ "$before" = "$after" ] && pass "(m) land refuses an unproven tree when main moved after the check" || fail "(m) rc $rc, main moved: $out"

# verify refuses a main that isn't the proven head's merge
out=$(cd "$root/a" && bash "$tool" verify origin main "$headA" 2>&1); rc=$?
[ $rc -eq 1 ] && pass "(k) verify refuses when M^2 isn't the proven head" || fail "(k) rc $rc $out"
out=$(bash "$tool" land origin main x $'two\nlines' 2>&1); [ $? -eq 2 ] && pass "(l) a two-line message is refused" || fail "(l) $out"

[ $fails -eq 0 ] && echo "ALL PASS" || { echo "$fails FAILED"; exit 1; }
