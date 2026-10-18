"""Render the public research dashboard from committed, reproducible offline exports."""

import argparse
import hashlib
import io
import json
import re
import runpy
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend/public"
OUT = PUBLIC / "research"
OLD = runpy.run_path(
    str(ROOT / "frontend/scripts/prepare-landing-research.py"),
    run_name="research_compatibility",
)
WHITE, RED, BLUE, MUTED, GRID = "#eef0f2", "#ff4760", "#a9bdce", "#b4b9c1", "#33363d"


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()


def style():
    plt.rcdefaults()
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10.5,
            "text.color": WHITE,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "svg.hashsalt": "foresite-dashboard-v1",
            "svg.fonttype": "path",
        }
    )


def clean(ax):
    ax.patch.set_alpha(0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(length=0, pad=7)
    ax.set_axisbelow(True)
    ax.grid(color=GRID, linewidth=0.5, alpha=0.7)


def save(fig):
    fig.patch.set_alpha(0)
    stream = io.BytesIO()
    fig.savefig(
        stream,
        format="svg",
        transparent=True,
        metadata={
            "Date": None,
            "Creator": "FORESITE offline research export",
            "Description": "Archived research; see dashboard-figures.json for provenance and dashboard.json for exact inputs.",
        },
    )
    plt.close(fig)
    return b"\n".join(line.rstrip() for line in stream.getvalue().splitlines()) + b"\n"


def render(
    kind,
    data,
    heldout,
    mobile=False,
    method="kaplan_meier",
    horizon=24,
    logarithmic=True,
):
    style()
    mc = data["monte_carlo_lab"]
    if kind == "brier-test":
        evidence = json.loads((OUT / "evidence.json").read_text())
        evidence["backtest"]["rows"] = [
            {
                "horizon": f"{h}h",
                **{
                    m: data["categories"]["Flood"]["test"][m][f"{h}h"]
                    for m in ("kaplan_meier", "logistic")
                },
            }
            for h in (6, 12, 24)
        ]
        return OLD["chart"]("backtest", evidence, mobile)
    if kind == "multi-disaster":
        fig, axes = (
            plt.subplots(6, 1, figsize=(3.7, 16.5))
            if mobile
            else plt.subplots(2, 3, figsize=(11, 6.6))
        )
        for ax, category in zip(axes.flat, data["categories"].values()):
            clean(ax)
            selected = category["selected_estimator"]
            rows = [category["test"][selected][f"{h}h"] for h in category["horizons"]]
            y = np.array([r["brier_score"] for r in rows])
            err = np.array(
                [
                    [
                        v - r["episode_bootstrap_brier_95"]["lower_95"]
                        for v, r in zip(y, rows)
                    ],
                    [
                        r["episode_bootstrap_brier_95"]["upper_95"] - v
                        for v, r in zip(y, rows)
                    ],
                ]
            )
            ax.errorbar(
                range(3),
                y,
                yerr=err,
                fmt="o-",
                color=WHITE,
                ecolor=BLUE,
                capsize=3,
                linewidth=1.4,
            )
            ax.set_ylim(0, 0.35)
            ax.set_xticks(range(3), [f"{h}h" for h in category["horizons"]])
            ax.set_yticks([0, 0.1, 0.2, 0.3])
            ax.set_title(
                f"{category['name']}\n{selected.replace('kaplan_meier', 'KM')}; n={rows[0]['snapshot_count']:,}",
                loc="left",
                fontsize=10,
                color=WHITE,
                pad=12,
            )
        fig.subplots_adjust(
            left=0.17 if mobile else 0.06,
            right=0.97,
            top=0.96,
            bottom=0.04 if mobile else 0.10,
            hspace=0.85,
            wspace=0.34,
        )
        return save(fig)
    facets = kind in ("cohort", "calibration", "duration-errors", "convergence")
    count = 3 if kind == "convergence" else 2
    if facets:
        fig, axes = (
            plt.subplots(count, 1, figsize=(3.7, 3.4 * count))
            if mobile
            else plt.subplots(1, count, figsize=(10.5 if count == 3 else 9.5, 4.1))
        )
        axes = np.atleast_1d(axes)
        for ax in axes:
            clean(ax)
    else:
        fig, ax = plt.subplots(figsize=(3.7, 3.5) if mobile else (7, 3.7))
        clean(ax)
    if kind == "cohort":
        cohort = data["flood_cohort"]
        values = [
            cohort["counts"]["rows_total"] - cohort["counts"]["unsupported_type"],
            cohort["counts"]["complete_end"],
            sum(
                cohort["split"][s]["event_record_count"]
                for s in ("train", "validation", "test")
            ),
        ]
        ax = axes[0]
        ax.barh([2, 1, 0], values, color=[BLUE, WHITE, RED], height=0.5)
        ax.set_yticks([2, 1, 0], ["Flood rows", "Valid intervals", "After purging"])
        ax.set_xlim(0, 14500)
        ax.set_xlabel("Recorded intervals")
        for y, v in zip([2, 1, 0], values):
            ax.text(v + 180, y, f"{v:,}", va="center", fontsize=9, color=WHITE)
        counts = {
            **cohort["split"]["train"]["event_year_counts"],
            **cohort["split"]["validation"]["event_year_counts"],
            **cohort["split"]["test"]["event_year_counts"],
        }
        ax = axes[1]
        ax.bar(
            range(5), list(counts.values()), color=[WHITE] * 3 + [RED, BLUE], width=0.6
        )
        ax.set_xticks(range(5), [str(y)[2:] for y in counts])
        ax.set_xlabel("Event year · 2021–2025")
        ax.set_ylabel("Eligible records")
        ax.set_title(
            "Train / validation / later test",
            fontsize=10,
            loc="left",
            color=WHITE,
            pad=12,
        )
    elif kind == "survival":
        hours = [p["hour"] for p in mc["curve"]]
        ax.plot(
            hours,
            [100 * p["analytical"] for p in mc["curve"]],
            color=WHITE,
            label="Analytical",
            linewidth=2.2,
        )
        ax.step(
            hours,
            [100 * p["simulated"] for p in mc["curve"]],
            where="post",
            color=RED,
            label="Simulated",
            linestyle="--",
            linewidth=1.6,
        )
        ax.set_ylim(0, 105)
        ax.set_xlim(0, 162)
        ax.set_ylabel("Recorded event ongoing (%)")
        ax.set_xlabel("Remaining hours from replay as-of")
        ax.legend(frameon=False, labelcolor=WHITE, fontsize=10)
    elif kind == "duration-distribution":
        resolved = [v for v in mc["durations_hours"] if v is not None]
        ax.hist(resolved, bins=np.arange(0.5, 163, 6), color=RED, edgecolor="#15171b")
        for value in (2, 10, 73):
            ax.axvline(
                value, color=WHITE if value != 10 else RED, linestyle="--", linewidth=1
            )
        ax.set_xlim(0, 163)
        ax.set_xlabel("Resolution hour · six-hour bins")
        ax.set_ylabel("Resolved simulation draws")
        ax.set_title(
            "4,828 resolved; 172 unresolved at 162h",
            fontsize=10,
            color=WHITE,
            loc="left",
            pad=12,
        )
    elif kind == "sample-paths":
        for i, value in enumerate(mc["durations_hours"][:60], 1):
            ax.hlines(
                i,
                0,
                162 if value is None else value,
                color=RED,
                linewidth=1.8,
                alpha=0.7,
            )
            ax.plot(
                162 if value is None else value,
                i,
                marker=">" if value is None else "o",
                markersize=3,
                color=RED if value is None else WHITE,
            )
        ax.set_xlim(0, 165)
        ax.set_ylim(61, 0)
        ax.set_xlabel("Remaining hours · model boundary 162h")
        ax.set_ylabel("Draw index · first 60, in order")
    elif kind == "convergence":
        for ax, h in zip(axes, (6, 12, 24)):
            points = [p for p in mc["convergence"] if p["horizon_hours"] == h]
            x = [p["draws"] for p in points]
            ax.axhline(
                points[0]["analytical"], color=WHITE, linestyle="--", linewidth=1.2
            )
            ax.plot(x, [p["simulated"] for p in points], "o-", color=RED, markersize=4)
            ax.fill_between(
                x,
                [p["lower_95"] for p in points],
                [p["upper_95"] for p in points],
                color=RED,
                alpha=0.16,
            )
            ax.set_xscale("log")
            ax.set_xticks([100, 1000, 5000], ["100", "1K", "5K"])
            ax.set_ylim(0, 1)
            ax.set_xlabel("Nested simulation draws")
            ax.set_title(
                f"{h}h persistence · 95% Wilson",
                fontsize=10,
                color=WHITE,
                loc="left",
                pad=12,
            )
        axes[0].set_ylabel("Ongoing proportion")
    elif kind == "calibration":
        for ax, period, title in zip(
            axes, ("validation", "test"), ("2024 validation", "2025 inspected test")
        ):
            bins = data["categories"]["Flood"][period][method][f"{horizon}h"][
                "reliability"
            ]
            ax.plot(
                [0, 1],
                [0, 1],
                "--",
                color=WHITE,
                linewidth=1,
                label="Perfect calibration",
            )
            ax.scatter(
                [b["mean_predicted"] for b in bins],
                [b["observed_frequency"] for b in bins],
                s=[20 + 100 * b["count"] / max(b["count"] for b in bins) for b in bins],
                color=BLUE,
                edgecolors=WHITE,
                linewidths=0.6,
            )
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_xticks([0, 0.5, 1])
            ax.set_yticks([0, 0.5, 1])
            ax.set_xlabel("Mean predicted persistence")
            ax.set_ylabel("Recorded ongoing fraction")
            ax.set_title(
                f"{title} · {horizon}h", fontsize=10, color=WHITE, loc="left", pad=12
            )
    elif kind == "duration-errors":
        rows = heldout["rows"]
        actual = np.array([r["observed_remaining_hours"] for r in rows])
        predicted = np.array([r[method]["median"] for r in rows])
        errors = np.abs(actual - predicted)
        ax = axes[0]
        ax.scatter(
            actual,
            predicted,
            s=6,
            color=BLUE,
            alpha=0.23,
            edgecolors="none",
            rasterized=False,
        )
        bounds = [min(min(actual), min(predicted)), max(max(actual), max(predicted))]
        ax.plot(bounds, bounds, "--", color=RED, linewidth=1)
        if logarithmic:
            ax.set_xscale("log")
            ax.set_yscale("log")
        ax.set_xlabel("Recorded remaining hours")
        ax.set_ylabel("Predicted median hours")
        ax.set_title(
            "3,539 snapshots · 567 reporting episodes",
            fontsize=10,
            color=WHITE,
            loc="left",
            pad=12,
        )
        ax = axes[1]
        ax.hist(errors, bins=35, color=BLUE, edgecolor="#15171b")
        ax.set_yscale("log")
        ax.set_xlabel("Absolute duration error (hours)")
        ax.set_ylabel("Snapshots · log count")
        ax.set_title(
            f"MAE {errors.mean():.2f}h · max {errors.max():.1f}h",
            fontsize=10,
            color=WHITE,
            loc="left",
            pad=12,
        )
    else:
        raise ValueError(kind)
    if facets:
        fig.subplots_adjust(
            left=0.23 if mobile else 0.10,
            right=0.96,
            bottom=0.10 if mobile else 0.18,
            top=0.93,
            hspace=0.65,
            wspace=0.50,
        )
    else:
        fig.subplots_adjust(
            left=0.23 if mobile else 0.13, right=0.97, bottom=0.20, top=0.87
        )
    return save(fig)


def make_page(data, heldout, assets, provenance):
    old_data = json.loads((OUT / "evidence.json").read_text())
    old_assets = {
        p.name: p.read_bytes()
        for p in OUT.glob("*.svg")
        if p.name in {r["file"] for r in old_data["figures"]}
    }
    legacy = OLD["section"](old_data, old_assets).replace(
        "No raw trial paths are shown.",
        "Sampled event-end timelines and all draws are provided below.",
    )

    def chunk(start, end):
        return legacy[legacy.index(start) : legacy.index(end, legacy.index(start))]

    source_cards = chunk('    <div class="lab-sources"', '    <div class="lab-methods"')
    models = chunk('    <section class="lab-models"', '    <div class="lab-charts"')
    original_data = re.search(
        r'<figure class="lab-chart" aria-labelledby="lab-data-title">[\s\S]*?</figure>',
        legacy,
    ).group()
    original_back = re.search(
        r'<figure class="lab-chart" aria-labelledby="lab-backtest-title">[\s\S]*?</figure>',
        legacy,
    ).group()
    original_mc = chunk(
        '      <div class="lab-chart lab-monte"',
        '      <figure class="lab-chart" aria-labelledby="lab-backtest-title">',
    )
    limits = chunk('    <section class="lab-limitations"', '    <div class="lab-trust"')
    trust = chunk('    <div class="lab-trust"', "  </section>")
    mc = data["monte_carlo_lab"]

    def table(headers, rows):
        return (
            '<div class="data-table-wrap"><table><thead><tr>'
            + "".join(f'<th scope="col">{h}</th>' for h in headers)
            + "</tr></thead><tbody>"
            + "".join(
                "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>" for row in rows
            )
            + "</tbody></table></div>"
        )

    def picture(name, alt):
        desktop = f"{name}.svg"
        mobile = f"{name}-mobile.svg"
        return f'<picture><source media="(max-width:600px)" srcset="/research/{mobile}?v={hash_bytes(assets[mobile])[:10]}"><img data-advanced-figure="{name}" src="/research/{desktop}?v={hash_bytes(assets[desktop])[:10]}" alt="{alt}" loading="lazy" decoding="async"></picture>'

    def card(name, title, copy_text, caption, rows, headers, controls="", full=False):
        prov = provenance[name]
        return f'<figure class="lab-chart advanced-figure {"data-wide" if full else ""}" id="figure-{name}" aria-labelledby="title-{name}"><p class="lab-eyebrow">{prov["kind"]}</p><h3 id="title-{name}">{title}</h3><p>{copy_text}</p>{controls}{picture(name, title)}<figcaption>{caption}<details class="lab-values"><summary>Values, provenance and downloads</summary>{table(headers, rows)}<p>Source: <a href="https://github.com/BraydinPG/planit-control-swamphacks/blob/main/{prov["source"]}">{prov["source"]}</a>. {prov["cohort"]}. <a href="/research/dashboard-figures.json">Figure ledger</a> · <a href="/research/dashboard.json">Exact research data</a>.</p></details></figcaption></figure>'

    cohort = card(
        "cohort",
        "From recorded rows to eligible cohorts.",
        "Flood records are filtered and whole reporting episodes stay together across chronological periods.",
        "11,571 Flood rows → 10,322 valid intervals → 10,310 after purging 12 boundary-crossing records. Year bars describe eligible Flood intervals, not every NOAA category.",
        [
            ["Flood rows", 11571],
            ["Malformed excluded", 1249],
            ["Boundary records purged", 12],
            ["Final eligible intervals", 10310],
        ],
        ["Stage", "Records"],
    )
    curve = card(
        "survival",
        "A full conditional survival curve.",
        "Analytical logistic-model survival and empirical survival from the same seeded draws, across all 162 supported remaining hours.",
        "Synthetic replay at age 6h; total modeled age limit 168h. No comparable observed cohort is overlaid. Unresolved tail remains unknown beyond the boundary.",
        [
            [p["hour"], f"{p['analytical']:.6f}", f"{p['simulated']:.6f}"]
            for p in mc["curve"]
        ],
        ["Remaining h", "Analytical", "MC ongoing"],
        full=True,
    )
    histogram = card(
        "duration-distribution",
        "Resolution times, including the unresolved tail.",
        "A histogram of actual regenerated integer event-end draws. Unresolved draws stay in the quantile denominator.",
        "4,828 resolved samples; 172 remain unresolved at 162h. Maximum resolved within modeled horizon is 162h; the true maximum possible duration is unknown.",
        [
            ["Minimum resolved", mc["minimum_resolved_hours"]],
            ["10th percentile", 2],
            ["Median", 10],
            ["90th percentile", 73],
            ["Max resolved within horizon", 162],
            ["Unresolved at 162h", 172],
        ],
        ["Statistic", "Hours / count"],
    )
    raster = card(
        "sample-paths",
        "Sixty real seeded sample timelines.",
        "Each row is one model-implied event-end draw: a red line while ongoing, a white dot at resolution, or an arrow for unresolved at the finite boundary.",
        "First 60 draws in original seed order, without outcome selection. These are persistence paths, not wind, temperature, flood-depth or physical storm trajectories.",
        [
            [i, "Unresolved >162h" if value is None else value]
            for i, value in enumerate(mc["durations_hours"][:60], 1)
        ],
        ["Draw", "Resolution h"],
    )
    convergence = card(
        "convergence",
        "Watch sampling estimates stabilize.",
        "Nested prefixes of 100, 500, 1,000, 2,500 and 5,000 draws share one seed. White lines mark analytical probabilities; red bands show 95% Wilson intervals.",
        "Bands describe Monte Carlo binomial sampling only. Prefixes are dependent; convergence need not be monotonic. They exclude parameter uncertainty and real-world forecast error.",
        [
            [
                p["draws"],
                p["horizon_hours"],
                f"{p['simulated']:.5f}",
                f"{p['lower_95']:.5f}–{p['upper_95']:.5f}",
            ]
            for p in mc["convergence"]
        ],
        ["Draws", "Horizon h", "MC ongoing", "95% Wilson"],
        full=True,
    )
    later = card(
        "brier-test",
        "A later period can favor the other model.",
        "Logistic has lower Brier error than KM at all three 2025 horizons. This does not reverse the validation-based selection or establish stable operational superiority.",
        "Fitted through 2024; 3,539 snapshots / 567 reporting episodes. 2025 was previously inspected, not a fresh untouched holdout. Whiskers: saved 95% episode-bootstrap intervals.",
        [
            [
                f"{h}h",
                f"{data['categories']['Flood']['test']['kaplan_meier'][f'{h}h']['brier_score']:.6f}",
                f"{data['categories']['Flood']['test']['logistic'][f'{h}h']['brier_score']:.6f}",
            ]
            for h in (6, 12, 24)
        ],
        ["Horizon", "KM Brier", "Logistic Brier"],
    )
    calibration_controls = '<div class="research-controls"><label>Flood comparison model<select id="calibration-model"><option value="kaplan_meier">Kaplan–Meier</option><option value="logistic">Logistic comparison</option></select></label><label>Horizon<select id="calibration-horizon"><option>6</option><option>12</option><option selected>24</option></select></label></div><p id="calibration-context" aria-live="polite">Kaplan–Meier · 24h · separate 2024 and inspected 2025 cohorts</p><div id="calibration-table"></div>'
    calibration_rows = [
        [
            period,
            b["count"],
            f"{b['mean_predicted']:.6f}",
            f"{b['observed_frequency']:.6f}",
        ]
        for period in ("validation", "test")
        for b in data["categories"]["Flood"][period]["kaplan_meier"]["24h"][
            "reliability"
        ]
    ]
    calibration = card(
        "calibration",
        "Predictions against recorded outcomes.",
        "Probability bins compare average predicted persistence with the actual fraction of recorded events that continued. Each period is shown separately.",
        "Diagonal = perfect calibration. Marker size scales with bin count, not certainty. No independent-snapshot confidence bands are invented; observations share reporting episodes. Controls only select saved results.",
        calibration_rows,
        ["Period", "Snapshots", "Mean predicted", "Recorded ongoing"],
        calibration_controls,
        True,
    )
    duration_controls = '<div class="research-controls"><label>Duration estimator<select id="duration-model"><option value="kaplan_meier">Kaplan–Meier</option><option value="logistic">Logistic comparison</option></select></label><label>Scatter axes<select id="duration-scale"><option value="log" selected>Logarithmic hours</option><option value="linear">Linear hours</option></select></label></div><p id="duration-context" aria-live="polite">All 3,539 inspected 2025 snapshots · no refitting</p>'
    duration_rows = [
        [
            m,
            f"{s['mean_absolute_error_hours']:.3f}",
            s["prediction_min_hours"],
            s["prediction_max_hours"],
            s["unidentified_intervals"],
        ]
        for m, s in heldout["verified_metrics"].items()
    ]
    duration = card(
        "duration-errors",
        "Actual remaining time versus predicted duration.",
        "Every inspected 2025 Flood snapshot is rescored using the approved fitted artifact. All six horizon Brier values and both duration MAEs reproduce the saved report.",
        f'Recorded remaining duration ranges from {heldout["observed_min_hours"]:.4f}h to {heldout["observed_max_hours"]:.2f}h. The diagonal marks exact agreement; error-bin counts use a log axis. Unidentified interval bounds remain null. Repeated snapshots are not independent disasters. <a href="/research/flood-holdout.csv">Download all snapshot predictions and recorded endpoints (CSV)</a>.',
        duration_rows,
        ["Estimator", "MAE h", "Min median h", "Max median h", "Unknown intervals"],
        duration_controls,
        True,
    )
    multi_rows = []
    for c in data["categories"].values():
        m = c["selected_estimator"]
        first = c["test"][m][f"{c['horizons'][0]}h"]
        multi_rows.append(
            [
                c["name"],
                f"{c['training']['records']:,} / {c['training']['groups']:,}",
                f"{first['snapshot_count']:,} / {first['episode_count']:,}",
                m,
                ", ".join(
                    f"{h}h: {c['test'][m][f'{h}h']['brier_score']:.4f}"
                    for h in c["horizons"]
                ),
            ]
        )
    event_options = "".join(f"<option>{name}</option>" for name in data["categories"])
    multi_controls = f'<div class="research-controls"><label>Research target<select id="research-event">{event_options}</select></label><label>Supported horizon<select id="research-horizon"><option>6</option><option>12</option><option>24</option></select></label><label>Period<select id="research-period"><option value="test">2025 retrospective</option><option value="validation">2024 validation</option></select></label></div><div id="research-readout" class="research-readout" aria-live="polite">Select a target and its supported horizon to inspect saved metrics.</div><details class="lab-values"><summary>Selected target methods and limitations</summary><ul id="research-target-limits"><li>Target-specific research limits accompany each saved result; full limits are in the downloadable dashboard data.</li></ul></details>'
    multi = card(
        "multi-disaster",
        "Separate targets. Separate evidence.",
        "Six retrospectively evaluated duration targets use their own event definitions, valid horizons and reporting cohorts. Panels show each selected estimator with 95% group-bootstrap Brier intervals.",
        'Raw Brier errors are not a cross-disaster ranking: prevalences, horizons and populations differ. Heat research is restricted to evaluated stations. Controls cannot enable rejected models or trigger inference. <a href="/research/backtest-comparison.csv">Download every model/horizon comparison (CSV)</a>.',
        multi_rows,
        [
            "Target",
            "Train records / groups",
            "Test snapshots / groups",
            "Selected",
            "Test Brier by horizon",
        ],
        multi_controls,
        True,
    )
    disabled = "".join(
        f"<article><h4>{item['name']}</h4><p>Not qualified: {', '.join(r.replace('_', ' ') for r in item['reasons'])}.</p></article>"
        for item in data["disabled_targets"]
    )
    bench = data["benchmark"]
    benchmark_table = table(
        ["Workers", "Elapsed s", "Snapshots / s", "Peak RSS MB"],
        [
            [
                r["workers"],
                f"{r['elapsed_seconds']:.4f}",
                f"{r['snapshots_per_second']:.2f}",
                f"{r['process_tree_peak_rss_mb']:.1f}",
            ]
            for r in bench["worker_benchmarks"]
        ],
    )
    overview = legacy[
        legacy.index('    <div class="lab-heading">') : legacy.index(
            '    <div class="lab-sources"'
        )
    ]
    heading = lambda ident, kicker, title, copy_text: (
        f'<header class="research-chapter" id="{ident}"><p class="lab-eyebrow">{kicker}</p><h2>{title}</h2><p>{copy_text}</p></header>'
    )
    return "\n".join(
        [
            OLD["START"],
            '<section class="lab dashboard" data-research-dashboard aria-labelledby="data-title">',
            overview,
            '<nav class="research-index" aria-label="Data page sections"><a href="#historical-data">Historical data</a><a href="#statistical-models">Models</a><a href="#monte-carlo-lab">Monte Carlo</a><a href="#historical-backtesting">Backtesting</a><a href="#multi-disaster">Multi-disaster</a><a href="#research-evidence">Evidence</a></nav>',
            heading(
                "historical-data",
                "01 / HISTORICAL DATA",
                "A traceable foundation.",
                "Official source inventories remain distinct from eligible model cohorts, independent disasters and verified work orders.",
            ),
            source_cards,
            '<div class="lab-charts">' + original_data + cohort + "</div>",
            '<div id="statistical-models">' + models + "</div>",
            heading(
                "monte-carlo-lab",
                "02 / OFFLINE RESEARCH",
                "MONTE CARLO SIMULATION LAB",
                "Thousands of simulated event trajectories. One probabilistic model. A measurable range of possible outcomes.",
            ),
            '<p class="research-chapter-note">Synthetic Flood replay · age 6h · September · seed 42 · logistic research comparison. A trajectory means a sampled recorded-event end time, not physical storm motion or intensity.</p>',
            '<div class="lab-charts">'
            + original_mc
            + curve
            + histogram
            + raster
            + convergence
            + "</div>",
            '<p class="research-downloads"><a href="/research/monte-carlo-draws.csv">Download all 5,000 genuine seeded draws (CSV)</a> · Minimum 1h · p10 2h · median 10h · p90 73h · maximum resolved within 162h: 162h · unresolved: 172. True upper tail remains unknown.</p>',
            heading(
                "historical-backtesting",
                "03 / CHRONOLOGICAL EVALUATION",
                "BACKTESTED AGAINST HISTORY",
                "Simulation consistency is a different question from prediction skill. Recorded historical endpoints provide the comparison below; no worksite reopening or worker outcome is inferred.",
            ),
            '<div class="lab-charts">'
            + original_back
            + later
            + calibration
            + duration
            + "</div>",
            heading(
                "multi-disaster",
                "04 / TARGET-SPECIFIC EVIDENCE",
                "ONE FRAMEWORK. MULTIPLE DISASTER TYPES.",
                "Each category retains its own support, estimator, horizon and limitations. Research eligibility does not establish operational validation.",
            ),
            '<div class="lab-charts">' + multi + "</div>",
            '<section class="research-disabled"><h3>Evaluation includes saying no.</h3><p>Strong Wind, Ice Storm and Heavy Snow did not pass the predetermined research criteria.</p><div class="lab-model-grid">'
            + disabled
            + '</div><p>The separate North Atlantic hurricane experiment predicts 24-hour maximum-wind-change classes from post-analysis tracks. It is not a duration model, a live operational forecast or local worksite wind. <a href="https://github.com/BraydinPG/planit-control-swamphacks/blob/main/ml/reports/multidisaster/hurricane_trend.json">Read the separate experiment</a>.</p></section>',
            '<section class="research-performance"><p class="lab-eyebrow">ARCHIVED ENGINEERING BENCHMARK</p><h3>Measure the pipeline. Keep the context.</h3><p>161 bounded snapshots; 1 / 4 / 8 / 12 workers, with matched outputs. One worker was retained. Concurrent short jobs affected timings; this is not live-feed latency or a full-backtest speedup.</p>'
            + benchmark_table
            + f'<p>Saved parsing/normalization: {bench["stage_timings_seconds"]["noaa_parse_and_normalization"]:.3f}s. Cached feature attachment: {bench["stage_timings_seconds"]["cached_weather_feature_attachment"]["elapsed_seconds"]:.4f}s for 100 events, zero network calls. <a href="https://github.com/BraydinPG/planit-control-swamphacks/blob/main/ml/reports/purged_v2/benchmark.json">Original benchmark and caveats</a>.</p></section>',
            '<div id="research-evidence">' + limits + "</div>",
            trust,
            '<p class="research-downloads"><a href="/research/dashboard.json">Download the complete precomputed dashboard data</a> · <a href="/research/dashboard-figures.json">Figure provenance ledger</a>. Controls select saved data only; no training or simulations run in this browser.</p>',
            '<p role="status" id="research-controls-status" class="research-controls-status">Static figures, tables and sources are available without interactive controls.</p>',
            "</section>",
            OLD["END"],
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads((OUT / "dashboard.json").read_text())
    heldout = json.loads((OUT / "flood-holdout.json").read_text())
    specs = {
        "cohort": (
            "Historical records and filtering",
            "ml/reports/purged_v2/backtest_metrics.json",
            "2021–2025 Flood intervals",
        ),
        "survival": (
            "Analytical and sampled survival",
            "ml/reports/purged_v2/monte_carlo_summary.json",
            "Synthetic Flood replay, seed 42, 5000 draws",
        ),
        "duration-distribution": (
            "Actual regenerated MC duration draws",
            "ml/monte_carlo.py",
            "5000 seeded draws; unresolved included in quantile denominator",
        ),
        "sample-paths": (
            "First 60 sampled event-end timelines",
            "ml/monte_carlo.py",
            "First 60 of the same 5000 draws, no outcome selection",
        ),
        "convergence": (
            "Nested-prefix sampling estimates",
            "ml/monte_carlo.py",
            "N=100/500/1000/2500/5000, 95% Wilson MC intervals",
        ),
        "brier-test": (
            "Inspected 2025 evaluation",
            "ml/reports/purged_v2/backtest_metrics.json",
            "3539 snapshots, 567 reporting episodes; trained through 2024",
        ),
        "calibration": (
            "Predicted versus recorded outcomes",
            "ml/reports/purged_v2/backtest_metrics.json",
            "Separate 2024 validation and 2025 inspected test bins",
        ),
        "duration-errors": (
            "All-snapshot recorded-duration comparison",
            "ml/backtest.py",
            "3539 inspected 2025 snapshots; fixed approved artifact, no refit",
        ),
        "multi-disaster": (
            "Six distinct retrospective targets",
            "ml/reports/multidisaster/registry.json",
            "Category-specific 2025 evaluation; no cross-target ranking",
        ),
    }
    provenance = {
        name: {
            "kind": v[0],
            "source": v[1],
            "cohort": v[2],
            "data_kind": "offline_research",
            "model_version": data["monte_carlo_lab"]["model_version"]
            if name not in ("cohort", "multi-disaster")
            else "see target-specific source",
            "constraints": "No operational validation or work authorization; full data/sources in dashboard.json",
        }
        for name, v in specs.items()
    }
    for name in ("survival", "duration-distribution", "sample-paths", "convergence"):
        provenance[name].update(
            sample_size=5000,
            displayed_draws=60 if name == "sample-paths" else 5000,
            seed=42,
            event_age_hours=6,
            remaining_model_horizon_hours=162,
            modeled_total_age_limit_hours=168,
            data_kind="fitted_probabilities_and_seeded_monte_carlo_draws",
            censoring="172 draws unresolved at 162h; true maximum unknown",
            artifact_sha256=data["monte_carlo_lab"]["artifact_sha256"],
        )
    provenance["cohort"].update(
        model_version=None,
        sample_size=10310,
        prediction_horizons_hours=None,
        data_kind="historical_record_and_split_counts",
    )
    for name in ("brier-test", "calibration", "duration-errors"):
        provenance[name].update(
            model_version="KM baseline and logistic comparison from noaa-flood-pooled-logistic-v2 artifact",
            prediction_horizons_hours=[6, 12, 24],
            test_snapshots=3539,
            test_reporting_episodes=567,
            data_kind="fitted_predictions_compared_with_recorded_historical_endpoints",
            artifact_sha256=heldout["artifact_sha256"],
            censoring="Unidentified duration bounds remain null; repeated snapshots are dependent",
        )
    provenance["calibration"].update(
        validation_snapshots=4053, validation_reporting_episodes=583
    )
    provenance["multi-disaster"]["targets"] = [
        {
            "name": c["name"],
            "source": c["report"],
            "artifact_version": c["model_version"],
            "selected_estimator": c["selected_estimator"],
            "horizons_hours": c["horizons"],
            "sample_support": c["training"],
            "test_snapshots": c["test"][c["selected_estimator"]][
                f"{c['horizons'][0]}h"
            ]["snapshot_count"],
            "test_groups": c["test"][c["selected_estimator"]][f"{c['horizons'][0]}h"][
                "episode_count"
            ],
        }
        for c in data["categories"].values()
    ]
    assets = {}
    for name in specs:
        for mobile in (False, True):
            assets[f"{name}{'-mobile' if mobile else ''}.svg"] = render(
                name, data, heldout, mobile
            )
    for method in ("kaplan_meier", "logistic"):
        for horizon in (6, 12, 24):
            for mobile in (False, True):
                assets[
                    f"calibration-{method}-{horizon}{'-mobile' if mobile else ''}.svg"
                ] = render("calibration", data, heldout, mobile, method, horizon)
    for method in ("kaplan_meier", "logistic"):
        for log in (False, True):
            for mobile in (False, True):
                assets[
                    f"duration-errors-{method}-{'log' if log else 'linear'}{'-mobile' if mobile else ''}.svg"
                ] = render("duration-errors", data, heldout, mobile, method, 24, log)
    manifest = {
        "schema_version": "dashboard-figures-1",
        "visible_figures": 12,
        "original_figures_unchanged": ["monte-carlo", "backtest", "data-sources"],
        "dashboard_sha256": hash_bytes((OUT / "dashboard.json").read_bytes()),
        "holdout_sha256": hash_bytes((OUT / "flood-holdout.json").read_bytes()),
        "source_hashes": data["sources"],
        "figures": [
            {"file": name, "sha256": hash_bytes(value)}
            for name, value in assets.items()
        ],
        "provenance": provenance,
        "matplotlib": matplotlib.__version__,
    }
    page = PUBLIC / "data.html"
    original = page.read_text(encoding="utf-8")
    start, rest = original.split(OLD["START"], 1)
    _, end = rest.split(OLD["END"], 1)
    updated = start + make_page(data, heldout, assets, provenance) + end
    assets["dashboard-figures.json"] = (
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    ).encode()
    for name, content in assets.items():
        path = OUT / name
        if args.check:
            if not path.exists() or path.read_bytes() != content:
                raise SystemExit("Figure mismatch: " + name)
        elif not path.exists() or path.read_bytes() != content:
            path.write_bytes(content)
    if args.check:
        if updated != original:
            raise SystemExit("Generated Data HTML differs")
    else:
        page.write_text(updated, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "checked": args.check,
                "visible_figures": 12,
                "responsive_figure_assets": len(assets) - 1,
                "original_charts_changed": False,
                "model_fit_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
