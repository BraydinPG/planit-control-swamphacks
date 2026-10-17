"""Species context settings, read from environment variables or backend/.env.

IPaC needs no API key today. Its documentation says a key will eventually be required;
add it here as a SecretStr when that happens and never log it.
"""

from datetime import timedelta
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class SpeciesSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ipac_resources_url: str = "https://ipac.ecosphere.fws.gov/location/api/resources"
    crithab_service_url: str = (
        "https://services.arcgis.com/QVENGdaPbd4LUkLV/ArcGIS/rest/services/"
        "USFWS_Critical_Habitat/FeatureServer"
    )
    species_timeout_seconds: float = 20.0
    # IPaC range data changes rarely; one lookup per site per day is plenty.
    species_cache_hours: float = 24.0
    # After this long without a successful refresh, cached context is withdrawn.
    species_unavailable_after_hours: float = 168.0
    # Half the side of the square footprint sent to IPaC, and of the map window.
    species_footprint_half_km: float = 0.5
    crithab_window_half_km: float = 3.0

    @property
    def cache_for(self) -> timedelta:
        return timedelta(hours=self.species_cache_hours)

    @property
    def unavailable_after(self) -> timedelta:
        return timedelta(hours=self.species_unavailable_after_hours)


@lru_cache
def get_species_settings() -> SpeciesSettings:
    return SpeciesSettings()
