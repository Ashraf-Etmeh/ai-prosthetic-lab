"""Golden cases: fake cases with the output they must give, checked against the app's analysis.

  python -m quality.golden_cases                 every data/quality/golden_cases/*.json
  python -m quality.golden_cases FILE ...        only these files
  python -m quality.golden_cases --no-search     statements and functional level only
  python -m quality.golden_cases --rag           also measure the RAG: calls the AI writer's API
                                                (shared/config.py LLM_PROVIDER; three calls per
                                                case: free-tier quota or money, ask first)
  python -m quality.golden_cases --held-out      the frozen held-out cases instead (only when
                                                the owner asks; combines with the options above)

Held-out cases (2026-10-13). The development cases in data/quality/golden_cases/
are run by default and may be looked at while tuning the search, the topics
or the prompt. The cases in data/quality/golden_cases_held_out/ are set aside to
measure whether that tuning carries over to cases it never saw: they are
frozen (each one's content hash in data/quality/golden_cases_held_out.json,
checked by the tests and before every --held-out run), never edited to fit
the app, and run only with --held-out. A held-out file can't be named
without --held-out, and --held-out runs nothing if a case differs from its
frozen hash. A change the owner decides on gets a new hash, date and note
in the manifest.

Since the RAG (2026-10-11) the review page's statements come from the search
and the AI, and the hand-written statements are the answer key. So:
- the statement, supporting-source, reasoning-path and functional-level
  checks test the answer key itself: what the hand-written rules
  (prosthetics/component_support.py, fitting_support.py) give for the case;
- the gap checks test the page's gap list; without --rag the AI is switched
  off, so the gaps come from the search and topic-word check, as before;
- --rag measures the RAG against the answer key: how many expected
  statements a checked RAG quote covers (same document, a run of
  COVER_WORDS words in common, counted for the statement it matches best:
  counted_for), any statement the case must not show that
  one covers, what the quote check removed, the gap sources, the kept items
  the sentence checks flag (reasoning/sentence_checks.py), and the tokens,
  time and estimated cost. These are measurements (INFO, or WARN for a
  statement that must not be shown or an AI part that didn't answer): they
  never fail the run.

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
and, optionally:
  interface_language               "ar": the case is submitted through POST /intake with the
                                   Arabic interface, filled in as an Arabic user would (لا يوجد
                                   for "none"); the case it stores must be the question
  twin_of                          the id of a case whose analysis this one must match exactly
                                   (statements, functional level, notes, gaps and, with the
                                   search, the passage each gap cites)

An orthotic case (question with "domain": "orthotics", added 2026-10-22) is
checked on its gaps only (evaluation_criteria ["gaps"], against
orthotics/fields.py FIELDS): there is no orthotic answer key yet,
so its statements_present, statements_absent, reasoning_path and
supporting_sources are empty and its functional_level null. It is entered
in English (no interface_language) and has no twin_of. With --rag its
measurements are the quote check, the gap sources and the sentence flags.

Every case goes through reasoning/pathway.py analyse_case(), the analysis behind
POST /intake (an Arabic one through the route itself, with the case store in
memory only, so nothing reaches data/records/cases/). The statement and functional-level checks don't depend on the
search, so they run without the embedding model. The gap checks need the
model and the vector store: without either (or with --no-search) they are
SKIPPED, with the reason; the model is never downloaded here.

Each check prints PASS, or what is missing and unexpected: FAIL in a
"reviewed" case, WARN in an "unreviewed" one. A gap citing a document the
search must leave out (RETRIEVAL_EXCLUDED_DOCUMENTS) is FAIL in any case, and
a malformed file is ERROR. Exit status 1 if anything is FAIL or ERROR.
"""

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from knowledge.catalog import load_catalog
from knowledge.ingest import INFO_FILE
from knowledge.retrieval import KnowledgeBaseMissing
from orthotics.case import OrthoticCase
from prosthetics import component_guide, fitting_guide
from prosthetics import intake as prosthetic_intake
from prosthetics.case import Case
from prosthetics.component_guide import K_LEVEL_DESCRIPTIONS
from prosthetics.component_support import component_support
from prosthetics.fitting_support import fitting_support
from reasoning import pathway
from reasoning.models import ORIGIN_RAG, ComponentSupport, FittingSupport, GuidelineStatement
from reasoning.pathway import analyse_case
from reasoning.sentence_checks import item_flags
from reasoning.writer import OfflineWriter, Writer, provider_writer
from shared.case_schema import case_from_dict
from shared.config import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_REVISION,
    GOLDEN_CASES_DIR,
    GOLDEN_HELD_OUT_DIR,
    GOLDEN_HELD_OUT_MANIFEST,
    PROJECT_ROOT,
    RETRIEVAL_EXCLUDED_DOCUMENTS,
    VECTOR_STORE_DIR,
)
from shared.field_guide import fields_for
from shared.forms import MAX_PRIOR_DEVICES
from shared.i18n import LANGUAGE_COOKIE, LANGUAGES
from shared.store import CaseRecord, CaseStore

