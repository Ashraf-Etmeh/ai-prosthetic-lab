"""The quote check: is a quote the model gave really in the passage it names?

Every sentence the model writes (reasoning/rag.py) must carry a quote copied
from one retrieved passage. Before anything is shown, this module checks it:

1. The quote is found in the passage, compared the way the quote tests
   compare text (prosthetics/tests/test_component_guide.py): line breaks and runs of
   spaces count as one space, and both texts are NFKC-normalised, as the
   extracted text is. Curly and straight quotation marks and the dash
   characters are also taken as the same, since they print alike; any
   other difference, even one letter, and the quote is refused.
2. What is shown is then the passage's own text at that place, not the
   model's copy of it.
3. The page is looked up in data/knowledge/extracted/<doc_id>.txt, the text the quote
   tests read; if the file is missing, the passage's own pages are used.

A grade (e.g. "Weak for") is kept only if the passage prints it after the
quote, as the VA/DoD guidelines print a recommendation's grade after it
(the same rule prosthetics/tests/test_component_guide.py checks for the hand-written
statements).
"""

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Optional

from shared.config import EXTRACTED_DIR, MIN_QUOTE_WORDS

_PAGE_MARKER = re.compile(r"^--- page (\d+) ---$", re.MULTILINE)
# Characters that print alike, compared as one. Never letters or digits.
_SAME_MARK = str.maketrans({
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
})
# The model sometimes wraps a quote in quotation marks; they are not part of it.
_WRAPPING = "\"'“”‘’«» "
# How far after a quote a grade may be printed and still belong to it.
GRADE_WINDOW_CHARS = 300


class QuoteRefused(ValueError):
    """The quote can't be shown. str(error) is the reason, kept in the log."""


def flat(text: str) -> str:
    """Line breaks and runs of spaces as one space, as when reading the PDF."""
    return " ".join(text.split())


def _comparable(text: str) -> str:
    return flat(unicodedata.normalize("NFKC", text).translate(_SAME_MARK))


def _comparable_with_map(text: str) -> tuple[str, list[int]]:
    """_comparable(text), and for each of its characters the index it came from in `text`."""
    out, where = [], []
    for index, char in enumerate(text):
        if char.isspace():
            if out and out[-1] != " ":
                out.append(" ")
                where.append(index)
            continue
        out.append(char.translate(_SAME_MARK))
        where.append(index)
    if out and out[-1] == " ":
        out.pop()
        where.pop()
    return "".join(out), where


def find_quote(quote: str, passage: str, min_words: int = MIN_QUOTE_WORDS) -> str:
    """The passage's own words that match `quote`. Raises QuoteRefused if there are none."""
    wanted = _comparable(quote).strip(_WRAPPING)
    if len(wanted.split()) < min_words:
        raise QuoteRefused(f"quote shorter than {min_words} words")
    passage = unicodedata.normalize("NFKC", passage)
    comparable, where = _comparable_with_map(passage)
    start = comparable.find(wanted)
    if start == -1:
        raise QuoteRefused("quote not found word for word in the passage")
    end = start + len(wanted) - 1
    return flat(passage[where[start]:where[end] + 1])


def grade_after(grade: str, quote: str, passage: str, window: int = GRADE_WINDOW_CHARS) -> bool:
    """Whether the passage prints `grade` within `window` characters after the quote."""
    comparable = _comparable(passage)
    start = comparable.find(_comparable(quote))
    if start == -1:
        return False
    after = comparable[start + len(_comparable(quote)):][:window]
    return _comparable(grade) in after


@lru_cache(maxsize=64)
def _pages(doc_id: str, folder: Path) -> dict[int, str]:
    path = folder / f"{doc_id}.txt"
    if not path.is_file():
        return {}
    parts = _PAGE_MARKER.split(path.read_text(encoding="utf-8"))  # [header, "1", page 1, "2", ...]
    return {int(number): _comparable(body) for number, body in zip(parts[1::2], parts[2::2])}


def locate_pages(quote: str, doc_id: str, first: Optional[int], last: Optional[int],
                 folder: Path = EXTRACTED_DIR) -> tuple[Optional[int], Optional[int]]:
    """The page the quote is on (start, end; end only if it runs onto the next page).

    Looked up in the extracted text between the passage's first and last
    page. Not found there (or no extracted text): the passage's own pages.
    """
    pages = _pages(doc_id, folder)
    wanted = _comparable(quote)
    if pages and first is not None:
        last = last or first
        for number in range(first, last + 1):
            if wanted in pages.get(number, ""):
                return number, None
        for number in range(first, last):  # across a page break
            if wanted in f"{pages.get(number, '')} {pages.get(number + 1, '')}":
                return number, number + 1
    return first, last if last != first else None
