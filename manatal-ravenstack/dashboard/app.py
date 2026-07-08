"""
RavenStack SaaS Analytics Dashboard
=====================================
Portfolio project built for a Product Analyst interview at Manatal, analyzing
the public "RavenStack" synthetic SaaS dataset (accounts, subscriptions,
feature usage, support tickets, churn events) by River @ Rivalytics
(kaggle.com/datasets/rivalytics/saas-subscription-and-churn-analytics-dataset).

Run locally with:  streamlit run app.py
(expects ../data/ravenstack.db to exist — see data/build_database.py)
"""

import sqlite3
import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------------------------------------------------------
# Page config + brand tokens (same Manatal-inspired system as the companion project)
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="RavenStack | SaaS Analytics",
    page_icon="🐦‍⬛",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORS = {
    "primary": "#4A3AFF",
    "primary_dark": "#372BC4",
    "navy": "#161340",
    "ink": "#1C1B33",
    "bg": "#F7F7FC",
    "surface": "#FFFFFF",
    "border": "#E7E6F5",
    "muted": "#6E6D8C",
    "success": "#17B897",
    "warning": "#FFB020",
    "danger": "#FF5C5C",
    "chart_seq": ["#4A3AFF", "#7D6DFF", "#A99BFF", "#17B897", "#5FD9C4", "#FFB020", "#FF8A65", "#FF5C5C"],
}

