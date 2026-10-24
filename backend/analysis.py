"""Core analysis: pick the forecast a buyer actually had at decision time,
compare it with what really got generated, and quantify the error.

Conventions
- all times are UTC (January in the UK is GMT, so UTC == London time all month)
- forecasts are hourly; actuals are half-hourly, so each hourly actual is the
  average of the two half-hours inside that hour
- error = forecast - actual
  positive error = over-forecast = wind came in below forecast, which is the
  risky direction for a buyer (they would have to buy extra power)
"""
import json
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from math import sqrt
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_CUTOFF = "09:00"  # UTC, on the day before delivery


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_data():
    actuals = json.loads((DATA_DIR / "wind_actuals.json").read_text())
    forecasts = json.loads((DATA_DIR / "wind_forecasts.json").read_text())
    return actuals, forecasts


def hourly_actuals(actuals):
    """Average each pair of half-hours (HH:00 and HH:30) into one hourly value."""
    half = {parse_time(a["startTime"]): a["generation"] for a in actuals}
    out = {}
    for t in sorted(half):
        if t.minute == 0:
            nxt = t + timedelta(minutes=30)
            if nxt in half:
                out[t] = (half[t] + half[nxt]) / 2
    return out


def index_forecasts(forecasts):
    """target hour -> sorted list of (publish_time, generation)."""
    idx = defaultdict(list)
    for f in forecasts:
        idx[parse_time(f["startTime"])].append(
            (parse_time(f["publishTime"]), f["generation"])
        )
    for t in idx:
        idx[t].sort()
    return idx


def pick_forecast(idx, target, cutoff_dt):
    """Latest forecast for `target` published at or before cutoff_dt."""
    pubs = idx.get(target)
    if not pubs:
        return None
    i = bisect_right(pubs, (cutoff_dt, float("inf"))) - 1
    return pubs[i] if i >= 0 else None


def cutoff_for(day, cutoff_hhmm):
    """Decision cutoff for delivery day `day` = previous day at hh:mm UTC."""
    h, m = map(int, cutoff_hhmm.split(":"))
    prev = day - timedelta(days=1)
    return datetime(prev.year, prev.month, prev.day, h, m, tzinfo=timezone.utc)


def build_rows(actuals, forecasts, cutoff=DEFAULT_CUTOFF):
    """One row per delivery hour in January 2026: the forecast the buyer had
    at the cutoff, the actual generation, and the error."""
    hourly = hourly_actuals(actuals)
    idx = index_forecasts(forecasts)
    rows, skipped = [], 0
    for target in sorted(hourly):
        if not (target.year == 2026 and target.month == 1):
            continue
        picked = pick_forecast(idx, target, cutoff_for(target.date(), cutoff))
        if picked is None:
            skipped += 1
            continue
        pub, fc = picked
        act = hourly[target]
        rows.append({
            "target": iso(target),
            "publishTime": iso(pub),
            "lead_hours": round((target - pub).total_seconds() / 3600, 1),
            "forecast": round(fc, 1),
            "actual": round(act, 1),
            "error": round(fc - act, 1),
        })
    return rows, skipped


def percentile(values, p):
    s = sorted(values)
    if not s:
        return None
    k = (len(s) - 1) * p / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def metrics(rows):
    n = len(rows)
    if n == 0:
        return None
    errs = [r["error"] for r in rows]
    abs_errs = [abs(e) for e in errs]
    mean_actual = sum(r["actual"] for r in rows) / n
    mae = sum(abs_errs) / n
    return {
        "n_hours": n,
        "mean_actual_mw": round(mean_actual, 1),
        "mae_mw": round(mae, 1),
        "rmse_mw": round(sqrt(sum(e * e for e in errs) / n), 1),
        "bias_mw": round(sum(errs) / n, 1),
        "mae_pct_of_mean_actual": round(100 * mae / mean_actual, 1),
        "p90_abs_error_mw": round(percentile(abs_errs, 90), 1),
        "p90_shortfall_mw": round(percentile(errs, 90), 1),
    }


if __name__ == "__main__":
    actuals, forecasts = load_data()

    rows, skipped = build_rows(actuals, forecasts)
    print(f"hours matched: {len(rows)} (expect 744), skipped: {skipped}")
    print("distinct publishes used:", len({r["publishTime"] for r in rows}))

    print("\nexample, first hour of 2 Jan:")
    print(rows[24])

    print("\nmetrics at 09:00 cutoff:")
    for k, v in metrics(rows).items():
        print(f"  {k}: {v}")

    print("\nwhat if the cutoff were different? (publish used on 15 Jan | MAE | P90 abs error)")
    for c in ["03:00", "05:00", "08:00", "09:00", "10:00"]:
        r, _ = build_rows(actuals, forecasts, cutoff=c)
        m = metrics(r)
        used = r[14 * 24]["publishTime"]
        print(f"  cutoff {c}: {used} | {m['mae_mw']} MW | {m['p90_abs_error_mw']} MW")
