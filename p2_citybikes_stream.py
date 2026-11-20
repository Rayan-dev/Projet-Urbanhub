"""Partie 2 – Flux Streaming : vélos en libre-service, principales villes de France.

Un relevé toutes les 150 s, ajouté au data lake :
    data/raw/citybikes/date=YYYY-MM-DD/snapshots.csv

Sources :
  - CityBikes API (api.citybik.es) pour tous les réseaux français des villes cibles.
    L'API publique est limitée à 300 « unités » par heure, et une requête coûte d'autant plus
    d'unités que le réseau a de stations (Vélib' ≈ 25 unités, petit réseau ≈ 1). Le script mesure
    le coût réel de chaque réseau dans les en-têtes (ratelimit-remaining / ratelimit-reset) et
    répartit le quota : réseaux interrogés du plus ancien relevé au plus récent, tant que le budget
    le permet. Il ne dépasse jamais le quota et ne s'arrête jamais.
  - Paris (Vélib') : flux GBFS open data officiel de Vélib' Métropole (celui que CityBikes agrège),
    sans quota, interrogé à chaque relevé. network_id = "velib-gbfs". Si ce flux échoue, Vélib'
    repasse par CityBikes.

Usage :
    python p2_citybikes_stream.py                 # Ctrl+C pour arrêter
    python p2_citybikes_stream.py --interval 180
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone

import requests

from config import RAW, nearest_city

API = "https://api.citybik.es/v2/networks"
GBFS_VELIB = "https://velib-metropole-opendata.smovengo.cloud/opendata/Velib_Metropole"
OUT = RAW / "citybikes"
NETS_CACHE = RAW / "citybikes_networks.json"
FIELDS = ["poll_time", "network_id", "city", "station_id", "station_name",
          "latitude", "longitude", "bikes_available", "free_slots", "timestamp"]
SAFETY = 0.85                 # part du quota restant que l'on s'autorise à utiliser
RESERVE = 5                   # unités jamais dépensées
CREDIT_CAP = 80               # crédit maximal accumulé entre deux relevés
FALLBACK_PER_HOUR = 60
DEFAULT_COST = {"velib": 25.0}

session = requests.Session()
session.headers["User-Agent"] = "UrbanHub-student-project"

quota = {"remaining": None, "reset": None, "limit": None, "seen": 0.0}
cost = {}                     # coût mesuré par réseau (unités de quota)
velib_info = {"stations": None, "fetched": 0.0}


class QuotaExceeded(Exception):
    pass


def _hdr(r, name):
    for key in (f"ratelimit-{name}", f"x-ratelimit-{name}"):
        if key in r.headers:
            try:
                return int(float(r.headers[key]))
            except ValueError:
                return None
    return None


def reset_left():
    if quota["reset"] is None:
        return None
    return quota["reset"] - (time.time() - quota["seen"])


def citybikes_get(url, **params):
    r = session.get(url, params=params, timeout=30)
    rem, reset, lim = _hdr(r, "remaining"), _hdr(r, "reset"), _hdr(r, "limit")
    if reset is not None:
        quota.update(remaining=rem, reset=reset, limit=lim or quota["limit"], seen=time.time())
    if r.status_code == 429:
        quota.update(remaining=0, reset=reset if reset is not None else 300, seen=time.time())
        raise QuotaExceeded()
    r.raise_for_status()
    return r.json()


def french_networks():
    """Réseaux français des villes cibles (mis en cache : aucune requête à chaque relance)."""
    while not NETS_CACHE.exists():
        try:
            nets = citybikes_get(API, fields="id,name,location")["networks"]
            nets = [n for n in nets if n["location"].get("country") == "FR"]
            NETS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            NETS_CACHE.write_text(json.dumps(nets), encoding="utf-8")
        except QuotaExceeded:
            wait = int(reset_left() or 300) + 5
            print(f"{datetime.now():%H:%M:%S} quota CityBikes atteint, attente {wait // 60} min...", flush=True)
            time.sleep(wait)
    nets = json.loads(NETS_CACHE.read_text(encoding="utf-8"))
    for n in nets:
        n["city"] = nearest_city(n["location"]["latitude"], n["location"]["longitude"])
    return [n for n in nets if n["city"]]


def budget_units(interval):
    """Unités de quota attribuées à ce relevé."""
    left = reset_left()
    if left is None:
        return FALLBACK_PER_HOUR * interval / 3600
    if left <= 0:   # quota remis à zéro depuis la dernière réponse
        return (quota["limit"] or FALLBACK_PER_HOUR) * interval / 3600 * SAFETY
    usable = max(0, (quota["remaining"] or 0) - RESERVE) * SAFETY
    return usable / max(1.0, left / interval)


def remaining_estimate():
    left = reset_left()
    if left is None or left <= 0:
        return quota["limit"] or FALLBACK_PER_HOUR
    return quota["remaining"] or 0


def fetch_velib_gbfs():
    """Stations Vélib' via le flux GBFS officiel (pas de quota)."""
    if velib_info["stations"] is None or time.time() - velib_info["fetched"] > 6 * 3600:
        info = session.get(f"{GBFS_VELIB}/station_information.json", timeout=30).json()
        velib_info["stations"] = {s["station_id"]: s for s in info["data"]["stations"]}
        velib_info["fetched"] = time.time()
    status = session.get(f"{GBFS_VELIB}/station_status.json", timeout=30).json()["data"]["stations"]
    out = []
    for s in status:
        meta = velib_info["stations"].get(s["station_id"])
        if meta is None or s.get("is_installed", 1) == 0:
            continue
        ts = s.get("last_reported")
        out.append({
            "id": f"velib-{meta.get('stationCode', s['station_id'])}",
            "name": meta.get("name"),
            "latitude": meta.get("lat"),
            "longitude": meta.get("lon"),
            "free_bikes": s.get("num_bikes_available"),
            "empty_slots": s.get("num_docks_available"),
            "timestamp": datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
        })
    return out


