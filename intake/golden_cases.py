"""Golden cases: fake cases with the output they must give, checked against the app's analysis.

  python -m intake.golden_cases                 every data/eval/golden_cases/*.json
  python -m intake.golden_cases FILE ...        only these files
  python -m intake.golden_cases --no-search     statements and functional level only

Each file holds one fake case in the research brief's benchmark fields:
  id, description, review_status   "unreviewed" (a draft) or "reviewed" (checked by the team)
  question                         the case input, exactly as Case.to_dict() gives it
  expected_answer
    gaps                           [{"field", "source_expected"}]: a shared/field_guide.py path,
                                   and true (a source is cited), false (none is) or null (either)
    statements_present             component and fitting statement ids that must be shown
    functional_level               the K-level description id that must be shown, or null
  common_wrong_answers
    statements_absent              statement ids that must not be shown
  supporting_sources               catalog ids behind the expected statements and K-level description
  reasoning_path                   per present or absent statement: "expected" ("present"/"absent")
                                   and "decided_by", the rule fields that decide it (levels, k_levels,
                                   ambulators_only, unilateral_only, bilateral_only), each with the
                                   "case_value" it reads (amputation_level, activity.k_level or side)
  evaluation_criteria              the checks that apply: statements, gaps, functional_level

Every case goes through intake/routes.py analyse_case(), the analysis behind
POST /intake. The statement and functional-level checks don't depend on the
search, so they run without the embedding model. The gap checks need the
model and the vector store: without either (or with --no-search) they are
SKIPPED, with the reason; the model is never downloaded here.

Each check prints PASS, or what is missing and unexpected: FAIL in a
"reviewed" case, WARN in an "unreviewed" one. A gap citing a document the
search must leave out (RETRIEVAL_EXCLUDED_DOCUMENTS) is FAIL in any case, and
a malformed file is ERROR. Exit status 1 if anything is FAIL or ERROR.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from intake.routes import analyse_case
from knowledge.catalog import load_catalog
from knowledge.ingest import INFO_FILE
from knowledge.retrieval import KnowledgeBaseMissing
from reasoning import component_guide, fitting_guide
from reasoning.component_guide import K_LEVEL_DESCRIPTIONS
from shared.case_schema import Case
from shared.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    GOLDEN_CASES_DIR,
    PROJECT_ROOT,
    RETRIEVAL_EXCLUDED_DOCUMENTS,
    VECTOR_STORE_DIR,
)
from shared.field_guide import FIELDS_BY_PATH
from shared.store import CaseRecord

KEYS = ("id", "description", "review_status", "question", "expected_answer", "common_wrong_answers",
        "supporting_sources", "reasoning_path", "evaluation_criteria")
REVIEW_STATUSES = ("unreviewed", "reviewed")
CRITERIA = ("statements", "gaps", "functional_level")
RULE_FIELDS = ("levels", "k_levels", "ambulators_only", "unilateral_only", "bilateral_only")
RULES = {rule.statement.id: rule for rule in (*component_guide.RULES, *fitting_guide.RULES)}
K_LEVEL_IDS = {statement.id for statement in K_LEVEL_DESCRIPTIONS.values()}

PASS, WARN, FAIL, SKIP, ERROR = "PASS", "WARN", "FAIL", "SKIP", "ERROR"


@dataclass
class GoldenCase:
    path: Path
    data: dict
    case: Case

    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def reviewed(self) -> bool:
        return self.data["review_status"] == "reviewed"

    @property
    def present(self) -> list[str]:
        return self.data["expected_answer"]["statements_present"]

    @property
    def absent(self) -> list[str]:
        return self.data["common_wrong_answers"]["statements_absent"]


@dataclass
class Finding:
    check: str
    status: str
    lines: list[str]  # the first is the summary; the rest are listed below it


# ---- Reading a case file --------------------------------------------------


def _keys(where: str, value, keys: tuple[str, ...]) -> None:
    if not isinstance(value, dict) or set(value) != set(keys):
        found = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ValueError(f"{where} must have exactly the keys {', '.join(keys)}; found {found}")


def _id_list(where: str, value, known, what: str) -> None:
    if not isinstance(value, list) or len(value) != len(set(value)):
        raise ValueError(f"{where} must be a list without repeats")
    unknown = [item for item in value if item not in known]
    if unknown:
        raise ValueError(f"{where}: not {what}: {', '.join(map(str, unknown))}")


def read_golden_case(path: Path) -> GoldenCase:
    """The case file, checked for shape. ValueError naming the file and the problem."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        _keys("the file", data, KEYS)
        if data["id"] != path.stem:
            raise ValueError(f"id {data['id']!r} must be the file name ({path.stem!r})")
        if data["review_status"] not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {list(REVIEW_STATUSES)}")
        criteria = data["evaluation_criteria"]
        if not criteria:
            raise ValueError("evaluation_criteria is empty")
        _id_list("evaluation_criteria", criteria, CRITERIA, "a check")

        case = Case.from_dict(data["question"])
        if case.to_dict() != data["question"]:
            raise ValueError("question must be exactly what Case.to_dict() gives (every field, values as stored)")
        if case.case_id != data["id"]:
            raise ValueError(f"question.case_id must be {data['id']!r}")

        expected = data["expected_answer"]
        _keys("expected_answer", expected, ("gaps", "statements_present", "functional_level"))
        gaps = expected["gaps"]
        if not isinstance(gaps, list):
            raise ValueError("expected_answer.gaps must be a list")
        for gap in gaps:
            _keys("each expected gap", gap, ("field", "source_expected"))
            if gap["source_expected"] is not None and not isinstance(gap["source_expected"], bool):
                raise ValueError(f"gap {gap['field']}: source_expected must be true, false or null")
        _id_list("expected_answer.gaps", [gap["field"] for gap in gaps], FIELDS_BY_PATH, "a gap field")
        _id_list("statements_present", expected["statements_present"], RULES, "a statement id")
        if expected["functional_level"] is not None and expected["functional_level"] not in K_LEVEL_IDS:
            raise ValueError(f"functional_level must be one of {sorted(K_LEVEL_IDS)} or null")

        wrong = data["common_wrong_answers"]
        _keys("common_wrong_answers", wrong, ("statements_absent",))
        _id_list("statements_absent", wrong["statements_absent"], RULES, "a statement id")
        both = set(expected["statements_present"]) & set(wrong["statements_absent"])
        if both:
            raise ValueError(f"both present and absent: {', '.join(sorted(both))}")
        _id_list("supporting_sources", data["supporting_sources"], {doc.id for doc in load_catalog()},
                 "a catalog id")

        path_ = data["reasoning_path"]
        listed = set(expected["statements_present"]) | set(wrong["statements_absent"])
        if not isinstance(path_, dict) or set(path_) != listed:
            raise ValueError("reasoning_path must have one entry for each present or absent statement")
        for statement_id, step in path_.items():
            _keys(f"reasoning_path.{statement_id}", step, ("expected", "decided_by"))
            should = "present" if statement_id in expected["statements_present"] else "absent"
            if step["expected"] != should:
                raise ValueError(f"reasoning_path.{statement_id}: expected must be {should!r}")
            if not isinstance(step["decided_by"], list) or not step["decided_by"]:
                raise ValueError(f"reasoning_path.{statement_id}: decided_by must name at least one rule field")
            for decision in step["decided_by"]:
                _keys(f"reasoning_path.{statement_id}.decided_by", decision, ("field", "case_value"))
            _id_list(f"reasoning_path.{statement_id}.decided_by",
                     [decision["field"] for decision in step["decided_by"]], RULE_FIELDS, "a rule field")
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError(f"{path.name}: {error}") from None
    return GoldenCase(path, data, case)


