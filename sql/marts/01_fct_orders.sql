-- Fact table: one row per valid (not canceled / unavailable) order.
-- Analysis window: 2017-01-01 .. 2018-08-31 (2016 and Sep-Oct 2018 are sparse / incomplete).
-- Order sequence is computed over *all* history so that customers who first bought in
-- 2016 are not miscounted as new in 2017.
create or replace table fct_orders as
with items as (
    select
        order_id,
        count(*)                          as n_items,
        sum(price)                        as items_value,
        sum(freight)                      as freight_value,
        arg_max(category, price)          as main_category,
        count(distinct seller_id)         as n_sellers
    from stg_order_items
    group by 1
),
seq as (
    select
        o.*,
        row_number() over (partition by customer_unique_id order by purchased_at) as customer_order_number,
        min(purchased_at) over (partition by customer_unique_id)                  as first_purchased_at,
        lag(purchased_at) over (partition by customer_unique_id order by purchased_at) as prev_purchased_at
    from stg_orders o
    where is_valid
)
select
    s.order_id,
    s.customer_unique_id,
    s.customer_state,
    s.order_status,
    s.purchased_at,
    s.order_month,
    s.delivered_at,
    s.delivery_days,
    s.delay_days,
    s.is_late,
    s.customer_order_number,
    s.customer_order_number = 1                                   as is_first_order,
    -- a "repeat" order must be placed on a later calendar day than the first order;
    -- same-day extra orders are usually one basket split across checkouts.
    s.customer_order_number > 1
        and s.purchased_at::date > s.first_purchased_at::date     as is_repeat_order,
    date_diff('day', s.prev_purchased_at, s.purchased_at)         as days_since_prev_order,
    i.n_items,
    i.n_sellers,
    i.main_category,
    i.items_value,
    i.freight_value,
    i.items_value + i.freight_value                               as gmv,
    p.main_payment_type,
    p.installments,
    r.review_score,
    r.has_comment
from seq s
left join items       i using (order_id)
left join stg_payments p using (order_id)
left join stg_reviews  r using (order_id)
where s.purchased_at >= timestamp '2017-01-01'
  and s.purchased_at <  timestamp '2018-09-01'
  and i.order_id is not null;
