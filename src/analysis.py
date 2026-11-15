"""Growth analysis on top of the warehouse built by src/pipeline.py.

Produces:
  reports/figures/*.png   charts used in the README
  reports/results.json    every number quoted in the README / executive summary
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize, proportions_ztest, confint_proportions_2indep

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "warehouse.duckdb"
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

# ---- chart style (validated reference palette, light mode) -------------------------
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "font.size": 10.5, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 30, "axes.axisbelow": True, "legend.frameon": False, "figure.dpi": 110, "savefig.dpi": 160,
})


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG / f"{name}.png", bbox_inches="tight")
    plt.close(fig)


def subtitle(ax, text: str) -> None:
    ax.text(0, 1.025, text, transform=ax.transAxes, color=INK2, fontsize=10, va="bottom")


con = duckdb.connect(str(DB), read_only=True)
q = lambda sql: con.execute(sql).df()  # noqa: E731
R: dict = {}

# ---- 1. Metric tree / headline KPIs ---------------------------------------------------
kpi = q("select * from mart_monthly_kpis")
kpi["order_month"] = pd.to_datetime(kpi["order_month"])
fo = q("select count(*) orders, sum(gmv) gmv, count(distinct customer_unique_id) customers, "
       "avg(is_repeat_order::int) repeat_order_share, sum(gmv) filter (where is_repeat_order)/sum(gmv) repeat_gmv_share "
       "from fct_orders").iloc[0]
cust = q("select avg(repeat_90d::int) r90, avg(repeat_180d::int) r180, avg(is_repeat_customer::int) r_any, "
         "count(*) n, median(days_to_second_purchase) med_days_2nd from dim_customers").iloc[0]
same_day = q("""select count(distinct customer_unique_id) from fct_orders
                where customer_order_number > 1 and not is_repeat_order""").iloc[0, 0]

h1_2017 = kpi[kpi.order_month.between("2017-01-01", "2017-08-01")]
h1_2018 = kpi[kpi.order_month.between("2018-01-01", "2018-08-01")]
R["headline"] = {
    "orders": int(fo.orders), "gmv_brl": round(float(fo.gmv)), "customers": int(fo.customers),
    "repeat_order_share": round(float(fo.repeat_order_share), 4),
    "repeat_gmv_share": round(float(fo.repeat_gmv_share), 4),
    "repeat_rate_90d": round(float(cust.r90), 4), "repeat_rate_180d": round(float(cust.r180), 4),
    "repeat_rate_any": round(float(cust.r_any), 4),
    "median_days_to_second_purchase": float(cust.med_days_2nd),
    "customers_with_same_day_extra_order_only": int(same_day),
    "gmv_growth_jan_aug_2018_vs_2017": round(h1_2018.gmv.sum() / h1_2017.gmv.sum() - 1, 3),
    "new_customer_share_of_active_2018": round(h1_2018.new_customers.sum() / h1_2018.active_customers.sum(), 4),
}

# Metric tree decomposition: GMV = active customers x orders/customer x AOV
tree = kpi.assign(year=kpi.order_month.dt.year)
tree = tree[tree.order_month.dt.month <= 8].groupby("year").agg(
    gmv=("gmv", "sum"), orders=("orders", "sum"), active=("active_customers", "sum"),
    new=("new_customers", "sum"), returning=("returning_customers", "sum"))
tree["orders_per_customer"] = tree.orders / tree.active
tree["aov"] = tree.gmv / tree.orders
growth = (tree.loc[2018] / tree.loc[2017] - 1).round(3)
R["metric_tree_jan_aug_yoy"] = {k: float(growth[k]) for k in
                                ["gmv", "active", "new", "returning", "orders_per_customer", "aov"]}

fig, ax = plt.subplots(figsize=(10, 4.6))
x = np.arange(len(kpi))
returning_orders = kpi.repeat_orders
ax.bar(x, kpi.orders - kpi.repeat_orders, color=BLUE, width=0.72, label="Orders from first-time customers")
ax.bar(x, returning_orders, bottom=kpi.orders - kpi.repeat_orders, color=ORANGE, width=0.72, edgecolor=SURFACE, linewidth=1.5,
       label="Orders from returning customers")
ax.set_xticks(x[::2], kpi.order_month.dt.strftime("%b '%y")[::2])
ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
ax.set_title("Growth is almost entirely new-customer driven")
subtitle(ax, f"Monthly orders, 2017-01 to 2018-08 · returning customers = "
             f"{R['headline']['repeat_order_share']:.1%} of orders")
ax.legend(loc="upper left")
ax.grid(axis="x", visible=False)
save(fig, "01_new_vs_returning_orders")

# ---- 2. Funnel -------------------------------------------------------------------------
fun = q("select * from mart_funnel order by step")
fun["pct_of_start"] = fun.customers / fun.customers.iloc[0]
fun["step_conversion"] = fun.customers / fun.customers.shift(1)
R["funnel"] = fun[["stage", "customers", "pct_of_start", "step_conversion"]].round(4).to_dict("records")

fig, ax = plt.subplots(figsize=(10, 4.4))
y = np.arange(len(fun))[::-1]
ax.barh(y, fun.customers, color=BLUE, height=0.62)
for yi, (_, r) in zip(y, fun.iterrows()):
    conv = "" if pd.isna(r.step_conversion) else f"   ({r.step_conversion:.0%} of previous step)"
    ax.text(r.customers + 600, yi, f"{r.customers:,.0f}{conv}", va="center", color=INK, fontsize=9.5)
ax.set_yticks(y, fun.stage)
ax.set_xlim(0, fun.customers.max() * 1.45)
ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
ax.grid(axis="y", visible=False)
ax.set_title("The journey breaks after the first order, not before it")
subtitle(ax, "First-time customers acquired Jan 2017 – Jun 2018 (≥ 90 days of follow-up)")
save(fig, "02_first_order_funnel")

# ---- 3. Cohort retention ---------------------------------------------------------------
coh = q("select * from mart_cohort_retention where months_since_first <= 12")
coh["cohort_month"] = pd.to_datetime(coh.cohort_month)
mat = coh.pivot(index="cohort_month", columns="months_since_first", values="retention_rate")
mat = mat.loc[mat.index <= "2018-07-01"].fillna(0.0)
# mask cells that are not yet observable (beyond Aug 2018)
for cm in mat.index:
    for m in mat.columns:
        if cm + pd.DateOffset(months=int(m)) > pd.Timestamp("2018-08-01"):
            mat.loc[cm, m] = np.nan
avg_curve = mat.mean()
R["cohort_avg_retention_by_month"] = {int(k): round(float(v), 5) for k, v in avg_curve.items()}

from matplotlib.colors import LinearSegmentedColormap
seq = LinearSegmentedColormap.from_list("blue_seq", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
fig, ax = plt.subplots(figsize=(10, 6.2))
im = ax.imshow(mat.values * 100, cmap=seq, aspect="auto", vmin=0, vmax=0.8)
ax.set_xticks(range(len(mat.columns)), [f"M{m}" for m in mat.columns])
ax.set_yticks(range(len(mat.index)), mat.index.strftime("%b '%y"))
ax.grid(False)
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = mat.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v*100:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if v * 100 > 0.45 else INK)
cb = fig.colorbar(im, ax=ax, shrink=0.8)
cb.set_label("% of cohort buying again in month N", color=INK2)
cb.outline.set_visible(False)
ax.set_title("Fewer than 1 in 100 customers come back in any given month")
subtitle(ax, "Monthly acquisition cohorts · % of cohort placing a repeat order N months after first purchase")
save(fig, "03_cohort_retention_heatmap")

# ---- 4. Delivery experience → review → repeat --------------------------------------
dc = q("""select * from dim_customers
          where first_order_is_late is not null and first_order_review_score is not null""")
dc["delay_bucket"] = pd.cut(dc.first_order_delay_days, [-999, -10, -5, 0, 3, 7, 14, 999],
                            labels=["10+ days early", "5–9 early", "0–4 early", "1–3 late",
                                    "4–7 late", "8–14 late", "15+ late"])
by_delay = dc.groupby("delay_bucket", observed=True).agg(
    customers=("customer_unique_id", "count"), avg_review=("first_order_review_score", "mean"),
    one_star=("first_order_review_score", lambda s: (s == 1).mean()))
R["review_by_delay_bucket"] = by_delay.round(3).reset_index().astype({"delay_bucket": str}).to_dict("records")

obs = dc[dc.repeat_180d.notna()].copy()
obs["repeat_180d"] = obs.repeat_180d.astype(int)
late_tbl = obs.groupby("first_order_is_late").agg(n=("repeat_180d", "size"), repeats=("repeat_180d", "sum"))
late_tbl["rate"] = late_tbl.repeats / late_tbl.n
z, p = proportions_ztest(late_tbl.repeats.values, late_tbl.n.values)
review_tbl = obs.groupby("first_order_review_score").repeat_180d.agg(["size", "mean"])
R["late_vs_ontime"] = {
    "share_first_orders_late": round(float(dc.first_order_is_late.mean()), 4),
    "avg_review_on_time": round(float(dc.loc[~dc.first_order_is_late.astype(bool), "first_order_review_score"].mean()), 2),
    "avg_review_late": round(float(dc.loc[dc.first_order_is_late.astype(bool), "first_order_review_score"].mean()), 2),
    "repeat_180d_on_time": round(float(late_tbl.loc[False, "rate"]), 4),
    "repeat_180d_late": round(float(late_tbl.loc[True, "rate"]), 4),
    "z_test_p_value": float(p),
    "repeat_180d_by_review": {int(k): round(float(v), 4) for k, v in review_tbl["mean"].items()},
}

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4), gridspec_kw={"width_ratios": [1.35, 1]})
ax = axes[0]
colors = [BLUE if "early" in str(b) else ORANGE for b in by_delay.index]
ax.bar(range(len(by_delay)), by_delay.avg_review, color=colors, width=0.7)
for i, v in enumerate(by_delay.avg_review):
    ax.text(i, v + 0.06, f"{v:.1f}", ha="center", color=INK, fontsize=9.5)
ax.set_xticks(range(len(by_delay)), by_delay.index, rotation=20, ha="right")
ax.set_ylim(0, 5.3)
ax.grid(axis="x", visible=False)
ax.set_title("Late delivery destroys the review")
subtitle(ax, "Avg review score of first order, by delivery vs. promised date")
ax = axes[1]
rv = review_tbl["mean"]
ax.bar(rv.index.astype(int), rv.values * 100, color=BLUE, width=0.62)
for k, v in rv.items():
    ax.text(k, v * 100 + 0.04, f"{v:.1%}", ha="center", fontsize=9.5)
ax.set_xticks(rv.index.astype(int), [f"{int(k)}★" for k in rv.index])
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
ax.set_ylim(0, rv.max() * 100 * 1.25)
ax.grid(axis="x", visible=False)
ax.set_title("…but review score barely moves repeat rate")
subtitle(ax, "180-day repeat rate by first-order review score (differences not significant)")
save(fig, "04_delivery_review_repeat")

# Monthly late-rate vs review (two small multiples, shared x — never a dual axis)
fig, axes = plt.subplots(2, 1, figsize=(10, 5.4), sharex=True)
axes[0].plot(kpi.order_month, kpi.late_delivery_rate * 100, color=ORANGE, lw=2)
axes[0].yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
axes[0].set_title("Peaks in late deliveries…")
subtitle(axes[0], "Share of delivered orders arriving after the promised date")
for d in ["2017-11-01", "2018-03-01"]:
    r = kpi[kpi.order_month == d].iloc[0]
    axes[0].annotate(f"{r.order_month:%b '%y}: {r.late_delivery_rate:.0%}",
                     (r.order_month, r.late_delivery_rate * 100), xytext=(8, -2),
                     textcoords="offset points", fontsize=9, color=INK)
axes[1].plot(kpi.order_month, kpi.avg_review_score, color=BLUE, lw=2)
axes[1].set_title("…show up as drops in customer satisfaction")
subtitle(axes[1], "Average review score of orders placed that month")
axes[1].xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b '%y"))
save(fig, "05_late_rate_vs_review_monthly")
R["late_rate_peaks"] = kpi.nlargest(3, "late_delivery_rate")[["order_month", "late_delivery_rate", "avg_review_score"]] \
    .assign(order_month=lambda d: d.order_month.dt.strftime("%Y-%m")).to_dict("records")

# ---- 5. Drivers of a second purchase (logistic regression) ---------------------------
m = obs.copy()
top_cats = m.first_order_category.value_counts().index[:15]
m["category"] = np.where(m.first_order_category.isin(top_cats), m.first_order_category, "other")
top_states = m.customer_state.value_counts().index[:10]
m["state"] = np.where(m.customer_state.isin(top_states), m.customer_state, "other")
m["is_late"] = m.first_order_is_late.astype(int)
m["log_gmv"] = np.log1p(m.first_order_gmv)
m["payment"] = m.first_order_payment_type.fillna("unknown")
m["review"] = m.first_order_review_score.astype(int)
m["happy"] = (m.review >= 4).astype(int)

ctrl = "log_gmv + C(category, Treatment('bed_bath_table')) + C(state, Treatment('SP')) + C(payment)"
m1 = smf.logit(f"repeat_180d ~ is_late + {ctrl}", data=m).fit(disp=False)
m2 = smf.logit(f"repeat_180d ~ is_late + happy + {ctrl}", data=m).fit(disp=False)


def odds(model, term):
    ci = model.conf_int().loc[term]
    return {"odds_ratio": round(float(np.exp(model.params[term])), 3),
            "ci_low": round(float(np.exp(ci[0])), 3), "ci_high": round(float(np.exp(ci[1])), 3),
            "p_value": round(float(model.pvalues[term]), 5)}


cat_terms = [t for t in m1.params.index if t.startswith("C(category")]
cat_or = pd.Series({t.split("[T.")[1].rstrip("]"): float(np.exp(m1.params[t])) for t in cat_terms}).sort_values()
R["logit"] = {
    "n": int(m1.nobs), "base_rate": round(float(m.repeat_180d.mean()), 4),
    "model1_is_late": odds(m1, "is_late"),
    "model2_is_late": odds(m2, "is_late"),
    "model2_happy_review": odds(m2, "happy"),
    "category_odds_vs_bed_bath_table": cat_or.round(3).to_dict(),
}

cat = (m.groupby("first_order_category").agg(n=("repeat_180d", "size"), rate=("repeat_180d", "mean"),
                                            aov=("first_order_gmv", "mean"))
       .query("n >= 1000").sort_values("rate"))
se = np.sqrt(cat.rate * (1 - cat.rate) / cat.n)
R["category_repeat_180d"] = cat.round(4).reset_index().to_dict("records")
fig, ax = plt.subplots(figsize=(10, 6))
yy = np.arange(len(cat))
avg = m.repeat_180d.mean()
ax.barh(yy, cat.rate * 100, color=[BLUE if r > avg else "#b7d3f6" for r in cat.rate], height=0.66,
        xerr=1.96 * se * 100, error_kw={"ecolor": INK2, "elinewidth": 0.8, "capsize": 0})
ax.axvline(avg * 100, color=INK2, lw=1, ls="--")
ax.text(avg * 100 + 0.05, len(cat) - 0.4, f"all categories {avg:.1%}", color=INK2, fontsize=9)
ax.set_yticks(yy, cat.index.str.replace("_", " "))
ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=1))
ax.grid(axis="y", visible=False)
ax.set_title("Where second purchases come from")
subtitle(ax, "180-day repeat rate by category of the first order (categories with ≥1,000 customers, 95% CI)")
save(fig, "06_repeat_by_category")

# ---- 6. RFM segments -------------------------------------------------------------------
rfm = q("""select segment, count(*) customers, sum(monetary) gmv, avg(monetary) avg_gmv,
                  avg(recency_days) avg_recency, avg(frequency) avg_frequency
           from mart_rfm group by 1""")
rfm["share_customers"] = rfm.customers / rfm.customers.sum()
rfm["share_gmv"] = rfm.gmv / rfm.gmv.sum()
order = ["Champions", "Loyal - at risk", "New high-value", "New customers", "Cooling down",
         "Lost high-value", "Lost low-value"]
rfm = rfm.set_index("segment").loc[order].reset_index()
R["rfm"] = rfm.round(4).to_dict("records")
fig, ax = plt.subplots(figsize=(10, 4.6))
yy = np.arange(len(rfm))[::-1]
h = 0.36
ax.barh(yy + h / 2 + 0.02, rfm.share_customers * 100, height=h, color=BLUE, label="Share of customers")
ax.barh(yy - h / 2 - 0.02, rfm.share_gmv * 100, height=h, color=ORANGE, label="Share of GMV")
for yi, r in zip(yy, rfm.itertuples()):
    ax.text(max(r.share_customers, r.share_gmv) * 100 + 0.6, yi,
            f"{r.customers:,} customers · avg R$ {r.avg_gmv:,.0f}", va="center", fontsize=9, color=INK2)
ax.set_yticks(yy, rfm.segment)
ax.set_xlim(0, 45)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.grid(axis="y", visible=False)
ax.legend(loc="upper right")
ax.set_title("RFM segments: who to win back, who to grow")
subtitle(ax, "Snapshot 2018-09-01 · Frequency bucketed 1 / 2 / 3+ orders because 97% buy once")
save(fig, "07_rfm_segments")

# ---- 7. A/B test: design + (simulated) readout ----------------------------------------
monthly_new = float(h1_2018.new_customers.mean())
base = float(cust.r90)
power = NormalIndPower()
design = []
for rel in [0.10, 0.20, 0.30, 0.50]:
    es = proportion_effectsize(base * (1 + rel), base)
    n = power.solve_power(effect_size=es, alpha=0.05, power=0.8, ratio=1.0, alternative="two-sided")
    design.append({"relative_mde": rel, "n_per_arm": int(np.ceil(n)),
                   "months_to_enroll": round(2 * n / monthly_new, 1)})
R["ab_design"] = {"baseline_repeat_90d": round(base, 4), "monthly_new_customers_2018": round(monthly_new),
                  "alpha": 0.05, "power": 0.8, "options": design}

# Chosen design: 30% relative MDE. SIMULATED outcome — clearly labelled, illustrative only.
chosen = next(d for d in design if d["relative_mde"] == 0.30)
n_arm = chosen["n_per_arm"]
rng = np.random.default_rng(42)
true_lift = 0.35
ctrl_conv = rng.binomial(n_arm, base)
trt_conv = rng.binomial(n_arm, base * (1 + true_lift))
z, p = proportions_ztest([trt_conv, ctrl_conv], [n_arm, n_arm])
lo, hi = confint_proportions_2indep(trt_conv, n_arm, ctrl_conv, n_arm, method="wald")
p_c, p_t = ctrl_conv / n_arm, trt_conv / n_arm
coupon_cost = 10.0  # BRL per redeemed coupon (assumption)
avg_repeat_order_gmv = float(q("select avg(gmv) from fct_orders where is_repeat_order").iloc[0, 0])
take_rate = 0.15  # assumed marketplace commission on GMV
R["ab_simulation"] = {
    "note": "SIMULATED data (seed 42) to demonstrate the analysis workflow — not a real experiment.",
    "hypothesis": "A R$10 second-purchase coupon sent 7 days after delivery increases 90-day repeat rate.",
    "n_per_arm": n_arm, "control_rate": round(p_c, 5), "treatment_rate": round(p_t, 5),
    "absolute_lift_pp": round((p_t - p_c) * 100, 3), "relative_lift": round(p_t / p_c - 1, 3),
    "diff_ci_95_pp": [round(lo * 100, 3), round(hi * 100, 3)], "p_value": round(float(p), 5),
    "assumed_coupon_cost_brl": coupon_cost, "assumed_take_rate": take_rate,
    "avg_repeat_order_gmv": round(avg_repeat_order_gmv, 2),
    # unit economics per 1,000 treated customers: incremental margin vs coupon cost
    "incremental_orders_per_1000": round((p_t - p_c) * 1000, 2),
    "incremental_margin_per_1000_brl": round((p_t - p_c) * 1000 * avg_repeat_order_gmv * take_rate, 2),
    "coupon_cost_per_1000_brl": round(p_t * 1000 * coupon_cost, 2),
}

# ---- 8. Opportunity sizing ------------------------------------------------------------
annual_new = monthly_new * 12
avg_repeat_orders_per_repeater = float(q(
    "select avg(n_repeat_orders) from dim_customers where is_repeat_customer").iloc[0, 0])
gmv_per_repeater = avg_repeat_orders_per_repeater * avg_repeat_order_gmv
scen = {}
for label, target in {"+0.5pp": cust.r180 + 0.005, "+1pp": cust.r180 + 0.01, "x2": cust.r180 * 2}.items():
    extra = annual_new * (target - cust.r180)
    scen[label] = {"target_repeat_180d": round(float(target), 4), "extra_repeat_customers": round(float(extra)),
                   "extra_gmv_brl": round(float(extra * gmv_per_repeater))}
R["opportunity"] = {"annual_new_customers_run_rate": round(annual_new), "gmv_per_repeat_customer": round(gmv_per_repeater, 2),
                    "scenarios": scen}

(ROOT / "reports" / "results.json").write_text(json.dumps(R, indent=2, default=str))
print(json.dumps(R, indent=2, default=str))
