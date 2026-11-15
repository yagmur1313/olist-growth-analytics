-- Monthly growth KPIs: the inputs of the metric tree
-- GMV = active customers x orders per customer x AOV ; active = new + returning
create or replace table mart_monthly_kpis as
select
    order_month,
    count(*)                                                        as orders,
    count(*) filter (where is_repeat_order)                         as repeat_orders,
    round(sum(gmv), 2)                                              as gmv,
    count(distinct customer_unique_id)                              as active_customers,
    count(distinct customer_unique_id) filter (where is_first_order) as new_customers,
    count(distinct customer_unique_id) filter (where is_repeat_order) as returning_customers,
    round(sum(gmv) filter (where is_repeat_order), 2)               as returning_gmv,
    round(avg(gmv), 2)                                              as aov,
    round(count(*) / count(distinct customer_unique_id), 4)         as orders_per_customer,
    round(avg(is_late::int) filter (where delivered_at is not null), 4) as late_delivery_rate,
    round(avg(delivery_days), 2)                                    as avg_delivery_days,
    round(avg(review_score), 3)                                     as avg_review_score
from fct_orders
group by 1
order by 1;