KEYS = ("id", "description", "review_status", "question", "expected_answer", "common_wrong_answers",
        "supporting_sources", "reasoning_path", "evaluation_criteria")
OPTIONAL_KEYS = ("interface_language", "twin_of")
REVIEW_STATUSES = ("unreviewed", "reviewed")
# What a user of each interface types in the comorbidities box for "none" (shared/forms.py NONE_ANSWERS).
NONE_TYPED = {"en": "none", "ar": "لا يوجد"}
# Set by the app, not by the form: left out when the stored case is compared with the question.
GENERATED = ("case_id", "created_at")
CRITERIA = ("statements", "gaps", "functional_level")
RULE_FIELDS = ("levels", "k_levels", "ambulators_only", "unilateral_only", "bilateral_only")
RULES = {rule.statement.id: rule for rule in (*component_guide.RULES, *fitting_guide.RULES)}
K_LEVEL_IDS = {statement.id for statement in K_LEVEL_DESCRIPTIONS.values()}
K_LEVEL_BY_ID = {statement.id: statement for statement in K_LEVEL_DESCRIPTIONS.values()}

PASS, WARN, FAIL, SKIP, ERROR, INFO = "PASS", "WARN", "FAIL", "SKIP", "ERROR", "INFO"
# Without --rag the AI is never called: the gaps come from the search and topic-word check.
NO_AI = OfflineWriter("golden cases run without the AI (use --rag to measure the RAG)")
# A RAG quote covers an expected statement when it is from the same document
# and they share a run of this many words.
COVER_WORDS = 6
# Dollars per million tokens (input, output), to estimate a --rag run's cost.
# Not listed: Gemini on the free tier, which charges nothing.
PRICES = {"claude-opus-5-5": (4.0, 20.0)}


@dataclass
class GoldenCase:
    path: Path
    data: dict
    case: Case | OrthoticCase

    @property
    def orthotic(self) -> bool:
        return self.case.domain == "orthotics"

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

    @property
    def interface_language(self) -> str:
        return self.data.get("interface_language", "en")

    @property
    def twin_of(self) -> Optional[str]:
        return self.data.get("twin_of")


@dataclass
class Finding:
    check: str
    status: str
    lines: list[str]  # the first is the summary; the rest are listed below it
    numbers: dict = field(default_factory=dict)  # --rag: counts added up over all cases


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
        if not isinstance(data, dict):
            raise ValueError("the file must hold one JSON object")
        _keys("the file", {key: value for key, value in data.items() if key not in OPTIONAL_KEYS}, KEYS)
        if data.get("interface_language", "en") not in LANGUAGES:
            raise ValueError(f"interface_language must be one of {list(LANGUAGES)}")
        twin = data.get("twin_of")
        if twin is not None and (twin == data["id"] or not (path.parent / f"{twin}.json").is_file()):
            raise ValueError(f"twin_of {twin!r} must be the id of another case file in {path.parent.name}/")
        if data["id"] != path.stem:
            raise ValueError(f"id {data['id']!r} must be the file name ({path.stem!r})")
        if data["review_status"] not in REVIEW_STATUSES:
            raise ValueError(f"review_status must be one of {list(REVIEW_STATUSES)}")
        criteria = data["evaluation_criteria"]
        if not criteria:
            raise ValueError("evaluation_criteria is empty")
        _id_list("evaluation_criteria", criteria, CRITERIA, "a check")

        case = case_from_dict(data["question"])
        if case.to_dict() != data["question"]:
            raise ValueError("question must be exactly what Case.to_dict() gives (every field, values as stored)")
        if case.case_id != data["id"]:
            raise ValueError(f"question.case_id must be {data['id']!r}")
        if case.domain == "orthotics":
            _orthotic_shape(data)

        expected = data["expected_answer"]
        _keys("expected_answer", expected, ("gaps", "statements_present", "functional_level"))
        gaps = expected["gaps"]
        if not isinstance(gaps, list):
            raise ValueError("expected_answer.gaps must be a list")
        for gap in gaps:
            _keys("each expected gap", gap, ("field", "source_expected"))
            if gap["source_expected"] is not None and not isinstance(gap["source_expected"], bool):
                raise ValueError(f"gap {gap['field']}: source_expected must be true, false or null")
        _id_list("expected_answer.gaps", [gap["field"] for gap in gaps], {info.path for info in fields_for(case)},
                 f"a gap field of a {case.domain} case")
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


