"""Figures and a bounded interpretation derived only from run tables."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def build_report(
    output: Path, annual: pd.DataFrame, summary: pd.DataFrame, planner_annual: pd.DataFrame
) -> None:
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    colors = {"energy_only": "#276a9f", "stylised_capacity_payment": "#b25825"}
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), layout="constrained")
    capacities = [
        c for c in annual if isinstance(c, str) and c.startswith("capacity_") and c.endswith("_mw")
    ]
    for name, group in annual.groupby("design"):
        label = str(name).replace("_", " ")
        by_year = group.groupby("year")
        for ax, column, scale, title in [
            (axes[0, 0], "mean_price_gbp_per_mwh", 1, "Annual weighted mean price (GBP/MWh)"),
            (axes[0, 1], "unserved_mwh", 1e6, "Weighted unserved energy (TWh)"),
        ]:
            stats = by_year[column]
            mean = stats.mean() / scale
            ax.plot(mean.index, mean, label=label, color=colors[str(name)])
            ax.fill_between(
                mean.index,
                stats.quantile(0.1) / scale,
                stats.quantile(0.9) / scale,
                alpha=0.18,
                color=colors[str(name)],
            )
            ax.set_title(title)
            ax.set_xlabel("Year")
        totals = (
            group.assign(total_capacity=group[capacities].sum(axis=1))
            .groupby("year")
            .total_capacity.mean()
        )
        axes[1, 0].plot(totals.index, totals / 1000, label=label, color=colors[str(name)])
    axes[1, 0].plot(
        planner_annual.year,
        planner_annual[capacities].sum(axis=1) / 1000,
        color="#344b3b",
        linestyle="--",
        label="perfect-foresight planner",
    )
    axes[1, 0].set(title="Installed generation (GW)", xlabel="Year")
    costs = summary.groupby("design").resource_npv_gbp
    means = costs.mean() / 1e9
    axes[1, 1].bar(range(len(means)), means, color=[colors[k] for k in means.index])
    axes[1, 1].set_xticks(range(len(means)), ["Energy only", "Stylised payment"])
    axes[1, 1].set_title("Discounted resource cost (billion GBP)")
    axes[1, 1].axhline(
        summary.planner_npv_gbp.iloc[0] / 1e9, color="#344b3b", linestyle="--", label="planner"
    )
    for ax in axes.flat:
        ax.grid(axis="y", alpha=0.2)
    axes[0, 0].legend(fontsize=8)
    axes[1, 0].legend(fontsize=8)
    fig.suptitle(
        "GB-FLEXABM | Synthetic scarcity-stress experiment, NOT a GB forecast", fontsize=13
    )
    fig.savefig(output / "comparison.png", dpi=155)
    plt.close(fig)
    paired = summary.pivot(index="seed", columns="design", values="resource_npv_gbp")
    difference = paired["stylised_capacity_payment"] - paired["energy_only"]
    lines = [
        "# Synthetic market-design experiment",
        "",
        "Scientific status: exploratory, uncalibrated; not a forecast or a welfare estimate for Great Britain.",
        "",
        f"Paired seeds: {len(paired)}. Shading in the figure is the empirical 10th–90th percentile across these seeds, not a calibrated prediction interval.",
        "",
        f"Mean resource-NPV difference (stylised payment minus energy-only): {difference.mean():,.0f} GBP.",
        f"Empirical difference range: {difference.min():,.0f} to {difference.max():,.0f} GBP.",
        "",
        "The initial fleet deliberately creates scarcity. High prices and unserved energy are properties of this synthetic stress fixture, not estimates of observed GB conditions.",
        "",
        "Capacity payments are investor/consumer transfers and excluded from the resource-cost objective. The planner has perfect foresight and continuous investment; the ABM has bounded expectations, finance budgets and pro-rata project rationing. The gap is conditional on those differences, not a general estimate of market inefficiency.",
        "",
        "Storage is fixed exogenously and cyclic within one repeated chronological block. Scarcity hours are deterministic weighted hours, not Monte Carlo LOLE. No official Capacity Market auction, CfD, heat or hydrogen behaviour is represented.",
        "",
        "## Evidence",
        "",
        "- `summary.csv`: paired system costs and verification gap.",
        "- `annual.csv`: capacities, weighted energy, prices, emissions and transfers.",
        "- `decisions.csv`, `settlements.csv`, `assets.csv`: investment/vintage/accounting trace.",
        "- `planner_annual.csv`, `planner_builds.csv`: normative benchmark.",
        "- `dispatch_reference.csv`: first-year shared physical reference.",
        "- `manifest.json`: code, dependency, config, seed and output hashes.",
        "",
        "![Synthetic experiment](comparison.png)",
        "",
    ]
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")
