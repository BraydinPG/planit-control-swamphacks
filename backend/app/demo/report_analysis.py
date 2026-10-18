"""A written-in-advance report analysis for the Everglades demo crew report.

The demo report has no photo and is seeded, so Gemini never analyzes it and the
"Gemini analysis, suggestion only" panel would sit empty. `ensure_demo_report_analysis`
stores a fixed analysis in the same shape the real job writes (`ReportEnrichment`), citing
the evidence the real job would have gathered (`gather_evidence`), so each cited id
resolves on the page. Simulated demo content: demo sites say so only in their name
(AGENTS.md rule 6 exception). It is filled only while the report has no analysis, so a
real one is never replaced; `app.demo.freshen` calls it each round, which also restores it
after a reseed.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db import models as db
from app.demo.scenario import FLOOD_ALERT_ID, WILDLIFE_REPORT_ID
from app.gemini.report_analysis import gather_evidence
from app.schemas import (
    AnalysisPoint,
    AnalysisVerdict,
    GeneratedBy,
    ReportCategory,
    ReportEnrichment,
    Severity,
)

HEAT_INDEX_ID = "demo-weather:heat-index"
SUMMARY = (
    "The site data is consistent with the crew member's report of an alligator on the "
    "levee access road. The active Flood Warning makes it more likely that alligators "
    "leave flooded canals for higher ground such as levees and culverts. Nothing supplied "
    "contradicts the report."
)


def ensure_demo_report_analysis(session: Session, now: datetime) -> bool:
    """Store the demo report's analysis when it has none. Commits; True when written."""
    report = session.get(db.CrewReport, WILDLIFE_REPORT_ID)
    if report is None or report.enrichment is not None:
        return False
    evidence = gather_evidence(session, report, False, now)
    ids = {e.id for e in evidence}
    supporting = [
        AnalysisPoint(
            statement="The crew member reported wildlife, marked it present, and named a "
            "specific place: the levee access road by the culvert.",
            evidence_ids=["crew:category", "crew:hazard_present", "crew:note"],
        )
    ]
    if FLOOD_ALERT_ID in ids:
        supporting.append(
            AnalysisPoint(
                statement="A Flood Warning is in effect. High water in nearby canals often "
                "pushes alligators onto levees, roads and culverts.",
                evidence_ids=[FLOOD_ALERT_ID],
            )
        )
    if HEAT_INDEX_ID in ids:
        supporting.append(
            AnalysisPoint(
                statement="The high heat index fits warm-weather alligator activity in "
                "the daytime.",
                evidence_ids=[HEAT_INDEX_ID],
            )
        )
    analysis = ReportEnrichment(
        status="complete",
        verdict=AnalysisVerdict.SUPPORTS,
        summary=SUMMARY,
        supporting=supporting,
        suggested_category=ReportCategory.WILDLIFE,
        severity_suggestion=Severity.MODERATE,
        confidence=0.8,
        unknowns=[
            "No photo was read; this analysis uses the report and site data.",
            "The animal's size, and whether it has left the road, are not known.",
        ],
        evidence=evidence,
        generated_by=GeneratedBy.GEMINI,
        analyzed_at=min(_aware(report.created_at) + timedelta(minutes=1), now),
    )
    report.enrichment = analysis.model_dump(mode="json")
    session.commit()
    return True


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)