def _orthotic_shape(data: dict) -> None:
    """An orthotic case is checked on its gaps only: there is no orthotic answer key yet."""
    if data["evaluation_criteria"] != ["gaps"]:
        raise ValueError('an orthotic case has evaluation_criteria ["gaps"] only: there is no orthotic '
                         "answer key yet (statements and functional level)")
    expected, wrong = data["expected_answer"], data["common_wrong_answers"]
    if (expected.get("statements_present") or expected.get("functional_level") is not None
            or wrong.get("statements_absent") or data["supporting_sources"] or data["reasoning_path"]):
        raise ValueError("an orthotic case has empty statements_present, statements_absent, supporting_sources "
                         "and reasoning_path, and a null functional_level")
    if "interface_language" in data or "twin_of" in data:
        raise ValueError("an orthotic case is entered in English and has no twin_of")


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


def reference(case: Case) -> tuple[ComponentSupport, FittingSupport]:
    """The answer key for the case: the hand-written statements the rules give."""
    return component_support(case), fitting_support(case)


def check_case(golden: GoldenCase, record: CaseRecord, gaps_skipped: Optional[str] = None,
               rag: bool = False) -> list[Finding]:
    """The findings for one case. gaps_skipped: why the gap checks can't run (None: they can).

    The statement and functional-level checks read the answer key (reference());
    the gap checks read the record. With `rag`, the RAG's measurements follow.
    """
    mismatch = FAIL if golden.reviewed else WARN
    criteria = golden.data["evaluation_criteria"]
    if "statements" in criteria or "functional_level" in criteria:
        components, fitting = reference(golden.case)
    findings = []

    if "statements" in criteria:
        shown = [cited.statement for cited in (*components.statements, *fitting.statements)]
        shown_ids = [statement.id for statement in shown]
        unexpected = [f"{i} (listed in statements_absent)" if i in golden.absent else f"{i} (not listed)"
                      for i in shown_ids if i not in golden.present]
        findings.append(_difference("statements", mismatch,
                                    [i for i in golden.present if i not in shown_ids], unexpected))
        sources = {statement.doc_id for statement in shown}
        if components.functional.description:
            sources.add(components.functional.description.statement.doc_id)
        expected_sources = golden.data["supporting_sources"]
        findings.append(_difference("supporting sources", mismatch,
                                    [s for s in expected_sources if s not in sources],
                                    sorted(sources - set(expected_sources))))
        problems = reasoning_problems(golden)
        findings.append(Finding("reasoning path", mismatch, [f"{len(problems)} problem(s)", *problems])
                        if problems else Finding("reasoning path", PASS, ["matches the rules and the case"]))

    if "functional_level" in criteria:
        description = components.functional.description
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
            # The expected sources were set from the search and topic-word check; the AI picks its
            # own, so with --rag a difference is a measurement, not a failure.
            findings.append(_difference("gaps", mismatch, [f for f in expected if f not in shown],
                                        [f for f in shown if f not in expected], () if rag else sources))
            if rag:
                cited = sum(1 for gap in record.gaps if gap.evidence)
                findings.append(Finding("rag gap sources", INFO, [
                    f"{cited} of {len(record.gaps)} gaps cite a passage; {len(sources)} differ from the "
                    "golden file (set from the topic-word check)", *(f"source: {s}" for s in sources)],
                    {"gaps": len(record.gaps), "gaps_cited": cited}))
            excluded = [f"{gap.field}: {gap.evidence.chunk_id}" for gap in record.gaps
                        if gap.evidence and gap.evidence.doc_id in RETRIEVAL_EXCLUDED_DOCUMENTS]
            findings.append(Finding("excluded documents", FAIL, [f"{len(excluded)} gap(s) cite one", *excluded])
                            if excluded else Finding("excluded documents", PASS, ["no gap cites one"]))
    if rag:
        findings += rag_findings(golden, record)
    return findings


