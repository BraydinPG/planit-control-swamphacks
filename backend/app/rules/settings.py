"""Prototype rule and score settings, read from environment variables or backend/.env.

These are configurable prototype values chosen by the team. They are not employer,
regulatory, or NWS policy. The lightning 10-mile / 30-minute rule is fixed by the brief
and lives in `app.rules.lightning`, not here.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RuleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Heat (T049): points scale from heat_min_points at the threshold to heat_max_points
    # at the extreme value. Below the threshold, heat adds nothing.
    heat_index_threshold_f: float = 103.0
    heat_index_extreme_f: float = 125.0
    heat_min_points: float = 0.5
    heat_max_points: float = 2.0
    heat_window_hours: int = 12

    # Flood (T049): points from the strongest active NWS flood alert.
    flood_warning_points: float = 2.0
    flood_watch_points: float = 1.0

    # Hurricane (T049A): an NWS Hurricane or Tropical Storm Warning for the site, or an NHC
    # active storm center within this distance. Prototype distance, not official policy.
    hurricane_storm_distance_miles: float = 50.0
    hurricane_points: float = 2.0

    # Earthquake (T049A): a USGS event at or above this magnitude within this distance of
    # the site. Prototype values, not official policy.
    earthquake_min_magnitude: float = 4.0
    earthquake_distance_miles: float = 25.0
    earthquake_points: float = 1.5

    # Score weights (T051).
    lightning_stop_work_points: float = 3.0
    report_low_points: float = 0.5
    report_moderate_points: float = 1.0
    report_high_points: float = 1.5


@lru_cache
def get_rule_settings() -> RuleSettings:
    return RuleSettings()
