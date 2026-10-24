"""Download January 2026 wind data from Elexon and save it as local JSON.

Actuals  : FUELHH (WIND only), half-hourly, settlement dates 1-31 Jan 2026
Forecasts: WINDFOR, hourly targets, every forecast published 30 Dec 2025 - 31 Jan 2026
           (we need late-December publishes because they cover 1 Jan targets)
"""
import json
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
DATA_DIR = Path(__file__).parent / "data"


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def fetch_actuals():
    url = (f"{BASE}/FUELHH/stream"
           "?settlementDateFrom=2026-01-01&settlementDateTo=2026-01-31"
           "&fuelType=WIND")
    rows = get_json(url)
    out = {}
    for r in rows:
        out[r["startTime"]] = r["generation"]
    return [{"startTime": k, "generation": out[k]} for k in sorted(out)]


def fetch_forecasts():
    seen = {}
    day = date(2025, 12, 30)
    last = date(2026, 1, 31)
    while day <= last:
        nxt = day + timedelta(days=1)
        url = (f"{BASE}/WINDFOR/stream"
               f"?publishDateTimeFrom={day}T00:00:00Z"
               f"&publishDateTimeTo={nxt}T00:00:00Z")
        for r in get_json(url):
            key = (r["publishTime"], r["startTime"])
            seen[key] = r["generation"]
        print("fetched forecasts published on", day)
        day = nxt
    return [{"publishTime": p, "startTime": s, "generation": seen[(p, s)]}
            for (p, s) in sorted(seen)]


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True)

    actuals = fetch_actuals()
    (DATA_DIR / "wind_actuals.json").write_text(json.dumps(actuals))
    print("actual rows:", len(actuals), "(expect 1488 = 31 days x 48)")

    forecasts = fetch_forecasts()
    (DATA_DIR / "wind_forecasts.json").write_text(json.dumps(forecasts))
    print("forecast rows:", len(forecasts))
    print("distinct publish times:", len({f["publishTime"] for f in forecasts}))