# ---- Measuring the RAG against the answer key ----------------------------------


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", unicodedata.normalize("NFKC", text).lower())


def shares_a_run(quote: str, statement: str, n: int = COVER_WORDS) -> bool:
    """Whether the two texts share a run of n words (or all of the shorter one)."""
    a, b = _words(quote), _words(statement)
    n = min(n, len(a), len(b))
    if n == 0:
        return False
    runs = {tuple(b[i:i + n]) for i in range(len(b) - n + 1)}
    return any(tuple(a[i:i + n]) in runs for i in range(len(a) - n + 1))


def longest_run(quote: str, statement: str) -> int:
    """The number of words in the longest run the two texts share."""
    a, b = _words(quote), _words(statement)
    best, previous = 0, [0] * (len(b) + 1)
    for word in a:
        current = [0] * (len(b) + 1)
        for j, other in enumerate(b, 1):
            if word == other:
                current[j] = previous[j - 1] + 1
                best = max(best, current[j])
        previous = current
    return best


def _text(statement: GuidelineStatement) -> str:
    return " ".join([statement.quote.text, *statement.quote.items])


def _answer_key_by_doc() -> dict[str, list[GuidelineStatement]]:
    by_doc: dict[str, list[GuidelineStatement]] = {}
    for statement in (*(rule.statement for rule in RULES.values()), *K_LEVEL_BY_ID.values()):
        by_doc.setdefault(statement.doc_id, []).append(statement)
    return by_doc


# Every hand-written statement a RAG quote can be counted for, by document.
ANSWER_KEY_BY_DOC = _answer_key_by_doc()


def counted_for(quote: str, doc_id: str) -> set[str]:
    """The answer-key statements a RAG quote covers.

    Of the statements of its document that share a run of COVER_WORDS words
    with it: the one(s) sharing the longest run, and any it holds whole.
    Statements of one document often share stock wording (the CMS K-level
    descriptions; ICRC's transtibial and transfemoral alignment sentences,
    which differ by two words), so a 6-word run alone credited one quote to
    several statements (2026-10-23: a transtibial quote counted as the
    transfemoral statement a transtibial case must not show). A page rule
    would not do: VA/DoD prints each recommendation on several pages.
    """
    runs = {}
    for statement in ANSWER_KEY_BY_DOC.get(doc_id, []):
        text = _text(statement)
        if shares_a_run(quote, text):
            runs[statement.id] = (longest_run(quote, text), len(_words(text)))
    best = max((run for run, _ in runs.values()), default=0)
    return {i for i, (run, size) in runs.items() if run == best or run == size}


def covering(statement: GuidelineStatement, record: CaseRecord) -> list[str]:
    """The ids of the RAG statements whose quote covers a hand-written statement (counted_for)."""
    return [cited.statement.id for cited in record.shown_statements()
            if cited.origin == ORIGIN_RAG and cited.statement.doc_id == statement.doc_id
            and statement.id in counted_for(cited.statement.quote.text, statement.doc_id)]


def estimated_cost(usage: dict, model: str) -> Optional[float]:
    price = PRICES.get(model)
    if price is None:
        return None
    return (usage.get("input_tokens", 0) * price[0] + usage.get("output_tokens", 0) * price[1]) / 1_000_000


