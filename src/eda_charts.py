#!/usr/bin/env python3
"""Exploratory charts for the Kaarobar analysis.

Reads the analysis views built by src/run_pipeline.py and saves one PNG per
question to images/. Chart titles state the finding, and every number in a
title is computed from the data, so titles stay true if the data changes.

Run after src/run_pipeline.py:
    python src/eda_charts.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from generate_data import EID_FITR, MEGA_SALES, RAMADAN  # noqa: E402  (public calendar, used for annotations)

DB_PATH = ROOT / "kaarobar.duckdb"
IMG_DIR = ROOT / "images"
COD, PREPAID, NEUTRAL, ACCENT, LIGHT = "#C8553D", "#2E86AB", "#5C6B73", "#F28F3B", "#D9DEE2"
FOOTNOTE = "Synthetic data: Kaarobar is a fictional marketplace."

sns.set_theme(style="whitegrid", context="notebook")
plt.rcParams.update({"axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 110})


def query(con, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def save(fig, name: str) -> None:
    fig.text(0.01, 0.005, FOOTNOTE, fontsize=8, color=NEUTRAL)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(IMG_DIR / name, dpi=150)
    plt.close(fig)
    print(f"saved images/{name}")


def monthly_revenue(con):
    m = query(con, "SELECT order_month, orders, net_revenue FROM mart.v_monthly_kpis ORDER BY order_month")
    m["order_month"] = pd.to_datetime(m.order_month)
    first, last = m.iloc[0], m.iloc[-1]
    growth = last.net_revenue / first.net_revenue
    fig, ax = plt.subplots(figsize=(11, 5))
    colors = [ACCENT if d.month == 11 else PREPAID for d in m.order_month]
    ax.bar(m.order_month, m.net_revenue / 1e6, width=25, color=colors)
    ax.set_ylabel("Net revenue, PKR million")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_title(f"Monthly net revenue grew {growth:.1f}x from {first.order_month:%b %Y} to {last.order_month:%b %Y}; "
                 "every November (11.11, White Friday) is a peak")
    save(fig, "01_monthly_revenue.png")


def daily_orders(con):
    d = query(con, "SELECT order_date, orders FROM mart.v_daily_orders ORDER BY order_date")
    d["order_date"] = pd.to_datetime(d.order_date)
    d["avg_7d"] = d.orders.rolling(7, center=True).mean()
    fig, ax = plt.subplots(figsize=(12, 5))
    for start, end in RAMADAN:
        ax.axvspan(pd.Timestamp(start), pd.Timestamp(end), color=LIGHT, alpha=0.8, lw=0)
    ax.plot(d.order_date, d.orders, color=PREPAID, lw=0.7, alpha=0.6, label="Daily orders")
    ax.plot(d.order_date, d.avg_7d, color=NEUTRAL, lw=1.6, label="7-day average")
    peak = d.loc[d.orders.idxmax()]
    for date, (name, _, _) in MEGA_SALES.items():
        if "11.11" in name:
            row = d[d.order_date == pd.Timestamp(date)].iloc[0]
            ax.annotate(f"{name}\n{int(row.orders)} orders", (row.order_date, row.orders),
                        xytext=(-95, -5), textcoords="offset points", fontsize=8,
                        arrowprops={"arrowstyle": "-", "color": NEUTRAL})
    for date in EID_FITR:
        ax.axvline(pd.Timestamp(date), color=COD, lw=1, ls=":")
    ax.set_ylabel("Orders per day")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(loc="upper left", frameon=False)
    ax.set_title(f"The busiest day ({peak.order_date:%d %b %Y}) had {peak.orders / d.avg_7d.median():.0f}x a typical day's orders; "
                 "Ramadan shaded, Eid ul Fitr dotted")
    save(fig, "02_daily_orders.png")


def payment_mix(con):
    p = query(con, "SELECT order_month, payment_method, share_pct FROM mart.v_payment_mix")
    p["order_month"] = pd.to_datetime(p.order_month)
    wide = p.pivot(index="order_month", columns="payment_method", values="share_pct").fillna(0)
    wide = wide[["Cash on Delivery", "Mobile Wallet", "Card"]]
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.stackplot(wide.index, wide.T.values, labels=wide.columns, colors=[COD, ACCENT, PREPAID], alpha=0.9)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(0, 100)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.legend(loc="lower left", frameon=True)
    cod0, cod1 = wide["Cash on Delivery"].iloc[0], wide["Cash on Delivery"].iloc[-1]
    w0, w1 = wide["Mobile Wallet"].iloc[0], wide["Mobile Wallet"].iloc[-1]
    ax.set_title(f"Cash on delivery fell from {cod0:.0f}% to {cod1:.0f}% of orders as mobile wallets rose from {w0:.0f}% to {w1:.0f}%")
    save(fig, "03_payment_mix.png")


def rto_drivers(con):
    r = query(con, "SELECT * FROM mart.v_rto_drivers")
    r["segment"] = r.customer_type + "\n" + r.order_value_band
    order = ["First order\nAbove PKR 15,000", "First order\nPKR 15,000 or less",
             "Repeat order\nAbove PKR 15,000", "Repeat order\nPKR 15,000 or less"]
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=r, x="segment", y="rto_rate_pct", hue="payment_group", order=order, hue_order=["COD", "Prepaid"],
                palette={"COD": COD, "Prepaid": PREPAID}, ax=ax)
    for c in ax.containers:
        ax.bar_label(c, fmt="%.1f%%", fontsize=9)
    ax.set_xlabel("")
    ax.set_ylabel("Parcels refused at the door (RTO), %")
    ax.legend(title="", frameon=False)
    cod_first = r[(r.payment_group == "COD") & (r.customer_type == "First order")]
    pre = r[r.payment_group == "Prepaid"]
    ratio = (cod_first.rto_orders.sum() / cod_first.shipped_orders.sum()) / (pre.rto_orders.sum() / pre.shipped_orders.sum())
    ax.set_title(f"First-time COD orders are refused at the door {ratio:.0f}x as often as prepaid orders")
    save(fig, "04_rto_drivers.png")


def courier_heatmap(con):
    c = query(con, "SELECT courier, city_tier, late_rate_pct FROM mart.v_courier_scorecard WHERE city_tier IS NOT NULL")
    wide = c.pivot(index="courier", columns="city_tier", values="late_rate_pct")
    wide.columns = [f"Tier {int(t)} cities" for t in wide.columns]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.heatmap(wide, annot=True, fmt=".0f", cmap="Reds", cbar_kws={"label": "Late deliveries, %"}, ax=ax)
    ax.set_ylabel("")
    worst = c.loc[c.late_rate_pct.idxmax()]
    ax.set_title(f"Late deliveries by courier: {worst.courier} misses the promised date on "
                 f"{worst.late_rate_pct:.0f}% of tier-{int(worst.city_tier)} orders")
    save(fig, "05_courier_late_rates.png")


def late_by_month(con):
    m = query(con, "SELECT order_month, late_rate_pct FROM mart.v_delivery_monthly ORDER BY order_month")
    m["order_month"] = pd.to_datetime(m.order_month)
    fig, ax = plt.subplots(figsize=(11, 4.8))
    colors = [COD if d.month in (11, 12) else NEUTRAL for d in m.order_month]
    ax.bar(m.order_month, m.late_rate_pct, width=25, color=colors)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_ylabel("Deliveries later than promised")
    peak = m.loc[m.late_rate_pct.idxmax()]
    ax.set_title(f"Couriers fall behind after every mega sale: {peak.late_rate_pct:.0f}% of "
                 f"{peak.order_month:%B %Y} deliveries were late")
    save(fig, "06_late_deliveries_by_month.png")


def first_order_retention(con):
    f = query(con, "SELECT * FROM mart.v_first_order_experience")
    order = ["Delivered on time", "Cancelled", "Delivered late", "Refused at door (RTO)"]
    f = f.set_index("first_order_experience").loc[order].reset_index()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = [PREPAID, NEUTRAL, COD, COD]
    bars = ax.bar(f.first_order_experience, f.repeat_90d_pct, color=colors)
    ax.bar_label(bars, labels=[f"{v:.0f}%\n(n={n:,})" for v, n in zip(f.repeat_90d_pct, f.customers)], fontsize=9)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylabel("Ordered again within 90 days")
    ax.set_ylim(0, f.repeat_90d_pct.max() * 1.25)
    on_time = f.set_index("first_order_experience").loc["Delivered on time", "repeat_90d_pct"]
    late = f.set_index("first_order_experience").loc["Delivered late", "repeat_90d_pct"]
    ax.set_title(f"A late first delivery cuts the 90-day repeat rate from {on_time:.0f}% to {late:.0f}%")
    save(fig, "07_first_order_retention.png")


def cohort_heatmap(con):
    c = query(con, """SELECT cohort_month, months_since_first, retention_pct FROM mart.v_cohort_retention
                      WHERE cohort_month <= DATE '2025-12-01' AND months_since_first BETWEEN 1 AND 6""")
    c["cohort_month"] = pd.to_datetime(c.cohort_month).dt.strftime("%Y-%m")
    wide = c.pivot(index="cohort_month", columns="months_since_first", values="retention_pct")
    fig, ax = plt.subplots(figsize=(9, 9))
    sns.heatmap(wide, annot=True, fmt=".0f", cmap="Blues", cbar_kws={"label": "Customers ordering again, %"}, ax=ax)
    ax.set_xlabel("Months after first order")
    ax.set_ylabel("First-order month (cohort)")
    nov = wide.loc[[i for i in wide.index if i.endswith("-11")], 1].mean()
    other = wide.loc[[i for i in wide.index if not i.endswith("-11")], 1].mean()
    ax.set_title(f"Month-1 retention averages {other:.0f}%, but November cohorts,\n"
                 f"full of mega-sale shoppers, manage only {nov:.0f}%")
    save(fig, "08_cohort_retention.png")


def acquisition_quality(con):
    a = query(con, "SELECT * FROM mart.v_acquisition_quality")
    ch = query(con, "SELECT * FROM mart.v_channel_quality ORDER BY repeat_90d_pct DESC")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1, 1.6]})
    bars = ax1.bar(["Mega-sale code", "Any other time"],
                   [a.set_index("acquisition").iloc[:, 1].get("First order used a mega-sale code"),
                    a.set_index("acquisition").iloc[:, 1].get("First order at any other time")],
                   color=[COD, PREPAID])
    ax1.bar_label(bars, fmt="%.0f%%")
    ax1.set_title("By first order", fontsize=11)
    ax1.set_ylabel("Ordered again within 90 days")
    ax1.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    bars = ax2.barh(ch.acquisition_channel, ch.repeat_90d_pct, color=NEUTRAL)
    ax2.bar_label(bars, fmt="%.0f%%", padding=3)
    ax2.invert_yaxis()
    ax2.set_title("By acquisition channel", fontsize=11)
    ax2.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    idx = a.set_index("acquisition")
    sale, other = idx.loc["First order used a mega-sale code"], idx.loc["First order at any other time"]
    fig.suptitle(f"Mega-sale customers come back less ({sale.repeat_90d_pct:.0f}% vs {other.repeat_90d_pct:.0f}%) "
                 f"and spend {100 * (1 - sale.avg_net_revenue / other.avg_net_revenue):.0f}% less over their lifetime",
                 x=0.01, ha="left", fontsize=12, fontweight="bold")
    save(fig, "09_acquisition_quality.png")


def returns_by_category(con):
    r = query(con, "SELECT * FROM mart.v_returns_by_category ORDER BY return_rate_pct DESC")
    reasons = ["size_or_fit", "not_as_described", "defective_or_damaged", "arrived_too_late", "changed_mind"]
    labels = ["Size or fit", "Not as described", "Defective or damaged", "Arrived too late", "Changed mind"]
    shares = r[reasons].fillna(0).div(r.items_delivered, axis=0) * 100
    fig, ax = plt.subplots(figsize=(11, 5))
    left = pd.Series(0.0, index=r.index)
    palette = [COD, ACCENT, NEUTRAL, "#8E9AAF", LIGHT]
    for col, label, color in zip(reasons, labels, palette):
        ax.barh(r.category, shares[col], left=left, label=label, color=color)
        left += shares[col]
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_xlabel("Items returned, % of items delivered")
    ax.legend(ncol=3, frameon=False, loc="lower right")
    top = r.iloc[0]
    ax.set_title(f"{top.category} has the highest return rate ({top.return_rate_pct:.0f}%), "
                 f"and {100 * top.size_or_fit / top.items_returned:.0f}% of those returns are size or fit problems")
    save(fig, "10_returns_by_category.png")


def rfm(con):
    s = query(con, "SELECT * FROM mart.v_rfm_summary")
    s["customer_share_pct"] = 100 * s.customers / s.customers.sum()
    s = s.sort_values("revenue_share_pct", ascending=False)
    long = s.melt(id_vars="segment", value_vars=["customer_share_pct", "revenue_share_pct"],
                  var_name="measure", value_name="pct")
    long["measure"] = long.measure.map({"customer_share_pct": "Share of customers", "revenue_share_pct": "Share of net revenue"})
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.barplot(data=long, x="segment", y="pct", hue="measure", palette=[LIGHT, PREPAID], ax=ax)
    for c in ax.containers:
        ax.bar_label(c, fmt="%.0f%%", fontsize=9)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.legend(title="", frameon=False)
    risk = s.set_index("segment").loc["At risk"]
    ax.set_title(f"'At risk' customers (no order for months, but bought often before) hold "
                 f"{risk.revenue_share_pct:.0f}% of net revenue")
    save(fig, "12_rfm_segments.png")


def city_tiers(con):
    g = query(con, "SELECT * FROM mart.v_city_tier_growth ORDER BY order_year, half, city_tier")
    g["period"] = g.order_year.astype(str) + " H" + g.half.astype(str)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
    for tier, color in zip((1, 2, 3), (PREPAID, NEUTRAL, COD)):
        t = g[g.city_tier == tier]
        ax1.plot(t.period, t.order_share_pct, marker="o", color=color, label=f"Tier {tier}")
        ax2.plot(t.period, t.cod_share_pct, marker="o", color=color, label=f"Tier {tier}")
    ax1.set_title("Share of orders", fontsize=11)
    ax2.set_title("Orders paid cash on delivery", fontsize=11)
    for ax in (ax1, ax2):
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
        ax.tick_params(axis="x", rotation=30)
    ax1.legend(frameon=False)
    t3 = g[g.city_tier == 3]
    fig.suptitle(f"Smaller (tier-3) cities grew from {t3.order_share_pct.iloc[0]:.0f}% to {t3.order_share_pct.iloc[-1]:.0f}% "
                 "of orders and still pay cash most often", x=0.01, ha="left", fontsize=12, fontweight="bold")
    save(fig, "13_city_tier_growth.png")


def main() -> None:
    IMG_DIR.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for chart in (monthly_revenue, daily_orders, payment_mix, rto_drivers, courier_heatmap, late_by_month,
                  first_order_retention, cohort_heatmap, acquisition_quality, returns_by_category, rfm, city_tiers):
        chart(con)
    con.close()


if __name__ == "__main__":
    main()
