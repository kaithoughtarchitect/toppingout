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
run_tests()  { local out=$1 ex=$2; shift 2; no_paid python -m pytest -rfE "$@" >"$out" 2>&1; echo $? >"$ex"; }
failed_ids() { grep -E '^(FAILED|ERROR) ' "$1" | cut -d' ' -f2 | sort -u; }
ran_ok()     { local ex; ex=$(cat "$2"); [ "$ex" -le 1 ] && ! grep -qE 'no tests ran|ERROR collecting' "$1"; }   # 0 pass, 1 test failures; 2-5 = interrupted/usage/no tests
```

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

## Affected tests (base-vs-head run 1)

- **Python:** `python snippets/import_scan.py [--root <test root> ...] <touched module> ...` derives the test modules that import a touched module, including relative imports, src layouts, sibling tests and helper modules.
- **Any other stack, or anything the scan can't see** (dynamic imports, plugins, fixtures): run the **whole affected suite** and say so in the report. An empty derived set is never proof on its own.

## Coverage and the old-code check

- **Branch coverage** (`WORK-ORDER.txt` B.2a): the profile names the command, e.g. pytest `--cov=<module> --cov-branch --cov-report=term-missing`, `coverage run --branch -m unittest` + `coverage report -m`, jest `--coverage`, `go test -coverprofile`, `cargo llvm-cov`.
- **Running new tests against the previous commit's code** (the foreman's test-first check): the profile names how. Python: a scratch copy of the old package placed first on `PYTHONPATH`. Elsewhere: a throwaway worktree at the previous commit with only the new test files copied in.
