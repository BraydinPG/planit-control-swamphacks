"""Prototype rule and score settings, read from environment variables or backend/.env.

These are configurable prototype values chosen by the team. They are not employer,
regulatory, or NWS policy. The lightning 10-mile / 30-minute rule is fixed by the brief
and lives in `app.rules.lightning`, not here.
"""

from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuleSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Heat (T049): points scale from heat_min_points at the threshold to heat_max_points
    # at the extreme value. Below the threshold, heat adds nothing.
    # Independent vs. co-occurring hazards (2026-10-18, user decision): flooding, lightning
    # and hurricanes usually arrive together, so their points already add up. Extreme
    # heat and earthquakes usually happen alone, so each alone outweighs a single
    # co-occurring factor. Heat stays well below a flood plus lightning together (5.0):
    # 2.5 at the threshold, 3.0 at 114 °F, at most 3.5 (user decision, 2026-10-18).
    heat_index_threshold_f: float = 103.0
    heat_index_extreme_f: float = 125.0
    heat_min_points: float = Field(default=2.5, ge=0, le=10, allow_inf_nan=False)
    heat_max_points: float = Field(default=3.5, ge=0, le=10, allow_inf_nan=False)
    heat_window_hours: int = 12

    # Flood (T049): points from the strongest active NWS flood alert.
    flood_warning_points: float = Field(default=2.0, ge=0, le=10, allow_inf_nan=False)
    flood_watch_points: float = Field(default=1.0, ge=0, le=10, allow_inf_nan=False)

    # Hurricane (T049A): an NWS Hurricane or Tropical Storm Warning for the site, or an NHC
    # active storm center within this distance. Prototype distance, not official policy.
    hurricane_storm_distance_miles: float = 50.0
    hurricane_points: float = Field(default=2.0, ge=0, le=10, allow_inf_nan=False)

    # Earthquake (T049A): a USGS event at or above this magnitude within this distance of
    # the site. Prototype values, not official policy.
    earthquake_min_magnitude: float = 4.0
    earthquake_distance_miles: float = 25.0
    earthquake_points: float = Field(default=4.0, ge=0, le=10, allow_inf_nan=False)

    # Score weights (T051).
    lightning_stop_work_points: float = Field(default=3.0, ge=0, le=10, allow_inf_nan=False)
    report_low_points: float = Field(default=0.5, ge=0, le=10, allow_inf_nan=False)
    report_moderate_points: float = Field(default=1.0, ge=0, le=10, allow_inf_nan=False)
    report_high_points: float = Field(default=1.5, ge=0, le=10, allow_inf_nan=False)
    # T051A: bound repeated reports in one reviewed category. Every distinct report
    # remains in the breakdown, including zero-credit capped/shared-notice entries.
    report_category_max_points: float = Field(default=3.0, ge=0, le=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_weights(self):
        """A more severe factor must not contribute fewer points."""
        if self.heat_min_points > self.heat_max_points:
            raise ValueError("heat_min_points must not exceed heat_max_points")
        if self.flood_watch_points > self.flood_warning_points:
            raise ValueError("flood_watch_points must not exceed flood_warning_points")
        if not self.report_low_points <= self.report_moderate_points <= self.report_high_points:
            raise ValueError("report weights must be ordered low <= moderate <= high")
        return self


@lru_cache
def get_rule_settings() -> RuleSettings:
    return RuleSettings()
