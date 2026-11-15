-- One row per customer (customer_unique_id) whose FIRST order falls in the analysis window.
-- Carries first-order experience attributes so we can study what drives a second purchase.
create or replace table dim_customers as
with first_orders as (
    select * from fct_orders where is_first_order
),
later as (
    select
        f.customer_unique_id,
        min(o.purchased_at) filter (where o.purchased_at::date > f.purchased_at::date) as second_purchase_at,
        count(*) filter (where o.purchased_at::date > f.purchased_at::date)           as n_repeat_orders,
        sum(o.gmv)                                                                     as lifetime_gmv,
        count(*)                                                                       as n_orders,
        max(o.purchased_at)                                                            as last_purchased_at
    from first_orders f
    join fct_orders o using (customer_unique_id)
    group by 1
)
select
    f.customer_unique_id,
    f.customer_state,
    f.purchased_at                     as first_purchased_at,
    f.order_month                      as cohort_month,
    f.gmv                              as first_order_gmv,
    f.main_category                    as first_order_category,
    f.main_payment_type                as first_order_payment_type,
    f.installments                     as first_order_installments,
    f.freight_value / nullif(f.gmv, 0) as first_order_freight_share,
    f.delivery_days                    as first_order_delivery_days,
    f.delay_days                       as first_order_delay_days,
    f.is_late                          as first_order_is_late,
    f.review_score                     as first_order_review_score,
    l.n_orders,
    l.n_repeat_orders,
    l.lifetime_gmv,
    l.last_purchased_at,
    l.second_purchase_at,
    date_diff('day', f.purchased_at, l.second_purchase_at) as days_to_second_purchase,
    l.n_repeat_orders > 0 as is_repeat_customer,
    -- 90-day repeat is only observable for customers with >= 90 days of follow-up
    case
        when f.purchased_at > timestamp '2018-09-01' - interval 90 day then null
        else coalesce(date_diff('day', f.purchased_at, l.second_purchase_at) <= 90, false)
    end as repeat_90d,
    case
        when f.purchased_at > timestamp '2018-09-01' - interval 180 day then null
        else coalesce(date_diff('day', f.purchased_at, l.second_purchase_at) <= 180, false)
    end as repeat_180d
from first_orders f
join later l using (customer_unique_id);