def rag_findings(golden: GoldenCase, record: CaseRecord) -> list[Finding]:
    """What the RAG gave for the case, measured against the answer key. Never FAIL.

    An orthotic case has no answer key yet: no coverage or must-not-show measure.
    """
    findings, covered = [], {}
    if not golden.orthotic:
        expected = [RULES[i].statement for i in golden.present]
        level = golden.data["expected_answer"]["functional_level"]
        if level:
            expected.append(K_LEVEL_BY_ID[level])
        covered = {statement.id: covering(statement, record) for statement in expected}
        missed = [i for i, by in covered.items() if not by]
        hit = len(expected) - len(missed)
        findings.append(Finding("rag coverage", INFO, [
            f"{hit} of {len(expected)} expected statements covered by a checked RAG quote"
            + (f" ({100 * hit // len(expected)}%)" if expected else ""), *(f"not covered: {i}" for i in missed)],
            {"expected": len(expected), "covered": hit}))

        forbidden = {i: by for i in golden.absent if (by := covering(RULES[i].statement, record))}
        findings.append(Finding("rag must-not-show", WARN if forbidden else PASS, [
            f"{len(forbidden)} statement(s) the case must not show are covered" if forbidden
            else "none of the statements the case must not show is covered",
            *(f"{i}: by {', '.join(by)}" for i, by in forbidden.items())], {"forbidden_shown": len(forbidden)}))

    rag = [cited for cited in record.shown_statements() if cited.origin == ORIGIN_RAG]
    used = {i for by in covered.values() for i in by}
    generation = record.generation
    parts = generation.parts.values() if generation else []
    unavailable = [f"{part.kind}: {part.reason}" for part in parts if part.status == "unavailable"]
    if unavailable:
        findings.append(Finding("rag parts", WARN, [f"{len(unavailable)} part(s) not answered", *unavailable]))
    kept = sum(len(part.items) for part in parts)
    removed = [entry for part in parts for entry in part.removed if entry["dropped"] == "item"]
    usage = {key: sum(part.usage.get(key, 0) for part in parts) for key in ("input_tokens", "output_tokens")}
    cost = estimated_cost(usage, generation.writer) if generation else None
    seconds = max((part.seconds or 0 for part in parts), default=0)
    findings.append(Finding("rag answer", INFO, [
        f"{len(rag)} statements shown ({len(rag) - len(used)} match no expected statement); quote check kept "
        f"{kept}, removed {len(removed)}; {usage['input_tokens']} input + {usage['output_tokens']} output "
        f"tokens, {seconds:.0f} s" + (f", about ${cost:.2f}" if cost is not None else ""),
        *(f"removed ({entry['topic']}): {entry['reason']}" for entry in removed)],
        {"shown": len(rag), "kept": kept, "removed": len(removed), "cost": cost or 0.0, "seconds": seconds,
         **usage}))

    # reasoning/sentence_checks.py: counted for calibration, never removed (the item stays on the page).
    flagged = [(item, flag) for part in parts for item in part.items for flag in item_flags(item)]
    items_flagged = len({item.id for item, _ in flagged})
    findings.append(Finding("rag sentence flags", INFO, [
        f"{items_flagged} of {kept} kept items flagged by the sentence checks (measurement only: nothing removed)",
        *(f"{item.id}: {flag.kind}: {flag.detail}" for item, flag in flagged)], {"flagged": items_flagged}))
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


def intake_form(question: dict, language: str) -> dict[str, str]:
    """The intake form filled in with the question, as a user of that interface would."""
    def text(value) -> str:
        return "" if value is None else str(value)

    limb, activity = question["residual_limb"], question["activity"]
    form = {
        "amputation_level": text(question["amputation_level"]), "side": text(question["side"]),
        "age_years": text(question["age_years"]), "body_weight_kg": text(question["body_weight_kg"]),
        "etiology": text(question["etiology"]),
        "months_since_amputation": text(question["months_since_amputation"]),
        "wound_status": text(limb["wound_status"]), "volume_stability": text(limb["volume_stability"]),
        "skin_condition": text(limb["skin_condition"]), "length_description": text(limb["length_description"]),
        "pain": text(limb["pain"]), "sensation": text(limb["sensation"]),
        "k_level": text(activity["k_level"]), "activity_description": text(activity["description"]),
        "functional_goals": text(activity["functional_goals"]),
        "contralateral_limb_status": text(question["contralateral_limb_status"]),
        "cognitive_status": text(question["cognitive_status"]), "intake_notes": text(question["intake_notes"]),
    }
    comorbidities = question["comorbidities"]
    form["comorbidities"] = (NONE_TYPED[language] if comorbidities == [] else "\n".join(comorbidities or []))
    devices = question["prior_devices"]
    if devices == []:
        form["no_prior_devices"] = "on"
    for n, device in enumerate(devices or [], start=1):
        current = device["currently_using"]
        form.update({f"device_{n}_description": device["device_description"],
                     f"device_{n}_years": text(device["years_used"]),
                     f"device_{n}_current": "" if current is None else ("yes" if current else "no"),
                     f"device_{n}_issues": text(device["issues"])})
    return form


@contextmanager
def _intake_route(retrieve):
    """POST /intake with this search (None: the normal one), saving cases in memory only."""
    saved = prosthetic_intake.store, pathway.retrieve_relevant_chunks
    prosthetic_intake.store = CaseStore(folder=None)  # never data/records/cases/
    if retrieve is not None:
        pathway.retrieve_relevant_chunks = retrieve
    try:
        yield prosthetic_intake.store
    finally:
        prosthetic_intake.store, pathway.retrieve_relevant_chunks = saved


