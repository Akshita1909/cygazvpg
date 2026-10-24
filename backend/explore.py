import json
import urllib.request
from collections import defaultdict

url = ("https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream"
       "?publishDateTimeFrom=2026-01-01T00:00:00Z"
       "&publishDateTimeTo=2026-01-02T00:00:00Z")

with urllib.request.urlopen(url) as r:
    rows = json.load(r)

print("total rows:", len(rows))

by_publish = defaultdict(list)
for row in rows:
    by_publish[row["publishTime"]].append(row["startTime"])

print("distinct publish times:", len(by_publish))
for pub in sorted(by_publish):
    starts = sorted(by_publish[pub])
    print(pub, "| rows:", len(starts), "| first target:", starts[0], "| last target:", starts[-1])
