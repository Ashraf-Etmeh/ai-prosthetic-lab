"""The reasoning pathway for one case: search, AI summaries with checked quotes, gaps, components, fitting.

SYSTEM_DESIGN.md §4: case data -> information analysis (local search) ->
specialised reasoning (the writer, every quote checked) -> assistive output.
Every domain's case goes through it the same way (the RAG, reasoning/rag.py).
"""

from knowledge.retrieval import KnowledgeBaseMissing, retrieve_relevant_chunks
from reasoning.rag import components_from, fitting_from, gaps_from, generate
from reasoning.writer import Writer, default_writer
from shared.case_schema import CaseCore
from shared.store import CaseRecord


def analyse_case(case: CaseCore, retrieve=None, writer: Writer | None = None) -> CaseRecord:
    """Everything the review page shows for a case: search, AI summaries, gaps, components, fitting.

    Used for a submitted form, the prepared trial cases
    (quality/load_trial_cases.py) and the golden cases (quality/golden_cases.py),
    so all are analysed the same way (the RAG, reasoning/rag.py).
    `retrieve` replaces the search (default: retrieve_relevant_chunks); the
    golden cases pass one that raises KnowledgeBaseMissing when the model is
    not available. `writer` replaces the AI (default: default_writer(), the
    API of shared/config.py LLM_PROVIDER unless switched off); without its answer the page lists the
    passages found, and the gaps come from the topic-word check.
    """
    warning = None
    try:
        chunks = (retrieve or retrieve_relevant_chunks)(case)
    except KnowledgeBaseMissing as e:
        # Still list the gaps, but say plainly that no sources were searched.
        chunks, warning = {}, f"The source library was not searched: {e}"
    generation = generate(case, chunks, writer or default_writer())
    return CaseRecord(case=case, retrieved_chunks=chunks, gaps=gaps_from(case, chunks, generation),
                      knowledge_warning=warning, components=components_from(case, generation),
                      fitting=fitting_from(case, generation), generation=generation)
