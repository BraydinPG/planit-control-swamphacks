"""Generate API fixture JSON for frontend fixture mode.

Every fixture is built from the canonical Pydantic models, so the JSON always matches
the contract and includes every field. All data is mock data for UI development:
site names, IDs, and coordinates are illustrative, not EIA-860M records.

Usage (from backend/):  python -m scripts.generate_fixtures
Output: frontend/src/fixtures/*.json
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel

from app.schemas import (
    Acknowledgement,
    Alert,
    Briefing,
    BriefingHazard,
    CrewReport,
    EventOutlook,
    Evidence,
    Explanation,
    FactorContribution,
    HazardNotice,
    HazardScore,
    Observation,
    RecommendedAction,
    ReportEnrichment,
    SiteDetail,
    SiteSummary,
    TeamRef,
)

OUT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "src" / "fixtures"

NOW = datetime(2026, 10, 17, 18, 0, tzinfo=UTC)
ORG = "org-sunbelt"
TEAM_A = TeamRef(id="team-a", name="Line Crew A", organization_id=ORG)
TEAM_B = TeamRef(id="team-b", name="Substation Crew B", organization_id=ORG)
TEAM_C = TeamRef(id="team-c", name="Vegetation Crew C", organization_id=ORG)

DEMO_SITE = "site-demo-everglades"
DEMO_LAT, DEMO_LON = 25.76, -80.49


def ago(minutes: float) -> datetime:
    return NOW - timedelta(minutes=minutes)


def ahead(minutes: float) -> datetime:
    return NOW + timedelta(minutes=minutes)


# ---- observations for the demo site: one per feed, covering every data state ----

OBSERVATIONS = [
    Observation(
        id="obs-wx-1",
        site_id=DEMO_SITE,
        source="NWS",
        hazard_type="weather",
        value=94,
        unit="°F",
        label="Air temperature (station KTMB)",
        lat=DEMO_LAT,
        lon=DEMO_LON,
        observed_at=ago(20),
        data_state="observed",
        fetched_at=ago(15),
    ),
    Observation(
        id="obs-fc-1",
        site_id=DEMO_SITE,
        source="NWS",
        hazard_type="forecast",
        value=108,
        unit="°F",
        label="Forecast heat index, 3 PM",
        lat=DEMO_LAT,
        lon=DEMO_LON,
        observed_at=ago(60),
        valid_at=ahead(60),
        data_state="forecast",
        fetched_at=ago(15),
    ),
    Observation(
        id="obs-flood-1",
        site_id=DEMO_SITE,
        source="NWS",
        hazard_type="flood_alert",
        value="Flood Watch",
        label="Flood Watch for Miami-Dade",
        source_ref="nws-alert-fixture-1",
        lat=DEMO_LAT,
        lon=DEMO_LON,
        observed_at=ago(90),
        valid_at=ahead(360),
        data_state="observed",
        fetched_at=ago(15),
    ),
    Observation(
        id="obs-ltg-1",
        site_id=DEMO_SITE,
        source="lightning-replay",
        hazard_type="lightning_strike",
        value=6.8,
        unit="mi",
        label="Strike 6.8 mi NW (replay)",
        lat=25.83,
        lon=-80.58,
        observed_at=ago(12),
        data_state="simulated",
        simulated=True,
    ),
    Observation(
        id="obs-ltg-2",
        site_id=DEMO_SITE,
        source="lightning-replay",
        hazard_type="lightning_strike",
        value=4.2,
        unit="mi",
        label="Strike 4.2 mi W (replay)",
        lat=25.77,
        lon=-80.56,
        observed_at=ago(3),
        data_state="simulated",
        simulated=True,
    ),
    Observation(
        id="obs-eq-1",
        site_id=DEMO_SITE,
        source="USGS",
        hazard_type="earthquake",
        value=None,
        unit="Mw",
        label="No qualifying earthquakes (last successful fetch 3 h ago)",
        lat=DEMO_LAT,
        lon=DEMO_LON,
        observed_at=ago(180),
        data_state="stale",
        fetched_at=ago(180),
    ),
    Observation(
        id="obs-hur-1",
        site_id=DEMO_SITE,
        source="NHC",
        hazard_type="hurricane",
        value=None,
        label="Hurricane feed unavailable",
        lat=DEMO_LAT,
        lon=DEMO_LON,
        observed_at=ago(5),
        data_state="unavailable",
    ),
]

# ---- score factors ----

F_LIGHTNING = FactorContribution(
    factor="lightning",
    label="Lightning stop-work active (simulated replay)",
    contribution=3.0,
    value=4.2,
    unit="mi",
    source="lightning-replay",
    observed_at=ago(3),
    data_state="simulated",
    evidence_id="obs-ltg-2",
)
F_HEAT = FactorContribution(
    factor="heat_index",
    label="Forecast heat index above prototype threshold (103 °F)",
    contribution=1.5,
    value=108,
    unit="°F",
    source="NWS",
    observed_at=ago(60),
    data_state="forecast",
    is_prototype=True,
    evidence_id="obs-fc-1",
)
F_FLOOD = FactorContribution(
    factor="flood",
    label="Flood Watch in effect",
    contribution=1.0,
    value="Flood Watch",
    source="NWS",
    observed_at=ago(90),
    data_state="observed",
    is_prototype=True,
    evidence_id="obs-flood-1",
)
F_MODEL = FactorContribution(
    factor="model",
    label="Model: 24 h weather-hazard likelihood",
    contribution=1.6,
    value=0.41,
    source="model baseline-0.1",
    observed_at=ago(30),
    data_state="observed",
    evidence_id="model-1",
)
F_REPORT = FactorContribution(
    factor="crew_report",
    label="Confirmed wildlife report (alligator near access road)",
    contribution=0.5,
    source="crew report",
    observed_at=ago(140),
    data_state="crew_reported",
    evidence_id="report-wildlife-1",
)
F_MODEL_FALLBACK = FactorContribution(
    factor="model",
    label="Model unavailable: labeled fallback component",
    contribution=2.5,
    source="model fallback",
    observed_at=ago(30),
    data_state="unavailable",
    evidence_id=None,
)
F_STALE_WX = FactorContribution(
    factor="heat_index",
    label="Heat index (stale: last NWS update 4 h ago)",
    contribution=0.8,
    value=99,
    unit="°F",
    source="NWS",
    observed_at=ago(240),
    data_state="stale",
    is_prototype=True,
)

DEMO_FACTORS = [F_LIGHTNING, F_MODEL, F_HEAT, F_FLOOD, F_REPORT]

# ---- alerts ----

ALERT_LIGHTNING_ACTIVE = Alert(
    id="alert-ltg-demo",
    site_id=DEMO_SITE,
    rule="lightning_stop_work",
    state="active",
    triggered_at=ago(12),
    latest_event_at=ago(3),
    clear_after=ahead(27),
    distance_miles=4.2,
    trigger_observation_ids=["obs-ltg-1", "obs-ltg-2"],
    evidence=[
        Evidence(id="obs-ltg-1", kind="observation", label="Strike 6.8 mi NW", observed_at=ago(12)),
        Evidence(id="obs-ltg-2", kind="observation", label="Strike 4.2 mi W", observed_at=ago(3)),
    ],
    simulated=True,
    acknowledgements=[
        Acknowledgement(
            id="ack-1",
            alert_id="alert-ltg-demo",
            user_id="user-crew-1",
            acknowledged_at=ago(10),
        )
    ],
)
ALERT_LIGHTNING_CLEARED = Alert(
    id="alert-ltg-cleared",
    site_id="site-fixture-c",
    rule="lightning_stop_work",
    state="cleared",
    triggered_at=ago(150),
    latest_event_at=ago(110),
    clear_after=ago(80),
    distance_miles=8.9,
    trigger_observation_ids=["obs-ltg-c1"],
    evidence=[
        Evidence(id="obs-ltg-c1", kind="observation", label="Strike 8.9 mi S", observed_at=ago(110))
    ],
    simulated=True,
)
ALERT_FLOOD = Alert(
    id="alert-flood-demo",
    site_id=DEMO_SITE,
    rule="flood",
    state="active",
    triggered_at=ago(90),
    latest_event_at=ago(90),
    trigger_observation_ids=["obs-flood-1"],
    evidence=[
        Evidence(id="obs-flood-1", kind="observation", label="Flood Watch", observed_at=ago(90))
    ],
    is_prototype_rule=True,
)
# The reset state: a second strike moved latest_event_at and clear_after forward.
ALERTS = [ALERT_LIGHTNING_ACTIVE, ALERT_FLOOD, ALERT_LIGHTNING_CLEARED]

# ---- reports ----

REPORT_WILDLIFE_CONFIRMED = CrewReport(
    id="report-wildlife-1",
    organization_id=ORG,
    team_id=TEAM_A.id,
    site_id=DEMO_SITE,
    reporter_id="user-crew-1",
    category="wildlife",
    hazard_present=True,
    note="Alligator on the east access road.",
    photo_url="/fixtures/photos/wildlife.jpg",
    lat=25.762,
    lon=-80.487,
    review_status="confirmed",
    reviewed_by="user-supervisor-1",
    reviewed_at=ago(130),
    confirmed_category="wildlife",
    confirmed_severity="moderate",
    notice_id="notice-wildlife-1",
    created_at=ago(140),
)
REPORT_POLE_PENDING = CrewReport(
    id="report-pole-1",
    organization_id=ORG,
    team_id=TEAM_A.id,
    site_id=DEMO_SITE,
    reporter_id="user-crew-2",
    category="broken_pole_downed_line",
    hazard_present=True,
    note=None,
    photo_url="/fixtures/photos/pole.jpg",
    lat=25.758,
    lon=-80.494,
    review_status="pending",
    enrichment=ReportEnrichment(
        suggested_category="broken_pole_downed_line",
        description="Leaning wooden pole with a conductor sagging toward the ground.",
        severity_suggestion="high",
        confidence=0.78,
        visible_evidence=["pole leaning about 30 degrees", "conductor below normal height"],
        generated_by="gemini",
    ),
    notice_id="notice-pole-1",
    created_at=ago(6),
)
REPORT_FIRE_ABSENT = CrewReport(
    id="report-fire-absent-1",
    organization_id=ORG,
    team_id=TEAM_B.id,
    site_id="site-fixture-b",
    reporter_id="user-crew-3",
    category="on_site_fire",
    hazard_present=False,
    note="Smoke was from a neighbor's controlled burn. No fire on site.",
    photo_url=None,
    lat=26.10,
    lon=-81.20,
    review_status="pending",
    created_at=ago(25),
)
REPORTS = [REPORT_POLE_PENDING, REPORT_FIRE_ABSENT, REPORT_WILDLIFE_CONFIRMED]

# ---- hazard notices ----

NOTICE_POLE_POTENTIAL = HazardNotice(
    id="notice-pole-1",
    hazard_label="broken electrical pole",
    source="crew_report",
    source_ref="report-pole-1",
    lat=25.758,
    lon=-80.494,
    radius_miles=1,
    radius_source="default",
    status="potential",
    created_at=ago(6),
    evidence=[Evidence(id="report-pole-1", kind="report", label="Crew report: broken pole")],
)
NOTICE_WILDLIFE_CONFIRMED = HazardNotice(
    id="notice-wildlife-1",
    hazard_label="wildlife",
    source="crew_report",
    source_ref="report-wildlife-1",
    lat=25.762,
    lon=-80.487,
    radius_miles=0.5,
    radius_source="gemini",
    status="confirmed",
    created_at=ago(140),
    confirmed_by="user-supervisor-1",
    confirmed_at=ago(130),
    suggested_instruction="Avoid the east access road; use the west gate.",
    instruction="Avoid the east access road. Use the west gate until wildlife control clears it.",
    instruction_sent_at=ago(128),
    evidence=[Evidence(id="report-wildlife-1", kind="report", label="Crew report: alligator")],
)
NOTICE_FLOOD_CONFIRMED = HazardNotice(
    id="notice-flood-1",
    hazard_label="flooding",
    source="feed",
    source_ref="obs-flood-1",
    lat=DEMO_LAT,
    lon=DEMO_LON,
    radius_miles=5,
    radius_source="default",
    status="confirmed",
    created_at=ago(90),
    confirmed_by="user-supervisor-1",
    confirmed_at=ago(60),
    suggested_instruction="Keep crews off low-lying access roads.",
    instruction="Keep crews off low-lying access roads until the Flood Watch ends.",
    instruction_sent_at=ago(58),
    evidence=[
        Evidence(id="obs-flood-1", kind="observation", label="Flood Watch (simulated scenario)")
    ],
)
NOTICES = [NOTICE_POLE_POTENTIAL, NOTICE_WILDLIFE_CONFIRMED, NOTICE_FLOOD_CONFIRMED]

# T050 advisory for the confirmed flood notice. Values are Cache's published synthetic
# adapter example (ml/INTEGRATION.md), not a prediction for a real event.
EVENT_OUTLOOK = EventOutlook(
    status="ok",
    event_id="notice-flood-1",
    event_type="Flood",
    as_of_utc=NOW,
    generated_at_utc=NOW,
    ongoing_probability={"6h": 0.709, "12h": 0.605, "24h": 0.473},
    remaining_hours_p10=2.0,
    remaining_hours_median=22.0,
    remaining_hours_p90=None,
    trend="unknown",
    model_version="noaa-flood-conditional-km-v2",
    is_simulated=True,
    limitations=[
        "Simulated scenario: synthetic example values, not a real event.",
        "NOAA event intervals describe regional recorded events, not verified site conditions.",
        "Recorded event resolution does not mean site conditions are safe or work may resume.",
    ],
)

# ---- sites ----

DEMO_SUMMARY = dict(
    id=DEMO_SITE,
    name="Demo: Everglades-style site (simulated scenario)",
    lat=DEMO_LAT,
    lon=DEMO_LON,
    assigned_team=TEAM_A,
    risk_score=7.6,
    risk_level="high",
    updated_at=ago(3),
    active_alerts=2,
    top_factors=DEMO_FACTORS[:3],
    data_completeness=0.71,
    model_version="baseline-0.1",
)

# Ordered as GET /api/sites returns them: assigned sites first, then risk_score descending.
SITES = [
    SiteSummary(**DEMO_SUMMARY),
    SiteSummary(
        id="site-fixture-b",
        name="Fixture Site B (representative power plant)",
        lat=26.10,
        lon=-81.20,
        assigned_team=TEAM_B,
        risk_score=5.4,
        risk_level="moderate",
        updated_at=ago(30),
        active_alerts=0,
        top_factors=[F_MODEL_FALLBACK],
        data_completeness=0.4,
        model_version="fallback-0",
    ),
    SiteSummary(
        id="site-fixture-c",
        name="Fixture Site C (representative power plant)",
        lat=27.95,
        lon=-82.46,
        assigned_team=TEAM_C,
        risk_score=2.3,
        risk_level="low",
        updated_at=ago(240),
        active_alerts=0,
        top_factors=[F_STALE_WX],
        data_completeness=0.55,
        model_version="baseline-0.1",
    ),
    SiteSummary(
        id="site-fixture-d",
        name="Fixture Site D (representative power plant, no team)",
        lat=28.54,
        lon=-81.38,
        assigned_team=None,
        risk_score=6.1,
        risk_level="high",
        updated_at=ago(20),
        active_alerts=0,
        top_factors=[F_HEAT],
        data_completeness=0.85,
        model_version="baseline-0.1",
    ),
    SiteSummary(
        id="site-fixture-e",
        name="Fixture Site E (representative power plant, no team, feeds unavailable)",
        lat=30.33,
        lon=-81.66,
        assigned_team=None,
        risk_score=3.0,
        risk_level="moderate",
        updated_at=ago(400),
        active_alerts=0,
        top_factors=[],
        data_completeness=0.0,
        model_version="fallback-0",
    ),
]

SITE_DETAIL = SiteDetail(
    **DEMO_SUMMARY | {"top_factors": DEMO_FACTORS[:3]},
    location_type="power_plant",
    source="Simulated demo scenario (Everglades-style); not an EIA-860M record",
    region="South Florida",
    observations=OBSERVATIONS,
    score=HazardScore(
        site_id=DEMO_SITE,
        risk_score=7.6,
        risk_level="high",
        factor_contributions=DEMO_FACTORS,
        model_version="baseline-0.1",
        model_is_fallback=False,
        confidence=0.68,
        data_completeness=0.71,
        previous_score=5.9,
        created_at=ago(3),
    ),
    alerts=[ALERT_LIGHTNING_ACTIVE, ALERT_FLOOD],
    reports=[REPORT_POLE_PENDING, REPORT_WILDLIFE_CONFIRMED],
    notices=NOTICES,
    event_outlook=EVENT_OUTLOOK,
)

# ---- briefings and explanations: one Gemini-generated, one deterministic fallback ----

BRIEF_EVIDENCE = [
    Evidence(id="obs-fc-1", kind="observation", label="Forecast heat index 108 °F"),
    Evidence(id="obs-flood-1", kind="observation", label="Flood Watch"),
    Evidence(id="alert-ltg-demo", kind="alert", label="Lightning stop-work (simulated)"),
    Evidence(id="report-wildlife-1", kind="report", label="Confirmed wildlife report"),
]
WINDOW = dict(
    forecast_window_start=datetime(2026, 10, 18, 11, 0, tzinfo=UTC),
    forecast_window_end=datetime(2026, 10, 18, 23, 0, tzinfo=UTC),
)
BRIEFINGS = [
    Briefing(
        id="briefing-gemini-1",
        site_id=DEMO_SITE,
        **WINDOW,
        summary=(
            "Tomorrow brings high heat and a continuing Flood Watch. Afternoon storms are "
            "possible. Wildlife remains near the east access road."
        ),
        risk_level="high",
        hazards=[
            BriefingHazard(hazard="Heat", risk_level="high", evidence_ids=["obs-fc-1"]),
            BriefingHazard(hazard="Flooding", risk_level="moderate", evidence_ids=["obs-flood-1"]),
            BriefingHazard(
                hazard="Wildlife", risk_level="moderate", evidence_ids=["report-wildlife-1"]
            ),
        ],
        recommended_actions=[
            RecommendedAction(
                action="Schedule heavy work before noon and plan water and shade breaks.",
                evidence_ids=["obs-fc-1"],
            ),
            RecommendedAction(
                action="Use the west gate; avoid the east access road.",
                evidence_ids=["report-wildlife-1"],
            ),
        ],
        evidence=BRIEF_EVIDENCE,
        unknowns=[
            "Hurricane feed unavailable at generation time.",
            "Earthquake data stale (last update 3 h ago).",
        ],
        generated_by="gemini",
        created_at=NOW,
    ),
    Briefing(
        id="briefing-fallback-1",
        site_id=DEMO_SITE,
        **WINDOW,
        summary="Gemini unavailable. Template briefing built from current site data.",
        risk_level="high",
        hazards=[
            BriefingHazard(
                hazard="Heat index 108 °F", risk_level="high", evidence_ids=["obs-fc-1"]
            ),
            BriefingHazard(
                hazard="Flood Watch", risk_level="moderate", evidence_ids=["obs-flood-1"]
            ),
        ],
        recommended_actions=[
            RecommendedAction(
                action="Review the active alerts and score factors before work starts.",
                evidence_ids=["obs-fc-1", "obs-flood-1"],
            )
        ],
        evidence=BRIEF_EVIDENCE[:2],
        unknowns=["Hurricane feed unavailable.", "Earthquake data stale."],
        generated_by="fallback",
        created_at=NOW,
    ),
]

EXPLANATIONS = [
    Explanation(
        site_id=DEMO_SITE,
        score_created_at=ago(3),
        explanation=(
            "The score rose from 5.9 to 7.6, mainly because the simulated lightning replay "
            "triggered a stop-work alert 4.2 miles away. Forecast heat and the Flood Watch "
            "add smaller amounts."
        ),
        top_factors=DEMO_FACTORS[:3],
        change_since_previous="+1.7 since the previous score",
        evidence=[
            Evidence(id="obs-ltg-2", kind="observation", label="Strike 4.2 mi W (replay)"),
            Evidence(id="model-1", kind="model_output", label="Model component 1.6"),
            Evidence(id="obs-fc-1", kind="observation", label="Forecast heat index 108 °F"),
        ],
        unknowns=["Hurricane feed unavailable; its contribution is unknown."],
        generated_by="gemini",
        created_at=NOW,
    ),
    Explanation(
        site_id=DEMO_SITE,
        score_created_at=ago(3),
        explanation=None,
        top_factors=DEMO_FACTORS[:3],
        change_since_previous=None,
        evidence=[],
        unknowns=["Gemini unavailable; showing the factor breakdown only."],
        generated_by="fallback",
        created_at=NOW,
    ),
]

FIXTURES: dict[str, BaseModel | list[BaseModel]] = {
    "sites.json": SITES,
    "site-detail.json": SITE_DETAIL,
    "alerts.json": ALERTS,
    "reports.json": REPORTS,
    "hazard-notices.json": NOTICES,
    "briefings.json": BRIEFINGS,
    "explanations.json": EXPLANATIONS,
}


def dump(value: BaseModel | list[BaseModel]) -> object:
    if isinstance(value, list):
        return [item.model_dump(mode="json") for item in value]
    return value.model_dump(mode="json")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, value in FIXTURES.items():
        text = json.dumps(dump(value), indent=2, ensure_ascii=False) + "\n"
        (OUT_DIR / name).write_text(text, encoding="utf-8")
        print(f"wrote {OUT_DIR / name}")


if __name__ == "__main__":
    main()
