"""What the source library says about each kind of intervention (rehabilitation module 1; plan Part 9).

Local search only (no AI, nothing sent anywhere), as orthotics/sources.py does: each intervention kind of
rehabilitation/plan.py has a fixed search text and topic words here, searched in the documents the catalog files
under "rehabilitation", for the case's limb. The page shows the first passages that mention the topic, quoted as
printed with their page, for the therapist to read and judge: not summarised, not checked to support the case, and
no grade worked out (a guideline's grade is in its own words). What the therapist typed is never searched: an
intervention of their own shows "No source in the library: the therapist's own".

PROPOSAL (Claude, 2026-10-27): the wording follows the library's rehabilitation sources (the VA/DoD guidelines on
stroke rehabilitation and on lower and upper limb amputation rehabilitation, WHO's Package of interventions for
rehabilitation, module 3, the ICRC physiotherapy manual on prosthetic gait); the owner may revise it.
"""

from typing import Callable, Optional

import numpy as np

from knowledge.embedding import embed_texts
from knowledge.models import ProtocolChunk
from knowledge.retrieval import VectorStore, search_items
from rehabilitation.plan import InterventionKind
from shared.config import REHAB_RETRIEVAL_DOMAINS

PASSAGES_PER_ITEM = 2
PER_DOCUMENT = 1
CANDIDATES = 25

# kind -> (search text, topic words a shown passage must contain)
INTERVENTIONS = {
    InterventionKind.GAIT_TRAINING: ("gait training and walking practice with a prosthesis or orthosis",
                                     r"gait training|walking (training|practice|programme|program)|ambulation"),
    InterventionKind.BALANCE_TRAINING: ("balance training to improve standing and walking balance",
                                        r"balance"),
    InterventionKind.STRENGTH_TRAINING: ("strengthening exercise and resistance training in rehabilitation",
                                         r"strength|resistance training|resistive exercise"),
    InterventionKind.TREADMILL_TRAINING: ("treadmill training with or without body weight support for walking",
                                          r"treadmill|body.weight.support"),
    InterventionKind.DEVICE_USE: ("training to put on, take off and care for the prosthesis or orthosis, and its "
                                  "wearing schedule", r"\bdon(ning)?\b|\bdoff|wearing (time|schedule)|put(ting)? on"),
    InterventionKind.TASK_PRACTICE: ("task-specific practice of daily activities in rehabilitation",
                                     r"task[- ](specific|oriented)|activities of daily living|\bADLs?\b"),
    InterventionKind.LIMB_CARE: ("care of the residual limb: skin care, oedema control, compression and "
                                 "desensitisation", r"oedema|edema|compression|desensiti|shrinker|skin care"),
    InterventionKind.MIRROR_THERAPY: ("mirror therapy or graded motor imagery for phantom limb pain",
                                      r"mirror|motor imagery"),
    InterventionKind.HOME_PROGRAMME: ("home exercise programme and self-management after discharge",
                                      r"home (exercise|program)|self-management"),
    InterventionKind.FALLS_PREVENTION: ("falls prevention and falls risk after stroke or amputation",
                                        r"\bfalls?\b"),
}

# Each search's passages, by (store, limb, search text) (knowledge/retrieval.py search_items).
_cache: dict[tuple, list[ProtocolChunk]] = {}


def find_passages(
    kinds: list[InterventionKind],
    limb: Optional[str],
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> dict[str, list[ProtocolChunk]]:
    """kind value -> the passages shown for it, best first ([]: none mention it). The therapist's own ("other") is
    never searched. Raises KnowledgeBaseMissing if the library hasn't been ingested."""
    items = {kind.value: INTERVENTIONS[kind] for kind in dict.fromkeys(kinds) if kind in INTERVENTIONS}
    if not items:
        return {}
    return search_items(items, _cache, REHAB_RETRIEVAL_DOMAINS, limb, (), PASSAGES_PER_ITEM, PER_DOCUMENT,
                        CANDIDATES, store=store, embed=embed)
