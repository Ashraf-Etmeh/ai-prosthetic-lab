"""Tests for .claude/hooks/protect_yardstick.py: Claude Code asks the owner before Claude changes the yardstick.

The hook lives outside the Python packages (Claude Code runs it as a script),
so it is loaded from its file.
"""

import importlib.util
import unittest

from shared.config import PROJECT_ROOT

_spec = importlib.util.spec_from_file_location("protect_yardstick",
                                               PROJECT_ROOT / ".claude" / "hooks" / "protect_yardstick.py")
hook = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hook)


def decide(tool: str, **given) -> str:
    return hook.decide({"tool_name": tool, "tool_input": given}, PROJECT_ROOT)


class FileToolTests(unittest.TestCase):
    def test_every_yardstick_path_asks(self):
        for path in ("data/eval/golden_cases/golden-01.json", "data/eval/golden_cases_held_out/golden-06.json",
                     "data/eval/golden_cases_held_out.json", "reasoning/component_guide.py",
                     "reasoning/fitting_guide.py", "data/knowledge/evidence_rules.csv", "data/review_log.jsonl",
                     "data/review_log.test.jsonl"):
            with self.subTest(path):
                self.assertTrue(decide("Edit", file_path=str(PROJECT_ROOT / path)))
                self.assertTrue(decide("Write", file_path=path))

    def test_other_files_and_reads_pass(self):
        for path in ("FUTURE_WORK.md", "reasoning/component_support.py", "data/eval/golden_cases_extra/x.json",
                     "data/knowledge/items.json", "intake/golden_cases.py"):
            with self.subTest(path):
                self.assertEqual(decide("Edit", file_path=path), "")
        self.assertEqual(decide("Read", file_path="reasoning/component_guide.py"), "")

    def test_git_bash_style_project_root(self):
        drive, rest = str(PROJECT_ROOT)[0], str(PROJECT_ROOT)[2:].replace("\\", "/")
        root = hook.Path(hook.native(f"/{drive.lower()}{rest}")) if hook.os.name == "nt" else PROJECT_ROOT
        event = {"tool_name": "Edit", "tool_input": {"file_path": str(PROJECT_ROOT / "reasoning" / "fitting_guide.py")}}
        self.assertTrue(hook.decide(event, root))


class ShellToolTests(unittest.TestCase):
    def test_writes_ask(self):
        for tool, command in [("Bash", "sed -i s/K3/K2/ data/eval/golden_cases/golden-01.json"),
                              ("Bash", "echo x >> data/review_log.jsonl"),
                              ("Bash", "git checkout -- reasoning/fitting_guide.py"),
                              ("Bash", "python -c \"open('data/eval/golden_cases/g.json','w')\""),
                              ("PowerShell", r"Set-Content data\eval\golden_cases_held_out\golden-06.json x")]:
            with self.subTest(command):
                self.assertTrue(decide(tool, command=command))

    def test_reads_and_runs_pass(self):
        for command in ("cat data/eval/golden_cases/golden-01.json", "grep -n K3 reasoning/component_guide.py",
                        "python -m intake.golden_cases --no-search", "python -m unittest"):
            with self.subTest(command):
                self.assertEqual(decide("Bash", command=command), "")


if __name__ == "__main__":
    unittest.main()
