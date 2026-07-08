-- ============================================================================
-- 01_data_quality_and_overview.sql
-- RavenStack — Data Structure Ownership & Data Quality Checks
-- Maps to JD: "Take complete ownership of the data structure... Ensure the
-- accuracy, integrity, and timeliness of data, implementing measures to
-- identify and rectify any anomalies."
--
-- NOTE: These checks surfaced REAL findings in this dataset (not hypothetical) —
-- see docs/README.md section "Data quality findings" for the full writeup.
-- ============================================================================

-- Q1.1 Referential integrity check — orphan foreign keys (should return 0 rows each)
SELECT 'subscriptions->accounts' AS check_name, COUNT(*) AS orphan_rows
FROM subscriptions s LEFT JOIN accounts a ON a.account_id = s.account_id WHERE a.account_id IS NULL
UNION ALL
SELECT 'feature_usage->subscriptions', COUNT(*)
FROM feature_usage f LEFT JOIN subscriptions s ON s.subscription_id = f.subscription_id WHERE s.subscription_id IS NULL
UNION ALL
SELECT 'support_tickets->accounts', COUNT(*)
FROM support_tickets t LEFT JOIN accounts a ON a.account_id = t.account_id WHERE a.account_id IS NULL
UNION ALL
SELECT 'churn_events->accounts', COUNT(*)
FROM churn_events c LEFT JOIN accounts a ON a.account_id = c.account_id WHERE a.account_id IS NULL;


-- Q1.2 ANOMALY: accounts flagged churn_flag = TRUE with no supporting churn_events
-- record AND a currently-active subscription (end_date IS NULL).
-- This is a genuine logical contradiction: the account claims to be churned,
-- but has no churn history AND an active, non-ended subscription right now.
-- This is exactly the kind of anomaly a Product Analyst would flag to Engineering.
WITH active_sub_accounts AS (
    SELECT DISTINCT account_id FROM subscriptions WHERE end_date IS NULL
),
accounts_with_churn_event AS (
    SELECT DISTINCT account_id FROM churn_events
)
SELECT a.account_id, a.account_name, a.churn_flag, a.plan_tier
FROM accounts a
JOIN active_sub_accounts s ON s.account_id = a.account_id
WHERE a.churn_flag = 1
  AND a.account_id NOT IN (SELECT account_id FROM accounts_with_churn_event)
ORDER BY a.account_id;


-- Q1.3 Reconciliation: accounts.churn_flag ("currently churned") vs. presence in
-- churn_events (historical log — an account can churn, reactivate, and be active
-- again). This query classifies every account into a clear reconciliation bucket.
WITH has_active_sub AS (
    SELECT DISTINCT account_id FROM subscriptions WHERE end_date IS NULL
),
has_churn_event AS (
    SELECT DISTINCT account_id FROM churn_events
)
SELECT
    CASE
        WHEN a.churn_flag = 1 AND ce.account_id IS NOT NULL THEN 'Churned, with history (expected)'
        WHEN a.churn_flag = 0 AND ce.account_id IS NOT NULL AND s.account_id IS NOT NULL
            THEN 'Reactivated (has churn history but currently active) (expected)'
        WHEN a.churn_flag = 1 AND ce.account_id IS NULL AND s.account_id IS NOT NULL
            THEN 'ANOMALY: flagged churned, no history, active subscription'
        WHEN a.churn_flag = 0 AND ce.account_id IS NULL THEN 'Never churned (expected)'
        ELSE 'Other / needs review'
    END AS reconciliation_bucket,
    COUNT(*) AS accounts
FROM accounts a
LEFT JOIN has_churn_event ce ON ce.account_id = a.account_id
LEFT JOIN has_active_sub s ON s.account_id = a.account_id
GROUP BY reconciliation_bucket
ORDER BY accounts DESC;


-- Q1.4 accounts.plan_tier ("initial plan") vs. most recent subscription's plan_tier
-- ("current plan") — these are DIFFERENT fields by design per the data dictionary,
-- but any report showing "current plan mix" must use the latest subscription,
-- NOT accounts.plan_tier. This query demonstrates why, and produces the correct
-- "current plan" view.
WITH latest_sub AS (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
)
SELECT
    a.plan_tier AS initial_plan_tier,
    l.plan_tier AS current_plan_tier,
    COUNT(*) AS accounts
FROM accounts a
JOIN latest_sub l ON l.account_id = a.account_id AND l.rn = 1
GROUP BY a.plan_tier, l.plan_tier
ORDER BY accounts DESC;


-- Q1.5 Business overview KPIs (a snapshot a Head of Product would want weekly)
WITH latest_sub AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
),
current_state AS (
    SELECT a.account_id, a.churn_flag, l.mrr_amount, l.plan_tier AS current_plan
    FROM accounts a JOIN latest_sub l ON l.account_id = a.account_id AND l.rn = 1
)
SELECT
    (SELECT COUNT(*) FROM accounts)                                        AS total_accounts,
    (SELECT COUNT(*) FROM accounts WHERE churn_flag = 0)                    AS active_accounts,
    ROUND(100.0 * (SELECT COUNT(*) FROM accounts WHERE churn_flag = 1) /
          (SELECT COUNT(*) FROM accounts), 1)                                AS overall_churn_rate_pct,
    ROUND((SELECT SUM(mrr_amount) FROM current_state WHERE churn_flag = 0), 0) AS active_mrr,
    (SELECT COUNT(*) FROM support_tickets)                                   AS total_tickets,
    ROUND((SELECT AVG(satisfaction_score) FROM support_tickets), 2)          AS avg_satisfaction_score,
    (SELECT COUNT(DISTINCT feature_name) FROM feature_usage)                 AS distinct_features_tracked;


-- Q1.6 Null / missing-value audit across key nullable fields
SELECT 'support_tickets.satisfaction_score' AS field,
       SUM(CASE WHEN satisfaction_score IS NULL THEN 1 ELSE 0 END) AS nulls,
       COUNT(*) AS total_rows,
       ROUND(100.0 * SUM(CASE WHEN satisfaction_score IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS null_pct
FROM support_tickets
UNION ALL
SELECT 'churn_events.feedback_text',
       SUM(CASE WHEN feedback_text IS NULL OR feedback_text = '' THEN 1 ELSE 0 END),
       COUNT(*),
       ROUND(100.0 * SUM(CASE WHEN feedback_text IS NULL OR feedback_text = '' THEN 1 ELSE 0 END) / COUNT(*), 1)
FROM churn_events
UNION ALL
SELECT 'subscriptions.end_date (active subs)',
       SUM(CASE WHEN end_date IS NULL THEN 1 ELSE 0 END),
       COUNT(*),
       ROUND(100.0 * SUM(CASE WHEN end_date IS NULL THEN 1 ELSE 0 END) / COUNT(*), 1)
FROM subscriptions;