# ---- Checking a case ------------------------------------------------------


def _rule_sets(rule, field: str) -> bool:
    """Whether the rule restricts who it applies to by this field."""
    value = getattr(rule, field)
    return bool(value) if field in ("levels", "k_levels") else value is True


def _case_value(case: Case, field: str):
    """The case value a rule field reads, as stored."""
    if field == "levels":
        return case.amputation_level.value
    if field in ("k_levels", "ambulators_only"):
        return case.activity.k_level.value if case.activity.k_level else None
    return case.side.value


def reasoning_problems(golden: GoldenCase) -> list[str]:
    """Where the written reasoning doesn't match the rule definitions or the case.

    It doesn't decide any rule: it checks that each named field is one the
    rule sets, that a present statement names every field its rule sets,
    and that each case_value is what the case holds.
    """
    problems = []
    for statement_id, step in golden.data["reasoning_path"].items():
        rule = RULES[statement_id]
        named = [decision["field"] for decision in step["decided_by"]]
        not_set = [field for field in named if not _rule_sets(rule, field)]
        if not_set:
            problems.append(f"{statement_id}: the rule doesn't set {', '.join(not_set)}")
        if step["expected"] == "present":
            unnamed = [field for field in RULE_FIELDS if _rule_sets(rule, field) and field not in named]
            if unnamed:
                problems.append(f"{statement_id}: present, but its rule also sets {', '.join(unnamed)}")
        for decision in step["decided_by"]:
            actual = _case_value(golden.case, decision["field"])
            if decision["case_value"] != actual:
                problems.append(f"{statement_id}: {decision['field']} reads {actual!r}, "
                                f"written as {decision['case_value']!r}")
    return problems