CUSTOM_CSS = f"""
<style>
    .stApp {{ background-color: {COLORS['bg']}; }}
    html, body, [class*="css"] {{ font-family: 'Inter', 'Segoe UI', -apple-system, sans-serif; }}
    section[data-testid="stSidebar"] {{ background-color: {COLORS['navy']}; }}
    section[data-testid="stSidebar"] * {{ color: #F1F0FF !important; }}
    .block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; }}
    h1, h2, h3 {{ color: {COLORS['navy']}; font-weight: 700; }}
    .manatal-header {{ display: flex; align-items: center; gap: 14px; margin-bottom: 0.2rem; }}
    .manatal-logo-badge {{
        background: {COLORS['primary']}; color: white; font-weight: 800; font-size: 20px;
        width: 42px; height: 42px; border-radius: 10px; display: flex;
        align-items: center; justify-content: center; letter-spacing: -1px;
    }}
    .manatal-subtitle {{ color: {COLORS['muted']}; font-size: 0.95rem; margin-top: -6px; }}
    .kpi-card {{
        background: {COLORS['surface']}; border: 1px solid {COLORS['border']};
        border-radius: 14px; padding: 18px 20px; box-shadow: 0 1px 2px rgba(22, 19, 64, 0.04);
    }}
    .kpi-label {{ color: {COLORS['muted']}; font-size: 0.78rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }}
    .kpi-value {{ color: {COLORS['navy']}; font-size: 1.7rem; font-weight: 800; margin-top: 2px; }}
    .section-tag {{
        display: inline-block; background: {COLORS['border']}; color: {COLORS['primary_dark']};
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
        padding: 3px 10px; border-radius: 999px; margin-bottom: 6px;
    }}
    .anomaly-tag {{
        display: inline-block; background: #FFE9E9; color: {COLORS['danger']};
        font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
        padding: 3px 10px; border-radius: 999px; margin-bottom: 6px;
    }}
    div[data-testid="stMetricValue"] {{ color: {COLORS['navy']}; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {COLORS['surface']}; border-radius: 10px 10px 0 0;
        padding: 8px 16px; color: {COLORS['muted']}; font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{ background-color: {COLORS['primary']} !important; color: white !important; }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

PLOTLY_TEMPLATE = go.layout.Template(
    layout=dict(
        font=dict(family="Inter, Segoe UI, sans-serif", color=COLORS["ink"]),
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        colorway=COLORS["chart_seq"],
        title=dict(font=dict(size=16, color=COLORS["navy"])),
        xaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
        yaxis=dict(gridcolor=COLORS["border"], zerolinecolor=COLORS["border"]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
)

# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ravenstack.db")


@st.cache_data(show_spinner=False)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    accounts = pd.read_sql("SELECT * FROM accounts", conn)
    subs = pd.read_sql("SELECT * FROM subscriptions", conn)
    features = pd.read_sql("SELECT * FROM feature_usage", conn)
    tickets = pd.read_sql("SELECT * FROM support_tickets", conn)
    churn = pd.read_sql("SELECT * FROM churn_events", conn)
    conn.close()

    accounts["signup_date"] = pd.to_datetime(accounts["signup_date"])
    subs["start_date"] = pd.to_datetime(subs["start_date"])
    subs["end_date"] = pd.to_datetime(subs["end_date"])
    features["usage_date"] = pd.to_datetime(features["usage_date"])
    tickets["submitted_at"] = pd.to_datetime(tickets["submitted_at"])
    tickets["closed_at"] = pd.to_datetime(tickets["closed_at"])
    churn["churn_date"] = pd.to_datetime(churn["churn_date"])

    # current (latest) subscription per account — used throughout for "current plan"/"current MRR"
    # NOTE: subscriptions has its own `churn_flag` (that specific subscription record ended),
    # which is a DIFFERENT concept from accounts.churn_flag ("is this account currently churned").
    # Rename to avoid silent collisions when merging the two frames.
    latest_sub = subs.sort_values("start_date").groupby("account_id").tail(1).copy()
    latest_sub = latest_sub.rename(columns={
        "plan_tier": "current_plan_tier",
        "mrr_amount": "current_mrr",
        "churn_flag": "sub_churn_flag",
    })

    return accounts, subs, features, tickets, churn, latest_sub


if not os.path.exists(DB_PATH):
    st.error(
        "Database not found. Run `python data/build_database.py` first to create "
        "`data/ravenstack.db`, then relaunch the dashboard."
    )
    st.stop()

accounts, subs, features, tickets, churn, latest_sub = load_data()

# ----------------------------------------------------------------------------
# Header
# ----------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="manatal-header">
        <div class="manatal-logo-badge">M</div>
        <div>
            <div style="font-size:1.5rem; font-weight:800; color:{COLORS['navy']};">RavenStack SaaS Analytics</div>
            <div class="manatal-subtitle">Product usage, revenue, churn &amp; support impact — Kaggle "RavenStack" dataset, styled for a Manatal Product Analyst interview</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

# ----------------------------------------------------------------------------
# Sidebar filters
# ----------------------------------------------------------------------------
st.sidebar.markdown("### 🧭 Filters")
industries = ["All"] + sorted(accounts["industry"].unique().tolist())
sel_industry = st.sidebar.selectbox("Industry", industries)

plans = ["All"] + sorted(latest_sub["current_plan_tier"].unique().tolist())
sel_plan = st.sidebar.selectbox("Current plan tier", plans)

referrals = ["All"] + sorted(accounts["referral_source"].unique().tolist())
sel_referral = st.sidebar.selectbox("Referral source", referrals)

st.sidebar.markdown("---")
st.sidebar.markdown(
    f"""
    <div style="font-size:0.8rem; opacity:0.85; line-height:1.5;">
    <b>About this data</b><br/>
    Public synthetic dataset ("RavenStack") by River @ Rivalytics on Kaggle —
    not self-generated. Built for interview prep; see
    <code>docs/README.md</code> for a documented data-quality investigation.
    </div>
    """,
    unsafe_allow_html=True,
)

# apply filters
acc_f = accounts.copy()
ls_f = latest_sub.copy()
if sel_industry != "All":
    acc_f = acc_f[acc_f["industry"] == sel_industry]
if sel_referral != "All":
    acc_f = acc_f[acc_f["referral_source"] == sel_referral]
ls_f = ls_f[ls_f["account_id"].isin(acc_f["account_id"])]
if sel_plan != "All":
    ls_f = ls_f[ls_f["current_plan_tier"] == sel_plan]
acc_f = acc_f[acc_f["account_id"].isin(ls_f["account_id"])]

acc_ids = set(acc_f["account_id"])
subs_f = subs[subs["account_id"].isin(acc_ids)]
sub_ids_f = set(subs_f["subscription_id"])
features_f = features[features["subscription_id"].isin(sub_ids_f)]
tickets_f = tickets[tickets["account_id"].isin(acc_ids)]
churn_f = churn[churn["account_id"].isin(acc_ids)]

# ----------------------------------------------------------------------------
# KPI row
# ----------------------------------------------------------------------------
total_accounts = len(acc_f)
active_accounts = int((acc_f["churn_flag"] == False).sum())  # noqa: E712
churn_rate = 100 * acc_f["churn_flag"].mean() if total_accounts else 0
active_mrr = ls_f.loc[ls_f["account_id"].isin(acc_f.loc[acc_f["churn_flag"] == False, "account_id"]), "current_mrr"].sum()  # noqa: E712
avg_satisfaction = tickets_f["satisfaction_score"].mean()
escalation_rate = 100 * tickets_f["escalation_flag"].mean() if len(tickets_f) else 0

kpi_cols = st.columns(5)
kpis = [
    ("Active Accounts", f"{active_accounts:,}", f"of {total_accounts:,} total"),
    ("Churn Rate", f"{churn_rate:.1f}%", "of filtered accounts"),
    ("Active MRR", f"${active_mrr:,.0f}", "current monthly recurring revenue"),
    ("Avg. CSAT", f"{avg_satisfaction:.2f} / 5" if pd.notna(avg_satisfaction) else "N/A", "support ticket satisfaction"),
    ("Escalation Rate", f"{escalation_rate:.1f}%", "of support tickets"),
]
for col, (label, value, sub) in zip(kpi_cols, kpis):
    col.markdown(
        f"""<div class="kpi-card"><div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div style="color:{COLORS['muted']}; font-size:0.78rem; margin-top:2px;">{sub}</div></div>""",
        unsafe_allow_html=True,
    )

st.write("")

# ----------------------------------------------------------------------------
# Tabs
# ----------------------------------------------------------------------------
tab_overview, tab_quality, tab_features, tab_revenue, tab_churn, tab_support = st.tabs(
    ["📊 Overview", "🔍 Data Quality", "🧩 Feature Adoption", "💰 Revenue & Plans",
     "🔻 Churn & Retention", "🎧 Support Impact"]
)

# ---------------- OVERVIEW ----------------
with tab_overview:
    st.markdown('<span class="section-tag">Business Overview</span>', unsafe_allow_html=True)
    c1, c2 = st.columns([1.3, 1])
    with c1:
        monthly = acc_f.copy()
        monthly["signup_month"] = monthly["signup_date"].dt.to_period("M").dt.to_timestamp()
        new_accts = monthly.groupby("signup_month").size().reset_index(name="new_accounts")
        fig = px.bar(new_accts, x="signup_month", y="new_accounts", title="New Accounts by Signup Month", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["primary"])
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        ind_counts = acc_f.groupby("industry").size().reset_index(name="accounts")
        fig = px.pie(ind_counts, names="industry", values="accounts", hole=0.55, title="Accounts by Industry",
                     template=PLOTLY_TEMPLATE, color_discrete_sequence=COLORS["chart_seq"])
        st.plotly_chart(fig, use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        plan_mrr = ls_f[ls_f["account_id"].isin(acc_f.loc[acc_f["churn_flag"] == False, "account_id"])].groupby("current_plan_tier")["current_mrr"].sum().reset_index()  # noqa: E712
        fig = px.bar(plan_mrr.sort_values("current_mrr"), x="current_mrr", y="current_plan_tier", orientation="h",
                     title="Active MRR by Current Plan Tier", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["primary"])
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        country_counts = acc_f.groupby("country").size().reset_index(name="accounts").sort_values("accounts", ascending=False)
        fig = px.bar(country_counts, x="accounts", y="country", orientation="h", title="Accounts by Country", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["success"])
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "Interview talking point: this exec-summary view uses the LATEST subscription per account for "
        "'current plan'/'current MRR', not accounts.plan_tier — see the Data Quality tab for why that distinction matters."
    )

# ---------------- DATA QUALITY ----------------
with tab_quality:
    st.markdown('<span class="anomaly-tag">Data Structure Ownership &amp; Integrity Checks</span>', unsafe_allow_html=True)
    st.write(
        "Maps directly to the JD line: *'Ensure the accuracy, integrity, and timeliness of data, "
        "implementing measures to identify and rectify any anomalies.'* These are real findings from "
        "profiling this dataset — not hypothetical examples."
    )

    # Anomaly: churn_flag=True, no churn_events, has active subscription
    active_sub_accounts = set(subs[subs["end_date"].isna()]["account_id"])
    churn_event_accounts = set(churn["account_id"])
    anomaly = accounts[
        (accounts["churn_flag"] == True)  # noqa: E712
        & (~accounts["account_id"].isin(churn_event_accounts))
        & (accounts["account_id"].isin(active_sub_accounts))
    ]

    c1, c2 = st.columns([1, 1.4])
    with c1:
        st.metric("Anomalous accounts found", f"{len(anomaly)}", help="churn_flag=True, but no churn_events record AND a currently-active (non-ended) subscription")
        st.markdown(
            f"""
            <div class="kpi-card" style="border-color:#FFD6D6;">
            <b>Finding:</b> {len(anomaly)} accounts are flagged <code>churn_flag = True</code> in the
            accounts table, but have <b>no corresponding row</b> in <code>churn_events</code> and
            currently hold an <b>active subscription</b> (no <code>end_date</code>). That's a logical
            contradiction — either the flag is stale, the churn event failed to log, or the
            reactivation wasn't reflected back onto the account record.
            </div>
            """, unsafe_allow_html=True,
        )
    with c2:
        st.dataframe(anomaly[["account_id", "account_name", "industry", "plan_tier", "churn_flag"]].head(15),
                     use_container_width=True, hide_index=True)

    st.markdown("#### Reconciliation: `accounts.churn_flag` vs. `churn_events` history")
    has_churn_event = accounts["account_id"].isin(churn_event_accounts)
    has_active = accounts["account_id"].isin(active_sub_accounts)

    def bucket(row_flag, has_event, is_active):
        if row_flag and has_event:
            return "Churned, with history (expected)"
        if not row_flag and has_event and is_active:
            return "Reactivated — has history, currently active (expected)"
        if row_flag and not has_event and is_active:
            return "ANOMALY: flagged churned, no history, active sub"
        if not row_flag and not has_event:
            return "Never churned (expected)"
        return "Other / needs review"

    recon = accounts.copy()
    recon["has_event"] = has_churn_event.values
    recon["is_active"] = has_active.values
    recon["bucket"] = [bucket(r, e, a) for r, e, a in zip(recon["churn_flag"], recon["has_event"], recon["is_active"])]
    recon_counts = recon["bucket"].value_counts().reset_index()
    recon_counts.columns = ["bucket", "accounts"]
    fig = px.bar(recon_counts.sort_values("accounts"), x="accounts", y="bucket", orientation="h",
                 title="Account Reconciliation Buckets", template=PLOTLY_TEMPLATE)
    colors_map = [COLORS["danger"] if "ANOMALY" in b else COLORS["primary"] for b in recon_counts.sort_values("accounts")["bucket"]]
    fig.update_traces(marker_color=colors_map)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Referential integrity checks (all should be 0)")
    ref_checks = pd.DataFrame({
        "check": ["subscriptions → accounts", "feature_usage → subscriptions", "support_tickets → accounts", "churn_events → accounts"],
        "orphan_rows": [
            (~subs["account_id"].isin(accounts["account_id"])).sum(),
            (~features["subscription_id"].isin(subs["subscription_id"])).sum(),
            (~tickets["account_id"].isin(accounts["account_id"])).sum(),
            (~churn["account_id"].isin(accounts["account_id"])).sum(),
        ]
    })
    st.dataframe(ref_checks, use_container_width=True, hide_index=True)

    st.markdown("#### Null-value audit on key nullable fields")
    null_audit = pd.DataFrame({
        "field": ["support_tickets.satisfaction_score", "churn_events.feedback_text", "subscriptions.end_date (active subs)"],
        "null_pct": [
            round(100 * tickets["satisfaction_score"].isna().mean(), 1),
            round(100 * churn["feedback_text"].isna().mean(), 1),
            round(100 * subs["end_date"].isna().mean(), 1),
        ]
    })
    fig = px.bar(null_audit, x="null_pct", y="field", orientation="h", title="% Null by Field", template=PLOTLY_TEMPLATE)
    fig.update_traces(marker_color=COLORS["warning"])
    st.plotly_chart(fig, use_container_width=True)

# ---------------- FEATURE ADOPTION ----------------
with tab_features:
    st.markdown('<span class="section-tag">Feature Usage · 40 tracked features</span>', unsafe_allow_html=True)

    c1, c2 = st.columns([1.3, 1])
    with c1:
        feat_summary = features_f.groupby("feature_name").agg(
            total_events=("usage_id", "count"), total_errors=("error_count", "sum")
        ).reset_index().sort_values("total_events", ascending=False).head(15)
        fig = px.bar(feat_summary, x="total_events", y="feature_name", orientation="h",
                     title="Top 15 Features by Usage Volume", template=PLOTLY_TEMPLATE, height=480)
        fig.update_traces(marker_color=COLORS["primary"])
        fig.update_layout(yaxis=dict(categoryorder="total ascending"))
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        beta_summary = features_f.groupby("is_beta_feature").agg(
            events=("usage_id", "count"), errors=("error_count", "sum"),
            avg_duration=("usage_duration_secs", "mean")
        ).reset_index()
        beta_summary["is_beta_feature"] = beta_summary["is_beta_feature"].map({0: "GA Feature", 1: "Beta Feature"})
        beta_summary["errors_per_event"] = (beta_summary["errors"] / beta_summary["events"]).round(3)
        fig = px.bar(beta_summary, x="is_beta_feature", y="errors_per_event", title="Errors per Event: Beta vs. GA Features",
                     template=PLOTLY_TEMPLATE, height=480)
        fig.update_traces(marker_color=[COLORS["warning"], COLORS["success"]])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Monthly usage trend — top 5 features")
    trend = features_f.copy()
    trend["month"] = trend["usage_date"].dt.to_period("M").dt.to_timestamp()
    top5 = feat_summary.head(5)["feature_name"].tolist()
    trend = trend[trend["feature_name"].isin(top5)]
    trend_agg = trend.groupby(["month", "feature_name"]).size().reset_index(name="events")
    fig = px.line(trend_agg, x="month", y="events", color="feature_name", markers=True,
                  title="Top 5 Features — Monthly Usage Trend", template=PLOTLY_TEMPLATE)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Feature error-rate watchlist (min. 20 events)")
    err_watch = features_f.groupby("feature_name").agg(
        total_events=("usage_id", "count"), total_errors=("error_count", "sum")
    ).reset_index()
    err_watch = err_watch[err_watch["total_events"] >= 20]
    err_watch["errors_per_event"] = (err_watch["total_errors"] / err_watch["total_events"]).round(3)
    err_watch = err_watch.sort_values("errors_per_event", ascending=False).head(10)
    fig = px.bar(err_watch, x="errors_per_event", y="feature_name", orientation="h",
                 title="Top 10 Features by Error Rate", template=PLOTLY_TEMPLATE)
    fig.update_traces(marker_color=COLORS["danger"])
    fig.update_layout(yaxis=dict(categoryorder="total ascending"))
    st.plotly_chart(fig, use_container_width=True)

# ---------------- REVENUE & PLANS ----------------
with tab_revenue:
    st.markdown('<span class="section-tag">Revenue, Plan Movement &amp; Referral Channel ROI</span>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        upgrades = int(subs_f["upgrade_flag"].sum())
        downgrades = int(subs_f["downgrade_flag"].sum())
        fig = go.Figure(data=[go.Bar(x=["Upgrades", "Downgrades"], y=[upgrades, downgrades],
                                      marker_color=[COLORS["success"], COLORS["danger"]])])
        fig.update_layout(title="Plan Movement: Upgrades vs. Downgrades", template=PLOTLY_TEMPLATE)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        billing_churn = ls_f.merge(acc_f[["account_id", "churn_flag"]], on="account_id")
        billing_agg = billing_churn.groupby("billing_frequency")["churn_flag"].mean().reset_index()
        billing_agg["churn_flag"] *= 100
        fig = px.bar(billing_agg, x="billing_frequency", y="churn_flag", title="Churn Rate: Monthly vs. Annual Billing",
                     template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["primary"])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Revenue cohort analysis by referral source")
    ref_rev = acc_f.merge(ls_f[["account_id", "current_mrr"]], on="account_id")
    ref_summary = ref_rev.groupby("referral_source").agg(
        accounts=("account_id", "nunique"),
        churn_rate=("churn_flag", "mean"),
        active_mrr=("current_mrr", lambda s: ref_rev.loc[s.index][ref_rev.loc[s.index, "churn_flag"] == False]["current_mrr"].sum())  # noqa: E712
    ).reset_index()
    ref_summary["churn_rate"] = (ref_summary["churn_rate"] * 100).round(1)
    c3, c4 = st.columns(2)
    with c3:
        fig = px.bar(ref_summary.sort_values("active_mrr"), x="active_mrr", y="referral_source", orientation="h",
                     title="Active MRR by Referral Source", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["primary"])
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        fig = px.bar(ref_summary.sort_values("churn_rate"), x="churn_rate", y="referral_source", orientation="h",
                     title="Churn Rate by Referral Source (%)", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["danger"])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Upgrade / downgrade rate by industry")
    ind_move = subs_f.merge(acc_f[["account_id", "industry"]], on="account_id")
    ind_agg = ind_move.groupby("industry").agg(
        upgrade_rate=("upgrade_flag", "mean"), downgrade_rate=("downgrade_flag", "mean")
    ).reset_index()
    ind_agg["upgrade_rate"] *= 100
    ind_agg["downgrade_rate"] *= 100
    ind_long = ind_agg.melt(id_vars="industry", value_vars=["upgrade_rate", "downgrade_rate"], var_name="type", value_name="rate")
    fig = px.bar(ind_long, x="industry", y="rate", color="type", barmode="group",
                 title="Upgrade vs. Downgrade Rate by Industry (%)", template=PLOTLY_TEMPLATE)
    st.plotly_chart(fig, use_container_width=True)

# ---------------- CHURN & RETENTION ----------------
with tab_churn:
    st.markdown('<span class="section-tag">Churn Drivers, Reactivation &amp; Retention</span>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        reason_counts = churn_f["reason_code"].value_counts().reset_index()
        reason_counts.columns = ["reason_code", "events"]
        fig = px.bar(reason_counts.sort_values("events"), x="events", y="reason_code", orientation="h",
                     title="Churn Events by Reason Code", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["danger"])
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        cohort = acc_f.copy()
        cohort["signup_month"] = cohort["signup_date"].dt.to_period("M").dt.to_timestamp()
        cohort_agg = cohort.groupby("signup_month").agg(accounts=("account_id", "count"), churned=("churn_flag", "sum")).reset_index()
        cohort_agg["logo_retention_pct"] = (100 - 100 * cohort_agg["churned"] / cohort_agg["accounts"]).round(1)
        fig = px.line(cohort_agg, x="signup_month", y="logo_retention_pct", markers=True,
                     title="Logo Retention % by Signup Cohort", template=PLOTLY_TEMPLATE)
        fig.update_traces(line_color=COLORS["primary"])
        fig.update_yaxes(range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Reactivation patterns: repeat churn-event counts per account")
    churn_counts = churn_f.groupby("account_id").size().reset_index(name="churn_event_count")
    def pattern(n):
        if n == 1:
            return "1 event (no reactivation seen)"
        elif n == 2:
            return "2 events (1 reactivation cycle)"
        else:
            return "3+ events (repeat churner)"
    churn_counts["pattern"] = churn_counts["churn_event_count"].apply(pattern)
    pat_counts = churn_counts["pattern"].value_counts().reset_index()
    pat_counts.columns = ["pattern", "accounts"]
    fig = px.bar(pat_counts, x="pattern", y="accounts", title="Churn-Reactivation Pattern Distribution", template=PLOTLY_TEMPLATE)
    fig.update_traces(marker_color=COLORS["chart_seq"][:len(pat_counts)])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Churn rate by seat-count bucket")
    acc_seat = acc_f.copy()
    acc_seat["seat_bucket"] = pd.cut(acc_seat["seats"], bins=[0, 10, 30, 60, 1000],
                                      labels=["1-10 (Small)", "11-30 (Mid)", "31-60 (Large)", "60+ (Enterprise-scale)"])
    seat_churn = acc_seat.groupby("seat_bucket", observed=True)["churn_flag"].mean().reset_index()
    seat_churn["churn_flag"] *= 100
    fig = px.bar(seat_churn, x="seat_bucket", y="churn_flag", title="Churn Rate by Account Size (Seats)", template=PLOTLY_TEMPLATE)
    fig.update_traces(marker_color=COLORS["primary"])
    st.plotly_chart(fig, use_container_width=True)

# ---------------- SUPPORT IMPACT ----------------
with tab_support:
    st.markdown('<span class="section-tag">Support Workload, Satisfaction &amp; Churn</span>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        prio_order = ["urgent", "high", "medium", "low"]
        prio_summary = tickets_f.groupby("priority").agg(
            tickets=("ticket_id", "count"), avg_resolution=("resolution_time_hours", "mean")
        ).reindex(prio_order).reset_index()
        fig = px.bar(prio_summary, x="priority", y="avg_resolution", title="Avg. Resolution Time by Priority (hrs)",
                     template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["primary"])
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        tc = tickets_f.groupby("account_id").size().reset_index(name="ticket_count")
        acc_tc = acc_f.merge(tc, on="account_id", how="left")
        acc_tc["ticket_count"] = acc_tc["ticket_count"].fillna(0)
        acc_tc["bucket"] = pd.cut(acc_tc["ticket_count"], bins=[-1, 0, 2, 5, 1000],
                                   labels=["0 tickets", "1-2 tickets", "3-5 tickets", "6+ tickets"])
        bucket_churn = acc_tc.groupby("bucket", observed=True)["churn_flag"].mean().reset_index()
        bucket_churn["churn_flag"] *= 100
        fig = px.bar(bucket_churn, x="bucket", y="churn_flag", title="Churn Rate by Support Ticket Volume", template=PLOTLY_TEMPLATE)
        fig.update_traces(marker_color=COLORS["danger"])
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Satisfaction score vs. churn rate")
    sat = tickets_f.dropna(subset=["satisfaction_score"]).groupby("account_id")["satisfaction_score"].mean().reset_index()
    sat_acc = sat.merge(acc_f[["account_id", "churn_flag"]], on="account_id")
    sat_acc["bucket"] = pd.cut(sat_acc["satisfaction_score"], bins=[0, 3.5, 4.5, 5.01],
                                labels=["Low (<3.5)", "Medium (3.5-4.5)", "High (4.5+)"])
    sat_bucket = sat_acc.groupby("bucket", observed=True)["churn_flag"].mean().reset_index()
    sat_bucket["churn_flag"] *= 100
    fig = px.bar(sat_bucket, x="bucket", y="churn_flag", title="Churn Rate by Avg. Satisfaction Bucket", template=PLOTLY_TEMPLATE)
    fig.update_traces(marker_color=COLORS["warning"])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Support burden by industry")
    ind_tickets = tickets_f.merge(acc_f[["account_id", "industry"]], on="account_id")
    ind_support = ind_tickets.groupby("industry").agg(
        tickets=("ticket_id", "count"), avg_satisfaction=("satisfaction_score", "mean")
    ).reset_index()
    accounts_per_ind = acc_f.groupby("industry").size().rename("accounts")
    ind_support = ind_support.merge(accounts_per_ind, on="industry")
    ind_support["tickets_per_account"] = (ind_support["tickets"] / ind_support["accounts"]).round(2)
    fig = px.bar(ind_support.sort_values("tickets_per_account"), x="tickets_per_account", y="industry", orientation="h",
                 title="Support Tickets per Account by Industry", template=PLOTLY_TEMPLATE)
    fig.update_traces(marker_color=COLORS["primary"])
    st.plotly_chart(fig, use_container_width=True)

st.write("")
st.markdown(
    f"""<div style="text-align:center; color:{COLORS['muted']}; font-size:0.78rem; padding-top:10px;
    border-top:1px solid {COLORS['border']};">
    RavenStack SaaS Analytics — portfolio project for Manatal interview prep · dataset by River @ Rivalytics (Kaggle)
    </div>""",
    unsafe_allow_html=True,
)
