-- First-order customer journey funnel: from first purchase to second purchase.
-- Restricted to customers acquired before 2018-06-03 so that everyone has >= 90 days
-- of follow-up for the final step.
create or replace table mart_funnel as
with first_any as (
    -- each person's very first order, including canceled / unavailable ones
    select * from stg_orders
    qualify row_number() over (partition by customer_unique_id order by purchased_at) = 1
),
base as (
    select o.*, c.repeat_90d
    from first_any o
    left join dim_customers c
      on c.customer_unique_id = o.customer_unique_id
     and c.first_purchased_at = o.purchased_at
    where o.purchased_at >= timestamp '2017-01-01'
      and o.purchased_at <= timestamp '2018-09-01' - interval 90 day
)
select * from (
    select 1 as step, 'Order placed'                   as stage, count(*) as customers from base
    union all
    select 2, 'Payment approved',            count(*) from base where approved_at is not null and is_valid
    union all
    select 3, 'Handed to carrier',           count(*) from base where shipped_at  is not null and is_valid
    union all
    select 4, 'Delivered',                   count(*) from base where delivered_at is not null and is_valid
    union all
    select 5, 'Delivered on time',           count(*) from base where is_late = false and is_valid
    union all
    select 6, 'Happy review (4-5 stars)',    count(*) from base b
        join stg_reviews r using (order_id) where b.is_late = false and b.is_valid and r.review_score >= 4
    union all
    select 7, 'Second purchase within 90d',  count(*) from base b
        join stg_reviews r using (order_id) where b.is_late = false and b.is_valid and r.review_score >= 4
        and b.repeat_90d
)
order by step;
