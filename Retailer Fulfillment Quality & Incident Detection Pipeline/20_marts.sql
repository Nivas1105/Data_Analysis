-- Dimensions
CREATE OR REPLACE TABLE dim.retailers AS
SELECT retailer_id, retailer_name, primary_region, launch_day FROM raw.retailers;

CREATE OR REPLACE TABLE dim.stores AS
SELECT store_id, retailer_id, region FROM raw.stores;

-- Daily retailer grain. Canceled orders are excluded from fulfillment metrics.
CREATE OR REPLACE TABLE mart.retailer_daily AS
SELECT
    t.*,
    1.0 * items_found / NULLIF(items_requested, 0)       AS fill_rate,
    1.0 * items_substituted / NULLIF(items_requested, 0) AS substitution_rate,
    1.0 * items_refunded / NULLIF(items_requested, 0)    AS refund_rate,
    1.0 * late_orders / NULLIF(completed_orders, 0)      AS late_rate,
    1.0 * canceled_orders / NULLIF(orders, 0)            AS cancel_rate
FROM (
    SELECT
        retailer_id,
        order_date,
        MIN(day_num) AS day_num,
        MIN(dow) AS dow,
        COUNT(*) AS orders,
        SUM(1 - is_canceled) AS completed_orders,
        SUM(CASE WHEN is_canceled = 0 THEN items_requested ELSE 0 END)  AS items_requested,
        SUM(CASE WHEN is_canceled = 0 THEN items_found ELSE 0 END)      AS items_found,
        SUM(CASE WHEN is_canceled = 0 THEN items_substituted ELSE 0 END) AS items_substituted,
        SUM(CASE WHEN is_canceled = 0 THEN items_refunded ELSE 0 END)   AS items_refunded,
        SUM(CASE WHEN is_canceled = 0 THEN is_late ELSE 0 END)          AS late_orders,
        SUM(is_canceled) AS canceled_orders,
        AVG(rating) AS avg_rating
    FROM stg.orders
    GROUP BY retailer_id, order_date
) t;

-- Long format: one row per retailer x day x metric (trials = denominator, used for sampling noise)
CREATE OR REPLACE TABLE mart.retailer_metrics_long AS
SELECT retailer_id, order_date, day_num, dow, 'fill_rate' AS metric, fill_rate AS value,
       completed_orders AS volume, items_requested AS trials, 'low' AS bad_direction
FROM mart.retailer_daily
UNION ALL
SELECT retailer_id, order_date, day_num, dow, 'substitution_rate', substitution_rate,
       completed_orders, items_requested, 'high' FROM mart.retailer_daily
UNION ALL
SELECT retailer_id, order_date, day_num, dow, 'refund_rate', refund_rate,
       completed_orders, items_requested, 'high' FROM mart.retailer_daily
UNION ALL
SELECT retailer_id, order_date, day_num, dow, 'late_rate', late_rate,
       completed_orders, completed_orders, 'high' FROM mart.retailer_daily
UNION ALL
SELECT retailer_id, order_date, day_num, dow, 'cancel_rate', cancel_rate,
       completed_orders, orders, 'high' FROM mart.retailer_daily;

