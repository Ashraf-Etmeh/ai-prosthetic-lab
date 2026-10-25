"""Run every verification in one go: the checks for prompts 0-2, then the golden cases.

  python scripts/verify_all.py                 without the search model (about 30 s)
  python scripts/verify_all.py --with-model    also the real search: the 0-2 checks over the
                                               trial cases, and the golden cases' gap checks
  python scripts/verify_all.py --record        first the unit tests too (about 3 min), and the result
                                               of each step added to data/quality/results/runs.jsonl for
                                               the quality page's release gate (quality/results.py)

Each runs in its own process, exactly as when started by hand:
  1. python -m unittest                        (with --record only)
  2. python scripts/verify_prompts_0_2.py [--with-model]
  3. python -m quality.golden_cases [--no-search] [--record]
None writes to data/records/cases/, the review logs or data/quality/trial/. Exit status 1
if any reports a failure.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIT_TESTS = "unit tests"


def _unit_tests() -> tuple[str, dict]:
    """Run the unit tests; (outcome, {"ran": n, "ok": bool}) from unittest's own summary."""
    done = subprocess.run([sys.executable, "-m", "unittest"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    output = done.stderr + done.stdout
    tail = output.strip().splitlines()[-3:]
    print("\n".join(tail))
    ran = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    ok = done.returncode == 0
    return ("OK" if ok else f"FAILED (exit {done.returncode})"), {"ran": int(ran.group(1)) if ran else None, "ok": ok,
                                                                  "summary": tail[-1] if tail else ""}


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python scripts/verify_all.py", description=__doc__.splitlines()[0])
    parser.add_argument("--with-model", action="store_true", help="also run the real search (loads bge-m3)")
    parser.add_argument("--record", action="store_true",
                        help="also run the unit tests, and record every result for the quality page")
    args = parser.parse_args(argv)
    steps = [
        ("checks for prompts 0-2", ["scripts/verify_prompts_0_2.py", *(["--with-model"] if args.with_model else [])]),
        ("golden cases", ["-m", "quality.golden_cases", *([] if args.with_model else ["--no-search"]),
                          *(["--record"] if args.record else [])]),
    ]
    results, unit_tests = [], None
    if args.record:
        print(f"\n===== {UNIT_TESTS}: python -m unittest", flush=True)
        outcome, unit_tests = _unit_tests()
        results.append((UNIT_TESTS, outcome))
    for name, command in steps:
        print(f"\n===== {name}: python {' '.join(command)}", flush=True)
        if command[0].endswith(".py") and not (ROOT / command[0]).is_file():
            print(f"{command[0]} not found")
            results.append((name, "not found"))
            continue
        code = subprocess.run([sys.executable, *command], cwd=ROOT).returncode
        results.append((name, "OK" if code == 0 else f"FAILED (exit {code})"))
    print("\n===== Summary")
    for name, outcome in results:
        print(f"  {name:24} {outcome}")
    if args.record:
        sys.path.insert(0, str(ROOT))
        from quality import results as recorded

        recorded.record_run(recorded.RELEASE_CHECK, {
            "steps": {name: outcome for name, outcome in results}, "unit_tests": unit_tests,
            "with_model": args.with_model})
        print(f"Recorded in {recorded.config.QUALITY_RESULTS_PATH.relative_to(ROOT).as_posix()}")
    return 0 if all(outcome == "OK" for _, outcome in results) else 1


if __name__ == "__main__":
    sys.exit(main())
