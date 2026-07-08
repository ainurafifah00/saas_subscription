# RavenStack SaaS Analytics — Portfolio Project (Manatal Interview)

A companion analytics project for the **Product Analyst** interview at **Manatal**, this time
built on a **real public dataset** rather than self-generated data: the "RavenStack" synthetic
SaaS dataset by **River @ Rivalytics** on Kaggle
([source](https://www.kaggle.com/datasets/rivalytics/saas-subscription-and-churn-analytics-dataset)).

This project is deliberately different in character from the companion `manatal-product-analytics`
project: instead of designing the schema myself, I did **exploratory data analysis and data-quality
investigation** on someone else's dataset — closer to what a first few weeks on the job would
actually look like when inheriting an existing data structure.

> 📄 For interview talking points and how to present this project, see
> **[docs/INTERVIEW_PREP.md](docs/INTERVIEW_PREP.md)**.
> 📄 The original dataset author's data dictionary is preserved at
> **[docs/RAVENSTACK_SOURCE_README.md](docs/RAVENSTACK_SOURCE_README.md)**.

---

## 1. Attribution

Per the dataset's license terms: **credit to River @ Rivalytics** for the original RavenStack
dataset (Kaggle, MIT-like license, fully synthetic, no PII). This project adds SQL analysis, a
Streamlit dashboard, and a documented data-quality investigation on top of that dataset — it
does not claim authorship of the underlying data.

---

## 2. Why this project, and how it maps to the job description

| JD requirement | What's in this project |
|---|---|
| "Take complete ownership of the data structure ... Ensure the accuracy, integrity, and timeliness of data, implementing measures to identify and rectify any anomalies" | `sql/01_data_quality_and_overview.sql` — a genuine data-quality investigation that found real anomalies in this dataset (see §4 below) |
| "Produce comprehensive reports ... feature usage, usage funnels, retention analysis" | `sql/02_feature_adoption.sql`, `sql/04_churn_and_retention.sql` |
| "Conduct independent analyses ... account usage" | `sql/03_revenue_and_plan_funnel.sql` — revenue cohorts, upgrade/downgrade funnels, referral-channel ROI |
| "Utilize data visualization tools to present information ... for stakeholders" | `dashboard/app.py` — 6-tab Streamlit dashboard, same Manatal-inspired visual system as the companion project |
| "Proficiency in SQL & Python ... Excel" | SQL analysis layer + pandas for the dashboard/validation layer; source data is plain CSV, openable directly in Excel |

This project also directly completes several of the "Suggested Projects" listed in the
dataset's own README: **feature adoption tracking during beta phases**, **support workload
forecasting**, **revenue cohort analysis by referral channel**, and **plan tier upgrade funnel
by industry**.

---

## 3. Project structure

```
manatal-ravenstack/
├── data/
│   ├── build_database.py            # builds ravenstack.db from the 5 source CSVs
│   ├── ravenstack.db                # SQLite database (generated)
│   └── ravenstack_*.csv             # original source data (5 files, from Kaggle)
├── sql/
│   ├── 01_data_quality_and_overview.sql
│   ├── 02_feature_adoption.sql
│   ├── 03_revenue_and_plan_funnel.sql
│   ├── 04_churn_and_retention.sql
│   └── 05_support_impact.sql
├── dashboard/
│   └── app.py                       # Streamlit dashboard
├── docs/
│   ├── INTERVIEW_PREP.md            # interview prep notes — read before the interview!
│   └── RAVENSTACK_SOURCE_README.md  # original dataset author's data dictionary
├── requirements.txt
└── README.md                        # this file
```

---

## 4. Data quality findings (the most interview-relevant part of this project)

Before writing any analysis query, I profiled all 5 tables and validated the referential
integrity and business-logic claims made in the dataset's own README. Two things stood out:

**Finding 1 — `accounts.plan_tier` vs. `subscriptions.plan_tier` are genuinely different fields.**
The data dictionary says `accounts.plan_tier` is the *initial* plan and `subscriptions.plan_tier`
is the plan *at time of billing*. I verified this empirically: 328 of 500 accounts (65.6%) have a
different value in `accounts.plan_tier` than in their most recent subscription record. **Any
"current plan mix" report must use the latest subscription record, not `accounts.plan_tier`** —
every query and dashboard chart in this project does this correctly via a `ROW_NUMBER() OVER
(PARTITION BY account_id ORDER BY start_date DESC)` pattern. Getting this wrong would silently
misclassify two-thirds of accounts in any plan-tier report — the kind of subtle bug that's easy
to ship and hard to notice without profiling first.

**Finding 2 — 35 accounts have a genuine data anomaly.** `accounts.churn_flag = True` should mean
"this account is currently churned." But 35 accounts are flagged `churn_flag = True` while
simultaneously (a) having **no corresponding row** in `churn_events`, and (b) holding a
**currently-active subscription** (no `end_date`). That's a logical contradiction — the account
claims to be both churned and actively subscribed, with no historical record explaining why.
See `sql/01_data_quality_and_overview.sql` Q1.2–Q1.3, or the **Data Quality tab** in the
dashboard, for the full reconciliation. (For contrast: 277 *other* accounts also have
`churn_flag = False` despite appearing in `churn_events` — but those are explained cleanly as
reactivations, since every one of them has an active subscription and a churn history. Only the
35 with *no* churn history are the real anomaly.)

I'd treat this exact kind of finding as a strong interview story — see
`docs/INTERVIEW_PREP.md` for how to present it.

---

## 5. How to run it

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Build the SQLite database from the source CSVs (already included in data/)
python data/build_database.py

# 3. Explore the SQL queries, e.g.:
sqlite3 data/ravenstack.db < sql/01_data_quality_and_overview.sql

# 4. Launch the dashboard
streamlit run dashboard/app.py
```

The dashboard opens at `http://localhost:8501`. Everything runs locally against the SQLite file
— no external services or API keys required.

---

## 6. The data model (as published by the dataset author)

| Table | Rows | Grain | Key columns |
|---|---|---|---|
| `accounts` | 500 | 1 per customer | `account_id`, `industry`, `country`, `plan_tier` (initial), `seats`, `is_trial`, `churn_flag` (current status) |
| `subscriptions` | 5,000 | 1 per billing-cycle subscription record (~10/account) | `subscription_id`, `account_id`, `plan_tier` (at billing time), `mrr_amount`, `arr_amount`, `upgrade_flag`, `downgrade_flag`, `billing_frequency` |
| `feature_usage` | 25,000 | 1 per feature-use event | `usage_id`, `subscription_id`, `feature_name` (40 features), `usage_count`, `usage_duration_secs`, `error_count`, `is_beta_feature` |
| `support_tickets` | 2,000 | 1 per support ticket | `ticket_id`, `account_id`, `priority`, `resolution_time_hours`, `satisfaction_score` (nullable), `escalation_flag` |
| `churn_events` | 600 | 1 per churn instance (accounts can churn/reactivate multiple times) | `churn_event_id`, `account_id`, `reason_code`, `refund_amount_usd`, `is_reactivation` |

Full column definitions are in `docs/RAVENSTACK_SOURCE_README.md` (the original author's data
dictionary, preserved as-is).

---

## 7. The dashboard

`dashboard/app.py` is a 6-tab Streamlit app, styled with the same Manatal-inspired visual system
(indigo `#4A3AFF` primary, navy sidebar, clean white surfaces) as the companion project:

1. **Overview** — growth, industry mix, MRR by current plan, geographic footprint
2. **Data Quality** — the anomaly investigation from §4, live-computed from the real data, plus
   referential-integrity and null-value audits
3. **Feature Adoption** — usage volume across 40 features, beta vs. GA error rates, monthly trend
4. **Revenue & Plans** — upgrade/downgrade funnel, revenue cohort by referral source, billing
   frequency vs. churn
5. **Churn & Retention** — churn reasons, reactivation patterns, cohort retention, seat-size vs. churn
6. **Support Impact** — resolution time by priority, ticket-volume vs. churn, CSAT vs. churn,
   support burden by industry

---

## 8. Honest disclosure

This dataset is itself synthetic (per its own README — generated with pandas/numpy/uuid to
simulate a "stealth-mode SaaS startup"), so none of the numbers reflect a real company. What's
real is the analytical process applied to it: profiling before analyzing, validating the data
dictionary's claims empirically rather than trusting them blindly, and surfacing a genuine
anomaly rather than assuming the data is clean. That process is the same regardless of whether
the underlying numbers are real or synthetic — which is the point of using it as an interview
demo.