-- Anomaly detection: compare each day to the same weekday over the prior 8 weeks
-- (controls for weekly seasonality). Noise = max(historical std, binomial std, floor).
-- An anomaly needs: enough history, enough volume, bad-direction z >= 3, AND a practical-size change.
CREATE OR REPLACE TABLE mart.metric_anomalies AS
WITH base AS (
    SELECT
        m.*,
        AVG(value) OVER (PARTITION BY retailer_id, metric, dow ORDER BY day_num
                         ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS base_mean,
        STDDEV_SAMP(value) OVER (PARTITION BY retailer_id, metric, dow ORDER BY day_num
                         ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS base_std,
        COUNT(value) OVER (PARTITION BY retailer_id, metric, dow ORDER BY day_num
                         ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING) AS base_n
    FROM mart.retailer_metrics_long m
),
scored AS (
    SELECT
        b.*,
        value - base_mean AS delta,
        (value - base_mean) / GREATEST(
            COALESCE(base_std, 0),
            SQRT(GREATEST(base_mean * (1 - base_mean), 0.0001) / NULLIF(trials, 0)),
            0.002
        ) AS z
    FROM base b
),
directed AS (
    SELECT s.*, CASE WHEN bad_direction = 'low' THEN -z ELSE z END AS bad_z FROM scored s
)
SELECT
    d.*,
    CASE WHEN base_n >= 5 AND volume >= 30 AND bad_z >= 3
          AND ABS(delta) >= (CASE metric WHEN 'late_rate' THEN 0.03
                                         WHEN 'cancel_rate' THEN 0.02 ELSE 0.015 END)
         THEN 1 ELSE 0 END AS is_anomaly
FROM directed d;

-- Incidents = runs of consecutive anomalous days (gaps-and-islands).
-- Keep runs of >= 2 days, or a single day that is extreme (z >= 5).
CREATE OR REPLACE TABLE mart.incidents AS
WITH flagged AS (
    SELECT retailer_id, metric, order_date, day_num, value, base_mean, bad_z, volume
    FROM mart.metric_anomalies WHERE is_anomaly = 1
),
grp AS (
    SELECT f.*, day_num - ROW_NUMBER() OVER (PARTITION BY retailer_id, metric ORDER BY day_num) AS grp_key
    FROM flagged f
)
SELECT
    retailer_id, metric,
    MIN(order_date) AS start_date, MAX(order_date) AS end_date,
    MIN(day_num) AS start_day, MAX(day_num) AS end_day,
    COUNT(*) AS days,
    AVG(value) AS avg_value, AVG(base_mean) AS avg_baseline,
    AVG(value) - AVG(base_mean) AS avg_delta,
    MAX(bad_z) AS peak_z,
    SUM(volume) AS affected_orders
FROM grp
GROUP BY retailer_id, metric, grp_key
HAVING COUNT(*) >= 2 OR MAX(bad_z) >= 5;

-- Launch impact: weeks since launch vs. mature-retailer benchmark
CREATE OR REPLACE TABLE mart.launch_ramp AS
WITH bench AS (
    SELECT 1.0 * SUM(d.items_found) / SUM(d.items_requested)       AS bench_fill_rate,
           1.0 * SUM(d.items_substituted) / SUM(d.items_requested) AS bench_sub_rate,
           1.0 * SUM(d.late_orders) / SUM(d.completed_orders)      AS bench_late_rate
    FROM mart.retailer_daily d JOIN dim.retailers r ON d.retailer_id = r.retailer_id
    WHERE r.launch_day < 0
)
SELECT
    r.retailer_id, r.retailer_name,
    CAST(FLOOR((d.day_num - r.launch_day) / 7.0) AS INTEGER) AS weeks_since_launch,
    SUM(d.orders) AS orders,
    1.0 * SUM(d.items_found) / SUM(d.items_requested)       AS fill_rate,
    1.0 * SUM(d.items_substituted) / SUM(d.items_requested) AS substitution_rate,
    1.0 * SUM(d.late_orders) / SUM(d.completed_orders)      AS late_rate,
    MIN(b.bench_fill_rate) AS bench_fill_rate,
    1.0 * SUM(d.items_found) / SUM(d.items_requested) - MIN(b.bench_fill_rate) AS fill_rate_gap_vs_bench
FROM mart.retailer_daily d
JOIN dim.retailers r ON d.retailer_id = r.retailer_id
CROSS JOIN bench b
WHERE r.launch_day >= 0
GROUP BY r.retailer_id, r.retailer_name, CAST(FLOOR((d.day_num - r.launch_day) / 7.0) AS INTEGER);

-- Scorecard: last 28 days vs the 28 days before
CREATE OR REPLACE TABLE mart.retailer_scorecard AS
WITH mx AS (SELECT MAX(day_num) AS m FROM mart.retailer_daily),
agg AS (
    SELECT
        d.retailer_id,
        SUM(CASE WHEN d.day_num > mx.m - 28 THEN d.items_found ELSE 0 END)     AS f_cur,
        SUM(CASE WHEN d.day_num > mx.m - 28 THEN d.items_requested ELSE 0 END) AS r_cur,
        SUM(CASE WHEN d.day_num <= mx.m - 28 AND d.day_num > mx.m - 56 THEN d.items_found ELSE 0 END)     AS f_prev,
        SUM(CASE WHEN d.day_num <= mx.m - 28 AND d.day_num > mx.m - 56 THEN d.items_requested ELSE 0 END) AS r_prev,
        SUM(CASE WHEN d.day_num > mx.m - 28 THEN d.late_orders ELSE 0 END)       AS l_cur,
        SUM(CASE WHEN d.day_num > mx.m - 28 THEN d.completed_orders ELSE 0 END)  AS c_cur,
        SUM(CASE WHEN d.day_num > mx.m - 28 THEN d.orders ELSE 0 END)            AS orders_28d
    FROM mart.retailer_daily d CROSS JOIN mx
    GROUP BY d.retailer_id
)
SELECT
    a.retailer_id, r.retailer_name, a.orders_28d,
    1.0 * f_cur / NULLIF(r_cur, 0)  AS fill_rate_28d,
    1.0 * f_prev / NULLIF(r_prev, 0) AS fill_rate_prev_28d,
    1.0 * f_cur / NULLIF(r_cur, 0) - 1.0 * f_prev / NULLIF(r_prev, 0) AS fill_rate_change,
    1.0 * l_cur / NULLIF(c_cur, 0)  AS late_rate_28d
FROM agg a JOIN dim.retailers r ON a.retailer_id = r.retailer_id;
