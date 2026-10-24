"""The clinical domains, and how shared code reaches a domain's parts without naming it.

SYSTEM_DESIGN.md §9, "Adding a domain": each domain is a package of the same
shape next to the shared parts (shared/, knowledge/, reasoning/, review/,
quality/):

    <domain>/case.py       its section of the case, on shared/case_schema.py CaseCore
    <domain>/fields.py     its field guide: FIELDS (the gap fields) and query_for()
    <domain>/topics.py     what it searches for: topics_for_case()
    <domain>/rag.py        its RAG: PROFILE, components_from(), fitting_from()
    <domain>/intake.py     its intake form (a Flask blueprint)
    <domain>/plan.py       optional: the specialist's work after the analysis (PLAN)
    <domain>/templates/<domain>/   its pages
    <domain>/tests/        its tests

A new domain adds its package and its name to DOMAINS.
"""

import importlib
import importlib.util
from types import ModuleType

DOMAINS = ("prosthetics", "orthotics")


def part(domain: str, name: str) -> ModuleType:
    """A domain's module: part("orthotics", "rag") is orthotics/rag.py."""
    if domain not in DOMAINS:
        raise ValueError(f"domain must be one of {sorted(DOMAINS)}, got {domain!r}")
    return importlib.import_module(f"{domain}.{name}")


def has_part(domain: str, name: str) -> bool:
    """Whether the domain has that module (e.g. a plan.py)."""
    return domain in DOMAINS and importlib.util.find_spec(f"{domain}.{name}") is not None


def load_cases() -> None:
    """Import every domain's case module, so each case class is registered (shared/case_schema.py)."""
    for domain in DOMAINS:
        part(domain, "case")
