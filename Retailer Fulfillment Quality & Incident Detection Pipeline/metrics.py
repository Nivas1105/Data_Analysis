"""Single source of truth for metric definitions.

`num` / `den` are SQL expressions over stg.orders. Canceled orders are excluded from
fulfillment metrics (they have no items/delivery) and counted only in cancel_rate.
The mart SQL (sql/20_marts.sql) must stay consistent with these definitions; a test
recomputes every metric independently in pandas and compares.
"""

METRICS = {
    "fill_rate": dict(
        label="Item fill rate",
        num="CASE WHEN is_canceled = 0 THEN items_found ELSE 0 END",
        den="CASE WHEN is_canceled = 0 THEN items_requested ELSE 0 END",
        bad="low",
    ),
    "substitution_rate": dict(
        label="Item substitution rate",
        num="CASE WHEN is_canceled = 0 THEN items_substituted ELSE 0 END",
        den="CASE WHEN is_canceled = 0 THEN items_requested ELSE 0 END",
        bad="high",
    ),
    "refund_rate": dict(
        label="Item refund rate",
        num="CASE WHEN is_canceled = 0 THEN items_refunded ELSE 0 END",
        den="CASE WHEN is_canceled = 0 THEN items_requested ELSE 0 END",
        bad="high",
    ),
    "late_rate": dict(
        label="Late delivery rate",
        num="CASE WHEN is_canceled = 0 THEN is_late ELSE 0 END",
        den="CASE WHEN is_canceled = 0 THEN 1 ELSE 0 END",
        bad="high",
    ),
    "cancel_rate": dict(
        label="Order cancellation rate",
        num="is_canceled",
        den="1",
        bad="high",
    ),
}
LATE_THRESHOLD_MIN = 10  # delivered >10 min after promised window = late
