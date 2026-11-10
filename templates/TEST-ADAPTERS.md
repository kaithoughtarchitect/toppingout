# Test adapters

Every comparison in a work order (base-vs-head, "the failing tests are the baseline's", the foreman's test-first check) compares **stable failing-test IDs**, never a summary line. The repo keeps its adapter as **three Bash functions** in one file, `<records>/test-adapter.sh`, which the repo profile names and every work order sources in its prefix line:

```bash
run_tests  <output file> <exit file> <test paths...>   # runs the tests from the current directory; writes ALL output to <output file> and the exit code to <exit file>
failed_ids <output file>                               # prints one failing-test ID per line, sorted, unique
ran_ok     <output file> <exit file>                   # exit 0 only if the run really ran: tests were collected and the process didn't crash
```

Each function reads **only the files it is given**, so two runs in two worktrees can be compared from anywhere:

```bash
( cd "$BASE" && run_tests "$DAY/bvh/base.txt" "$DAY/bvh/base.exit" <set> )
( cd "$WT"   && run_tests "$DAY/bvh/head.txt" "$DAY/bvh/head.exit" <set> )
ran_ok "$DAY/bvh/base.txt" "$DAY/bvh/base.exit" && ran_ok "$DAY/bvh/head.txt" "$DAY/bvh/head.exit" || echo "PROCESS FAILURE: report it, don't compare"
comm -13 <(failed_ids "$DAY/bvh/base.txt") <(failed_ids "$DAY/bvh/head.txt") > "$DAY/bvh/red_at_head_only.txt"   # must be empty
```

A run that collected nothing or crashed is a **process failure**, reported separately, never an empty failure list.

## Adapter files for common runners

Copy one into `<records>/test-adapter.sh` and adjust the command line. Every adapter starts with the paid-key guard, so no test run can spend money (`RULES.md` money guard). Set `PAID_KEYS` from the repo profile's "Paid keys to strip":

```bash
PAID_KEYS="OPENROUTER_API_KEY OPENAI_API_KEY"   # from the repo profile
no_paid() { local a=(); for k in $PAID_KEYS; do a+=(-u "$k"); done; env "${a[@]}" "$@"; }
```

 Runners that report in JSON write it **next to the output file** (`<output>.json`), so each run has its own.

**pytest**

```bash
TEST_WORKERS=""   # empty = one process; a number only after the parallel proof (below) is recorded in the repo profile
run_tests()  { local out=$1 ex=$2; shift 2; no_paid python -m pytest -rfE --durations=30 ${TEST_WORKERS:+-n "$TEST_WORKERS" --dist loadfile} "$@" >"$out" 2>&1; echo $? >"$ex"; }
failed_ids() { grep -E '^(FAILED|ERROR) ' "$1" | cut -d' ' -f2 | sort -u; }
ran_ok()     { local ex; ex=$(cat "$2"); [ "$ex" -le 1 ] && ! grep -qE 'no tests ran|ERROR collecting' "$1"; }   # 0 pass, 1 test failures; 2-5 = interrupted/usage/no tests
```

`--durations=30` ends every output with the 30 slowest tests, so where a run's time goes is always on disk at no extra cost.

**unittest**

```bash
run_tests()  { local out=$1 ex=$2; shift 2; no_paid python -m unittest -v "$@" >"$out" 2>&1; echo $? >"$ex"; }
failed_ids() { grep -E '^(FAIL|ERROR): ' "$1" | sed -E 's/^(FAIL|ERROR): //' | sort -u; }
ran_ok()     { grep -qE '^Ran [1-9][0-9]* tests?' "$1" && ! grep -qE 'Failed to import test module|^ImportError' "$1"; }
```

**jest** (vitest: the same, with `no_paid npx vitest run --reporter=json --outputFile="$out.json"`)

```bash
run_tests()  { local out=$1 ex=$2; shift 2; no_paid npx jest --json --outputFile="$out.json" "$@" >"$out" 2>&1; echo $? >"$ex"; }
failed_ids() { node -e 'const r=require(require("path").resolve(process.argv[1]+".json"));for(const f of r.testResults)for(const a of f.assertionResults||[])if(a.status==="failed")console.log(f.name+" > "+a.fullName)' "$1" | sort -u; }
ran_ok()     { node -e 'const r=require(require("path").resolve(process.argv[1]+".json"));process.exit(r.numTotalTests>0&&!r.testResults.some(f=>f.status==="failed"&&!(f.assertionResults||[]).length)?0:1)' "$1"; }
```

**go test**

```bash
run_tests()  { local out=$1 ex=$2; shift 2; no_paid go test -json "$@" >"$out" 2>&1; echo $? >"$ex"; }
failed_ids() { grep '"Action":"fail"' "$1" | grep '"Test":' | sed -E 's/.*"Package":"([^"]*)".*"Test":"([^"]*)".*/\1 \2/' | sort -u; }
ran_ok()     { grep -q '"Action":"run"' "$1" && ! grep -qE '\[(build|setup) failed\]' "$1"; }
```

**cargo test**

```bash
run_tests()  { local out=$1 ex=$2; shift 2; no_paid cargo test --no-fail-fast "$@" >"$out" 2>&1; echo $? >"$ex"; }
failed_ids() { grep -E '^test .* \.\.\. FAILED$' "$1" | awk '{print $2}' | sort -u; }
ran_ok()     { grep -qE '^running [1-9]' "$1" && ! grep -q 'error: could not compile' "$1"; }
```

**Another runner:** write the same three functions, then **prove the adapter** before the first job: two fixture runs where base and head fail **different** tests (same count), and `comm -13` must print the head-only one. Record the proof in the repo profile.

## Affected tests (each work order, and base-vs-head run 1)

- **Python:** `python snippets/import_scan.py [--root <test root> ...] <touched module> ...` derives the test modules that import a touched module, including relative imports, src layouts, sibling tests and helper modules. It prints one path per line, then `COUNT <n>`; the list without that last line is the **affected set**.
- **Any other stack, or anything the scan can't see** (dynamic imports, plugins, fixtures): run the **whole affected suite** and say so in the report. An empty derived set is never proof on its own.
- **Each work order** runs its affected set once before any change (`BEFORE`) and once after, with its new tests (`AFFECTED`), not the whole suite (`WORK-ORDER.txt`); the whole suite runs at t0 and at the final head (`METHOD.md` §7). After must equal before: the same failing-test IDs, and the passed count up by exactly the new tests.
- **A big set runs once, as the whole suite.** When the set holds more than half the suite's test files (a core module that most tests import), running it before and after would cost nearly two whole runs. The work order then runs the whole suite once, with no `BEFORE`, and compares it with the last whole-suite output (t0's or the previous work order's): the same failing IDs, the passed count up by exactly the new tests. Measured on one project's job: its core module's set was 24 to 28 of 45 test files, 66 to 88% of a run's time.
- **The whole test folder instead** when the derived set is empty, when the work order touches a conftest, a fixture, a test helper or a file the scan can't follow (data, SQL, config), or for a stack the scan can't read.
- **A fast suite keeps the whole suite every work order.** When one whole-suite run takes under about 5 minutes, the repo profile says "Whole suite every work order: yes" and `AFFECTED` is the whole test folder. The rule follows the measured time.

## Speed: one suite at a time, several workers in it

Runs never overlap (`RULES.md`), but one run may use several processes. A serial pytest run on a 12-core machine uses one core; with workers it can be several times faster. Most other runners already do this (jest, vitest, go test and cargo test run in parallel by default).

**pytest:** `pytest-xdist` (a dev dependency), switched on by setting `TEST_WORKERS` in the adapter. **Only after the parallel proof**, because tests that share something (a file outside `tmp_path`, a port, one disposable database, the process environment) can pass alone and fail side by side:

```bash
bash snippets/parallel_proof.sh "<records>/test-adapter.sh" <workers, e.g. 6> <test paths...>
```

It runs the suite once with one process and three times with the workers, and prints **PROVED** only when all four runs really ran with **identical failing-test IDs** and the parallel runs are at least twice as fast. Record its last line in the repo profile ("Parallel workers"), then set `TEST_WORKERS` in the adapter. Run it when no other session is running tests.

**A test that differs side by side** is a finding, never retried to green. The adapter's `--dist loadfile` keeps every test of one file on one worker, in order, so tests that share something within a file are safe. Tests in **different files** that share something (one disposable database, a fixed file or port) either move into one file or stop sharing it (`tmp_path`, a free port, a database per worker), then prove again. A test that only fails under load (a timing assertion) is fixed, not grouped.

**A trap, checked 2026-11-10:** `@pytest.mark.xdist_group` with `--dist loadgroup` silently does nothing with pytest 9.2 and pytest-xdist 3.8 (the grouped tests still ran on two workers and clashed); it works on pytest 8.4. Don't rely on it without the proof.

**CI:** the same switch in the workflow's test step (`-n <the runner's core count> --dist loadfile`) once the proof holds on the CI runner's shape with that same worker count; prove the number CI will use.

## Coverage and the old-code check

- **Branch coverage** (`WORK-ORDER.txt` B.2a): the profile names the command, e.g. pytest `--cov=<module> --cov-branch --cov-report=term-missing`, `coverage run --branch -m unittest` + `coverage report -m`, jest `--coverage`, `go test -coverprofile`, `cargo llvm-cov`.
- **Running new tests against the previous commit's code** (the foreman's test-first check): the profile names how. Python: a scratch copy of the old package placed first on `PYTHONPATH`. Elsewhere: a throwaway worktree at the previous commit with only the new test files copied in.
