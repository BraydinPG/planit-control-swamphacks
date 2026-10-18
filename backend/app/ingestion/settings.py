"""Ingestion settings read from environment variables or backend/.env."""

from datetime import timedelta
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IngestionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    nws_user_agent: str | None = None
    nws_base_url: str = "https://api.weather.gov"
    nws_timeout_seconds: float = 10.0
    nws_forecast_hours: int = 12
    feed_stale_after_minutes: int = 60
    feed_unavailable_after_minutes: int = 360

    # Feed refresh loop (T049B). Off by default so tests and local runs never fetch live
    # feeds unless asked. The loop waits for each refresh to finish before sleeping.
    feed_refresh_enabled: bool = False
    feed_refresh_seconds: float = 300.0
    feed_site_workers: int = Field(6, ge=1, le=16)
    feed_round_budget_seconds: float = Field(480, gt=0, le=1800)
    feed_http_max_retries: int = Field(1, ge=0, le=3)
    feed_http_budget_seconds: float = Field(20, gt=0, le=60)
    feed_http_connect_seconds: float = Field(3, gt=0, le=30)
    feed_http_backoff_seconds: float = Field(0.5, ge=0, le=5)
    nws_http_connections: int = Field(4, ge=1, le=8)
    nws_min_interval_seconds: float = Field(0.25, ge=0, le=10)
    usgs_http_connections: int = Field(2, ge=1, le=4)
    usgs_min_interval_seconds: float = Field(0.5, ge=0, le=10)
    nws_point_cache_seconds: float = Field(86400, gt=0)
    nws_not_covered_cache_seconds: float = Field(3600, gt=0)
    nws_station_cache_seconds: float = Field(3600, gt=0)
    flood_gauge_batch_degrees: float = Field(0.5, gt=0, le=1)
    flood_gauge_batch_sites: int = Field(32, ge=1, le=100)

    # Braydin's feeds (T045–T045D). Search radii decide which events reach a site's
    # Observations. They are wider than the rule distances and are not rule settings.
    feed_timeout_seconds: float = 10.0
    lightning_search_radius_miles: float = 30.0
    lightning_lookback_minutes: int = 60
    lightning_live_enabled: bool = True
    glm_satellites: str = "goes19,goes18"
    glm_poll_seconds: float = 20.0
    glm_backfill_minutes: int = 5
    glm_bucket_url: str = "https://noaa-{satellite}.s3.amazonaws.com"
    nhc_storms_url: str = "https://www.nhc.noaa.gov/CurrentStorms.json"
    hurricane_search_radius_miles: float = 300.0
    usgs_earthquake_url: str = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
    )
    earthquake_search_radius_miles: float = 100.0
    usgs_water_url: str = "https://waterservices.usgs.gov/nwis/iv/"
    flood_gauge_search_radius_miles: float = 10.0
    flood_gauge_max_gauges: int = 3

    @property
    def stale_after(self) -> timedelta:
        return timedelta(minutes=self.feed_stale_after_minutes)

    @property
    def unavailable_after(self) -> timedelta:
        return timedelta(minutes=self.feed_unavailable_after_minutes)


@lru_cache
def get_ingestion_settings() -> IngestionSettings:
    return IngestionSettings()
