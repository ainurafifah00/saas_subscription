# Interview Prep — RavenStack Project (Manatal Product Analyst)

This is your **second** portfolio piece for the same interview. Use it alongside (not instead
of) `manatal-product-analytics/docs/INTERVIEW_PREP.md`. The two projects tell a complementary
story if you present them together: one shows you can **design a data structure from scratch**
(the Manatal-specific project), the other shows you can **inherit someone else's data, question
it, and find real problems in it** (this one). That range — "I can build the schema, and I can
also be handed a messy one and make it trustworthy" — is exactly what the JD is asking for.

---

## 1. The 45-second pitch

> "For a second piece, I wanted to show the other half of the job — not designing a schema from
> scratch, but inheriting one and making it trustworthy. I found a public multi-table SaaS
> dataset on Kaggle, profiled every table before writing a single analysis query, and actually
> found a real data-quality anomaly — 35 accounts flagged as churned with no supporting history
> and an active subscription. I documented the investigation and built the SQL and dashboard
> around the *validated* version of the data, not just the numbers at face value."

This pitch works well as a **follow-up** if the Manatal project's Q&A goes well and they ask "do
you have anything else?" — it shows range without you having to say "I have more."

---

## 2. Lead with the data-quality finding — it's your strongest asset here

Don't bury this in the dashboard tour — it's the most senior-feeling thing in either project.
Most portfolio projects show a person who can write a GROUP BY. This shows a person who
**doesn't trust a column's face value until they've checked it** — which is precisely what "own
the data structure... ensure accuracy, integrity, and timeliness" means in practice.

Suggested delivery, if they ask "tell me about a time you found a data quality issue" (a very
likely behavioral question for this exact role):

> "It's actually in this project. The dataset has a `churn_flag` column on the accounts table
> that's supposed to mean 'currently churned.' I cross-checked it against the churn_events log
> and found 35 accounts marked as churned with zero churn history *and* a currently active
> subscription — which is a contradiction; you can't be flagged churned with no record of when
> or why, while still paying. I traced it by reconciling every account into buckets — expected
> churned, expected reactivated, never churned, and 'anomaly' — and the 35 fell cleanly into
> their own bucket once I did that. In a real job I'd take that straight to Engineering with the
> specific account IDs rather than just flagging 'something's off somewhere.'"

That last sentence matters — it shows you'd escalate precisely, not vaguely.

---

## 3. How to walk through the dashboard

1. **Overview** — quick, 10 seconds.
2. **Data Quality** — spend the most time here. Show the anomaly count, the reconciliation bar
   chart, and be ready to explain *why* the 277-account "reactivated" bucket is NOT an anomaly
   (it's fully explained by active subscriptions) while the 35-account bucket IS. That
   distinction — knowing which anomalies are real vs. which are just an unfamiliar-but-valid
   pattern — is the actual skill being tested.
3. **Feature Adoption** — point out the beta-vs-GA error rate comparison; this is the kind of
   pre-launch go/no-go signal a Product Analyst would generate.
4. **Revenue & Plans** — the referral-source revenue/churn comparison directly answers "which
   acquisition channel is actually worth the CAC" — a favorite SaaS PM question.
5. **Churn & Retention** — the reactivation-pattern chart is a nice, less-common metric (most
   churn dashboards ignore win-back cycles entirely).
6. **Support Impact** — ticket-volume-vs-churn bucket chart is your "early warning signal"
   story.

---

## 4. Likely questions & how to answer them

### "Why use someone else's dataset instead of building your own again?"
*"I already had a self-built version for this interview [gesture at the first project]. I
wanted this one to test a different skill — most of the job isn't designing a schema on day
one, it's inheriting an existing one from Engineering and figuring out whether you can trust
it. So I deliberately treated this dataset as something I didn't build and had to verify."*

### "How did you decide the 35 accounts were a real anomaly and not just, say, edge cases the
### dataset generator intentionally created?"
Be honest and precise: *"I can't fully rule that out — I don't have access to the generator's
source code, and the README does mention 'edge cases' like reactivations and mid-cycle changes
were deliberately included. But I distinguished it from the *other* apparent mismatch — 277
accounts where churn_flag=False despite having churn history — by checking whether each group
had a coherent explanation. The 277 all have an active subscription today, so 'reactivated
customer, flag correctly says not-currently-churned' is a fully consistent story. The 35 don't
have that: no churn history at all, yet flagged churned, while also currently active. There's no
consistent narrative that makes that combination correct. That's the bar I'd use in a real job
too — not 'this looks weird,' but 'I can't construct any consistent story for why this is
correct.'"*

### "What would you actually do with this finding if it were real production data?"
Concrete next steps, in order: (1) pull the exact 35 account IDs and check application/audit
logs for what actually happened to them; (2) check whether the anomaly clusters around a
particular time window or code deploy (a systemic bug vs. random noise); (3) loop in Engineering
with the specific IDs and reproduction query rather than a vague "something's off"; (4) until
resolved, exclude those 35 from churn-rate reporting with a documented caveat, rather than
silently including them and skewing the churn rate.

### "Walk me through the accounts.plan_tier vs subscriptions.plan_tier distinction — why does it
### matter?"
*"accounts.plan_tier is fixed at signup — it's the plan they started on. subscriptions.plan_tier
changes every billing cycle as accounts upgrade or downgrade. If you want 'what plan is this
account on right now,' you have to go to the latest subscription record, not the accounts table
— I verified empirically that these disagree for two-thirds of accounts, so this isn't a rare
edge case, it's the norm. I built every 'current plan' view in this project off the latest
subscription row using a window function, specifically to avoid that trap."*

### "What's a limitation of this analysis you'd flag yourself, unprompted?"
Good answer: *"The satisfaction_score field only ranges from 3–5 in this data even though the
data dictionary describes it as 1–5 — I noticed that during profiling but don't have a way to
know if that's intentional (maybe very low scores get escalated/handled differently and never
recorded as a plain ticket close) or a generation quirk. I'd flag it rather than assume either
way."* (This is true — worth actually checking before the interview if you want to cite it
confidently; see §5.)

---

## 5. Facts to have ready (pulled directly from profiling this exact data)

- 500 accounts, 5,000 subscriptions (~10 per account on average), 25,000 feature usage events
  across 40 features, 2,000 support tickets, 600 churn events.
- Overall churn rate: 22.0% (110 of 500 accounts currently flagged churned).
- `satisfaction_score` is null on 825/2,000 tickets (41.25%) — worth asking in an interview
  setting *why* so many tickets have no score, since that's a large enough gap to bias any CSAT
  metric built on it.
- `satisfaction_score`, where present, ranges 3–5, not the 1–5 the data dictionary describes —
  a minor documentation/data mismatch worth naming if asked about limitations.
- Referential integrity is clean — 0 orphaned foreign keys across all 4 relationships.
- 175 accounts have more than one churn_events row (churn → reactivate → sometimes churn again).

---

## 6. Smart questions to ask them (dataset-specific angle)

- "When Engineering hands off a new event or table to Product, is there a standard validation
  step today, or would building one be part of this role?"
- "How does Manatal currently handle a 'current state' field (like a plan or status flag) that
  can drift out of sync with the event log it's derived from — is that a known pattern here?"

---

## 7. One thing to avoid

Don't present this project as "look how many charts I made." Present it as "look at the process
I used before I trusted the data enough to chart it." The dashboard is the artifact; the
profiling and reconciliation work is the actual demonstration of Product Analyst judgment.
