# Project brief: Kaarobar marketplace analytics

The requirements document written before any analysis: who needs what, which questions answer it, and how every metric is defined. The scenario and data are synthetic.

## Background
Kaarobar is a fictional Pakistani online marketplace selling fashion, footwear, electronics, mobile accessories, home and kitchen, beauty, grocery, and baby products in 16 cities. Orders have grown quickly since January 2024. Three worries keep coming up in leadership meetings:

1. Parcels refused at the door (returned to origin, or RTO), mostly on cash-on-delivery orders.
2. Late deliveries, especially after mega sales like 11.11 and White Friday.
3. Customers who buy once and never come back.

In March and April 2026, the product team also tested a one-page checkout against the current checkout.

## Stakeholders and decisions

| Stakeholder | What they need to know | Decision it informs |
|---|---|---|
| Head of Operations | Which couriers are late, and where? What do refused parcels cost? | Courier allocation and cash-on-delivery policy |
| Growth Lead | Which customers come back, and which channels and promotions bring them? | Marketing budget and sale strategy |
| Checkout Product Manager | Did the one-page checkout lift conversion, and for whom? | Whether to roll it out, and on which devices |
| Category Managers | Which categories and sellers drive returns, and why? | Size guides and seller reviews |
| Finance | Monthly revenue, order value, and payment mix | Forecasts and cash-flow planning |

## Business questions
Each question has one SQL view in `sql/04_analysis.sql`.

| # | Question | View |
|---|---|---|
| 1 | How fast is the business growing? | `mart.v_monthly_kpis`, `mart.v_headline_kpis` |
| 2 | When do people buy? | `mart.v_daily_orders` |
| 3 | How are customers paying, and how is that changing? | `mart.v_payment_mix` |
| 4 | Who refuses parcels at the door, and what does it cost? | `mart.v_rto_drivers`, `mart.v_rto_by_tier`, `mart.v_rto_cost` |
| 5 | Which courier delivers on time, and where? | `mart.v_courier_scorecard` |
| 6 | Did moving volume to the cheapest courier hurt delivery? | `mart.v_delivery_monthly` |
| 7 | Does the first order decide whether a customer comes back? | `mart.v_first_order_experience` |
| 8 | How well does each monthly cohort retain? | `mart.v_cohort_retention` |
| 9 | Are customers won in mega sales, or through each channel, worth as much? | `mart.v_acquisition_quality`, `mart.v_channel_quality` |
| 10 | What comes back, and why? | `mart.v_returns_by_category` |
| 11 | Which sellers ship items that do not match their listing? | `mart.v_seller_returns` |
| 12 | Which customers are most valuable, and which are slipping away? | `mart.v_rfm`, `mart.v_rfm_summary` |
| 13 | Did the one-page checkout work? | `mart.v_ab_test`, `src/ab_test.py` |
| 14 | Where is growth coming from geographically? | `mart.v_city_tier_growth` |

## Metric definitions

| Metric | Definition |
|---|---|
| GMV | Sum of quantity times charged unit price, across all orders, in PKR |
| Net revenue | GMV of delivered orders minus refunds for returned items |
| Average order value (AOV) | GMV divided by orders |
| RTO rate | Orders returned to origin, divided by orders that were delivered or returned to origin |
| Late delivery rate | Delivered orders whose delivery date is after the promised date, divided by delivered orders with a delivery timestamp |
| 90-day repeat rate | Customers who placed a second order within 90 days of their first, divided by customers whose first order is at least 90 days before the extract date |
| Checkout conversion | Checkout sessions that ended in an order, divided by checkout sessions, bots excluded |
| City tier | 1: Karachi, Lahore, Islamabad, Rawalpindi. 2: large regional cities. 3: smaller cities |

## Scope and assumptions
- Period: 2024-01-01 to 2026-06-30. The extract was taken on 2026-06-30, so later deliveries and returns are not in the data.
- Money is in PKR and not adjusted for inflation.
- A refused parcel costs PKR 420 to handle: PKR 180 courier fee each way plus PKR 60 packaging and handling. This is an assumption, stated wherever it is used.
- Customers with more than one account (same email) are merged into the earliest account.
- QA test accounts and their orders are excluded from every metric.

## Deliverables
1. A reproducible SQL pipeline: load, profile, clean, model, analyse, and test.
2. Exploratory charts, one per question, with the finding in the title.
3. An A/B test readout with significance tests and a sample ratio check.
4. Recommendations for each stakeholder.
5. Next: a Power BI dashboard on the `mart` tables for the weekly operations review.

## Success criteria
- Every number in the README can be reproduced with four commands.
- All data quality checks pass on the cleaned data.
- Each stakeholder question is answered with a chart and a recommendation.
