"""The clinical domains, and how shared code reaches a domain's parts without naming it.

SYSTEM_DESIGN.md §9, "Adding a domain": each domain is a package of the same
shape next to the shared parts (shared/, knowledge/, reasoning/, review/,
quality/):

    <domain>/case.py       its section of the case, on shared/case_schema.py CaseCore
    <domain>/fields.py     its field guide: FIELDS (the gap fields) and query_for()
    <domain>/topics.py     what it searches for: topics_for_case(), SEARCH_DOMAINS (the catalog domains
                           searched) and PASSAGES_PER_DOCUMENT (None: no limit)
    <domain>/rag.py        its RAG: PROFILE (with its cloud switch), components_from(), fitting_from()
    <domain>/intake.py     its intake form (a Flask blueprint)
    <domain>/plan.py       the specialist's work after the intake (PLAN, BACK_TO)
    <domain>/hard_stops.py its clinic rules applied to the case (RULES, case_checks())
    <domain>/modules.py    its module pages (a Flask blueprint)
    <domain>/nav.py        what the shared header shows for it
    <domain>/templates/<domain>/   its pages
    <domain>/tests/        its tests

A new domain adds its package and its name to DOMAINS.

A shared part with pages of its own (since plan Part 4, 2026-10-25: review/, the
reasoning and review pages) is in SHARED_PARTS with a <part>/nav.py of the same
kind: the header lists it next to the domains.
"""

import importlib
import importlib.util
from types import ModuleType

DOMAINS = ("prosthetics", "orthotics")
SHARED_PARTS = ("review",)  # the reasoning and review pages (SYSTEM_DESIGN.md §7.2)


def part(domain: str, name: str) -> ModuleType:
    """A domain's module: part("orthotics", "rag") is orthotics/rag.py."""
    if domain not in DOMAINS:
        raise ValueError(f"domain must be one of {sorted(DOMAINS)}, got {domain!r}")
    return importlib.import_module(f"{domain}.{name}")


def has_part(domain: str, name: str) -> bool:
    """Whether the domain has that module (e.g. a plan.py)."""
    return domain in DOMAINS and importlib.util.find_spec(f"{domain}.{name}") is not None


def nav(name: str) -> ModuleType:
    """What the header shows for a domain or a shared part: its nav.py."""
    if name not in DOMAINS + SHARED_PARTS:
        raise ValueError(f"must be one of {sorted(DOMAINS + SHARED_PARTS)}, got {name!r}")
    return importlib.import_module(f"{name}.nav")


def load_cases() -> None:
    """Import every domain's case module, so each case class is registered (shared/case_schema.py)."""
    for domain in DOMAINS:
        part(domain, "case")
