"""The topics of an orthotic case's RAG: what is searched, and what the AI is asked about.

PROPOSAL, awaiting the owner (2026-10-22): the sections and their search
wording follow the stroke-AFO design of 2026-10-21 (modules 1-3 and fitting).

Three parts, one AI call each (reasoning/rag.py with orthotics/rag.py PROFILE):
- "gaps": one topic per missing intake field (orthotics/fields.py FIELDS).
- "devices": what the sources say about an ankle-foot orthosis or FES for
  walking, the types of AFO, their effects and limits, and when not to
  provide one. Shown side by side, never ranked: the orthotist chooses.
- "design_fitting": design (ankle angle, stiffness, trim lines, materials),
  fitting and check-out, timing and training, and outcome measures.

The search text is each topic's own wording, without the case's side or
months since onset: with them, 6 fewer of 26 topic searches found a right
passage (python -m knowledge.evaluate --orthotics, 2026-10-22). The wording
names stroke where it matters. It decides nothing: the AI reports what the
passages say, and the orthotist decides.
"""

from orthotics.case import OrthoticCase
from reasoning.rag_topics import GAPS, Topic
from shared.config import ORTHOTIC_PASSAGES_PER_DOCUMENT, ORTHOTIC_RETRIEVAL_DOMAINS
from shared.field_guide import build_query, missing_fields

DEVICES, DESIGN_FITTING = "devices", "design_fitting"
PARTS = (GAPS, DEVICES, DESIGN_FITTING)
# What an orthotic case searches (knowledge/retrieval.py): only documents with the "orthotics" domain, at most
# ORTHOTIC_PASSAGES_PER_DOCUMENT passages from one document (shared/config.py).
SEARCH_DOMAINS = ORTHOTIC_RETRIEVAL_DOMAINS
PASSAGES_PER_DOCUMENT = ORTHOTIC_PASSAGES_PER_DOCUMENT

# key: (label for the AI, what to search for). Keys never clash with a field
# path or a prosthetic topic key (the prosthetic "fitting" is "orthosis_fitting" here).
DEVICE_SECTIONS = {
    "afo_or_fes": ("Ankle-foot orthosis or FES for walking",
                   "ankle-foot orthosis or functional electrical stimulation to improve walking after stroke: "
                   "gait speed, mobility and balance"),
    "afo_types": ("Types of ankle-foot orthosis",
                  "types of ankle-foot orthosis: solid, hinged or articulated, posterior leaf spring, carbon, "
                  "prefabricated or custom-made"),
    "effects_limits": ("Effects of an ankle-foot orthosis and their limits",
                       "effects of ankle-foot orthoses after stroke on walking, balance and falls, compensatory or "
                       "therapeutic effects, and the limits of the evidence"),
    "cautions": ("When not to provide an orthosis or FES, and cautions",
                 "when an ankle-foot orthosis or FES should not be provided: spasticity, skin and sensation "
                 "problems, contraindications and risks"),
}
DESIGN_SECTIONS = {
    "design": ("Orthosis design: ankle angle, stiffness, trim lines, materials",
               "ankle-foot orthosis design: ankle angle, stiffness, trim lines, polypropylene thickness, padding "
               "and footwear"),
    "orthosis_fitting": ("Fitting and check-out of the orthosis",
                         "fitting an orthosis and checking its fit, comfort and function before delivery; trim "
                         "lines, pressure on the skin, donning"),
    "timing_training": ("Timing of provision and training with the orthosis",
                        "when the orthosis is provided after stroke, training the user in its use, gait training "
                        "and follow-up"),
    "outcome_measures": ("Outcome measures",
                         "outcome measures for people using an ankle-foot orthosis after stroke: walking speed, "
                         "balance, falls and satisfaction"),
}


def topics_for_case(case: OrthoticCase) -> list[Topic]:
    """Every topic of the orthotic case, part by part, in the order the review page shows them."""
    topics = [Topic(missing.info.path, GAPS, missing.info.label, build_query(case, missing.info))
              for missing in missing_fields(case)]
    topics += [Topic(key, DEVICES, label, query) for key, (label, query) in DEVICE_SECTIONS.items()]
    topics += [Topic(key, DESIGN_FITTING, label, query) for key, (label, query) in DESIGN_SECTIONS.items()]
    return topics
