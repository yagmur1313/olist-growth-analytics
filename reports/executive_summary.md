# Executive summary: Olist growth health check

**Period:** Jan 2017 – Aug 2018 · **Data:** 97,905 orders, 94,703 customers, R$15.7M GMV

## Situation
GMV grew **+140%** year over year (Jan–Aug). The metric tree shows that almost all of this came from **new customers (+136%)**. Orders per customer and AOV were flat. Returning customers account for only **2.4% of orders**.

## Complication
- Only **2.0%** of first-time buyers order again within 180 days (1.3% within 90 days). Every monthly cohort shows the same flat curve.
- 78% of first-time buyers have a good experience (on-time delivery, 4–5★ review), but only **1 in 100** buys again within 90 days. The leak sits *after* the experience, in lifecycle and re-engagement, not in operations.
- Late deliveries collapse reviews (4.3★ → 2.1★ when 4–7 days late). They spiked to **12% (Nov '17)** and **19% (Mar '18)** of orders, and to 12% in BA and RJ. Because new customers drive growth, these public reviews are a risk to acquisition.
- Late delivery's effect on *repeat purchase* is directionally negative but **not statistically significant** (OR 0.80, p = 0.08). First-order **category** is the stronger signal: there is a 2.7× spread between categories.

## Recommendations

| # | Action | Owner | Success metric | Expected impact |
|---|---|---|---|---|
| 1 | **Dynamic delivery-promise buffer** by season and region. ETAs are padded by ~12 days on average but still breached at peaks. | Ops / Product | Late rate < 5% every month; share of 1★ reviews | Protects the review score that ~98% of growth depends on (test the link to conversion next) |
| 2 | **Category-targeted second-purchase flow** (bed/bath, furniture, sports, bags), days 30–75, with a permanent holdout. No blanket coupons. | Growth / CRM | 90-day repeat rate | +1 pp of 180-day repeat ≈ +775 customers ≈ **R$130k GMV/yr** |
| 3 | **Power-aware experimentation.** Design for MDE ≥ 30% (~4.7 months) or use leading indicators, and require a unit-economics check before shipping. | Data | Tests completed per quarter; % shipped with a positive ROI | Avoids shipping "significant but unprofitable" features. In a simulated test, a R$10 coupon was +48% significant yet lost R$47 per 1,000 customers |

## What we can't answer with this data
There is no traffic or marketing-spend data, so we cannot compute CAC, LTV:CAC or checkout conversion. The next step is to join the Olist data with acquisition data to test whether review score drives conversion.
