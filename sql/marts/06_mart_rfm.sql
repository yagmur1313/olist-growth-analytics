-- RFM segmentation as of the snapshot date 2018-09-01.
-- Because ~97% of customers buy only once, Frequency is bucketed as 1 / 2 / 3+ orders
-- instead of quintiles (quintiles would all collapse to "1").
create or replace table mart_rfm as
with base as (
    select
        customer_unique_id,
        customer_state,
        date_diff('day', last_purchased_at, timestamp '2018-09-01') as recency_days,
        1 + n_repeat_orders                                         as frequency,
        lifetime_gmv                                                as monetary
    from dim_customers
),
scored as (
    select
        *,
        6 - ntile(5) over (order by recency_days)                  as r_score,  -- 5 = most recent
        case when frequency >= 3 then 5 when frequency = 2 then 4 else 1 end as f_score,
        ntile(5) over (order by monetary)                          as m_score
    from base
)
select
    *,
    case
        when f_score >= 4 and r_score >= 4                 then 'Champions'
        when f_score >= 4                                  then 'Loyal - at risk'
        when r_score >= 4 and m_score >= 4                 then 'New high-value'
        when r_score >= 4                                  then 'New customers'
        when r_score = 3                                   then 'Cooling down'
        when m_score >= 4                                  then 'Lost high-value'
        else 'Lost low-value'
    end as segment
from scored;
