"""Partie 2 – Flux Streaming : vélos en libre-service (CityBikes API), réseaux français.

Interroge l'API toutes les 2 minutes et ajoute chaque relevé au data lake :
    data/raw/citybikes/date=YYYY-MM-DD/snapshots.csv

Usage :
    python p2_citybikes_stream.py              # tourne en continu (Ctrl+C pour arrêter)
    python p2_citybikes_stream.py --interval 180
    python p2_citybikes_stream.py --all-fr     # tous les réseaux français, pas seulement les villes cibles
"""
import argparse
import csv
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from config import RAW, nearest_city

API = "https://api.citybik.es/v2/networks"
OUT = RAW / "citybikes"
FIELDS = ["poll_time", "network_id", "city", "station_id", "station_name",
          "latitude", "longitude", "bikes_available", "free_slots", "timestamp"]

session = requests.Session()
session.headers["User-Agent"] = "UrbanHub-student-project"


def french_networks(all_fr):
    nets = session.get(API, params={"fields": "id,name,location"}, timeout=30).json()["networks"]
    nets = [n for n in nets if n["location"].get("country") == "FR"]
    for n in nets:
        n["city"] = nearest_city(n["location"]["latitude"], n["location"]["longitude"])
    if not all_fr:
        nets = [n for n in nets if n["city"]]
    return nets


def fetch(net):
    r = session.get(f"{API}/{net['id']}", params={"fields": "stations"}, timeout=30)
    r.raise_for_status()
    return net, r.json()["network"]["stations"]


def poll(nets):
    now = datetime.now(timezone.utc)
    rows = []
    with ThreadPoolExecutor(8) as pool:
        for fut in [pool.submit(fetch, n) for n in nets]:
            try:
                net, stations = fut.result()
            except Exception as e:
                print("  erreur réseau :", e)
                continue
            for s in stations:
                rows.append({
                    "poll_time": now.isoformat(),
                    "network_id": net["id"],
                    "city": net["city"] or net["location"].get("city"),
                    "station_id": s["id"],
                    "station_name": s.get("name"),
                    "latitude": s.get("latitude"),
                    "longitude": s.get("longitude"),
                    "bikes_available": s.get("free_bikes"),
                    "free_slots": s.get("empty_slots"),
                    "timestamp": s.get("timestamp"),
                })
    path = OUT / f"date={now:%Y-%m-%d}" / "snapshots.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=120, help="secondes entre deux relevés")
    ap.add_argument("--all-fr", action="store_true")
    args = ap.parse_args()
    nets = french_networks(args.all_fr)
    print(f"{len(nets)} réseaux suivis :", ", ".join(f"{n['id']} ({n['city']})" for n in nets))
    i = 0
    while True:
        t0 = time.time()
        try:
            n = poll(nets)
            print(f"{datetime.now():%H:%M:%S} relevé {i}: {n} stations")
        except Exception as e:  # ne jamais arrêter la collecte pour une erreur ponctuelle
            print("Erreur :", e)
        i += 1
        if i % 30 == 0:  # rafraîchit la liste des réseaux ~toutes les heures
            try:
                nets = french_networks(args.all_fr)
            except Exception:
                pass
        time.sleep(max(0, args.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
