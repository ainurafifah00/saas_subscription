-- ============================================================================
-- 02_feature_adoption.sql
-- Feature Usage & Beta Feature Adoption Analysis
-- Maps to JD: "Produce comprehensive reports across various topics within
-- Product, including but not limited to feature usage..."
-- ============================================================================

-- Q2.1 Feature usage volume & breadth across all 40 tracked features
SELECT
    feature_name,
    COUNT(*)                                          AS total_events,
    COUNT(DISTINCT subscription_id)                    AS unique_subscriptions,
    SUM(usage_count)                                     AS total_usage_count,
    ROUND(AVG(usage_duration_secs) / 60.0, 1)             AS avg_duration_minutes,
    SUM(error_count)                                      AS total_errors
FROM feature_usage
GROUP BY feature_name
ORDER BY total_events DESC
LIMIT 15;


-- Q2.2 Beta feature adoption: usage volume, error rate, and engagement time
-- vs. general-availability (GA) features — useful for a pre-launch go/no-go call.
SELECT
    is_beta_feature,
    COUNT(*)                                              AS events,
    COUNT(DISTINCT feature_name)                            AS distinct_features,
    ROUND(AVG(usage_duration_secs) / 60.0, 1)                AS avg_duration_minutes,
    ROUND(1.0 * SUM(error_count) / COUNT(*), 3)               AS errors_per_event,
    ROUND(100.0 * SUM(CASE WHEN error_count > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_events_with_errors
FROM feature_usage
GROUP BY is_beta_feature;


-- Q2.3 Feature adoption by plan tier (using CURRENT plan, not accounts.plan_tier —
-- see 01_data_quality_and_overview.sql Q1.4 for why that distinction matters)
WITH latest_sub AS (
    SELECT s.subscription_id, s.account_id, s.plan_tier,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
),
current_plan AS (
    SELECT account_id, plan_tier AS current_plan_tier FROM latest_sub WHERE rn = 1
)
SELECT
    cp.current_plan_tier,
    COUNT(*)                                     AS usage_events,
    COUNT(DISTINCT f.feature_name)                 AS distinct_features_used,
    ROUND(AVG(f.usage_duration_secs) / 60.0, 1)     AS avg_duration_minutes
FROM feature_usage f
JOIN subscriptions s ON s.subscription_id = f.subscription_id
JOIN current_plan cp ON cp.account_id = s.account_id
GROUP BY cp.current_plan_tier
ORDER BY usage_events DESC;


-- Q2.4 Feature usage errors by feature — a "quality watchlist" ranking features
-- by error rate (min 20 events, to avoid noise from low-volume features)
SELECT
    feature_name,
    COUNT(*)                                          AS total_events,
    SUM(error_count)                                    AS total_errors,
    ROUND(1.0 * SUM(error_count) / COUNT(*), 3)          AS errors_per_event
FROM feature_usage
GROUP BY feature_name
HAVING COUNT(*) >= 20
ORDER BY errors_per_event DESC
LIMIT 10;


-- Q2.5 Monthly feature usage trend for top 5 features (by volume)
WITH top_features AS (
    SELECT feature_name FROM feature_usage
    GROUP BY feature_name ORDER BY COUNT(*) DESC LIMIT 5
)
SELECT
    strftime('%Y-%m', usage_date)   AS usage_month,
    feature_name,
    COUNT(*)                         AS events
FROM feature_usage
WHERE feature_name IN (SELECT feature_name FROM top_features)
GROUP BY usage_month, feature_name
ORDER BY usage_month, events DESC;


-- Q2.6 Industry-level feature engagement — which SaaS vertical uses the
-- product most heavily (events per active subscription)?
WITH latest_sub AS (
    SELECT s.subscription_id, s.account_id,
           ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY start_date DESC) AS rn
    FROM subscriptions s
)
SELECT
    a.industry,
    COUNT(f.usage_id)                                                  AS total_events,
    COUNT(DISTINCT a.account_id)                                        AS accounts,
    ROUND(1.0 * COUNT(f.usage_id) / COUNT(DISTINCT a.account_id), 1)      AS events_per_account
FROM accounts a
JOIN subscriptions s ON s.account_id = a.account_id
JOIN feature_usage f ON f.subscription_id = s.subscription_id
GROUP BY a.industry
ORDER BY events_per_account DESC;
