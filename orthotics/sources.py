"""What the source library says about each device type, part and design step (modules 3 and 4).

Local search only (no AI, nothing sent anywhere): each item of orthotics/plan.py's
vocabularies has a fixed search text and topic words here. The pages show the
first passages the search finds that mention the item's topic, quoted as
printed with their page, for the orthotist to read and judge. They are not
summarised and not checked to support the option: the page says so. What the
orthotist typed is never searched.

Measured while building (2026-10-23): without the topic words, a third of the
passages were title pages, a publisher's disclaimer or another device; the
scoliosis guideline and the cerebral palsy review, about other conditions,
also ranked, so they are left out here (no AI judges whether they apply to
stroke), and so are table-of-contents passages. The topic words are English: the Arabic WHO documents are searched
but rarely shown.

PROPOSAL (2026-10-23): the wording follows the library's own terms (the ICRC
AFO manual's designs, Choo 2021's AFO types, Wang 2025 on 3D printing, NICE
HTG178 on FES); the owner may revise it.
"""

from typing import Callable, Optional

import numpy as np

from knowledge.embedding import embed_texts
from knowledge.models import ProtocolChunk
from knowledge.retrieval import VectorStore, search_items
from orthotics.plan import DeviceType, Part, Step
from shared.config import ORTHOTIC_RETRIEVAL_DOMAINS

PASSAGES_PER_ITEM = 3
PER_DOCUMENT = 2  # at most this many of an item's passages from one document
CANDIDATES = 25  # passages searched per item before the topic words are checked
# About other conditions than stroke (scoliosis bracing; children with cerebral palsy).
EXCLUDED_DOCUMENTS = ("scoliosis_sosort_guidelines_2016", "orthoses_cerebral_palsy_review_2024")

# item -> (search text, topic words a shown passage must contain)
DEVICES = {
    DeviceType.SOLID_AFO: ("rigid AFO: blocks ankle movements, mediolateral stabilization of the subtalar joint",
                           r"\brigid\b|\bsolid\b"),
    DeviceType.HINGED_AFO: ("articulated ankle-foot orthosis with ankle joints and a plantarflexion stop",
                            r"articulated|hinged|\bjoints?\b"),
    DeviceType.FLEXIBLE_AFO: ("flexible ankle-foot orthosis giving dorsiflexion assistance", r"flexible"),
    DeviceType.POSTERIOR_LEAF_SPRING: ("posterior leaf spring ankle-foot orthosis for foot drop", r"leaf spring"),
    DeviceType.CARBON_AFO: ("carbon fibre or carbon composite ankle-foot orthosis", r"carbon"),
    DeviceType.ANTERIOR_SHELL_AFO: ("anti-talus ankle-foot orthosis with an anterior shell",
                                    r"anti-?talus|anterior shell"),
    DeviceType.PRINTED_AFO: ("3D-printed ankle-foot orthosis: design, materials and outcomes",
                             r"3D[- ]?print|additive manufactur"),
    DeviceType.PREFABRICATED_AFO: ("prefabricated or off-the-shelf ankle-foot orthosis compared with custom-made",
                                   r"prefabricated|off-the-shelf"),
    DeviceType.FES: ("functional electrical stimulation of the peroneal nerve for drop foot after stroke",
                     r"electrical stimulation|\bFES\b"),
}
PARTS = {
    Part.POLYPROPYLENE_SHELL: ("polypropylene shell of an ankle-foot orthosis: thickness and moulding",
                               r"polypropylene"),
    Part.CARBON_COMPOSITE: ("carbon composite material for an ankle-foot orthosis", r"carbon"),
    Part.PRINTED_SHELL: ("materials for 3D-printed orthoses such as nylon and thermoplastic polyurethane",
                         r"nylon|polyamide|\bTPU\b|polyurethane|\bPLA\b|3D[- ]?print"),
    Part.EVA_LINING: ("EVA foam lining inside an orthosis for comfort and to prevent skin breakage",
                      r"\bEV ?A\b|lining|padding"),
    Part.ANKLE_JOINTS: ("ankle joints of an articulated orthosis, such as the Tamarack flexure joint",
                        r"\bjoints?\b"),
    Part.PLANTARFLEXION_STOP: ("plantarflexion stop to prevent plantarflexion in an ankle-foot orthosis",
                               r"plantar ?flexion stop|prevent plantar ?flexion|plantar ?flexion control"),
    Part.POSTERIOR_REINFORCEMENT: ("plastic reinforcement at the Achilles tendon for plantarflexion control",
                                   r"reinforcement"),
    Part.STRAPS: ("straps of an ankle-foot orthosis: proximal strap, distal strap and closure",
                  r"\bstraps?\b|velcro|buckle"),
    Part.HEEL_WEDGE: ("heel wedge or shoe modification to tune the shank angle of an ankle-foot orthosis",
                      r"wedge|heel height|shoe modification"),
    Part.FOOTWEAR: ("footwear worn with an ankle-foot orthosis: shoe size and fit", r"\bshoes?\b|footwear"),
}
STEPS = {
    Step.CAPTURE: ("taking a plaster cast or a 3D scan of the leg for an ankle-foot orthosis",
                   r"\bcast\b|casting|\bscan|impression"),
    Step.RECTIFY: ("rectification of the positive plaster model or digital model of the leg",
                   r"rectif|modification of the (plaster|positive)"),
    Step.PARAMETERS: ("ankle-foot orthosis design: ankle angle, trim lines and material thickness",
                      r"trim line|thickness|degrees? of dorsi"),
    Step.SIMULATE: ("finite element simulation or pressure analysis of an orthosis design before manufacture",
                    r"finite element|simulat|pressure (distribution|map|analysis)"),
    Step.FABRICATE: ("manufacturing an ankle-foot orthosis: draping polypropylene or 3D printing",
                     r"drap|thermoform|vacuum|3D[- ]?print|manufactur"),
    Step.RELEASE: ("before delivery of an orthosis, check its fit and function; training and follow-up",
                   r"deliver|follow-up|fitting|check-?out"),
}

# Each search's passages, by (store, limb, search text) (knowledge/retrieval.py search_items).
_cache: dict[tuple, list[ProtocolChunk]] = {}


def find_passages(
    items: dict[str, tuple[str, str]],
    store: Optional[VectorStore] = None,
    embed: Callable[[list[str]], np.ndarray] = embed_texts,
) -> dict[str, list[ProtocolChunk]]:
    """key -> the passages shown for that (search text, topic words), best first ([]: none mention it).

    Raises KnowledgeBaseMissing if the library hasn't been ingested.
    """
    return search_items(items, _cache, ORTHOTIC_RETRIEVAL_DOMAINS, "lower", EXCLUDED_DOCUMENTS,
                        PASSAGES_PER_ITEM, PER_DOCUMENT, CANDIDATES, store=store, embed=embed)
