"""Reuse six already provisioned, trusted local models. No download or training."""

import argparse
import hashlib
import json
from pathlib import Path

from ml.config import ARTIFACT_DIR, PACKAGE_ROOT
from ml.dispatch import read_registry
from ml.provision import check_reference
from ml.train import load_models


def reuse(source: Path, destination: Path = ARTIFACT_DIR) -> list[str]:
    """The operator must trust source pickles; hashes are identity, not sandboxing.

    Validate all six before writing. Existing differing files are preserved and
    rejected. Input directories and fixed registry paths never come from HTTP.
    """
    source, destination = source.resolve(), destination.resolve()
    receipt_rel = Path("provisioned_v2/active_event.manifest.json")
    receipt_bytes = (source / receipt_rel).read_bytes()
    receipt = json.loads(receipt_bytes)
    if receipt.get("reference_predictions_verified") is not True:
        raise ValueError("Flood receipt lacks reference verification")
    items = [
        (
            Path("provisioned_v2/active_event.joblib"),
            receipt["artifact_sha256"],
            "Flood",
            None,
        )
    ]
    for entry in read_registry()["events"].values():
        if (
            entry.get("status") == "evaluated_research"
            and entry.get("prediction_eligible") is True
        ):
            relative = Path(entry["artifact"])
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or relative.parts[0] != "multidisaster"
            ):
                raise ValueError("Invalid trusted registry artifact path")
            items.append(
                (
                    relative,
                    entry["artifact_sha256"],
                    entry["event_type"],
                    entry["artifact_model_version"],
                )
            )
    if len(items) != 6:
        raise ValueError(
            "Expected original Flood and exactly five qualified expansion models"
        )
    bodies = {receipt_rel: receipt_bytes}
    for relative, checksum, event_type, version in items:
        path = (source / relative).resolve()
        if not path.is_relative_to(source) or path.stat().st_size > 5_000_000:
            raise ValueError("Artifact path / size exceeds allowed local reuse")
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != checksum:
            raise ValueError("Trusted model checksum mismatch; nothing copied")
        model = load_models(
            path, expected_sha256=checksum, expected_event_type=event_type
        )
        if event_type == "Flood":
            check_reference(
                model, json.loads((PACKAGE_ROOT / "model_reference.json").read_text())
            )
        elif model.model_version != version:
            raise ValueError("Expansion model version differs from registry")
        bodies[relative] = body
    for relative, body in bodies.items():
        path = (destination / relative).resolve()
        if not path.is_relative_to(destination):
            raise ValueError("Destination escapes artifact directory")
        if path.exists() and path.read_bytes() != body:
            raise ValueError(
                "Existing different artifact/receipt preserved; nothing copied"
            )
    for relative, body in bodies.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # Exclusive create also preserves files introduced concurrently.
            with path.open("xb") as stream:
                stream.write(body)
    return [item[2] for item in items]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from-artifacts",
        type=Path,
        required=True,
        help="Trusted existing ml/artifacts directory",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            {
                "verified_reused_models": reuse(args.from_artifacts),
                "training_performed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
