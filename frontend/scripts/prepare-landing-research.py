"""Export landing-page evidence from saved reports; never train, sample or fetch.

Requires scripts/landing-research-requirements.txt in an isolated Python environment.
Run from any directory; --check verifies the committed assets and HTML without writes.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend/public"
START = "<!-- research-evidence:start -->"
END = "<!-- research-evidence:end -->"
SOURCES = {
    "flood": "ml/reports/purged_v2/backtest_metrics.json",
    "monte_carlo": "ml/reports/purged_v2/monte_carlo_summary.json",
    "stations": "ml/reports/multidisaster/station_coverage.json",
    "nhc": "ml/reports/multidisaster/hurdat_coverage.json",
    "eia": "ml/reports/worker_outlook/eia_coverage.json",
    "targets": "ml/reports/multidisaster/registry.json",
}
WHITE, RED, MUTED, LINE = "#eef0f2", "#ff4760", "#b4b9c1", "#33363d"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def read_evidence():
    reports = {
        name: json.loads((ROOT / path).read_bytes()) for name, path in SOURCES.items()
    }
    flood, mc = reports["flood"], reports["monte_carlo"]
    assert flood["production_eligibility"] is False
    assert flood["smoke_test"]["enabled"] is False
    assert flood["model"]["default_estimator"] == "kaplan_meier"
    assert mc["scope"] == "offline_internal_only" and mc["is_simulated"] is True
    datasets = [
        {
            "name": "NOAA Storm Events",
            "count": flood["source_row_counts"]["rows_total"],
        },
        {
            "name": "Station measurements",
            "count": sum(
                s["source_rows"] for s in reports["stations"]["stations"].values()
            ),
        },
        {
            "name": "NHC track points",
            "count": reports["nhc"]["full_archive"]["track_points"],
        },
    ]
    validation = flood["validation_2024_train_through_2023"]
    rows = []
    for horizon in ("6h", "12h", "24h"):
        row = {"horizon": horizon}
        for method in ("kaplan_meier", "logistic"):
            record = validation[method][horizon]
            row[method] = {
                key: record[key]
                for key in (
                    "brier_score",
                    "snapshot_count",
                    "episode_count",
                    "episode_bootstrap_brier_95",
                )
            }
        assert (
            row["kaplan_meier"]["snapshot_count"] == row["logistic"]["snapshot_count"]
        )
        rows.append(row)
    targets = [
        name
        for name, entry in reports["targets"]["events"].items()
        if entry["prediction_eligible"]
    ]
    assert len(targets) == 6, (
        "Review target-count copy if the research registry changes"
    )
    return {
        "scope": "archived_research_not_live_forecast_or_safety_validation",
        "sources": [
            {"path": path, "sha256": digest((ROOT / path).read_bytes())}
            for path in SOURCES.values()
        ],
        "datasets": datasets,
        "total_records_and_measurements": sum(d["count"] for d in datasets),
        "reference_sites": reports["eia"]["selected_research_locations"],
        "research_targets": targets,
        "monte_carlo": mc,
        "backtest": {
            "period": "2024 validation; trained through 2023",
            "split": flood["split"],
            "rows": rows,
        },
    }


def chart(kind, evidence, mobile):
    """Use fixed scales, direct report values and exported vector artwork."""
    plt.rcdefaults()
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11 if mobile else 12,
            "text.color": WHITE,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "svg.hashsalt": "foresite-research-v1",
            "svg.fonttype": "path",
        }
    )
    fig, ax = plt.subplots(figsize=(3.7, 3.5) if mobile else (7, 3.7))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_axisbelow(True)
    ax.tick_params(length=0, pad=9)
    if kind in ("monte-carlo", "backtest"):
        ax.grid(axis="y", color=LINE, linewidth=0.6)
        xs = [0, 1, 2]
        if kind == "monte-carlo":
            mc = evidence["monte_carlo"]
            series = [
                ("Analytical", "analytical_ongoing_probability", WHITE),
                ("Simulated", "simulated_ongoing_proportion", RED),
            ]
            for index, (label, field, color) in enumerate(series):
                values = [100 * mc[field][h] for h in ("6h", "12h", "24h")]
                ax.bar(
                    [x + (index - 0.5) * 0.32 for x in xs],
                    values,
                    width=0.28,
                    label=label,
                    color=color,
                )
            ax.set_ylim(0, 105)
            ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
            ax.set_ylabel("Recorded event still ongoing", fontsize=11)
        else:
            for index, (method, label, color) in enumerate(
                (("kaplan_meier", "KM baseline", WHITE), ("logistic", "Logistic", RED))
            ):
                records = [row[method] for row in evidence["backtest"]["rows"]]
                values = [r["brier_score"] for r in records]
                errors = [
                    [
                        v - r["episode_bootstrap_brier_95"]["lower_95"]
                        for v, r in zip(values, records)
                    ],
                    [
                        r["episode_bootstrap_brier_95"]["upper_95"] - v
                        for v, r in zip(values, records)
                    ],
                ]
                ax.bar(
                    [x + (index - 0.5) * 0.34 for x in xs],
                    values,
                    width=0.29,
                    color=color,
                    label=label,
                    hatch="///" if index else None,
                    yerr=errors,
                    error_kw={"ecolor": MUTED, "capsize": 3, "linewidth": 1},
                    edgecolor="#15171b",
                )
            ax.set_ylim(0, 0.32)
            ax.set_yticks([0, 0.1, 0.2, 0.3], ["0", "0.1", "0.2", "0.3"])
            ax.set_ylabel("Brier error · lower is better", fontsize=11)
        ax.set_xticks(xs, ["6 hours", "12 hours", "24 hours"])
        ax.legend(
            loc="lower left",
            bbox_to_anchor=(-0.08 if mobile else -0.02, 1.01),
            ncol=2,
            frameon=False,
            labelcolor=WHITE,
            fontsize=10 if mobile else 11,
            handlelength=1.2,
            columnspacing=1.5,
        )
        fig.subplots_adjust(
            left=0.20 if mobile else 0.12, right=0.97, bottom=0.14, top=0.85
        )
    else:
        values = [d["count"] for d in evidence["datasets"]]
        bars = ax.barh([2, 1, 0], values, height=0.34, color=[RED, WHITE, "#8b95a5"])
        ax.set_xlim(0, 430000)
        ax.set_ylim(-0.55, 2.65)
        ax.set_yticks([])
        ax.set_xticks([0, 200000, 400000])
        ax.xaxis.set_major_formatter(
            FuncFormatter(
                lambda value, _: "0" if value == 0 else f"{value / 1000:.0f}K"
            )
        )
        ax.grid(axis="x", color=LINE, linewidth=0.6)
        for bar, dataset in zip(bars, evidence["datasets"]):
            y = bar.get_y() + bar.get_height() + 0.08
            ax.text(
                0,
                y,
                dataset["name"],
                fontsize=10 if mobile else 11,
                va="bottom",
                color=WHITE,
            )
            ax.text(
                425000,
                y,
                f"{dataset['count']:,}",
                fontsize=10 if mobile else 11,
                va="bottom",
                ha="right",
                color=WHITE,
            )
        fig.subplots_adjust(left=0.04, right=0.96, bottom=0.14, top=0.95)
    out = io.BytesIO()
    fig.savefig(
        out,
        format="svg",
        transparent=True,
        metadata={
            "Date": None,
            "Creator": "FORESITE report exporter / Matplotlib",
            "Title": kind,
            "Description": "Archived repository research. Exact values and source hashes accompany this figure in evidence.json.",
        },
    )
    plt.close(fig)
    return out.getvalue()


def section(data, assets):
    mc = data["monte_carlo"]
    counts = [d["count"] for d in data["datasets"]]

    def source(path, label):
        return f'<a href="https://github.com/BraydinPG/planit-control-swamphacks/blob/main/{path}">{label}</a>'

    def picture(name, alt):
        def url(suffix):
            filename = f"{name}{suffix}.svg"
            return f"/research/{filename}?v={digest(assets[filename])[:10]}"

        return f'<picture><source media="(max-width: 600px)" width="370" height="350" srcset="{url("-mobile")}"><img src="{url("")}" alt="{alt}" width="700" height="370" loading="lazy" decoding="async"></picture>'

    mc_rows = "".join(
        f'<tr><th scope="row">{h}</th><td>{mc["analytical_ongoing_probability"][h]:.6f}</td><td>{mc["simulated_ongoing_proportion"][h]:.6f}</td></tr>'
        for h in ("6h", "12h", "24h")
    )
    back_rows = "".join(
        f'<tr><th scope="row">{r["horizon"]}</th><td>{r["kaplan_meier"]["brier_score"]:.6f}</td><td>{r["logistic"]["brier_score"]:.6f}</td></tr>'
        for r in data["backtest"]["rows"]
    )
    source_rows = "".join(
        f'<tr><th scope="row">{d["name"]}</th><td>{d["count"]:,}</td></tr>'
        for d in data["datasets"]
    )
    max_error = 100 * max(mc["absolute_probability_error"].values())
    return f"""{START}
  <section class="lab" aria-labelledby="lab-title">
    <div class="lab-heading">
      <p class="lab-eyebrow">THE SCIENCE BEHIND THE OUTLOOK</p>
      <h2 id="lab-title">Built on Real Data.<br><span>Tested with Real Simulations.</span></h2>
      <p class="lab-intro">Official environmental data. Historically evaluated models. Thousands of simulated outcomes. FORESITE brings these together to help teams understand disruption—not just detect it.</p>
      <p class="lab-scope">Research estimates for certain already-active hazards. Decision support, with uncertainty kept visible.</p>
    </div>

    <div class="lab-sources" aria-label="Historical data and infrastructure sources">
      <article><p class="lab-source-type">NOAA STORM EVENTS</p><strong>{counts[0]:,}</strong><h3>Recorded storm events</h3><p>2021–2025 records provide reported event intervals for duration research.</p></article>
      <article><p class="lab-source-type">NOAA STATION WEATHER</p><strong>{counts[1]:,}</strong><h3>Hourly measurements</h3><p>Three evaluated stations support observed heat-index episode research.</p></article>
      <article><p class="lab-source-type">NHC HURDAT2</p><strong>{counts[2]:,}</strong><h3>Historical track points</h3><p>Post-analysis Atlantic best tracks. Historical context, not issued forecasts.</p></article>
      <article><p class="lab-source-type">EIA INFRASTRUCTURE</p><strong>{data["reference_sites"]}</strong><h3>Mapped reference locations</h3><p>Representative power plants, not proof of active crews or complete live coverage.</p></article>
    </div>
    <p class="lab-feed-note"><span class="lab-status-dot" aria-hidden="true"></span><strong>Live evidence is a separate layer.</strong> NWS, NHC and USGS observations and issued products add timestamped context. Coverage and freshness vary; missing inputs stay unknown.</p>

    <div class="lab-methods" aria-label="How the research works">
      <article><span aria-hidden="true">01</span><div><h3>Backtest against history.</h3><p>Group related episodes, separate time periods, and compare statistical models with simpler survival baselines.</p></div></article>
      <article><span aria-hidden="true">02</span><div><h3>Explore uncertainty.</h3><p>Monte Carlo draws sample model-implied durations. Many possible outcomes replace a single exact future.</p></div></article>
      <article><span aria-hidden="true">03</span><div><h3>Keep the evidence visible.</h3><p>Supported horizons, source provenance and limitations accompany each outlook. Unsupported predictions stay unavailable.</p></div></article>
    </div>

    <div class="lab-charts">
      <div class="lab-chart lab-monte" role="group" aria-labelledby="lab-mc-title">
        <div class="lab-chart-story"><p class="lab-eyebrow">01 / MONTE CARLO CONSISTENCY</p><h3 id="lab-mc-title">One model.<br>{mc["trials"]:,} possible outcomes.</h3><p>In this saved flood replay, {mc["trials"]:,} seeded draws closely reproduce the model’s own persistence probabilities at 6, 12 and 24 hours.</p><p class="lab-callout"><strong>{max_error:.2f} percentage points</strong><span>largest analytical–sampling difference</span></p><p class="lab-caveat">A consistency check—not proof of forecast accuracy. Archived {mc["as_of_utc"][:10]} replay using the logistic research model, not a current worksite forecast.</p></div>
        <figure class="lab-chart-visual" aria-labelledby="lab-mc-title">
          {picture("monte-carlo", "Grouped bars compare analytical persistence with simulated ongoing proportions at 6, 12 and 24 hours, on a zero to 100 percent scale.")}
          <figcaption>Probability the recorded Flood event remains ongoing. {mc["trials"]:,} draws · seed {mc["seed"]}. Offline research only.
          <details class="lab-values"><summary>Exact values and experiment</summary><table><caption>Ongoing probability · archived simulated replay</caption><thead><tr><th>Horizon</th><th>Analytical</th><th>Simulated</th></tr></thead><tbody>{mc_rows}</tbody></table><p>{source(SOURCES["monte_carlo"], "Original experiment JSON")} · Model: {mc["model_version"]}. No raw trial paths are shown.</p></details></figcaption>
        </figure>
      </div>

      <figure class="lab-chart" aria-labelledby="lab-backtest-title">
        <p class="lab-eyebrow">02 / HISTORICAL VALIDATION</p><h3 id="lab-backtest-title">Test the model. Keep the better baseline.</h3><p>On the 2024 Flood validation cohort, the simpler Kaplan–Meier survival baseline had lower Brier error at all three horizons. It remains the selected default.</p>
        {picture("backtest", "Grouped Brier-error bars compare the Kaplan–Meier baseline and logistic model at 6, 12 and 24 hours. The baseline has lower error at every horizon; whiskers show 95 percent episode-bootstrap intervals.")}
        <figcaption>Trained through 2023; {data["backtest"]["rows"][0]["kaplan_meier"]["snapshot_count"]:,} validation snapshots from {data["backtest"]["rows"][0]["kaplan_meier"]["episode_count"]} reporting episodes. Whiskers: 95% episode-bootstrap intervals, {data["backtest"]["rows"][0]["kaplan_meier"]["episode_bootstrap_brier_95"]["replicates"]} resamples. Lower Brier error is better.
        <details class="lab-values"><summary>Exact values and evaluation</summary><table><caption>2024 validation Brier error</caption><thead><tr><th>Horizon</th><th>KM baseline</th><th>Logistic</th></tr></thead><tbody>{back_rows}</tbody></table><p>{source(SOURCES["flood"], "Full metrics, intervals and splits")} · {source("ml/EVALUATION.md", "Evaluation limitations")}. This is the model-selection cohort, not a new untouched holdout. Calibration and duration error still limit use; retrospective evaluation is not operational safety validation.</p></details></figcaption>
      </figure>

      <figure class="lab-chart" aria-labelledby="lab-data-title">
        <p class="lab-eyebrow">03 / SOURCE SCALE</p><h3 id="lab-data-title">A traceable data foundation.</h3><p>{data["total_records_and_measurements"]:,} historical records and measurements across three source inventories. Different units and reporting processes—not independent training examples.</p>
        {picture("data-sources", f"Horizontal bars show {counts[0]:,} NOAA Storm Events records, {counts[1]:,} station measurements, and {counts[2]:,} NHC historical track points on a shared zero-based count scale.")}
        <figcaption>Source volume, not forecast accuracy. These inventories include records outside the final eligible model cohorts; the NHC count covers the full historical archive.
        <details class="lab-values"><summary>Exact counts and source reports</summary><table><caption>Historical source inventories</caption><thead><tr><th>Dataset</th><th>Records / measurements</th></tr></thead><tbody>{source_rows}</tbody></table><p>{source(SOURCES["flood"], "NOAA rows")} · {source(SOURCES["stations"], "Station coverage")} · {source(SOURCES["nhc"], "NHC archive")} · {source(SOURCES["eia"], "EIA locations")}</p></details></figcaption>
      </figure>
    </div>

    <div class="lab-trust"><p class="lab-eyebrow">MODELS INFORM. PEOPLE DECIDE.</p><h3>Prediction is not permission.</h3><p>Statistical models estimate uncertainty. Deterministic rules raise alerts and calculate the separate 0–10 index. Supervisors make operational decisions. Neither ML nor Gemini can declare a site safe, authorize work or clear an alert.</p><a href="/research/evidence.json">Inspect the chart data and source hashes <span aria-hidden="true">↗</span></a></div>
  </section>
{END}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = read_evidence()
    assets = {}
    for name in ("monte-carlo", "backtest", "data-sources"):
        for mobile in (False, True):
            assets[f"{name}{'-mobile' if mobile else ''}.svg"] = chart(
                name, data, mobile
            )
    data["figure_generator"] = {
        "path": "frontend/scripts/prepare-landing-research.py",
        "matplotlib": matplotlib.__version__,
    }
    data["figures"] = [
        {"file": name, "sha256": digest(content)} for name, content in assets.items()
    ]
    assets["evidence.json"] = (
        json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    landing = PUBLIC / "landing.html"
    original = landing.read_text(encoding="utf-8")
    fragment = section(data, assets)
    if START in original:
        before, rest = original.split(START, 1)
        _, after = rest.split(END, 1)
        updated = before + fragment + after
    else:
        # Keep the hero and existing product-intelligence section intact.
        updated = original.replace(
            '  <section class="intelligence"',
            fragment + '\n\n  <section class="intelligence"',
            1,
        )
    assert updated != original or START in original
    mismatches = []
    for filename, content in assets.items():
        path = PUBLIC / "research" / filename
        if args.check:
            if not path.exists() or path.read_bytes() != content:
                mismatches.append(str(path.relative_to(ROOT)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    if args.check:
        if original != updated:
            mismatches.append("frontend/public/landing.html")
        if mismatches:
            raise SystemExit(
                "Research exports differ; regenerate: " + ", ".join(mismatches)
            )
    else:
        landing.write_text(updated, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "check": args.check,
                "charts": 3,
                "responsive_variants": 6,
                "total_source_records": data["total_records_and_measurements"],
                "network_calls": 0,
                "models_changed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
