-- Products with English category names.
create or replace table stg_products as
select
    p.product_id,
    coalesce(t.product_category_name_english, p.product_category_name, 'unknown') as category,
    p.product_weight_g,
    p.product_photos_qty
from raw_products p
left join raw_category_translation t using (product_category_name);

-- One row per order line.
create or replace table stg_order_items as
select
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    p.category,
    i.price::double          as price,
    i.freight_value::double  as freight
from raw_order_items i
left join stg_products p using (product_id);

-- Payments aggregated to the order.
create or replace table stg_payments as
select
    order_id,
    arg_max(payment_type, payment_value) as main_payment_type,
    max(payment_installments)            as installments,
    sum(payment_value)::double           as payment_value
from raw_payments
group by 1;

-- Reviews: a few orders have several reviews, keep the latest one.
create or replace table stg_reviews as
select
    order_id,
    arg_max(review_score, review_answer_timestamp)         as review_score,
    max(review_comment_message is not null)                as has_comment
from raw_reviews
group by 1;
