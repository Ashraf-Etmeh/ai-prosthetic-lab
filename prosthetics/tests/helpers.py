"""The prosthetic route tests' fixtures: an intake form, passages of catalogued documents, and a search
that returns them (the real search would load the 2.3 GB model)."""

from knowledge.models import ProtocolChunk
from shared.testing import RouteTestCase

BASE_FORM = {"amputation_level": "transtibial", "side": "left"}

# Every input on the intake form filled in.
FULL_FORM = {
    **BASE_FORM,
    "etiology": "vascular", "months_since_amputation": "5",
    "age_years": "64", "body_weight_kg": "81",
    "wound_status": "healed", "volume_stability": "stable", "skin_condition": "intact",
    "length_description": "mid-length", "pain": "mild phantom pain", "sensation": "reduced",
    "k_level": "K2", "activity_description": "walks indoors", "functional_goals": "walk to the shop",
    "device_1_description": "PTB socket, SACH foot", "device_1_years": "2",
    "device_1_current": "no", "device_1_issues": "loose fit",
    "comorbidities": "Diabetes", "contralateral_limb_status": "foot ulcer healed",
    "cognitive_status": "intact", "intake_notes": "test case",
}

VOLUME_PASSAGE = ProtocolChunk(
    chunk_id="test_guideline_2024-0007",
    text="Residual limb volume should be stable before the definitive socket is cast.",
    source="01_guidelines/test.pdf",
    title="Test Guideline",
    year=2024,
    page=14,
    end_page=14,
    language="en",
    score=0.71,
)


def catalogued_passage(chunk_id: str, text: str, page: int, score: float = 0.66) -> ProtocolChunk:
    """A passage of a catalogued document (so its title and kind of source are known)."""
    return ProtocolChunk(chunk_id=chunk_id, text=text, source="01_guidelines/test.pdf", title="Search title",
                         year=2024, page=page, end_page=page, language="en", score=score)


KNEE_PASSAGE = catalogued_passage(
    "lower_limb_amputation_va_dod_cpg_2024-0901",
    "For prosthetic ambulators, we suggest prescribing microprocessor knee units over non-microprocessor "
    "knee units. Weak for Reviewed, New-added", 56)
K_LEVEL_PASSAGE = catalogued_passage(
    "lower_limb_prosthesis_cms_consensus_2017-0901",
    "Level 2: Has the ability or potential for ambulation with the ability to traverse low level "
    "environmental barriers such as curbs, stairs or uneven surfaces.", 5)
READINESS_PASSAGE = catalogued_passage(
    "prosthetic_gait_analysis_icrc_manual_2014-0901",
    "Those who are ready for fitting are free of pain and infection and have no oedema.", 49)
PROSTHESIS_TYPE_PASSAGE = catalogued_passage(
    "upper_limb_amputation_va_dod_cpg_2022-0901",
    "For patients with a major unilateral upper limb amputation, we suggest use of a body-powered or "
    "externally powered prosthesis.", 40)


def fake_retrieval(case):
    """Stands in for the real search, so tests never load the 2.3 GB model."""
    return {"residual_limb.volume_stability": [VOLUME_PASSAGE], "knee": [KNEE_PASSAGE],
            "functional_level": [K_LEVEL_PASSAGE], "readiness": [READINESS_PASSAGE],
            "prosthesis_type": [PROSTHESIS_TYPE_PASSAGE]}


class ProstheticRouteTestCase(RouteTestCase):
    """The app with the prosthetic passages above standing in for the search (shared/testing.py RouteTestCase)."""

    fake_retrieval = staticmethod(fake_retrieval)

    def post_intake(self, **fields):
        return self.client.post("/intake", data={**BASE_FORM, **fields})
