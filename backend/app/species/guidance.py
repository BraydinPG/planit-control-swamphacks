"""Curated worker-encounter guidance, keyed by IPaC scientific name.

Each entry paraphrases one cited public source, checked 2026-10-17. Gemini may reword
these for crews but never adds to them. Species without an entry show "encounter
guidance not reviewed", which is unknown, not "harmless".

Every entry stays `pending_review` until the organization's safety lead signs off and
sets `reviewed_by`. Guidance is conservative: keep distance, do not handle, contact the
named authority. It never covers capture, handling, or relocation, and it is not a
substitute for the employer's site procedures.
"""

from dataclasses import dataclass

PENDING_REVIEW = "pending_review"
FWC_GATOR_HOTLINE = "FWC Nuisance Alligator Hotline 866-392-4286 (866-FWC-GATOR)"
FWS_FLORIDA_OFFICE = "USFWS Florida Ecological Services Office (352) 448-9151"


@dataclass(frozen=True)
class Guidance:
    key: str
    hazard: str | None
    actions: tuple[str, ...]
    contact: str | None
    source: str
    source_url: str
    review_status: str = PENDING_REVIEW
    reviewed_by: str | None = None

    @property
    def evidence_id(self) -> str:
        return f"guidance:{self.key}"


_ALLIGATOR = Guidance(
    key="american-alligator",
    hazard="Large reptile that can bite. Most active between dusk and dawn.",
    actions=(
        "Keep your distance if you see one.",
        "Never feed an alligator. Feeding is illegal in Florida.",
        "Report an alligator that threatens people or property to FWC.",
    ),
    contact=FWC_GATOR_HOTLINE,
    source="Florida Fish and Wildlife Conservation Commission (FWC), Living with Alligators",
    source_url="https://myfwc.com/conservation/you-conserve/wildlife/alligators/",
)

_CROCODILE = Guidance(
    key="american-crocodile",
    hazard="Large reptile that can bite. Most active between dusk and dawn.",
    actions=(
        "Keep your distance if you see one.",
        "Never feed a crocodile, directly or by leaving fish scraps.",
        "Report a crocodile that threatens people or property to FWC.",
    ),
    contact=FWC_GATOR_HOTLINE,
    source="Florida Fish and Wildlife Conservation Commission (FWC), American Crocodile",
    source_url="https://myfwc.com/wildlifehabitats/wildlife/american-crocodile/",
)

_PANTHER = Guidance(
    key="florida-panther",
    hazard="Large cat. FWC advises how to respond to a close encounter.",
    actions=(
        "Do not run. Give the animal room to leave.",
        "Face the animal, stand tall, and do not crouch or bend over.",
        "Make yourself look larger, for example by raising your arms.",
        "If attacked, fight back without turning your back.",
    ),
    contact="FWC, for a dead or injured panther: 888-404-3922",
    source="Florida Fish and Wildlife Conservation Commission (FWC), Living with Panthers",
    source_url="https://myfwc.com/wildlifehabitats/wildlife/panther/living/",
)

_INDIGO_SNAKE = Guidance(
    key="eastern-indigo-snake",
    hazard=None,  # the cited source does not describe a worker hazard
    actions=(
        "Stop activity near the snake until your site's protection procedure is followed.",
        "Do not harass, harm, capture, or collect it. Federal penalties apply.",
        "Notify the USFWS Florida office as your site procedure directs.",
    ),
    contact=FWS_FLORIDA_OFFICE,
    source="USFWS, Standard Protection Measures for the Eastern Indigo Snake",
    source_url="https://www.fws.gov/story/eastern-indigo-snake-conservation",
)

_BAT = Guidance(
    key="bats",
    hazard="Bats can carry rabies, and a bat bite may not be visible.",
    actions=(
        "Do not touch or handle a bat, alive or dead.",
        "If you have contact with a bat, wash the area with soap and water.",
        "Report any bat contact to your supervisor and a health professional promptly.",
    ),
    contact="Local health department or animal control",
    source="U.S. Centers for Disease Control and Prevention (CDC), Rabies",
    source_url="https://www.cdc.gov/rabies/",
)

GUIDANCE: dict[str, Guidance] = {
    "Alligator mississippiensis": _ALLIGATOR,
    "Crocodylus acutus": _CROCODILE,
    "Puma (=Felis) concolor coryi": _PANTHER,
    # Listed for similarity of appearance to the panther; in Florida, the same animal.
    "Puma (=Felis) concolor (all subsp. except coryi)": _PANTHER,
    "Drymarchon couperi": _INDIGO_SNAKE,
    "Eumops floridanus": _BAT,
    "Perimyotis subflavus": _BAT,
}


def guidance_for(scientific_name: str | None) -> Guidance | None:
    return GUIDANCE.get(scientific_name) if scientific_name else None