def submit_through_form(golden: GoldenCase, retrieve, writer: Writer = NO_AI) -> tuple[Finding, Optional[CaseRecord]]:
    """Submit the question through the intake form in the case's interface language.

    The finding says whether the form took it and stored exactly the question
    (apart from the generated id and time); the record is what it stored.
    """
    from app import create_app  # here: the Flask app is only needed for this

    mismatch = FAIL if golden.reviewed else WARN
    language = golden.interface_language
    if len(golden.data["question"]["prior_devices"] or []) > MAX_PRIOR_DEVICES:
        return Finding("intake form", mismatch, [f"more than {MAX_PRIOR_DEVICES} prior devices: "
                                                 "the form has no row for them"]), None
    app = create_app()
    app.config["RAG_WRITER"] = writer
    client = app.test_client()
    client.set_cookie(LANGUAGE_COOKIE, language)
    with _intake_route(retrieve) as case_store:
        response = client.post("/intake", data=intake_form(golden.data["question"], language))
    if response.status_code != 302:
        return Finding("intake form", mismatch, [f"POST /intake ({language}) answered {response.status_code}, "
                                                 "not 302 (case saved)"]), None
    record = case_store.get(response.headers["Location"].rstrip("/").rsplit("/", 1)[-1])
    stored = {k: v for k, v in record.case.to_dict().items() if k not in GENERATED}
    asked = {k: v for k, v in golden.data["question"].items() if k not in GENERATED}
    differing = [f"{key}: stored {stored[key]!r}, question {asked[key]!r}" for key in asked if stored[key] != asked[key]]
    if differing:
        return Finding("intake form", mismatch, [f"{len(differing)} field(s) stored otherwise", *differing]), record
    return Finding("intake form", PASS, [f"submitted in '{language}', stored as the question"]), record


def _analysis(record: CaseRecord, searched: bool) -> dict[str, list]:
    """The parts of an analysis a twin must share; the cited passages only when the search ran.

    The statements, functional level and notes are the answer key's for the
    stored case; the gaps are the record's.
    """
    components, fitting = reference(record.case)
    description = components.functional.description
    parts = {
        "statements": [c.statement.id for c in (*components.statements, *fitting.statements)],
        "functional level": [description.statement.id if description else None],
        "notes": list(components.notes),
        "gaps": [f"{gap.field} ({gap.status})" for gap in record.gaps],
    }
    if searched:
        parts["gap sources"] = [f"{gap.field}: {gap.evidence.chunk_id if gap.evidence else 'none'}"
                                for gap in record.gaps]
    return parts


def compare_with_twin(golden: GoldenCase, record: CaseRecord, gaps_skipped: Optional[str]) -> Finding:
    """Compared without the AI: two AI answers may differ from run to run."""
    mismatch = FAIL if golden.reviewed else WARN
    twin = read_golden_case(golden.path.parent / f"{golden.twin_of}.json")
    twin_record = analyse_case(twin.case, retrieve=_not_searched(gaps_skipped) if gaps_skipped else None,
                               writer=NO_AI)
    searched = not gaps_skipped and not record.knowledge_warning and not twin_record.knowledge_warning
    mine, theirs = _analysis(record, searched), _analysis(twin_record, searched)
    differing = [f"{part}: {mine[part]} here, {theirs[part]} in {twin.id}" for part in mine if mine[part] != theirs[part]]
    if differing:
        return Finding("twin", mismatch, [f"differs from {twin.id} in {len(differing)} part(s)", *differing])
    compared = ", ".join(mine)
    return Finding("twin", PASS, [f"same analysis as {twin.id} ({compared})"])


