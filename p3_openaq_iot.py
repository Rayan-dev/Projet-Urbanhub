"""Partie 3 – Flux IoT : pollution (OpenAQ API v3), villes françaises cibles.

Prérequis : clé gratuite sur https://explore.openaq.org  puis
    export OPENAQ_API_KEY="..."            (Windows : set OPENAQ_API_KEY=...)

Usage :
    python p3_openaq_iot.py discover            # liste capteurs -> data/raw/openaq/sensors.csv
    python p3_openaq_iot.py backfill --days 30  # historique horaire -> data/raw/openaq/history/
    python p3_openaq_iot.py stream --interval 600   # simulation flux IoT (relevés "latest")
"""
import argparse
import csv
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from config import RAW, CITIES

API = "https://api.openaq.org/v3"
OUT = RAW / "openaq"
POLLUTANTS = {"pm25", "pm10", "no2", "o3", "co"}
FIELDS = ["sensor_id", "location_id", "city", "pollutant", "value", "unit",
          "timestamp", "latitude", "longitude"]

session = requests.Session()
session.headers["X-API-Key"] = os.environ.get("OPENAQ_API_KEY", "")


def get(path, **params):
    """GET avec respect de la limite (~60 req/min) et reprise sur 429/5xx."""
    for attempt in range(6):
        r = session.get(f"{API}{path}", params=params, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            try:
                wait = max(5, int(float(r.headers.get("x-ratelimit-reset", ""))))
            except ValueError:
                wait = 10 * (attempt + 1)
            print(f"  limite atteinte, pause {wait}s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        time.sleep(1.05)
        return r.json()
    raise RuntimeError(f"échec {path}")


def discover():
    rows = []
    for city, (lat, lon) in CITIES.items():
        bbox = f"{lon-0.2},{lat-0.15},{lon+0.2},{lat+0.15}"   # minLon,minLat,maxLon,maxLat
        locs = get("/locations", bbox=bbox, limit=1000)["results"]
        for loc in locs:
            c = loc.get("coordinates") or {}
            for s in loc.get("sensors", []):
                p = s["parameter"]
                if p["name"] in POLLUTANTS:
                    rows.append({"sensor_id": s["id"], "location_id": loc["id"],
                                 "location_name": loc.get("name"), "city": city,
                                 "pollutant": p["name"], "unit": p.get("units"),
                                 "latitude": c.get("latitude"), "longitude": c.get("longitude"),
                                 "last_seen": (loc.get("datetimeLast") or {}).get("utc")})
        print(f"{city}: {len(locs)} sites")
    df = pd.DataFrame(rows)
    # on garde les capteurs encore actifs (vus dans les 7 derniers jours)
    df["last_seen"] = pd.to_datetime(df["last_seen"], utc=True, errors="coerce")
    df = df[df["last_seen"] >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=7)]
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "sensors.csv", index=False)
    print(f"{len(df)} capteurs actifs :\n", df.groupby(["city", "pollutant"]).size().unstack(fill_value=0))
    return df


def sensors():
    p = OUT / "sensors.csv"
    return pd.read_csv(p) if p.exists() else discover()


def backfill(days):
    sens = sensors()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    dest = OUT / "history"
    dest.mkdir(parents=True, exist_ok=True)
    for i, s in enumerate(sens.itertuples(), 1):
        f = dest / f"{s.sensor_id}.csv"
        if f.exists():
            continue
        rows, page = [], 1
        while True:
            res = get(f"/sensors/{s.sensor_id}/hours", datetime_from=start.isoformat(),
                      datetime_to=end.isoformat(), limit=1000, page=page)["results"]
            for m in res:
                rows.append({"sensor_id": s.sensor_id, "location_id": s.location_id, "city": s.city,
                             "pollutant": s.pollutant, "value": m["value"], "unit": s.unit,
                             "timestamp": m["period"]["datetimeFrom"]["utc"],
                             "latitude": s.latitude, "longitude": s.longitude})
            if len(res) < 1000:
                break
            page += 1
        pd.DataFrame(rows, columns=FIELDS).to_csv(f, index=False)
        print(f"[{i}/{len(sens)}] capteur {s.sensor_id} {s.city} {s.pollutant}: {len(rows)} heures")


def stream(interval):
    sens = sensors()
    meta = sens.set_index("sensor_id")
    while True:
        t0 = time.time()
        now = datetime.now(timezone.utc)
        rows = []
        for loc_id in sens["location_id"].unique():
            try:
                res = get(f"/locations/{loc_id}/latest")["results"]
            except Exception as e:
                print("  erreur", loc_id, e)
                continue
            for m in res:
                sid = m.get("sensorsId")
                if sid not in meta.index:
                    continue
                s = meta.loc[sid]
                rows.append({"sensor_id": sid, "location_id": loc_id, "city": s.city,
                             "pollutant": s.pollutant, "value": m["value"], "unit": s.unit,
                             "timestamp": m["datetime"]["utc"],
                             "latitude": s.latitude, "longitude": s.longitude})
        path = OUT / "stream" / f"date={now:%Y-%m-%d}" / "readings.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, FIELDS)
            if new:
                w.writeheader()
            w.writerows(rows)
        print(f"{datetime.now():%H:%M:%S} {len(rows)} mesures reçues")
        time.sleep(max(0, interval - (time.time() - t0)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "backfill", "stream"])
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--interval", type=int, default=600)
    a = ap.parse_args()
    if not session.headers["X-API-Key"]:
        raise SystemExit("Définissez OPENAQ_API_KEY d'abord.")
    {"discover": discover, "backfill": lambda: backfill(a.days), "stream": lambda: stream(a.interval)}[a.cmd]()
