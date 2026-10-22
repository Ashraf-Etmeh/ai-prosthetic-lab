"""Flags on the AI's kept sentences: measurement only. Nothing is removed, changed or shown.

  python -m reasoning.sentence_checks [CASE_FILE ...]   flags in stored case files (default: data/cases/*.json)

The quote check (reasoning/quote_check.py) proves a quote is in its passage,
not that the AI's sentence says only what the quote says. These checks look,
by code, for the failures the blueprint lists (§5 step 2 and step 4; §8) in
each kept item's English sentence, its Arabic sentence and its quote:

  number not in quote      a number in the English sentence the quote doesn't have
                           (years and the digits of codes left out)
  numbers differ in Arabic the Arabic sentence's numbers (Arabic-Indic digits read
                           as 0-9) are not the English sentence's
  code not in quote        a K-level (K0-K4) or HCPCS L-code the quote doesn't have
  codes differ in Arabic   the two sentences name different codes
  level not in quote       an amputation level the sentence names that the quote
                           doesn't (synonyms such as "TT", "below-knee" count)
  negation differs         one of sentence and quote negates (not, no, never,
                           without, ...) and the other doesn't
  advice wording           a directive, a choice or ranking, a readiness verdict or
                           a recommendation in the sentence's own voice (CLAUDE.md
                           principle 1); "also in the quote" when the quote has the word
  advice wording in Arabic the same in the Arabic sentence (fewer patterns)

They are deliberately simple and will flag some faithful sentences (a source's
own "should", an Arabic number written as a word). Until the owner approves
patterns, from flags counted on real AI output (`golden_cases --rag`, or this
command over stored cases), a flag is a measurement: the item stays on the page
exactly as before.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

NUMBER_NOT_IN_QUOTE = "number not in quote"
NUMBERS_DIFFER_AR = "numbers differ in Arabic"
CODE_NOT_IN_QUOTE = "code not in quote"
CODES_DIFFER_AR = "codes differ in Arabic"
LEVEL_NOT_IN_QUOTE = "level not in quote"
NEGATION_DIFFERS = "negation differs"
ADVICE = "advice wording"
ADVICE_AR = "advice wording in Arabic"
KINDS = (NUMBER_NOT_IN_QUOTE, NUMBERS_DIFFER_AR, CODE_NOT_IN_QUOTE, CODES_DIFFER_AR, LEVEL_NOT_IN_QUOTE,
         NEGATION_DIFFERS, ADVICE, ADVICE_AR)

_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)
_CODE = re.compile(r"(?<![A-Za-z0-9])(K[0-4]|L\d{4})(?![A-Za-z0-9])", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\d.,])\d+(?:[.,]\d+)?(?![\d])")
_LEVELS = {  # canonical level: the ways a source or a sentence names it
    "transtibial": r"trans-?tibial|below[- ]knee|\bTT\b",
    "transfemoral": r"trans-?femoral|above[- ]knee|\bTF\b",
    "knee disarticulation": r"knee disarticulation|through[- ]knee",
    "hip disarticulation": r"hip disarticulation",
    "partial foot": r"partial[- ]foot",
    "Syme": r"\bsyme",
    "transradial": r"trans-?radial|below[- ]elbow",
    "transhumeral": r"trans-?humeral|above[- ]elbow",
    "wrist disarticulation": r"wrist disarticulation",
    "elbow disarticulation": r"elbow disarticulation",
    "shoulder disarticulation": r"shoulder disarticulation",
    "partial hand": r"partial[- ]hand",
}
_NEGATION = re.compile(r"\b(not|no|never|without|none|neither|nor|cannot)\b|n't\b", re.IGNORECASE)
_ADVICE = {
    "directive": r"\b(should|must|needs? to|has to|have to|ought to)\b",
    "choice or ranking": r"\b(best|better|first choice|preferred|choose|select|ideal|optimal|ranks?|ranked)\b",
    "readiness verdict": r"\b(this|the) (patient|person|case) (is|are|seems|appears|would be)( not)? "
                         r"(ready|eligible|a candidate|suitable)\b",
    "own recommendation": r"\b(I|we) (recommend|suggest|advise)\b|\brecommended for (this|the) (patient|person|case)\b",
}
_ADVICE_AR = {
    "directive": r"(يجب|ينبغي|لا بد|لا بدّ)",
    "choice or ranking": r"(الأفضل|الأنسب|الخيار الأول)",
    "readiness verdict": r"\b(جاهز|جاهزة|مؤهل|مؤهلة)\b",
}


@dataclass(frozen=True)
class Flag:
    kind: str  # one of KINDS
    detail: str


def _codes(text: str) -> set[str]:
    return {code.upper() for code in _CODE.findall(text.translate(_DIGITS))}


def _numbers(text: str) -> set[str]:
    """Numbers as written (comma read as a decimal point), leaving out codes' digits and years."""
    text = _CODE.sub(" ", text.translate(_DIGITS))
    found = {n.replace(",", ".") for n in _NUMBER.findall(text)}
    return {n for n in found if not (len(n) == 4 and n.isdigit() and 1950 <= int(n) <= 2099)}