def run_case(path: Path, gaps_skipped: Optional[str], writer: Writer = NO_AI,
             rag: bool = False) -> tuple[Optional[GoldenCase], list[Finding]]:
    """The findings for one case file. With `rag`, `writer` is the AI that is measured."""
    try:
        golden = read_golden_case(path)
    except ValueError as error:
        return None, [Finding("case file", ERROR, [str(error)])]
    retrieve = _not_searched(gaps_skipped) if gaps_skipped else None
    findings = []
    try:
        if golden.interface_language == "en":
            record = analyse_case(golden.case, retrieve=retrieve, writer=writer)
        else:
            form, record = submit_through_form(golden, retrieve, writer)
            findings.append(form)
            if record is None:
                return golden, findings  # nothing stored: nothing else to check
        findings += check_case(golden, record, gaps_skipped, rag=rag)
        if golden.twin_of:
            # With the AI, the twin's own gap sources would come from another answer: compare without it.
            twin_record = record if not rag else analyse_case(record.case, retrieve=retrieve, writer=NO_AI)
            findings.append(compare_with_twin(golden, twin_record, gaps_skipped))
    except Exception as error:  # the analysis itself failed: report it with the case, go on
        findings.append(Finding("analysis", ERROR, [f"{type(error).__name__}: {error}"]))
    return golden, findings


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


# ---- Held-out cases ---------------------------------------------------------


def content_hash(path: Path) -> str:
    """SHA-256 of the case file's JSON content: line endings and layout don't change it."""
    data = json.loads(path.read_text(encoding="utf-8"))
    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def frozen_problems() -> list[str]:
    """Where the held-out folder differs from its manifest: changed, missing or unlisted cases."""
    folder, manifest = GOLDEN_HELD_OUT_DIR, GOLDEN_HELD_OUT_MANIFEST
    if not manifest.is_file():
        return [f"{_shown(manifest)} is missing"]
    frozen = json.loads(manifest.read_text(encoding="utf-8"))["cases"]
    files = {path.stem: path for path in folder.glob("*.json")}
    problems = [f"{case_id}: frozen in {_shown(manifest)}, but not in {_shown(folder)}/"
                for case_id in sorted(set(frozen) - set(files))]
    problems += [f"{case_id}: in {_shown(folder)}/, but not frozen in {_shown(manifest)}"
                 for case_id in sorted(set(files) - set(frozen))]
    for case_id in sorted(set(files) & set(frozen)):
        try:
            changed = content_hash(files[case_id]) != frozen[case_id]["sha256"]
        except ValueError:
            changed = True  # no longer JSON
        if changed:
            problems.append(f"{case_id}: changed since it was frozen on {frozen[case_id]['frozen_on']}")
    return problems


def case_paths(files: list[Path], held_out: bool) -> list[Path]:
    """The case files to run: the development cases, or with held_out the frozen held-out ones.

    Exits with the reason, running nothing, if a held-out file is named
    without held_out, another file with it, or a held-out case differs from
    its frozen hash.
    """
    named_held_out = [path for path in files if path.resolve().parent == GOLDEN_HELD_OUT_DIR.resolve()]
    if not held_out:
        if named_held_out:
            sys.exit(f"Held-out case(s) {', '.join(path.stem for path in named_held_out)}: "
                     "run them with --held-out (only when the owner asks)")
        return files or sorted(GOLDEN_CASES_DIR.glob("*.json"))
    others = [path for path in files if path not in named_held_out]
    if others:
        sys.exit(f"--held-out runs only the cases in {_shown(GOLDEN_HELD_OUT_DIR)}/, "
                 f"not {', '.join(map(str, others))}")
    problems = frozen_problems()
    if problems:
        sys.exit("The held-out cases are not as frozen; nothing was run:\n  " + "\n  ".join(problems)
                 + "\nHeld-out cases are never edited to fit the app. If the owner decides a change is "
                 f"needed, record its new hash (content_hash), date and reason in {_shown(GOLDEN_HELD_OUT_MANIFEST)}.")
    return files or sorted(GOLDEN_HELD_OUT_DIR.glob("*.json"))


