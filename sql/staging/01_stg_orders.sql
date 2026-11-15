-- One row per order, enriched with the person-level customer id and delivery metrics.
-- Note: Olist issues a new customer_id for every order; customer_unique_id identifies the person.
create or replace table stg_orders as
select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    c.customer_state,
    c.customer_city,
    o.order_status,
    cast(o.order_purchase_timestamp       as timestamp) as purchased_at,
    cast(o.order_approved_at              as timestamp) as approved_at,
    cast(o.order_delivered_carrier_date   as timestamp) as shipped_at,
    cast(o.order_delivered_customer_date  as timestamp) as delivered_at,
    cast(o.order_estimated_delivery_date  as timestamp) as estimated_delivery_at,
    date_trunc('month', cast(o.order_purchase_timestamp as timestamp))::date as order_month,
    date_diff('day', cast(o.order_purchase_timestamp as timestamp),
                     cast(o.order_delivered_customer_date as timestamp)) as delivery_days,
    -- positive = days late, negative = days early
    date_diff('day', cast(o.order_estimated_delivery_date as date),
                     cast(o.order_delivered_customer_date as date)) as delay_days,
    case
        when o.order_delivered_customer_date is null then null
        when cast(o.order_delivered_customer_date as date)
             > cast(o.order_estimated_delivery_date as date) then true
        else false
    end as is_late,
    o.order_status not in ('canceled', 'unavailable') as is_valid
from raw_orders o
join raw_customers c using (customer_id);
