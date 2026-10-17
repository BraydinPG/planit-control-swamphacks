"""Shared paths and modeling limits for the Cache ML package."""

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
RAW_DATA_DIR = PACKAGE_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PACKAGE_ROOT / "data" / "processed"
ARTIFACT_DIR = PACKAGE_ROOT / "artifacts"
REPORT_DIR = PACKAGE_ROOT / "reports"
LEGACY_MODEL_PATH = ARTIFACT_DIR / "active_event.joblib"
MODEL_PATH = ARTIFACT_DIR / "provisioned_v2" / "active_event.joblib"
NOAA_INDEX_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
NOAA_DETAILS_PREFIX = "StormEvents_details-ftp_v1.0_d"
NOAA_MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
SUPPORTED_EVENT_TYPE = "Flood"
SNAPSHOT_OFFSETS_HOURS = (0, 6, 12)
MAX_FOLLOWUP_HOURS = 168
HORIZONS_HOURS = (6, 12, 24)
RANDOM_SEED = 42
