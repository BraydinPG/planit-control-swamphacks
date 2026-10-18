"""Fixed synthetic T051A rule evaluation, not predictive or operational validation.

From repository root: python backend/tests/score_scenarios.py
Optional: --output docs/site-risk-scoring-evaluation.json
No network, database, Auth0 session, ML artifacts or Gemini required. Explicit defaults
override local environment settings so the checked report is byte-reproducible.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

# ruff: noqa: E402 -- direct script execution needs the repository backend import root.
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.nws_alerts import NO_ACTIVE_ALERTS
from app.ingestion.nws_weather import HEAT_INDEX, RELATIVE_HUMIDITY, TEMPERATURE
from app.ingestion.settings import IngestionSettings
from app.rules.score import MODEL_VERSION, compute_score
from app.rules.settings import RuleSettings
from app.schemas import (
    Alert,
    CrewReport,
    DataState,
    HazardScore,
    HazardType,
    Observation,
    SiteDetail,
)

NOW = datetime(2026, 10, 17, 18, tzinfo=UTC)


@dataclass(frozen=True)
class Site:
    id: str = "synthetic-scoring-site"
    lat: float = 25.76
    lon: float = -80.49
    name: str = "Synthetic scoring site"


SITE = Site()


def defaults(model):
    return model(
        _env_file=None, **{key: field.default for key, field in model.model_fields.items()}
    )


def reading(kind=HazardType.WEATHER, value=90.0, label=HEAT_INDEX, **extra):
    payload = dict(
        id=f"synthetic:{kind}:{label}",
        site_id=SITE.id,
        source="NWS",
        hazard_type=kind,
        value=value,
        unit="°F",
        label=label,
        lat=SITE.lat,
        lon=SITE.lon,
        source_ref="station:synthetic",
        observed_at=NOW - timedelta(minutes=5),
        fetched_at=NOW,
        data_state=DataState.OBSERVED,
    )
    payload.update(extra)
    return Observation(**payload)


def flood(value=None, **extra):
    payload = dict(
        kind=HazardType.FLOOD_ALERT, value=value, label=value or NO_ACTIVE_ALERTS, unit=None
    )
    payload.update(extra)
    return reading(**payload)


def lightning(**extra):
    payload = dict(
        kind=HazardType.LIGHTNING_STRIKE,
        value=None,
        label="No live flashes in feed window",
        source="GOES GLM",
        unit=None,
    )
    payload.update(extra)
    return reading(**payload)


def active_alert(**extra):
    payload = dict(
        id="synthetic-alert",
        site_id=SITE.id,
        rule="lightning_stop_work",
        state="active",
        triggered_at=NOW - timedelta(minutes=15),
        latest_event_at=NOW - timedelta(minutes=5),
        clear_after=NOW + timedelta(minutes=25),
        distance_miles=4.2,
    )
    payload.update(extra)
    return Alert(**payload)


def report(id="synthetic-report", **extra):
    payload = dict(
        id=id,
        site_id=SITE.id,
        organization_id="synthetic-org",
        team_id="synthetic-team",
        reporter_id="synthetic-crew",
        category="broken_pole_downed_line",
        hazard_present=True,
        lat=SITE.lat,
        lon=SITE.lon,
        review_status="confirmed",
        reviewed_by="synthetic-supervisor",
        confirmed_category="broken_pole_downed_line",
        confirmed_severity="high",
        created_at=NOW - timedelta(minutes=30),
        reviewed_at=NOW - timedelta(minutes=10),
    )
    payload.update(extra)
    return CrewReport(**payload)


def storm(**extra):
    return reading(
        HazardType.HURRICANE,
        90.0,
        "Synthetic NHC storm",
        source="NHC",
        unit="kt",
        source_ref="synthetic-storm",
        **extra,
    )


def quake(**extra):
    payload = dict(
        kind=HazardType.EARTHQUAKE,
        value=4.5,
        label="Synthetic USGS earthquake",
        source="USGS",
        unit="mw",
        source_ref="synthetic-quake",
    )
    payload.update(extra)
    return reading(**payload)


def healthy():
    return [reading(), flood(), lightning()]


def forecast_pair(**extra):
    return [
        reading(
            HazardType.FORECAST,
            value,
            label,
            unit=unit,
            valid_at=NOW + timedelta(hours=2),
            data_state=DataState.FORECAST,
            source_ref="forecastHourly",
            **extra,
        )
        for value, label, unit in [(100.0, TEMPERATURE, "°F"), (60.0, RELATIVE_HUMIDITY, "%")]
    ]


@dataclass
class Scenario:
    id: str
    observations: list
    score: float
    completeness: float
    alerts: tuple = ()
    reports: tuple = ()

    def evaluate(self):
        return compute_score(
            SITE.id,
            self.observations,
            list(self.alerts),
            list(self.reports),
            NOW,
            settings=defaults(RuleSettings),
            site=SITE,
        )


def scenarios():
    unavailable = lightning(data_state=DataState.UNAVAILABLE, label="Live feed unavailable")
    return [
        Scenario("no_evidence", [], 0, 0),
        Scenario("partial_heat_only", [reading()], 0, 0.33),
        Scenario("healthy_supported_inputs", healthy(), 0, 1),
        Scenario(
            "all_built_scored_feeds_healthy",
            healthy()
            + [
                reading(
                    HazardType.HURRICANE,
                    None,
                    "No active NHC storms",
                    source="NHC",
                    unit=None,
                    source_ref=None,
                ),
                reading(
                    HazardType.HURRICANE,
                    None,
                    "No active NWS tropical alerts",
                    unit=None,
                    source_ref=None,
                ),
                quake(value=None, source_ref=None, label="No earthquakes in search window"),
            ],
            0,
            1,
        ),
        Scenario("heat_threshold", [reading(value=103), flood(), lightning()], 2.5, 1),
        Scenario("heat_elevated", [reading(value=110), flood(), lightning()], 2.8, 1),
        Scenario("heat_extreme", [reading(value=125), flood(), lightning()], 3.5, 1),
        Scenario("eligible_forecast_not_double_counted", healthy() + forecast_pair(), 3.5, 1),
        Scenario("flood_watch", [reading(), flood("Flood Watch"), lightning()], 1, 1),
        Scenario("flood_warning", [reading(), flood("Flood Warning"), lightning()], 2, 1),
        Scenario(
            "strongest_flood_once",
            healthy() + [flood("Flood Watch"), flood("Flood Warning")] * 3,
            2,
            1,
        ),
        Scenario("active_lightning", healthy(), 3, 1, (active_alert(),)),
        Scenario(
            "held_lightning_feed_failure",
            [reading(), flood(), unavailable],
            3,
            0.67,
            (active_alert(clear_after=NOW - timedelta(minutes=1)),),
        ),
        Scenario("hurricane_near", healthy() + [storm()], 2, 1),
        Scenario(
            "hurricane_warning",
            healthy()
            + [
                reading(
                    HazardType.HURRICANE, "Hurricane Warning", "Synthetic site warning", unit=None
                )
            ],
            2,
            1,
        ),
        Scenario("hurricane_distant", healthy() + [storm(lat=SITE.lat + 2)], 0, 1),
        Scenario(
            "duplicate_storm_and_warning",
            healthy()
            + [
                storm(),
                storm(),
                reading(HazardType.HURRICANE, "Hurricane Warning", "Synthetic warning", unit=None),
            ],
            2,
            1,
        ),
        Scenario("earthquake_near", healthy() + [quake()], 4, 1),
        Scenario("earthquake_below_magnitude", healthy() + [quake(value=3.9)], 0, 1),
        Scenario("earthquake_distant", healthy() + [quake(lat=SITE.lat + 2)], 0, 1),
        Scenario("duplicate_quake", healthy() + [quake(), quake()], 4, 1),
        Scenario("confirmed_report", healthy(), 1.5, 1, reports=(report(),)),
        Scenario("duplicate_report_id", healthy(), 1.5, 1, reports=(report(), report())),
        Scenario(
            "shared_notice",
            healthy(),
            1.5,
            1,
            reports=(report("r1", notice_id="n1"), report("r2", notice_id="n1")),
        ),
        Scenario(
            "category_cap_retains_independent_reports",
            healthy(),
            3,
            1,
            reports=tuple(report(f"r{i}") for i in range(6)),
        ),
        Scenario(
            "independent_categories",
            healthy(),
            4.5,
            1,
            reports=(
                report("r1"),
                report("r2", confirmed_category="wildlife"),
                report("r3", confirmed_category="on_site_fire"),
            ),
        ),
        Scenario(
            "excluded_report_states",
            healthy(),
            0,
            1,
            reports=(
                report("r1", review_status="pending"),
                report("r2", review_status="rejected"),
                report("r3", hazard_present=False),
            ),
        ),
        Scenario(
            "stale_heat_retained",
            [reading(value=110, data_state=DataState.STALE), flood(), lightning()],
            2.8,
            0.67,
        ),
        Scenario(
            "stale_flood_retained",
            [reading(), flood("Flood Warning", data_state=DataState.STALE), lightning()],
            2,
            0.67,
        ),
        Scenario(
            "unavailable_flood",
            [reading(), flood(data_state=DataState.UNAVAILABLE), lightning()],
            0,
            0.67,
        ),
        Scenario(
            "replay_not_live_coverage",
            [
                reading(),
                flood(),
                lightning(
                    source="lightning-replay", data_state=DataState.SIMULATED, simulated=True
                ),
            ],
            0,
            0.67,
        ),
        Scenario(
            "expired_flood", [reading(), flood("Flood Warning", valid_at=NOW), lightning()], 0, 0.67
        ),
        Scenario(
            "future_observation",
            [reading(value=125, observed_at=NOW + timedelta(minutes=1)), flood(), lightning()],
            0,
            0.67,
        ),
        Scenario(
            "raw_gauge_and_rain_excluded",
            healthy()
            + [
                reading(
                    HazardType.FLOOD_GAUGE,
                    999,
                    "Gauge stage (no datum/threshold)",
                    unit="ft",
                    source="USGS",
                ),
                reading(
                    HazardType.FORECAST,
                    100,
                    "Precipitation probability",
                    unit="%",
                    valid_at=NOW + timedelta(hours=1),
                ),
            ],
            0,
            1,
        ),
        Scenario(
            "compound_saturated",
            [reading(value=125), flood("Flood Warning"), lightning(), storm(), quake()],
            10,
            1,
            (active_alert(),),
            (report(),),
        ),
    ]


def evaluation():
    cache = defaults(IngestionSettings)
    rows = []
    examples = {}
    with patch("app.rules.score.get_ingestion_settings", return_value=cache):
        for case in scenarios():
            result = case.evaluate()
            HazardScore.model_validate_json(result.model_dump_json())
            assert result.risk_score == case.score, case.id
            assert result.data_completeness == case.completeness, case.id
            assert result == case.evaluate(), case.id
            rows.append(
                dict(
                    id=case.id,
                    score=result.risk_score,
                    band=result.risk_level.value,
                    completeness=result.data_completeness,
                    contributions=[
                        dict(
                            factor=f.factor,
                            points=f.contribution,
                            state=f.data_state.value,
                            evidence_id=f.evidence_id,
                        )
                        for f in result.factor_contributions
                    ],
                )
            )
            if case.id in {
                "no_evidence",
                "healthy_supported_inputs",
                "compound_saturated",
                "held_lightning_feed_failure",
            }:
                examples[case.id] = result.model_dump(mode="json")
        # Read owner-published fixtures without regenerating frontend data.
        fixture_dir = Path(__file__).resolve().parents[2] / "frontend/src/fixtures"
        detail = SiteDetail.model_validate_json(
            (fixture_dir / "site-detail.json").read_text(encoding="utf-8")
        )
        fixture_score = compute_score(
            detail.id,
            detail.observations,
            detail.alerts,
            detail.reports,
            NOW,
            settings=defaults(RuleSettings),
            site=detail,
        )
        examples["existing_demo_detail_recomputed"] = fixture_score.model_dump(mode="json")
        reference_path = (
            Path(__file__).resolve().parents[2] / "ml/fixtures/hazard_coverage/backend_sites.json"
        )
        reference_rows = json.loads(reference_path.read_text(encoding="utf-8"))["records"][:2]
        assert all(
            r["id"] == r["site"]["id"] and r["id"].startswith("eia860m-") for r in reference_rows
        )
        reference_sites = [
            Site(id=r["id"], lat=r["site"]["lat"], lon=r["site"]["lon"], name=r["site"]["name"])
            for r in reference_rows
        ]
        assert len(reference_sites) == 2
        comparisons = []
        for reference in reference_sites:
            base = [
                o.model_copy(
                    update={"site_id": reference.id, "lat": reference.lat, "lon": reference.lon}
                )
                for o in healthy()
            ]
            quiet = compute_score(
                reference.id, base, [], [], NOW, settings=defaults(RuleSettings), site=reference
            )
            compound = compute_score(
                reference.id,
                base,
                [active_alert(site_id=reference.id)],
                [report(site_id=reference.id)],
                NOW,
                settings=defaults(RuleSettings),
                site=reference,
            )
            assert compound.risk_score > quiet.risk_score
            assert compound.data_completeness == quiet.data_completeness
            comparisons.append(
                dict(
                    site_id=reference.id,
                    name=reference.name,
                    context="synthetic scenarios at reference coordinates; no actual incident",
                    healthy_index=quiet.risk_score,
                    lightning_plus_report_index=compound.risk_score,
                    completeness=quiet.data_completeness,
                )
            )
    return dict(
        method="synthetic fixed-time deterministic rule checks; no real-world accuracy claim",
        as_of=NOW.isoformat(),
        model_version=MODEL_VERSION,
        settings=defaults(RuleSettings).model_dump(),
        freshness_minutes=dict(
            stale=cache.feed_stale_after_minutes, unavailable=cache.feed_unavailable_after_minutes
        ),
        passed=len(rows),
        scenarios=rows,
        equal_coverage_reference_comparisons=comparisons,
        existing_demo_fixture=dict(
            path="frontend/src/fixtures/site-detail.json",
            archived_illustrative_score=detail.risk_score,
            recomputed_index=fixture_score.risk_score,
            note="Simulated rules-0.2 fixture recomputed with the same algorithm; "
            "not a live score or operational validation.",
        ),
        canonical_examples=examples,
    )


def render_evaluation():
    return json.dumps(evaluation(), indent=2, ensure_ascii=False, allow_nan=False) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = render_evaluation()
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    else:
        print(rendered, end="")
