#!/usr/bin/env python3
"""Evaluate the one-page checkout A/B test (2026-03-02 to 2026-04-26).

1. Sample ratio mismatch (SRM): did the planned 50/50 split hold? Checked
   before and after removing bot sessions, because bots can break the split.
2. Checkout conversion by group, overall and per device: two-proportion
   z-test and a 95% confidence interval for the difference.

The statistics use only the standard library (math.erfc), so no SciPy.
Run after src/run_pipeline.py:
    python src/ab_test.py
"""
from __future__ import annotations

import math
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "kaarobar.duckdb"
OUT_DIR = ROOT / "outputs"
IMG_DIR = ROOT / "images"

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "axes.spines.top": False, "axes.spines.right": False})


def normal_sf(z: float) -> float:
    """P(Z > z) for a standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def srm_test(n_control: int, n_treatment: int) -> tuple[float, float]:
    """Chi-square goodness-of-fit against a 50/50 split (1 degree of freedom)."""
    expected = (n_control + n_treatment) / 2
    chi2 = ((n_control - expected) ** 2 + (n_treatment - expected) ** 2) / expected
    return chi2, math.erfc(math.sqrt(chi2 / 2))


def two_proportion_test(x_c: int, n_c: int, x_t: int, n_t: int) -> dict:
    p_c, p_t = x_c / n_c, x_t / n_t
    pooled = (x_c + x_t) / (n_c + n_t)
    z = (p_t - p_c) / math.sqrt(pooled * (1 - pooled) * (1 / n_c + 1 / n_t))
    se_diff = math.sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    diff = p_t - p_c
    return {"control_rate_pct": 100 * p_c, "treatment_rate_pct": 100 * p_t,
            "lift_pts": 100 * diff, "ci_low_pts": 100 * (diff - 1.96 * se_diff),
            "ci_high_pts": 100 * (diff + 1.96 * se_diff), "z": z, "p_value": 2 * normal_sf(abs(z))}


def main() -> None:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    ab = con.execute("SELECT * FROM mart.v_ab_test").df()
    con.close()

    print("=== Sample ratio check (planned 50/50) ===")
    for label, data in (("all sessions, bots included", ab), ("bots removed", ab[~ab.is_bot])):
        n = data.groupby("experiment_group").sessions.sum()
        chi2, p = srm_test(int(n["control"]), int(n["treatment"]))
        verdict = "split is broken, investigate" if p < 0.001 else "split holds"
        print(f"{label:30s} control {int(n['control']):>6,}  treatment {int(n['treatment']):>6,}  "
              f"chi2 {chi2:7.2f}  p {p:.2g}  -> {verdict}")

    rows = []
    human = ab[~ab.is_bot]
    segments = [("All devices", human)] + [(d, human[human.device_type == d]) for d in ("Android", "iOS", "Desktop")]
    segments.append(("All devices, bots included", ab))
    for name, data in segments:
        g = data.groupby("experiment_group")[["sessions", "orders"]].sum()
        r = two_proportion_test(int(g.loc["control", "orders"]), int(g.loc["control", "sessions"]),
                                int(g.loc["treatment", "orders"]), int(g.loc["treatment", "sessions"]))
        rows.append({"segment": name, "control_sessions": int(g.loc["control", "sessions"]),
                     "treatment_sessions": int(g.loc["treatment", "sessions"]), **r})
    results = pd.DataFrame(rows)
    results.to_csv(OUT_DIR / "ab_test_results.csv", index=False)

    print("\n=== Checkout conversion, treatment minus control ===")
    show = results.copy()
    for col in ("control_rate_pct", "treatment_rate_pct", "lift_pts", "ci_low_pts", "ci_high_pts", "z"):
        show[col] = show[col].round(2)
    show["p_value"] = show["p_value"].map(lambda p: f"{p:.2g}")
    print(show.to_string(index=False))

    # chart: conversion by device with the 95% CI of the lift
    plot = results[results.segment.isin(["Android", "iOS", "Desktop", "All devices"])].set_index("segment")
    plot = plot.loc[["Android", "iOS", "Desktop", "All devices"]]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = range(len(plot))
    ax.errorbar(plot.lift_pts, y, xerr=[plot.lift_pts - plot.ci_low_pts, plot.ci_high_pts - plot.lift_pts],
                fmt="o", color="#2E86AB", ecolor="#2E86AB", capsize=5, markersize=8, linewidth=2)
    ax.axvline(0, color="#5C6B73", linewidth=1, linestyle="--")
    for i, (seg, r) in enumerate(plot.iterrows()):
        ax.annotate(f"{r.lift_pts:+.1f} pts  ({r.control_rate_pct:.1f}% to {r.treatment_rate_pct:.1f}%)",
                    (r.ci_high_pts, i), xytext=(8, 0), textcoords="offset points", va="center", fontsize=9)
    ax.set_yticks(list(y), plot.index)
    ax.invert_yaxis()
    ax.set_xlabel("Change in checkout conversion, percentage points (95% CI)")
    ax.set_title("The one-page checkout lifted mobile conversion; desktop did not change")
    ax.set_xlim(min(-1.5, plot.ci_low_pts.min() - 0.5), plot.ci_high_pts.max() + 6)
    fig.text(0.01, 0.01, "Synthetic data. Bot sessions (under 3 seconds) removed.", fontsize=8, color="#5C6B73")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(IMG_DIR / "11_ab_test.png", dpi=150)
    print("\nsaved images/11_ab_test.png and outputs/ab_test_results.csv")


if __name__ == "__main__":
    main()
