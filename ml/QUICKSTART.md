# ML Quickstart

The ML package predicts recorded-event persistence for a confirmed active NOAA Flood interval. It does not predict event onset, site safety, work clearance, or lightning state. NOAA and weather downloads are cached below `ml/data/raw/` and ignored by Git; model artifacts are ignored below `ml/artifacts/`.

## Windows PowerShell

From the repository root:

```powershell
py -3.14 -m venv ml/.venv
$python = ".\ml\.venv\Scripts\python.exe"
& $python -m pip install -r ml/requirements.txt
& $python -m ml.sources.noaa --years 2021 2022 2023 2024 2025
& $python -m ml.train --input-dir ml/data/raw --through-year 2024
& $python -m ml.backtest --input-dir ml/data/raw --output-dir ml/reports
& $python -m ml.monte_carlo --event-fixture ml/fixtures/active_flood.json --trials 5000 --seed 42
& $python -m pytest ml/tests -q
```

Use `py -3.11` or another supported Python 3.11+ runtime in the first command if Python 3.14 is unavailable. The archive downloader discovers current NOAA revision names from the official index, retries transient failures, enforces per-file byte limits, checks gzip integrity, and records SHA-256 hashes.

The backtest command trains its validation model through 2023, evaluates 2024, then trains through 2024 and holds out all 2025 NOAA episode groups. It also writes `ml/artifacts/active_event.joblib` and `ml/reports/backtest_metrics.json`. The standalone `ml.train` command trains through the selected year but does not replace the chronological backtest.

## Inference

Run from the repository root after training/backtesting:

```powershell
& $python -c 'from ml.predict import predict_active_event; import json; event={"site_id":"fixture-site","event_id":"fixture-event","event_type":"Flood","event_status":"historical_replay","event_start_utc":"2024-09-10T10:00:00Z","as_of_utc":"2024-09-10T16:00:00Z","location":{"region":"fixture county","spatial_match_quality":"region_only"},"is_simulated":True}; result=predict_active_event(event); print(json.dumps(result, indent=2, allow_nan=False))'
```

The values above are fixture-only shape data. A missing artifact or unsupported event returns `status="unavailable"` with no probabilities. A `historical_replay` input is always marked simulated. Current observations can be validated for as-of timing, but this trained artifact does not use weather measurements.

## Optional retrospective weather lookup

```powershell
& $python -m ml.sources.weather --latitude 27.9 --longitude -82.7 --start 2024-09-10 --end 2024-09-11 --as-of-utc 2024-09-10T16:00:00Z --output ml/data/raw/weather/example.json
```

Open-Meteo archive values are retrospective reanalysis, not forecasts actually issued at the historical decision time. This adapter is not part of current model features or operational inference.

## Reports and limits

- `ml/reports/source_manifest.json`: archive URLs, filenames, retrieval times, sizes, and checksums.
- `ml/reports/backtest_metrics.json`: validation/test splits, scores, reliability bins, bootstrap bounds, duration errors, and a held-out replay.
- `ml/reports/monte_carlo_summary.json`: offline model-implied sampling summary; never production data.
- Raw archives, downloaded weather, and binary model artifacts are not committed.
