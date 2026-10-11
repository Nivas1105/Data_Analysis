-- Staging: validate, de-duplicate, and type raw orders. Nothing is silently dropped:
-- every excluded row lands in stg.orders_rejected with a reason.
CREATE OR REPLACE TABLE stg.orders_checked AS
SELECT
    o.*,
    ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_ts) AS rn,
    CASE
        WHEN store_id IS NULL THEN 'missing_store'
        WHEN items_requested IS NULL OR items_requested <= 0 THEN 'bad_items_requested'
        WHEN items_found > items_requested THEN 'found_exceeds_requested'
        WHEN canceled = 0 AND delivery_delay_min IS NULL THEN 'missing_delay'
        ELSE NULL
    END AS dq_reason
FROM raw.orders o;

CREATE OR REPLACE TABLE stg.orders AS
SELECT
    order_id,
    order_ts,
    CAST(order_date AS DATE) AS order_date,
    day_num,
    dow,
    retailer_id,
    store_id,
    items_requested,
    items_found,
    items_substituted,
    items_refunded,
    delivery_delay_min,
    canceled AS is_canceled,
    CASE WHEN canceled = 0 AND delivery_delay_min > 10 THEN 1 ELSE 0 END AS is_late,
    rating
FROM stg.orders_checked
WHERE rn = 1 AND dq_reason IS NULL;

CREATE OR REPLACE TABLE stg.orders_rejected AS
SELECT
    order_id, retailer_id, store_id, day_num,
    CASE WHEN rn > 1 THEN 'duplicate' ELSE dq_reason END AS reject_reason
FROM stg.orders_checked
WHERE rn > 1 OR dq_reason IS NOT NULL;
