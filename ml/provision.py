"""Rebuild a separate trusted model from checksum-pinned NOAA revisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import tempfile
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from ml.config import ARTIFACT_DIR, LEGACY_MODEL_PATH, MODEL_PATH, NOAA_INDEX_URL, NOAA_MAX_ARCHIVE_BYTES, PACKAGE_ROOT, RAW_DATA_DIR
from ml.events import read_noaa_detail_files
from ml.features import split_events_by_episode
from ml.predict import predict_active_event
from ml.sources.noaa import _request_with_retries, _validate_gzip
from ml.train import fit_models, load_models, save_models

PROVISIONED_MODEL_PATH = ARTIFACT_DIR / "provisioned_v2" / "active_event.joblib"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_archive(entry: dict[str, Any], input_dir: Path, *, download: bool = False) -> Path:
    """Keep existing files intact, reject wrong revisions, and never discover latest."""
    name = entry.get("file", entry.get("path"))
    if not isinstance(name, str) or Path(name).name != name or not name.endswith(".csv.gz"):
        raise ValueError("manifest archive must be a basename ending in .csv.gz")
    if entry.get("url") != NOAA_INDEX_URL + name:
        raise ValueError("manifest URL must identify the exact official NOAA archive")
    path = input_dir / name
    if not path.exists():
        if not download:
            raise FileNotFoundError(f"Missing pinned archive {name}; use --download to retrieve it")
        input_dir.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            fd, temporary_name = tempfile.mkstemp(prefix="noaa-provision-", suffix=".part", dir=input_dir)
            os.close(fd)
            temporary = Path(temporary_name)
            body = _request_with_retries(entry["url"], timeout=30, retries=3, limit=NOAA_MAX_ARCHIVE_BYTES)
            size, checksum = len(body), hashlib.sha256(body).hexdigest()
            temporary.write_bytes(body)
            if size != entry["bytes"] or checksum != entry["sha256"]:
                raise ValueError(f"Pinned archive size or SHA-256 mismatch: {name}")
            _validate_gzip(temporary)
            # An existing mismatched file must never be silently replaced.
            if path.exists():
                raise FileExistsError(f"Archive appeared during provisioning: {name}")
            temporary.rename(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    if path.stat().st_size != entry["bytes"] or file_sha256(path) != entry["sha256"]:
        raise ValueError(f"Pinned archive size or SHA-256 mismatch: {name}; existing file preserved")
    _validate_gzip(path)
    return path


def check_reference(models: Any, reference: dict[str, Any]) -> None:
    for key in ("model_version", "training_event_count", "training_episode_count"):
        if getattr(models, key) != reference[key]:
            raise ValueError(f"Reproduced model differs from reference: {key}")
    if models.training_policy != reference["training_policy"]:
        raise ValueError("Reproduced training policy differs from reference")
    for sample in reference["predictions"]:
        result = predict_active_event(sample["context"], model=models, estimator=sample["estimator"])
        if result["status"] != "ok":
            raise ValueError("Reproduced reference prediction is unavailable")
        for horizon, expected in sample["ongoing_probability"].items():
            actual = result["outcomes"]["recorded_event_ongoing_probability"][horizon]
            if not math.isclose(actual, expected, rel_tol=0, abs_tol=1e-10):
                raise ValueError("Reproduced prediction differs from reference; inspect numerical environment")


def provision(*, input_dir: Path = RAW_DATA_DIR, output: Path = PROVISIONED_MODEL_PATH,
              download: bool = False, verify_only: bool = False) -> dict[str, Any]:
    if output.resolve() == LEGACY_MODEL_PATH.resolve() or "before_optimization" in output.name:
        raise ValueError("Provision into a separate path to preserve existing model artifacts")
    manifest = json.loads((PACKAGE_ROOT / "reports/source_manifest.json").read_text(encoding="utf-8"))
    reference = json.loads((PACKAGE_ROOT / "model_reference.json").read_text(encoding="utf-8"))
    paths = []
    for index, entry in enumerate(manifest["archives"], 1):
        print(f"[provision] archive {index}/{len(manifest['archives'])}: {entry['year']}", flush=True)
        paths.append(ensure_archive(entry, input_dir, download=download))
    receipt_path = output.with_suffix(".manifest.json")
    if output.exists():
        if not receipt_path.exists():
            raise ValueError("Existing artifact has no provisioning receipt; preserved without loading")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        models = load_models(output, expected_sha256=receipt["artifact_sha256"])
        check_reference(models, reference)
        print("[provision] existing artifact and reference predictions verified", flush=True)
        return receipt
    if verify_only:
        raise FileNotFoundError("Provisioned artifact is missing; run without --verify-only to build it")
    print("[provision] parsing pinned Flood intervals and fitting through 2024; no evaluation rerun", flush=True)
    events, counts = read_noaa_detail_files(paths)
    splits = split_events_by_episode(events)
    models = fit_models(splits["train"] + splits["validation"])
    check_reference(models, reference)
    save_models(models, output)
    receipt = {
        "schema_version": 1, "artifact": output.name, "artifact_sha256": file_sha256(output),
        "model_version": models.model_version, "source_row_counts": counts,
        "source_manifest_sha256": file_sha256(PACKAGE_ROOT / "reports/source_manifest.json"),
        "reference_predictions_verified": True, "python": platform.python_version(),
        "dependencies": {name: version(name) for name in ("numpy", "scipy", "scikit-learn", "joblib", "threadpoolctl")},
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "production_eligibility": False,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
    print("[provision] separate artifact and SHA-256 receipt written", flush=True)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output", type=Path, default=PROVISIONED_MODEL_PATH)
    parser.add_argument("--download", action="store_true", help="retrieve missing exact NOAA revisions only")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(provision(input_dir=args.input_dir, output=args.output, download=args.download,
                               verify_only=args.verify_only), indent=2))


if __name__ == "__main__":
    main()