def describe(golden: GoldenCase) -> str:
    case = golden.case
    if golden.orthotic:
        months = f", {case.months_since_onset:g} months" if case.months_since_onset is not None else ""
        return (f"{golden.id}  [{golden.data['review_status']}]  orthotics: "
                f"{case.condition.value}, {case.side.value}{months}")
    k_level = f", {case.activity.k_level.value}" if case.activity.k_level else ", no K-level"
    if not case.is_lower_limb:
        k_level = ""
    language = f", {golden.interface_language} interface" if golden.interface_language != "en" else ""
    twin = f", twin of {golden.twin_of}" if golden.twin_of else ""
    return (f"{golden.id}  [{golden.data['review_status']}]  "
            f"{case.amputation_level.value}, {case.side.value}{k_level}{language}{twin}")


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m quality.golden_cases", description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help=f"case files (default: {_shown(GOLDEN_CASES_DIR)}/*.json)")
    parser.add_argument("--no-search", action="store_true", help="skip the gap checks (no embedding model)")
    parser.add_argument("--rag", action="store_true",
                        help="also measure the RAG: calls the AI writer's API (LLM_PROVIDER), three calls "
                             "per case (free-tier quota or money)")
    parser.add_argument("--held-out", action="store_true",
                        help=f"run the frozen held-out cases ({_shown(GOLDEN_HELD_OUT_DIR)}/) instead: "
                             "only when the owner asks, never to tune on")
    parser.add_argument("--record", action="store_true",
                        help="add the result to data/quality/results/runs.jsonl, for the quality page "
                             "(quality/results.py)")
    args = parser.parse_args(argv)
    paths = case_paths(args.files, args.held_out)
    if not paths:
        sys.exit(f"No golden cases in {_shown(GOLDEN_HELD_OUT_DIR if args.held_out else GOLDEN_CASES_DIR)}")
    if args.held_out:
        print(f"HELD-OUT run: {len(paths)} frozen case(s), as frozen. Record the result in FUTURE_WORK.md "
              "and tune nothing on it.")

    gaps_skipped = "skipped with --no-search" if args.no_search else search_unavailable()
    if args.rag and gaps_skipped:
        sys.exit(f"--rag needs the search: {gaps_skipped}")
    if gaps_skipped:
        print(f"Gap checks SKIPPED: {gaps_skipped}")
    else:
        print("Gap checks search the source library; the first case loads the model (10-30 s) ...")
    writer = provider_writer() if args.rag else NO_AI
    if args.rag:
        print(f"RAG run: {writer.name}, three calls per case, about a minute per case ...")
    totals = dict.fromkeys((PASS, WARN, FAIL, SKIP, ERROR, INFO), 0)
    numbers: dict[str, float] = {}
    failed_cases = []
    for path in paths:
        golden, findings = run_case(path, gaps_skipped, writer=writer, rag=args.rag)
        print(f"\n{describe(golden) if golden else path.name}")
        if any(finding.status in (FAIL, ERROR) for finding in findings):
            failed_cases.append(golden.id if golden else path.stem)
        for finding in findings:
            totals[finding.status] += 1
            for key, value in finding.numbers.items():
                numbers[key] = numbers.get(key, 0) + value
            print(f"  {finding.status:5} {finding.check:18} {finding.lines[0]}")
            for line in finding.lines[1:]:
                print(f"  {'':5} {'':18} - {line}")
        sys.stdout.flush()
    print(f"\n{len(paths)} case(s): " + ", ".join(f"{count} {status}" for status, count in totals.items()))
    if args.rag and numbers:
        n = {key: int(value) if key != "cost" else value for key, value in numbers.items()}
        expected = n.get("expected", 0)
        print(f"RAG: {n.get('covered', 0)} of {expected} expected statements covered"
              + (f" ({100 * n.get('covered', 0) // expected}%)" if expected else "")
              + f"; {n.get('forbidden_shown', 0)} must-not-show statement(s) covered; "
              f"{n.get('gaps_cited', 0)} of {n.get('gaps', 0)} gaps cite a passage; quote check kept "
              f"{n.get('kept', 0)}, removed {n.get('removed', 0)}; {n.get('input_tokens', 0)} input + "
              f"{n.get('output_tokens', 0)} output tokens, about ${numbers.get('cost', 0):.2f}; "
              f"{n.get('flagged', 0)} kept items flagged by the sentence checks")
    if args.record:
        from quality import results  # here: only a recorded run needs it

        mode = results.RAG if args.rag else (results.NO_SEARCH if gaps_skipped else results.SEARCH)
        results.record_run(results.GOLDEN_CASES, {
            "set": results.HELD_OUT if args.held_out else results.DEVELOPMENT, "mode": mode,
            "cases": len(paths), "passed": len(paths) - len(failed_cases), "failed_cases": failed_cases,
            "totals": totals, "gaps_skipped": gaps_skipped,
            "rag": {key: int(value) if key != "cost" else round(value, 4) for key, value in numbers.items()}
            if args.rag else None})
        print(f"Recorded in {_shown(results.config.QUALITY_RESULTS_PATH)}")
    return 1 if totals[FAIL] or totals[ERROR] else 0


if __name__ == "__main__":
    sys.exit(main())