def write_rows(now, network_id, city, stations):
    rows = [{
        "poll_time": now.isoformat(),
        "network_id": network_id,
        "city": city,
        "station_id": s["id"],
        "station_name": s.get("name"),
        "latitude": s.get("latitude"),
        "longitude": s.get("longitude"),
        "bikes_available": s.get("free_bikes"),
        "free_slots": s.get("empty_slots"),
        "timestamp": s.get("timestamp"),
    } for s in stations]
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
    ap.add_argument("--interval", type=int, default=150, help="secondes entre deux relevés")
    args = ap.parse_args()

    nets = french_networks()
    last = {n["id"]: 0.0 for n in nets}
    print(f"{len(nets)} réseaux CityBikes :", ", ".join(f"{n['id']} ({n['city']})" for n in nets), flush=True)
    print(f"Paris via le flux GBFS Vélib' à chaque relevé ; CityBikes réparti selon le quota. "
          f"Relevé toutes les {args.interval} s.", flush=True)

    credit, i = 0.0, 0
    while True:
        t0 = time.time()
        now = datetime.now(timezone.utc)
        n_st, done = 0, []

        # 1) Paris : flux GBFS officiel
        gbfs_ok = False
        try:
            n_st += write_rows(now, "velib-gbfs", "Paris", fetch_velib_gbfs())
            done.append("velib-gbfs")
            gbfs_ok = True
        except Exception as e:
            print(f"  flux GBFS Vélib' indisponible ({e}) : Vélib' passe par CityBikes", flush=True)

        # 2) CityBikes : du relevé le plus ancien au plus récent, dans la limite du crédit
        credit = min(credit + budget_units(args.interval), CREDIT_CAP)
        todo = sorted((n for n in nets if not (gbfs_ok and n["id"] == "velib")), key=lambda n: last[n["id"]])
        for net in todo:
            c = cost.get(net["id"], DEFAULT_COST.get(net["id"], 3.0))
            if c > credit or remaining_estimate() - c < RESERVE:
                break                     # on économise pour ce réseau au prochain relevé
            rem0, left0 = quota["remaining"], reset_left()
            try:
                data = citybikes_get(f"{API}/{net['id']}", fields="stations")
            except QuotaExceeded:
                print(f"  quota CityBikes atteint : reprise automatique dans {int(reset_left() or 0) // 60} min",
                      flush=True)
                credit = 0.0
                break
            except Exception as e:
                print(f"  erreur {net['id']} : {e}", flush=True)
                last[net["id"]] = time.time()
                continue
            n_st += write_rows(now, net["id"], net["city"], data["network"]["stations"])
            done.append(net["id"])
            last[net["id"]] = time.time()
            # coût réel de cette requête
            if rem0 is not None and left0 is not None and left0 > 0 and quota["remaining"] is not None \
                    and quota["remaining"] < rem0:
                measured = rem0 - quota["remaining"]
                cost[net["id"]] = 0.5 * cost.get(net["id"], measured) + 0.5 * measured
            credit -= cost.get(net["id"], c)

        q = ""
        if quota["remaining"] is not None:
            q = f" | quota CityBikes {quota['remaining']}/{quota['limit'] or '?'}, " \
                f"remise à zéro dans {max(0, reset_left() or 0) / 60:.0f} min"
        print(f"{datetime.now():%H:%M:%S} relevé {i}: {n_st} stations ({', '.join(done) or 'aucune'}){q}",
              flush=True)
        i += 1
        time.sleep(max(0, args.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
