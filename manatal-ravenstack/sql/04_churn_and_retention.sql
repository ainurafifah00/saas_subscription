-- ============================================================================
-- 04_churn_and_retention.sql
-- Churn Drivers, Reactivation & Retention Cohort Analysis
-- Maps to JD: "retention analysis" reporting pillar + "understanding user
-- behavior" independent analysis
-- ============================================================================

-- Q4.1 Churn reason breakdown, with average refund issued per reason
SELECT
    reason_code,
    COUNT(*)                                    AS churn_events,
    ROUND(AVG(refund_amount_usd), 2)              AS avg_refund_usd,
    SUM(CASE WHEN refund_amount_usd > 0 THEN 1 ELSE 0 END) AS events_with_refund,
    SUM(is_reactivation)                            AS were_reactivations
FROM churn_events
GROUP BY reason_code
ORDER BY churn_events DESC;


-- Q4.2 Did a preceding upgrade or downgrade (within 90 days, per the flag)
-- predict churn reason? E.g. do "pricing" churns disproportionately follow
-- an upgrade (price shock), while "features" churns follow a downgrade?
SELECT
    reason_code,
    SUM(preceding_upgrade_flag)                                     AS preceded_by_upgrade,
    SUM(preceding_downgrade_flag)                                    AS preceded_by_downgrade,
    COUNT(*) - SUM(preceding_upgrade_flag) - SUM(preceding_downgrade_flag) AS no_preceding_change,
    ROUND(100.0 * SUM(preceding_upgrade_flag) / COUNT(*), 1)           AS pct_preceded_by_upgrade
FROM churn_events
GROUP BY reason_code
ORDER BY pct_preceded_by_upgrade DESC;


-- Q4.3 Reactivation analysis: of accounts that churned, what % came back at
-- least once, and how many churn-reactivate cycles do repeat accounts show?
WITH churn_counts AS (
    SELECT account_id, COUNT(*) AS churn_event_count, SUM(is_reactivation) AS reactivation_count
    FROM churn_events
    GROUP BY account_id
)
SELECT
    CASE
        WHEN churn_event_count = 1 THEN '1 churn event (no reactivation seen)'
        WHEN churn_event_count = 2 THEN '2 churn events (1 reactivation cycle)'
        WHEN churn_event_count >= 3 THEN '3+ churn events (repeat churner)'
    END AS churn_pattern,
    COUNT(*)                    AS accounts
FROM churn_counts
GROUP BY churn_pattern
ORDER BY accounts DESC;


-- Q4.4 Churn rate by industry and current plan tier (cross-tab) — identifies
-- the highest-risk segment combinations
WITH latest_sub AS (
    SELECT s.*, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
)
SELECT
    a.industry,
    l.plan_tier                                          AS current_plan,
    COUNT(*)                                              AS accounts,
    SUM(a.churn_flag)                                       AS churned,
    ROUND(100.0 * SUM(a.churn_flag) / COUNT(*), 1)           AS churn_rate_pct
FROM accounts a
JOIN latest_sub l ON l.account_id = a.account_id AND l.rn = 1
GROUP BY a.industry, l.plan_tier
HAVING accounts >= 5
ORDER BY churn_rate_pct DESC
LIMIT 15;


-- Q4.5 Signup-month cohort churn — of accounts that signed up in month X,
-- what % have churned as of today? (a simple logo-retention-by-cohort view)
SELECT
    strftime('%Y-%m', signup_date)                       AS signup_month,
    COUNT(*)                                               AS accounts_in_cohort,
    SUM(churn_flag)                                          AS churned,
    ROUND(100.0 - 100.0 * SUM(churn_flag) / COUNT(*), 1)      AS logo_retention_pct
FROM accounts
GROUP BY signup_month
ORDER BY signup_month;


-- Q4.6 Seats vs. churn — does account size (seat count) correlate with churn risk?
-- Useful because larger accounts are typically stickier / harder to fully replace.
SELECT
    CASE
        WHEN seats <= 10 THEN '1-10 seats (Small)'
        WHEN seats <= 30 THEN '11-30 seats (Mid)'
        WHEN seats <= 60 THEN '31-60 seats (Large)'
        ELSE '60+ seats (Enterprise-scale)'
    END AS seat_bucket,
    COUNT(*)                                    AS accounts,
    SUM(churn_flag)                               AS churned,
    ROUND(100.0 * SUM(churn_flag) / COUNT(*), 1)    AS churn_rate_pct
FROM accounts
GROUP BY seat_bucket
ORDER BY churn_rate_pct DESC;