def _levels(text: str) -> set[str]:
    return {level for level, pattern in _LEVELS.items() if re.search(pattern, text, re.IGNORECASE)}


def _matches(patterns: dict[str, str], text: str, flags: int = re.IGNORECASE) -> list[tuple[str, str]]:
    return [(name, match.group(0)) for name, pattern in patterns.items() for match in re.finditer(pattern, text, flags)]


def flags(quote: str, sentence_en: str, sentence_ar: str) -> list[Flag]:
    """Every flag for one item. An empty list: none of the checks found anything."""
    found: list[Flag] = []
    quote_numbers, en_numbers, ar_numbers = _numbers(quote), _numbers(sentence_en), _numbers(sentence_ar)
    for number in sorted(en_numbers - quote_numbers):
        found.append(Flag(NUMBER_NOT_IN_QUOTE, number))
    if en_numbers != ar_numbers:
        found.append(Flag(NUMBERS_DIFFER_AR, f"English {sorted(en_numbers)}, Arabic {sorted(ar_numbers)}"))
    quote_codes, en_codes, ar_codes = _codes(quote), _codes(sentence_en), _codes(sentence_ar)
    for code in sorted(en_codes - quote_codes):
        found.append(Flag(CODE_NOT_IN_QUOTE, code))
    if en_codes != ar_codes:
        found.append(Flag(CODES_DIFFER_AR, f"English {sorted(en_codes)}, Arabic {sorted(ar_codes)}"))
    for level in sorted(_levels(sentence_en) - _levels(quote)):
        found.append(Flag(LEVEL_NOT_IN_QUOTE, level))
    quote_negates, sentence_negates = bool(_NEGATION.search(quote)), bool(_NEGATION.search(sentence_en))
    if quote_negates != sentence_negates:
        found.append(Flag(NEGATION_DIFFERS, "the quote negates, the sentence doesn't" if quote_negates
                          else "the sentence negates, the quote doesn't"))
    for name, words in _matches(_ADVICE, sentence_en):
        also = " (also in the quote)" if re.search(rf"\b{re.escape(words)}\b", quote, re.IGNORECASE) else ""
        found.append(Flag(ADVICE, f"{name}: {words!r}{also}"))
    for name, words in _matches(_ADVICE_AR, sentence_ar, 0):
        found.append(Flag(ADVICE_AR, f"{name}: {words!r}"))
    return found


def item_flags(item) -> list[Flag]:
    """Flags for a kept item (reasoning/rag.py Item)."""
    return flags(item.quote, item.sentence_en, item.sentence_ar)


# ---- Over stored cases ------------------------------------------------------


def stored_items(path: Path):
    """(case id, item) for every kept item in one case file; nothing for a case analysed without the AI."""
    from reasoning.rag import Generation  # here: the checks themselves need nothing from the RAG module

    data = json.loads(path.read_text(encoding="utf-8"))
    if not data.get("generation"):
        return
    generation = Generation.from_dict(data["generation"])
    for part in generation.parts.values():
        for item in part.items:
            yield data.get("case", {}).get("case_id", path.stem), item


def main(argv=None) -> int:
    from shared.config import CASES_DIR

    if hasattr(sys.stdout, "reconfigure"):  # a console; not when the output is captured
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m reasoning.sentence_checks", description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help=f"case files (default: {CASES_DIR}/*.json)")
    args = parser.parse_args(argv)
    paths = args.files or sorted(CASES_DIR.glob("*.json"))
    items = flagged = 0
    kinds = dict.fromkeys(KINDS, 0)
    for path in paths:
        for case_id, item in stored_items(path):
            items += 1
            found = item_flags(item)
            flagged += bool(found)
            for flag in found:
                kinds[flag.kind] += 1
                print(f"{case_id}  {item.id}  {flag.kind}: {flag.detail}")
    print(f"\n{len(paths)} case file(s), {items} kept AI item(s), {flagged} flagged (measurement only: nothing "
          "was removed)")
    for kind, count in kinds.items():
        if count:
            print(f"  {kind:26} {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
