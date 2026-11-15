-- Monthly acquisition cohorts: share of each cohort that placed a repeat order
-- in month N after their first purchase (N = 1..). Month 0 = acquisition month.
create or replace table mart_cohort_retention as
with activity as (
    select distinct
        c.cohort_month,
        c.customer_unique_id,
        date_diff('month', c.cohort_month, o.order_month) as months_since_first
    from dim_customers c
    join fct_orders o using (customer_unique_id)
    where o.is_repeat_order
),
sizes as (
    select cohort_month, count(*) as cohort_size
    from dim_customers
    group by 1
)
select
    a.cohort_month,
    s.cohort_size,
    a.months_since_first,
    count(distinct a.customer_unique_id)                         as retained_customers,
    round(count(distinct a.customer_unique_id) / s.cohort_size, 5) as retention_rate
from activity a
join sizes s using (cohort_month)
where a.months_since_first >= 1
group by 1, 2, 3
order by 1, 3;
