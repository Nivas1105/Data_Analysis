"""Seeded synthetic grocery-fulfillment data.

IMPORTANT: this data is entirely synthetic. It is modeled on the *structure* of an
online-grocery marketplace (retailers -> stores -> orders) and contains no real
Instacart data. Known incidents are injected on purpose and written to
`ground_truth_incidents` so the anomaly detector can be scored objectively.
The detector never reads that table.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

DOW_VOL = np.array([1.00, 0.90, 0.90, 0.95, 1.05, 1.20, 1.25])  # Mon..Sun
REGIONS = ["West", "Midwest", "South", "Northeast"]
NAMES = ["Alder", "Birch", "Cedar", "Dune", "Elm", "Fjord", "Granite", "Harbor", "Iris",
         "Juniper", "Kestrel", "Lumen", "Maple", "Nova", "Onyx", "Pine", "Quartz", "Ridge",
         "Summit", "Tundra", "Umber", "Vale", "Willow", "Zephyr"]
SUFFIX = ["Market", "Foods", "Grocer", "Fresh"]
LAUNCHES = {5: 30, 8: 45}  # retailer_id -> launch day_num (others launched before the window)

# id, retailer_id, kind, start, end, effect, scope, expected metrics
INCIDENTS = [
    dict(id=1, retailer=3, start=40, end=43, effect="fill", amount=-0.12, scope="store_subset", n=6,
         expected="fill_rate,substitution_rate,refund_rate",
         desc="Inventory-feed outage in 6 West-region stores"),
    dict(id=2, retailer=7, start=61, end=66, effect="fill", amount=-0.07, scope="all_stores", n=None,
         expected="fill_rate,substitution_rate,refund_rate",
         desc="Chain-wide assortment/inventory accuracy problem"),
    dict(id=3, retailer=11, start=75, end=79, effect="late", amount=12.0, scope="all_stores", n=None,
         expected="late_rate", desc="Shopper/carrier capacity shortage"),
    dict(id=4, retailer=14, start=52, end=54, effect="cancel", amount=0.12, scope="all_stores", n=None,
         expected="cancel_rate", desc="Checkout/ordering outage causing cancellations"),
    dict(id=5, retailer=18, start=90, end=92, effect="refund", amount=0.10, scope="store_subset", n=4,
         expected="refund_rate", desc="Produce-quality issue in 4 stores"),
    dict(id=6, retailer=2, start=46, end=49, effect="fill", amount=-0.05, scope="all_stores", n=None,
         expected="fill_rate,substitution_rate,refund_rate", desc="Moderate chain-wide fill drop"),
    dict(id=7, retailer=9, start=95, end=96, effect="cancel", amount=0.08, scope="all_stores", n=None,
         expected="cancel_rate", desc="Short cancellation spike"),
]


def dataset_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def generate(seed: int = 42, days: int = 120, start: str = "2026-01-05") -> dict:
    rng = np.random.default_rng(seed)
    start_ts = pd.Timestamp(start)
    n_ret = len(NAMES)

    # ---- retailers -------------------------------------------------------------------------
    rid = np.arange(1, n_ret + 1)
    base_fill = np.clip(rng.normal(0.93, 0.015, n_ret), 0.88, 0.97)
    base_cancel = np.clip(rng.normal(0.025, 0.006, n_ret), 0.01, 0.045)
    primary_region = rng.choice(REGIONS, n_ret)
    launch_day = np.array([LAUNCHES.get(int(r), -(200 + 20 * int(r))) for r in rid])
    retailers = pd.DataFrame({
        "retailer_id": rid,
        "retailer_name": [f"{NAMES[i]} {SUFFIX[i % 4]}" for i in range(n_ret)],
        "primary_region": primary_region,
        "launch_day": launch_day,
    })

    # ---- stores ----------------------------------------------------------------------------
    n_stores = rng.integers(8, 26, n_ret)
    for r in (3, 18):  # incident retailers need enough stores for a meaningful subset
        n_stores[r - 1] = 20
    rows = []
    sid = 0
    for i in range(n_ret):
        for _ in range(n_stores[i]):
            sid += 1
            region = primary_region[i] if rng.random() < 0.7 else rng.choice(REGIONS)
            rows.append((f"S{sid:04d}", int(rid[i]), region))
    stores = pd.DataFrame(rows, columns=["store_id", "retailer_id", "region"])
    S, D = len(stores), days
    store_ret = stores["retailer_id"].to_numpy()

    # make incident-1 stores identifiable by region (first 6 stores of retailer 3 -> West)
    r3 = np.where(store_ret == 3)[0]
    stores.loc[r3[:6], "region"] = "West"
    stores.loc[r3[6:], "region"] = "Midwest"
    store_region = stores["region"].to_numpy()

    base_vol = rng.uniform(8, 16, S)
    fill_eff = rng.normal(0, 0.01, S)
    late_eff = rng.normal(0, 1.5, S)

    day_idx = np.arange(D)
    dow_d = (start_ts.dayofweek + day_idx) % 7
    lam = base_vol[:, None] * DOW_VOL[dow_d][None, :] * (1 + 0.001 * day_idx)[None, :]

    # launches: no orders before launch, volume ramps over 28 days
    for r, L in LAUNCHES.items():
        m = store_ret == r
        for d in range(D):
            if d < L:
                lam[m, d] = 0
            elif d < L + 28:
                lam[m, d] *= 0.4 + 0.6 * (d - L) / 28

    fill_adj = np.zeros((S, D))
    late_adj = np.zeros((S, D))
    cancel_add = np.zeros((S, D))
    refund_add = np.zeros((S, D))
    target = {"fill": fill_adj, "late": late_adj, "cancel": cancel_add, "refund": refund_add}

    gt = []
    for inc in INCIDENTS:
        idx = np.where(store_ret == inc["retailer"])[0]
        affected = idx[: inc["n"]] if inc["scope"] == "store_subset" else idx
        target[inc["effect"]][np.ix_(affected, np.arange(inc["start"], inc["end"] + 1))] += inc["amount"]
        gt.append(dict(incident_id=inc["id"], kind="incident", retailer_id=inc["retailer"],
                       start_day=inc["start"], end_day=inc["end"], expected_metrics=inc["expected"],
                       scope=inc["scope"], n_stores_affected=int(len(affected)),
                       n_stores_total=int(len(idx)), description=inc["desc"]))
    for r, L in LAUNCHES.items():
        idx = np.where(store_ret == r)[0]
        for k in range(14):  # launch ramp: fill penalty decays linearly over 14 days
            fill_adj[idx, L + k] += -0.08 * (1 - k / 14)
        gt.append(dict(incident_id=100 + r, kind="launch_ramp", retailer_id=r, start_day=L,
                       end_day=L + 13, expected_metrics="fill_rate,substitution_rate,refund_rate",
                       scope="all_stores", n_stores_affected=int(len(idx)), n_stores_total=int(len(idx)),
                       description="New-retailer launch ramp (elevated misses that decay)"))
    ground_truth = pd.DataFrame(gt)

    # ---- orders ----------------------------------------------------------------------------
    counts = rng.poisson(lam)
    s_idx, d_idx = np.nonzero(counts)
    rep = counts[s_idx, d_idx]
    s = np.repeat(s_idx, rep)
    d = np.repeat(d_idx, rep)
    n = len(s)
    r_idx = store_ret[s] - 1
    dow = dow_d[d]
    weekend = (dow >= 5).astype(float)

    p_fill = np.clip(base_fill[r_idx] + fill_eff[s] + fill_adj[s, d] - 0.01 * weekend, 0.3, 0.995)
    req = np.clip(1 + rng.poisson(16, n), 1, 60)
    found = rng.binomial(req, p_fill)
    missing = req - found
    subs = rng.binomial(missing, 0.6)
    refund = rng.binomial(missing - subs, 0.8) + rng.binomial(found, np.clip(0.01 + refund_add[s, d], 0, 0.5))
    refund = np.minimum(refund, req)
    delay = rng.normal(-2 + late_eff[s] + late_adj[s, d] + 2 * weekend, 9)
    canceled = (rng.random(n) < np.clip(base_cancel[r_idx] + cancel_add[s, d], 0, 0.9)).astype(int)

    found = np.where(canceled == 1, 0, found)
    subs = np.where(canceled == 1, 0, subs)
    refund = np.where(canceled == 1, 0, refund)
    delay = np.where(canceled == 1, np.nan, delay)
    quality = 4.8 - 2.5 * (1 - found / req) - 0.03 * np.maximum(np.nan_to_num(delay), 0)
    rating = np.clip(np.round(rng.normal(quality, 0.5)), 1, 5)
    rating = np.where((rng.random(n) < 0.35) & (canceled == 0), rating, np.nan)

    order_ts = (start_ts + pd.to_timedelta(d, unit="D")
                + pd.to_timedelta(rng.integers(420, 1320, n), unit="m"))
    orders = pd.DataFrame({
        "order_id": np.arange(1, n + 1),
        "order_ts": order_ts,
        "order_date": order_ts.normalize(),
        "day_num": d.astype(int),
        "dow": dow.astype(int),
        "retailer_id": store_ret[s],
        "store_id": stores["store_id"].to_numpy()[s],
        "items_requested": req, "items_found": found,
        "items_substituted": subs, "items_refunded": refund,
        "delivery_delay_min": np.round(delay, 1),
        "canceled": canceled, "rating": rating,
    })

    # ---- deliberate data-quality problems (so validation has something to catch) -------------
    bad = rng.choice(n, int(n * 0.002), replace=False)
    orders.loc[bad[: len(bad) // 2], "items_found"] = orders.loc[bad[: len(bad) // 2], "items_requested"] + 3
    orders.loc[bad[len(bad) // 2:], "store_id"] = None
    miss = rng.choice(np.where(canceled == 0)[0], int(n * 0.001), replace=False)
    orders.loc[miss, "delivery_delay_min"] = np.nan
    dups = orders.sample(int(n * 0.003), random_state=seed)
    orders = pd.concat([orders, dups], ignore_index=True)

    return dict(retailers=retailers, stores=stores, orders=orders, ground_truth=ground_truth,
                meta=dict(seed=seed, days=days, start=start, dataset_hash=dataset_hash(orders),
                          injected_duplicates=len(dups), injected_bad_rows=len(bad), injected_missing_delay=len(miss)))