def _difference(check: str, status: str, missing: list[str], unexpected: list[str],
                wrong_source: list[str] = ()) -> Finding:
    if not missing and not unexpected and not wrong_source:
        return Finding(check, PASS, ["as expected"])
    counts = [f"{len(missing)} missing" if missing else "", f"{len(unexpected)} unexpected" if unexpected else "",
              f"{len(wrong_source)} with a source other than expected" if wrong_source else ""]
    return Finding(check, status, [", ".join(c for c in counts if c),
                                   *(f"missing: {m}" for m in missing),
                                   *(f"unexpected: {u}" for u in unexpected),
                                   *(f"source: {s}" for s in wrong_source)])


def check_case(golden: GoldenCase, record: CaseRecord, gaps_skipped: Optional[str] = None) -> list[Finding]:
    """The findings for one case. gaps_skipped: why the gap checks can't run (None: they can)."""
    mismatch = FAIL if golden.reviewed else WARN
    criteria = golden.data["evaluation_criteria"]
    findings = []

    if "statements" in criteria:
        shown = [cited.statement for cited in (*record.components.statements, *record.fitting.statements)]
        shown_ids = [statement.id for statement in shown]
        unexpected = [f"{i} (listed in statements_absent)" if i in golden.absent else f"{i} (not listed)"
                      for i in shown_ids if i not in golden.present]
        findings.append(_difference("statements", mismatch,
                                    [i for i in golden.present if i not in shown_ids], unexpected))
        sources = {statement.doc_id for statement in shown}
        if record.components.functional.description:
            sources.add(record.components.functional.description.statement.doc_id)
        expected_sources = golden.data["supporting_sources"]
        findings.append(_difference("supporting sources", mismatch,
                                    [s for s in expected_sources if s not in sources],
                                    sorted(sources - set(expected_sources))))
        problems = reasoning_problems(golden)
        findings.append(Finding("reasoning path", mismatch, [f"{len(problems)} problem(s)", *problems])
                        if problems else Finding("reasoning path", PASS, ["matches the rules and the case"]))

    if "functional_level" in criteria:
        description = record.components.functional.description
        actual = description.statement.id if description else None
        expected = golden.data["expected_answer"]["functional_level"]
        findings.append(Finding("functional level", PASS, [f"shown: {actual or 'none'}, as expected"])
                        if actual == expected else
                        Finding("functional level", mismatch, [f"expected {expected or 'none'}, "
                                                               f"shown {actual or 'none'}"]))

    if "gaps" in criteria:
        if gaps_skipped or record.knowledge_warning:
            findings.append(Finding("gaps", SKIP, [gaps_skipped or record.knowledge_warning]))
        else:
            expected = {gap["field"]: gap["source_expected"] for gap in golden.data["expected_answer"]["gaps"]}
            shown = {gap.field: gap for gap in record.gaps}
            sources = [f"{field}: source {'expected' if want else 'not expected'}, "
                       f"{'cited ' + shown[field].evidence.citation if shown[field].evidence else 'none cited'}"
                       for field, want in expected.items()
                       if field in shown and want is not None and want != (shown[field].evidence is not None)]
            findings.append(_difference("gaps", mismatch, [f for f in expected if f not in shown],
                                        [f for f in shown if f not in expected], sources))
            excluded = [f"{gap.field}: {gap.evidence.chunk_id}" for gap in record.gaps
                        if gap.evidence and gap.evidence.doc_id in RETRIEVAL_EXCLUDED_DOCUMENTS]
            findings.append(Finding("excluded documents", FAIL, [f"{len(excluded)} gap(s) cite one", *excluded])
                            if excluded else Finding("excluded documents", PASS, ["no gap cites one"]))
    return findings


