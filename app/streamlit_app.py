"""Olist Growth Analytics — interactive dashboard.

Run locally:  streamlit run app/streamlit_app.py
Reads the small parquet marts in data/marts/ (committed), so it deploys on
Streamlit Community Cloud without the raw data.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import (confint_proportions_2indep, proportion_effectsize,
                                          proportions_ztest)

MARTS = Path(__file__).resolve().parents[1] / "data" / "marts"
BLUE, ORANGE, INK2, GRID = "#2a78d6", "#eb6834", "#52514e", "#e6e5e0"

st.set_page_config(page_title="Olist Growth Analytics", page_icon="📈", layout="wide")


@st.cache_data
def load():
    kpi = pd.read_parquet(MARTS / "mart_monthly_kpis.parquet")
    kpi["order_month"] = pd.to_datetime(kpi["order_month"])
    coh = pd.read_parquet(MARTS / "mart_cohort_retention.parquet")
    coh["cohort_month"] = pd.to_datetime(coh["cohort_month"])
    fun = pd.read_parquet(MARTS / "mart_funnel.parquet").sort_values("step")
    rfm = pd.read_parquet(MARTS / "mart_rfm.parquet")
    cust = pd.read_parquet(MARTS / "dim_customers.parquet")
    for c in ["first_order_is_late", "repeat_90d", "repeat_180d"]:
        cust[c] = cust[c].astype("boolean")
    return kpi, coh, fun, rfm, cust


def style(fig, height=380):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=30, b=10), plot_bgcolor="rgba(0,0,0,0)",
                      paper_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=1.08, x=0),
                      hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


kpi, coh, fun, rfm, cust = load()

st.title("📈 Olist Growth Analytics")
st.caption("Why does a marketplace growing 140% YoY have a 2% repeat-purchase rate — and what should we do about it? "
           "Data: Olist Brazilian E-commerce public dataset, Jan 2017 – Aug 2018.")

# ---- sidebar filters -----------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    months = kpi.order_month.dt.date.tolist()
    start, end = st.select_slider("Period", options=months, value=(months[0], months[-1]),
                                  format_func=lambda d: d.strftime("%b %Y"))
    states = sorted(cust.customer_state.dropna().unique())
    sel_states = st.multiselect("Customer state", states, placeholder="All states")
    cats = cust.first_order_category.value_counts().index.tolist()
    sel_cats = st.multiselect("First-order category", cats, placeholder="All categories")
    st.caption("State and category filters apply to the customer-level tabs.")

k = kpi[(kpi.order_month.dt.date >= start) & (kpi.order_month.dt.date <= end)]
c = cust[(cust.first_purchased_at.dt.date >= start) &
         (cust.first_purchased_at.dt.date <= pd.Timestamp(end).to_period("M").end_time.date())]
if sel_states:
    c = c[c.customer_state.isin(sel_states)]
if sel_cats:
    c = c[c.first_order_category.isin(sel_cats)]

tabs = st.tabs(["Overview", "Funnel", "Cohorts", "Delivery & reviews", "Segments", "A/B test planner"])

# ---- Overview ------------------------------------------------------------------------
with tabs[0]:
    a, b, cc, d, e = st.columns(5)
    a.metric("GMV", f"R$ {k.gmv.sum()/1e6:,.1f}M")
    b.metric("Orders", f"{k.orders.sum():,}")
    cc.metric("AOV", f"R$ {k.gmv.sum()/k.orders.sum():,.0f}")
    d.metric("Returning-customer share of orders",
             f"{k.repeat_orders.sum()/k.orders.sum():.1%}")
    r180 = c.repeat_180d.dropna()
    e.metric("180-day repeat rate", f"{r180.mean():.2%}" if len(r180) else "n/a",
             help="Share of customers placing a second order (on a later day) within 180 days. "
                  "Only customers with 180 days of follow-up are counted.")

    st.subheader("Metric tree")
    st.markdown(
        "**GMV** = Active customers × Orders per customer × AOV  \n"
        "**Active customers** = New customers + Returning customers  \n"
        "Growth in this period came almost entirely from *new customers*; orders per customer and AOV were flat.")
    fig = go.Figure()
    fig.add_bar(x=k.order_month, y=k.orders - k.repeat_orders, name="Orders from first-time customers", marker_color=BLUE,
                hovertemplate="%{x|%b %Y}<br>%{y:,} first-time orders<extra></extra>")
    fig.add_bar(x=k.order_month, y=k.repeat_orders, name="Orders from returning customers",
                marker_color=ORANGE, hovertemplate="%{x|%b %Y}<br>%{y:,} returning orders<extra></extra>")
    fig.update_layout(barmode="stack", bargap=0.25, legend_traceorder="normal")
    st.plotly_chart(style(fig), width="stretch")
    with st.expander("Monthly KPI table"):
        st.dataframe(k.assign(order_month=k.order_month.dt.strftime("%Y-%m")), hide_index=True,
                     width="stretch")

# ---- Funnel --------------------------------------------------------------------------
with tabs[1]:
    st.subheader("First-order journey funnel")
    st.caption("Customers acquired Jan 2017 – Jun 2018 (all have ≥ 90 days of follow-up). Not affected by filters.")
    f = fun.copy()
    f["conv"] = f.customers / f.customers.shift(1)
    fig = go.Figure(go.Bar(
        x=f.customers, y=f.stage, orientation="h", marker_color=BLUE,
        customdata=np.stack([f.customers / f.customers.iloc[0], f.conv.fillna(1)], axis=1),
        hovertemplate="%{y}<br>%{x:,} customers<br>%{customdata[0]:.1%} of start"
                      "<br>%{customdata[1]:.1%} of previous step<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 420), width="stretch")
    st.info("Operations keep ~90% of customers through on-time delivery and ~73% end up happy — "
            "but only **1 in 100** buys again within 90 days. The leak is *after* a good experience, "
            "which points to a missing lifecycle/re-engagement motion rather than a broken checkout.")

# ---- Cohorts -------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Cohort retention")
    max_m = st.slider("Months after first purchase", 3, 18, 12)
    ch = coh[(coh.months_since_first <= max_m) & (coh.cohort_month.dt.date >= start) &
             (coh.cohort_month.dt.date <= end)]
    mat = ch.pivot(index="cohort_month", columns="months_since_first", values="retention_rate").fillna(0)
    for cm in mat.index:  # blank out months not yet observable
        for m in mat.columns:
            if cm + pd.DateOffset(months=int(m)) > pd.Timestamp("2018-08-01"):
                mat.loc[cm, m] = np.nan
    fig = px.imshow(mat * 100, color_continuous_scale=["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"],
                    aspect="auto", labels=dict(x="Months since first purchase", y="Cohort", color="% retained"),
                    y=mat.index.strftime("%b %Y"), text_auto=".2f")
    fig.update_traces(hovertemplate="Cohort %{y}<br>Month %{x}<br>%{z:.2f}% bought again<extra></extra>")
    st.plotly_chart(style(fig, 560), width="stretch")
    st.caption("Repeat orders on the same calendar day as the first order are excluded "
               "(they are almost always one basket split across checkouts).")

# ---- Delivery & reviews --------------------------------------------------------------
with tabs[3]:
    st.subheader("Delivery experience → review → repeat")
    d = c.dropna(subset=["first_order_delay_days", "first_order_review_score"]).copy()
    d["bucket"] = pd.cut(d.first_order_delay_days, [-999, -10, -5, 0, 3, 7, 14, 999],
                         labels=["10+ days early", "5–9 early", "0–4 early", "1–3 late", "4–7 late",
                                 "8–14 late", "15+ late"])
    g = d.groupby("bucket", observed=True).agg(n=("customer_unique_id", "size"),
                                               review=("first_order_review_score", "mean"),
                                               repeat=("repeat_180d", "mean")).reset_index()
    col1, col2 = st.columns(2)
    fig = px.bar(g, x="bucket", y="review", custom_data=["n"],
                 color=g.bucket.astype(str).str.contains("late").map({True: "Late", False: "On time"}),
                 color_discrete_map={"Late": ORANGE, "On time": BLUE})
    fig.update_traces(hovertemplate="%{x}<br>avg review %{y:.2f}<br>%{customdata[0]:,} customers<extra></extra>")
    fig.update_layout(title="Avg first-order review score", legend_title=None, xaxis_title=None, yaxis_title=None)
    col1.plotly_chart(style(fig), width="stretch")
    w = c.dropna(subset=["repeat_180d", "first_order_review_score"])
    rv = w.groupby("first_order_review_score").repeat_180d.agg(["mean", "size"]).reset_index()
    fig = px.bar(rv, x="first_order_review_score", y="mean", custom_data=["size"], color_discrete_sequence=[BLUE])
    fig.update_traces(hovertemplate="%{x}★<br>repeat rate %{y:.2%}<br>%{customdata[0]:,} customers<extra></extra>")
    fig.update_layout(title="180-day repeat rate by review score", xaxis_title=None, yaxis_title=None)
    fig.update_yaxes(tickformat=".1%")
    col2.plotly_chart(style(fig), width="stretch")

    st.markdown("**Late-delivery rate vs. review score by month** (two panels, one scale each)")
    col1, col2 = st.columns(2)
    fig = px.line(k, x="order_month", y="late_delivery_rate", color_discrete_sequence=[ORANGE])
    fig.update_traces(line_width=2, hovertemplate="%{x|%b %Y}<br>%{y:.1%} late<extra></extra>")
    fig.update_yaxes(tickformat=".0%", title=None)
    fig.update_xaxes(title=None)
    col1.plotly_chart(style(fig, 300), width="stretch")
    fig = px.line(k, x="order_month", y="avg_review_score", color_discrete_sequence=[BLUE])
    fig.update_traces(line_width=2, hovertemplate="%{x|%b %Y}<br>avg review %{y:.2f}<extra></extra>")
    fig.update_yaxes(title=None)
    fig.update_xaxes(title=None)
    col2.plotly_chart(style(fig, 300), width="stretch")

# ---- Segments ------------------------------------------------------------------------
with tabs[4]:
    st.subheader("RFM segments (snapshot 2018-09-01)")
    rr = rfm[rfm.customer_unique_id.isin(c.customer_unique_id)]
    seg = rr.groupby("segment").agg(customers=("customer_unique_id", "size"), gmv=("monetary", "sum"),
                                    avg_gmv=("monetary", "mean"), avg_recency=("recency_days", "mean")).reset_index()
    seg["share_customers"] = seg.customers / seg.customers.sum()
    seg["share_gmv"] = seg.gmv / seg.gmv.sum()
    long = seg.melt(id_vars="segment", value_vars=["share_customers", "share_gmv"], var_name="metric")
    long["metric"] = long.metric.map({"share_customers": "Share of customers", "share_gmv": "Share of GMV"})
    fig = px.bar(long, y="segment", x="value", color="metric", barmode="group", orientation="h",
                 color_discrete_map={"Share of customers": BLUE, "Share of GMV": ORANGE})
    fig.update_traces(hovertemplate="%{y}<br>%{x:.1%}<extra></extra>")
    fig.update_xaxes(tickformat=".0%", title=None)
    fig.update_yaxes(title=None)
    fig.update_layout(legend_title=None)
    st.plotly_chart(style(fig, 420), width="stretch")
    playbook = pd.DataFrame({
        "Segment": ["Champions", "Loyal - at risk", "New high-value", "New customers", "Cooling down",
                    "Lost high-value", "Lost low-value"],
        "Suggested play": ["Referral program, early access", "Personal win-back with service recovery",
                           "Post-delivery cross-sell in the same category", "Welcome series, 2nd-order nudge at day 30–75",
                           "Reminder with category-relevant picks", "One-time win-back test (holdout!)",
                           "Low-cost channels only; don't spend coupons"]})
    st.dataframe(seg.merge(playbook, left_on="segment", right_on="Segment").drop(columns="Segment")
                 .style.format({"gmv": "R$ {:,.0f}", "avg_gmv": "R$ {:,.0f}", "avg_recency": "{:.0f} d",
                                "share_customers": "{:.1%}", "share_gmv": "{:.1%}"}),
                 hide_index=True, width="stretch")

# ---- A/B test planner ----------------------------------------------------------------
with tabs[5]:
    st.subheader("Experiment planner: second-purchase campaign")
    base_default = float(cust.repeat_90d.dropna().mean())
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**1 · Sample size**")
        base = st.number_input("Baseline 90-day repeat rate", 0.001, 0.5, round(base_default, 4), step=0.001,
                               format="%.4f")
        mde = st.slider("Minimum detectable effect (relative lift)", 0.05, 1.0, 0.30, 0.05)
        traffic = st.number_input("New customers per month", 100, 100000, 6458, step=100)
        alpha = st.selectbox("Significance level (α)", [0.01, 0.05, 0.10], index=1)
        power = st.selectbox("Power (1-β)", [0.8, 0.9], index=0)
        es = proportion_effectsize(base * (1 + mde), base)
        n = int(np.ceil(NormalIndPower().solve_power(effect_size=es, alpha=alpha, power=power)))
        st.metric("Customers needed per arm", f"{n:,}")
        st.metric("Enrolment time (50/50 split)", f"{2*n/traffic:.1f} months",
                  help="Plus 90 days to observe the outcome for the last enrolled customer.")
    with col2:
        st.markdown("**2 · Read out a result**")
        n_c = st.number_input("Control: customers", 1, 10_000_000, 15047)
        x_c = st.number_input("Control: repeat buyers", 0, 10_000_000, 174)
        n_t = st.number_input("Treatment: customers", 1, 10_000_000, 15047)
        x_t = st.number_input("Treatment: repeat buyers", 0, 10_000_000, 257)
        if x_c <= n_c and x_t <= n_t:
            z, p = proportions_ztest([x_t, x_c], [n_t, n_c])
            lo, hi = confint_proportions_2indep(x_t, n_t, x_c, n_c, method="wald")
            pc, pt = x_c / n_c, x_t / n_t
            st.metric("Relative lift", f"{pt/pc-1:+.1%}" if pc else "n/a",
                      delta=f"{(pt-pc)*100:+.2f} pp absolute")
            st.write(f"95% CI of the difference: **{lo*100:+.2f} pp to {hi*100:+.2f} pp** · p-value **{p:.4f}**")
            if p < 0.05:
                st.success("Statistically significant at α = 0.05")
            else:
                st.warning("Not significant at α = 0.05")
            st.markdown("**3 · Is it worth it?**")
            coupon = st.number_input("Coupon cost per redemption (R$)", 0.0, 200.0, 10.0)
            aov = st.number_input("Avg repeat-order GMV (R$)", 1.0, 5000.0, 149.0)
            take = st.slider("Marketplace take rate", 0.05, 0.30, 0.15, 0.01)
            inc_margin = (pt - pc) * 1000 * aov * take
            cost = pt * 1000 * coupon  # every redeemer gets the coupon, incl. those who'd have bought anyway
            st.write(f"Per 1,000 treated customers: incremental margin **R$ {inc_margin:,.0f}** vs coupon cost "
                     f"**R$ {cost:,.0f}** → net **R$ {inc_margin-cost:,.0f}**")
            st.caption("Default inputs are a SIMULATED example (see README). Significant ≠ profitable: "
                       "coupons are also paid to customers who would have bought anyway.")
