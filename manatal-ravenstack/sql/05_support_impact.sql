-- ============================================================================
-- 05_support_impact.sql
-- Support Workload & Its Relationship to Satisfaction and Churn
-- Maps to JD independent-analysis pillar + README's suggested project:
-- "Support workload forecasting"
-- ============================================================================

-- Q5.1 Support ticket volume and resolution performance by priority
SELECT
    priority,
    COUNT(*)                                                AS tickets,
    ROUND(AVG(resolution_time_hours), 1)                      AS avg_resolution_hours,
    ROUND(AVG(first_response_time_minutes), 1)                 AS avg_first_response_minutes,
    ROUND(AVG(satisfaction_score), 2)                            AS avg_satisfaction,
    SUM(escalation_flag)                                          AS escalations,
    ROUND(100.0 * SUM(escalation_flag) / COUNT(*), 1)              AS escalation_rate_pct
FROM support_tickets
GROUP BY priority
ORDER BY CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END;


-- Q5.2 Does support ticket volume per account correlate with churn?
-- (a classic "support load as a churn early-warning signal" analysis)
WITH ticket_counts AS (
    SELECT account_id, COUNT(*) AS ticket_count, AVG(satisfaction_score) AS avg_satisfaction
    FROM support_tickets
    GROUP BY account_id
)
SELECT
    CASE
        WHEN tc.ticket_count IS NULL THEN '0 tickets'
        WHEN tc.ticket_count <= 2 THEN '1-2 tickets'
        WHEN tc.ticket_count <= 5 THEN '3-5 tickets'
        ELSE '6+ tickets'
    END AS ticket_volume_bucket,
    COUNT(DISTINCT a.account_id)                          AS accounts,
    SUM(a.churn_flag)                                        AS churned,
    ROUND(100.0 * SUM(a.churn_flag) / COUNT(DISTINCT a.account_id), 1) AS churn_rate_pct
FROM accounts a
LEFT JOIN ticket_counts tc ON tc.account_id = a.account_id
GROUP BY ticket_volume_bucket
ORDER BY churn_rate_pct DESC;


-- Q5.3 Satisfaction score distribution vs. churn — do accounts with lower
-- average satisfaction actually churn more? (validates whether CSAT is a
-- useful leading indicator here)
WITH acct_satisfaction AS (
    SELECT account_id, AVG(satisfaction_score) AS avg_satisfaction
    FROM support_tickets
    WHERE satisfaction_score IS NOT NULL
    GROUP BY account_id
)
SELECT
    CASE
        WHEN avg_satisfaction < 3.5 THEN 'Low (<3.5)'
        WHEN avg_satisfaction < 4.5 THEN 'Medium (3.5-4.5)'
        ELSE 'High (4.5+)'
    END AS satisfaction_bucket,
    COUNT(DISTINCT s.account_id)                            AS accounts,
    SUM(a.churn_flag)                                          AS churned,
    ROUND(100.0 * SUM(a.churn_flag) / COUNT(DISTINCT s.account_id), 1) AS churn_rate_pct
FROM acct_satisfaction s
JOIN accounts a ON a.account_id = s.account_id
GROUP BY satisfaction_bucket
ORDER BY churn_rate_pct DESC;


-- Q5.4 Escalations: what fraction of escalated tickets belong to accounts
-- that eventually churned, vs. non-escalated tickets?
SELECT
    t.escalation_flag,
    COUNT(DISTINCT t.account_id)                             AS accounts,
    SUM(DISTINCT_churn.churn_flag)                             AS churned_accounts
FROM support_tickets t
JOIN (SELECT DISTINCT account_id, churn_flag FROM accounts) DISTINCT_churn
    ON DISTINCT_churn.account_id = t.account_id
GROUP BY t.escalation_flag;


-- Q5.5 Monthly support ticket volume trend — for workload forecasting
SELECT
    strftime('%Y-%m', submitted_at)  AS ticket_month,
    COUNT(*)                          AS tickets_submitted,
    ROUND(AVG(resolution_time_hours), 1) AS avg_resolution_hours
FROM support_tickets
GROUP BY ticket_month
ORDER BY ticket_month;


-- Q5.6 Industry-level support burden — which verticals generate
-- disproportionate support load relative to their account count?
SELECT
    a.industry,
    COUNT(DISTINCT a.account_id)                                    AS accounts,
    COUNT(t.ticket_id)                                                AS tickets,
    ROUND(1.0 * COUNT(t.ticket_id) / COUNT(DISTINCT a.account_id), 2)  AS tickets_per_account,
    ROUND(AVG(t.satisfaction_score), 2)                                 AS avg_satisfaction
FROM accounts a
LEFT JOIN support_tickets t ON t.account_id = a.account_id
GROUP BY a.industry
ORDER BY tickets_per_account DESC;