# ---- Running ----------------------------------------------------------------


def search_unavailable(store_dir: Path = VECTOR_STORE_DIR) -> Optional[str]:
    """Why the gap checks can't search here, or None. Never loads or downloads the model."""
    info_path = store_dir / INFO_FILE
    if not info_path.is_file():
        return f"no vector store in {_shown(store_dir)}; build it with: python -m knowledge.ingest"
    info = json.loads(info_path.read_text(encoding="utf-8"))
    if info.get("model") != EMBEDDING_MODEL_NAME or info.get("revision") != EMBEDDING_MODEL_REVISION:
        return (f"the vector store was built with {info.get('model')} ({info.get('revision')}), not "
                f"{EMBEDDING_MODEL_NAME}; rebuild it with: python -m knowledge.ingest")
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return "huggingface_hub is not installed, so the embedding model can't be looked up"
    if not isinstance(try_to_load_from_cache(EMBEDDING_MODEL_NAME, "config.json",
                                             revision=EMBEDDING_MODEL_REVISION), str):
        return (f"the embedding model {EMBEDDING_MODEL_NAME} ({EMBEDDING_MODEL_REVISION[:7]}) is not in the "
                "local Hugging Face cache (this command never downloads it; see README.md)")
    return None


def _not_searched(reason: str):
    def retrieve(case: Case):
        raise KnowledgeBaseMissing(reason)
    return retrieve


def run_case(path: Path, gaps_skipped: Optional[str]) -> tuple[Optional[GoldenCase], list[Finding]]:
    try:
        golden = read_golden_case(path)
    except ValueError as error:
        return None, [Finding("case file", ERROR, [str(error)])]
    try:
        record = analyse_case(golden.case, retrieve=_not_searched(gaps_skipped) if gaps_skipped else None)
    except Exception as error:  # the analysis itself failed: report it with the case, go on
        return golden, [Finding("analysis", ERROR, [f"{type(error).__name__}: {error}"])]
    return golden, check_case(golden, record, gaps_skipped)


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def describe(golden: GoldenCase) -> str:
    case = golden.case
    k_level = f", {case.activity.k_level.value}" if case.activity.k_level else ""
    return (f"{golden.id}  [{golden.data['review_status']}]  "
            f"{case.amputation_level.value}, {case.side.value}{k_level}")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m intake.golden_cases", description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help=f"case files (default: {_shown(GOLDEN_CASES_DIR)}/*.json)")
    parser.add_argument("--no-search", action="store_true", help="skip the gap checks (no embedding model)")
    args = parser.parse_args(argv)
    paths = args.files or sorted(GOLDEN_CASES_DIR.glob("*.json"))
    if not paths:
        sys.exit(f"No golden cases in {_shown(GOLDEN_CASES_DIR)}")

    gaps_skipped = "skipped with --no-search" if args.no_search else search_unavailable()
    if gaps_skipped:
        print(f"Gap checks SKIPPED: {gaps_skipped}")
    else:
        print("Gap checks search the source library; the first case loads the model (10-30 s) ...")
    totals = dict.fromkeys((PASS, WARN, FAIL, SKIP, ERROR), 0)
    for path in paths:
        golden, findings = run_case(path, gaps_skipped)
        print(f"\n{describe(golden) if golden else path.name}")
        for finding in findings:
            totals[finding.status] += 1
            print(f"  {finding.status:5} {finding.check:18} {finding.lines[0]}")
            for line in finding.lines[1:]:
                print(f"  {'':5} {'':18} - {line}")
    print(f"\n{len(paths)} case(s): " + ", ".join(f"{count} {status}" for status, count in totals.items()))
    return 1 if totals[FAIL] or totals[ERROR] else 0


if __name__ == "__main__":
    sys.exit(main())
