-- ============================================================================
-- 03_revenue_and_plan_funnel.sql
-- Revenue (MRR/ARR), Plan Tier Movement & Upgrade/Downgrade Funnel Analysis
-- Maps to JD: "account usage" independent analysis + suggested project
-- "Plan tier upgrade funnel by industry" / "Revenue cohort analysis by referral channel"
-- ============================================================================

-- Q3.1 Active MRR & ARR by current plan tier
WITH latest_sub AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
)
SELECT
    l.plan_tier,
    COUNT(*)                                    AS active_accounts,
    SUM(l.mrr_amount)                             AS total_mrr,
    SUM(l.arr_amount)                             AS total_arr,
    ROUND(AVG(l.mrr_amount), 0)                    AS avg_mrr_per_account
FROM latest_sub l
JOIN accounts a ON a.account_id = l.account_id
WHERE l.rn = 1 AND a.churn_flag = 0
GROUP BY l.plan_tier
ORDER BY total_mrr DESC;


-- Q3.2 Upgrade / downgrade funnel: of all subscriptions, what fraction moved,
-- and what's the net (upgrades - downgrades) plan-tier momentum?
SELECT
    SUM(upgrade_flag)                                          AS total_upgrades,
    SUM(downgrade_flag)                                          AS total_downgrades,
    SUM(upgrade_flag) - SUM(downgrade_flag)                       AS net_upward_movement,
    COUNT(*)                                                       AS total_subscriptions,
    ROUND(100.0 * SUM(upgrade_flag) / COUNT(*), 1)                  AS pct_subs_upgraded,
    ROUND(100.0 * SUM(downgrade_flag) / COUNT(*), 1)                 AS pct_subs_downgraded
FROM subscriptions;


-- Q3.3 Upgrade/downgrade rates by industry (maps to README's suggested project:
-- "Plan tier upgrade funnel by industry")
SELECT
    a.industry,
    COUNT(*)                                             AS subscriptions,
    SUM(s.upgrade_flag)                                     AS upgrades,
    SUM(s.downgrade_flag)                                    AS downgrades,
    ROUND(100.0 * SUM(s.upgrade_flag) / COUNT(*), 1)          AS upgrade_rate_pct,
    ROUND(100.0 * SUM(s.downgrade_flag) / COUNT(*), 1)         AS downgrade_rate_pct
FROM subscriptions s
JOIN accounts a ON a.account_id = s.account_id
GROUP BY a.industry
ORDER BY upgrade_rate_pct DESC;


-- Q3.4 Revenue cohort analysis by referral source (maps to README's suggested
-- project: "Revenue cohort analysis by referral channel") — which acquisition
-- channel brings in the highest-value, most retained accounts?
WITH latest_sub AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
)
SELECT
    a.referral_source,
    COUNT(DISTINCT a.account_id)                                     AS accounts,
    ROUND(100.0 * SUM(CASE WHEN a.churn_flag = 1 THEN 1 ELSE 0 END) /
          COUNT(DISTINCT a.account_id), 1)                            AS churn_rate_pct,
    ROUND(SUM(CASE WHEN a.churn_flag = 0 THEN l.mrr_amount ELSE 0 END), 0) AS active_mrr,
    ROUND(AVG(CASE WHEN a.churn_flag = 0 THEN l.mrr_amount END), 0)      AS avg_active_mrr_per_account
FROM accounts a
JOIN latest_sub l ON l.account_id = a.account_id AND l.rn = 1
GROUP BY a.referral_source
ORDER BY active_mrr DESC;


-- Q3.5 Billing frequency mix and its relationship to churn — do annual-billed
-- accounts churn less than monthly-billed ones? (a classic SaaS retention lever)
WITH latest_sub AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
)
SELECT
    l.billing_frequency,
    COUNT(*)                                            AS accounts,
    SUM(a.churn_flag)                                     AS churned,
    ROUND(100.0 * SUM(a.churn_flag) / COUNT(*), 1)          AS churn_rate_pct,
    ROUND(AVG(l.mrr_amount), 0)                             AS avg_mrr
FROM latest_sub l
JOIN accounts a ON a.account_id = l.account_id
WHERE l.rn = 1
GROUP BY l.billing_frequency;


-- Q3.6 Trial-to-paid conversion: of accounts that started as a trial
-- (accounts.is_trial reflects current state, so we check subscription
-- history for accounts that had an is_trial=1 subscription and later a paid one)
WITH trial_accounts AS (
    SELECT DISTINCT account_id FROM subscriptions WHERE is_trial = 1
),
converted AS (
    SELECT DISTINCT account_id FROM subscriptions WHERE is_trial = 0
)
SELECT
    COUNT(DISTINCT t.account_id)                                          AS ever_trialed,
    COUNT(DISTINCT CASE WHEN c.account_id IS NOT NULL THEN t.account_id END) AS converted_to_paid,
    ROUND(100.0 * COUNT(DISTINCT CASE WHEN c.account_id IS NOT NULL THEN t.account_id END)
          / COUNT(DISTINCT t.account_id), 1)                                  AS trial_to_paid_conversion_pct
FROM trial_accounts t
LEFT JOIN converted c ON c.account_id = t.account_id;
