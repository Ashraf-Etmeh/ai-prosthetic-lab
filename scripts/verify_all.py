"""Run every verification in one go: the checks for prompts 0-2, then the golden cases.

  python scripts/verify_all.py                 without the search model (about 30 s)
  python scripts/verify_all.py --with-model    also the real search: the 0-2 checks over the
                                               trial cases, and the golden cases' gap checks

Each runs in its own process, exactly as when started by hand:
  1. python scripts/verify_prompts_0_2.py [--with-model]
  2. python -m quality.golden_cases [--no-search]
Neither writes to data/records/cases/, the review logs or data/quality/trial/. Exit status 1
if either reports a failure.
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python scripts/verify_all.py", description=__doc__.splitlines()[0])
    parser.add_argument("--with-model", action="store_true", help="also run the real search (loads bge-m3)")
    args = parser.parse_args(argv)
    steps = [
        ("checks for prompts 0-2", ["scripts/verify_prompts_0_2.py", *(["--with-model"] if args.with_model else [])]),
        ("golden cases", ["-m", "quality.golden_cases", *([] if args.with_model else ["--no-search"])]),
    ]
    results = []
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
    return 0 if all(outcome == "OK" for _, outcome in results) else 1


if __name__ == "__main__":
    sys.exit(main())
