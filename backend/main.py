"""FastAPI backend for the wind forecast accuracy tool.

All numbers come from analysis.py, which reads the January 2026 snapshot in
data/. Every endpoint takes an optional `cutoff` (HH:MM, UTC, applied to the
day before delivery) so the buyer can test different decision times.
"""
import re
from collections import defaultdict
from datetime import date
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from analysis import DEFAULT_CUTOFF, build_rows, cutoff_for, iso, load_data, metrics

app = FastAPI(title="Wind forecast accuracy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

FIRST_DAY = date(2026, 1, 1)
LAST_DAY = date(2026, 1, 31)


@lru_cache(maxsize=1)
def data():
    return load_data()


@lru_cache(maxsize=64)
def rows_for(cutoff: str):
    actuals, forecasts = data()
    rows, _ = build_rows(actuals, forecasts, cutoff=cutoff)
    return rows


def check_cutoff(cutoff: str) -> str:
    m = re.fullmatch(r"(\d{2}):(\d{2})", cutoff)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise HTTPException(400, "cutoff must look like HH:MM (UTC), e.g. 09:00")
    return cutoff


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config():
    return {
        "first_day": FIRST_DAY.isoformat(),
        "last_day": LAST_DAY.isoformat(),
        "default_cutoff": DEFAULT_CUTOFF,
        "timezone_note": "All times are UTC. January in the UK is GMT, so UTC equals London time.",
    }


@app.get("/api/day")
def day(date_: str = Query(..., alias="date"), cutoff: str = DEFAULT_CUTOFF):
    """Everything the buyer needs for one delivery day."""
    cutoff = check_cutoff(cutoff)
    try:
        d = date.fromisoformat(date_)
    except ValueError:
        raise HTTPException(400, "date must look like 2026-01-15")
    if not (FIRST_DAY <= d <= LAST_DAY):
        raise HTTPException(404, "date must be between 2026-01-01 and 2026-01-31")

    hours = [r for r in rows_for(cutoff) if r["target"].startswith(d.isoformat())]
    return {
        "date": d.isoformat(),
        "decision_cutoff": iso(cutoff_for(d, cutoff)),
        "forecast_publish_times": sorted({r["publishTime"] for r in hours}),
        "hours": hours,
        "metrics": metrics(hours),
        "total_forecast_mwh": round(sum(r["forecast"] for r in hours), 1),
        "total_actual_mwh": round(sum(r["actual"] for r in hours), 1),
    }


@app.get("/api/summary")
def summary(cutoff: str = DEFAULT_CUTOFF):
    """January-wide error numbers, plus one row per delivery day."""
    cutoff = check_cutoff(cutoff)
    rows = rows_for(cutoff)

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["target"][:10]].append(r)

    daily = []
    for d in sorted(by_day):
        m = metrics(by_day[d])
        daily.append({
            "date": d,
            "mae_mw": m["mae_mw"],
            "bias_mw": m["bias_mw"],
            "mean_actual_mw": m["mean_actual_mw"],
        })

    over = sum(1 for r in rows if r["error"] > 0)
    return {
        "cutoff_utc": cutoff,
        "metrics": metrics(rows),
        "share_hours_over_forecast_pct": round(100 * over / len(rows), 1),
        "daily": daily,
    }


@app.get("/api/hourly-profile")
def hourly_profile(cutoff: str = DEFAULT_CUTOFF):
    """Error by hour of the day (UTC), averaged over January."""
    cutoff = check_cutoff(cutoff)
    by_hour = defaultdict(list)
    for r in rows_for(cutoff):
        by_hour[int(r["target"][11:13])].append(r)

    out = []
    for h in range(24):
        m = metrics(by_hour[h])
        out.append({
            "hour": h,
            "mae_mw": m["mae_mw"],
            "bias_mw": m["bias_mw"],
            "mean_actual_mw": m["mean_actual_mw"],
        })
    return out
