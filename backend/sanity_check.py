"""Sanity checks on the +1852 MW bias before we trust it."""
from collections import defaultdict
from datetime import timedelta

from analysis import (
    load_data, build_rows, metrics, hourly_actuals,
    index_forecasts, pick_forecast, iso,
)

actuals, forecasts = load_data()
rows, _ = build_rows(actuals, forecasts)

# 1. how one-sided is the error?
over = sum(1 for r in rows if r["error"] > 0)
print(f"hours over-forecast: {over} of {len(rows)} ({100 * over / len(rows):.0f}%)")

by_day = defaultdict(list)
for r in rows:
    by_day[r["target"][:10]].append(r["error"])
daily = {d: sum(v) / len(v) for d, v in by_day.items()}
pos_days = sum(1 for v in daily.values() if v > 0)
print(f"days with positive average error: {pos_days} of {len(daily)}")

print("\nworst 3 days (avg error MW):")
for d, v in sorted(daily.items(), key=lambda kv: kv[1], reverse=True)[:3]:
    print(f"  {d}: {v:.0f}")
print("best 3 days (avg error MW):")
for d, v in sorted(daily.items(), key=lambda kv: kv[1])[:3]:
    print(f"  {d}: {v:.0f}")

# 2. does the bias survive a near-real-time forecast (made 1 hour before delivery)?
hourly = hourly_actuals(actuals)
idx = index_forecasts(forecasts)
near = []
for target in sorted(hourly):
    if not (target.year == 2026 and target.month == 1):
        continue
    picked = pick_forecast(idx, target, target - timedelta(hours=1))
    if picked is None:
        continue
    pub, fc = picked
    act = hourly[target]
    near.append({
        "target": iso(target),
        "lead_hours": (target - pub).total_seconds() / 3600,
        "forecast": fc,
        "actual": act,
        "error": fc - act,
    })

print(f"\nnear-real-time forecast, hours matched: {len(near)}")
avg_lead = sum(r["lead_hours"] for r in near) / len(near)
print(f"average lead time: {avg_lead:.1f} hours")
m = metrics(near)
for k in ["mae_mw", "rmse_mw", "bias_mw", "p90_abs_error_mw"]:
    print(f"  {k}: {m[k]}")

print("\nday-ahead (09:00 cutoff) for comparison:")
m2 = metrics(rows)
for k in ["mae_mw", "rmse_mw", "bias_mw", "p90_abs_error_mw"]:
    print(f"  {k}: {m2[k]}")
