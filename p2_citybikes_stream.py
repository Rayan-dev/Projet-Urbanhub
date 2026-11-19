"""Partie 2 – Flux Streaming : vélos en libre-service (CityBikes API), réseaux français.

Interroge l'API à intervalle régulier et ajoute chaque relevé au data lake :
    data/raw/citybikes/date=YYYY-MM-DD/snapshots.csv

Quota : l'API publique CityBikes limite le nombre de requêtes par heure (une requête par
réseau et par relevé). Le script lit le quota réel dans les en-têtes de réponse
(ratelimit-remaining / ratelimit-reset) et répartit les requêtes restantes sur l'heure :
  - Vélib' (Paris) est interrogé à chaque relevé (priorité) ;
  - les autres réseaux sont interrogés à tour de rôle avec le budget restant.
Il ne dépasse donc plus le quota, et attend la remise à zéro si besoin au lieu de planter.

Usage :
    python p2_citybikes_stream.py                 # relevé toutes les 150 s (Ctrl+C pour arrêter)
    python p2_citybikes_stream.py --interval 180
    python p2_citybikes_stream.py --all-fr        # tous les réseaux français
"""
import argparse
import csv
import json
import time
from collections import deque
from datetime import datetime, timezone

import requests

from config import RAW, nearest_city

API = "https://api.citybik.es/v2/networks"
OUT = RAW / "citybikes"
NETS_CACHE = RAW / "citybikes_networks.json"
FIELDS = ["poll_time", "network_id", "city", "station_id", "station_name",
          "latitude", "longitude", "bikes_available", "free_slots", "timestamp"]
PRIORITY = ["velib"]          # interrogés à chaque relevé
SAFETY = 0.85                 # on n'utilise que 85 % du quota restant
FALLBACK_PER_HOUR = 60        # si l'API ne renvoie pas d'en-têtes de quota

session = requests.Session()
session.headers["User-Agent"] = "UrbanHub-student-project"

quota = {"remaining": None, "reset": None, "limit": None, "seen": 0.0}
# Coût moyen d'une requête en unités de quota (mesuré : les gros réseaux comptent plusieurs unités)
cost = {"per_req": 4.0}


def _hdr(r, name):
    for key in (f"ratelimit-{name}", f"x-ratelimit-{name}"):
        if key in r.headers:
            try:
                return int(float(r.headers[key]))
            except ValueError:
                return None
    return None


def get(url, **params):
    """GET : met à jour l'état du quota ; sur 429, attend la remise à zéro puis réessaie."""
    while True:
        r = session.get(url, params=params, timeout=30)
        rem, reset, lim = _hdr(r, "remaining"), _hdr(r, "reset"), _hdr(r, "limit")
        if reset is not None:
            quota.update(remaining=rem, reset=reset, limit=lim, seen=time.time())
        if r.status_code == 429:
            wait = (reset if reset is not None else 300) + 5
            quota.update(remaining=0, reset=wait, seen=time.time())
            print(f"{datetime.now():%H:%M:%S} quota CityBikes atteint, attente {wait // 60} min {wait % 60} s...",
                  flush=True)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()


def french_networks(all_fr, refresh=False):
    """Liste des réseaux français ; mise en cache pour ne pas consommer de requête à chaque relance."""
    if NETS_CACHE.exists() and not refresh:
        nets = json.loads(NETS_CACHE.read_text(encoding="utf-8"))
    else:
        nets = get(API, fields="id,name,location")["networks"]
        nets = [n for n in nets if n["location"].get("country") == "FR"]
        NETS_CACHE.parent.mkdir(parents=True, exist_ok=True)
        NETS_CACHE.write_text(json.dumps(nets), encoding="utf-8")
    for n in nets:
        n["city"] = nearest_city(n["location"]["latitude"], n["location"]["longitude"])
    if not all_fr:
        nets = [n for n in nets if n["city"]]
    return nets


def budget(interval):
    """Nombre de requêtes autorisées pour ce relevé, d'après le quota restant."""
    if quota["reset"] is None:
        return max(1, int(FALLBACK_PER_HOUR * interval / 3600))
    elapsed = time.time() - quota["seen"]
    reset_left = quota["reset"] - elapsed
    c = cost["per_req"]
    if reset_left <= 0:                       # le quota a été remis à zéro depuis
        return max(1, int((quota["limit"] or FALLBACK_PER_HOUR) * interval / 3600 * SAFETY / c))
    cycles_left = max(1.0, reset_left / interval)
    return int(max(0, quota["remaining"] or 0) * SAFETY / cycles_left / c)


def update_cost(before, n_requests):
    """Mesure le coût réel d'une requête à partir de la baisse du quota restant."""
    rem0, reset0 = before
    rem1, reset1 = quota["remaining"], quota["reset"]
    if None in (rem0, rem1, reset0, reset1) or n_requests == 0:
        return
    if rem1 < rem0 and reset1 <= reset0:      # même fenêtre horaire
        measured = (rem0 - rem1) / n_requests
        cost["per_req"] = max(1.0, 0.5 * cost["per_req"] + 0.5 * measured)


def write_rows(now, net, stations):
    rows = [{
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
    ap.add_argument("--all-fr", action="store_true")
    args = ap.parse_args()

    nets = french_networks(args.all_fr)
    prio = [n for n in nets if n["id"] in PRIORITY]
    others = deque(n for n in nets if n["id"] not in PRIORITY)
    print(f"{len(nets)} réseaux suivis :", ", ".join(f"{n['id']} ({n['city']})" for n in nets), flush=True)
    print(f"Prioritaire(s) à chaque relevé : {', '.join(n['id'] for n in prio) or 'aucun'} ; "
          f"les autres à tour de rôle selon le quota. Relevé toutes les {args.interval} s.", flush=True)

    i = 0
    while True:
        t0 = time.time()
        allowed = budget(args.interval)
        todo = prio[:allowed]
        while len(todo) < allowed and others and len(todo) < len(nets):
            todo.append(others[0])
            others.rotate(-1)
        now = datetime.now(timezone.utc)
        before = (quota["remaining"], quota["reset"])
        n_st, done = 0, []
        for net in todo:
            try:
                data = get(f"{API}/{net['id']}", fields="stations")
                n_st += write_rows(now, net, data["network"]["stations"])
                done.append(net["id"])
            except Exception as e:     # ne jamais arrêter la collecte pour une erreur ponctuelle
                print(f"  erreur {net['id']} : {e}", flush=True)
        update_cost(before, len(done))
        q = ""
        if quota["remaining"] is not None:
            q = f" | quota restant {quota['remaining']}"
            if quota["limit"]:
                q += f"/{quota['limit']}"
            q += f", remise à zéro dans {max(0, quota['reset'] - (time.time() - quota['seen'])) / 60:.0f} min"
            q += f", coût ~{cost['per_req']:.1f}/requête"
        if done:
            print(f"{datetime.now():%H:%M:%S} relevé {i}: {n_st} stations ({', '.join(done)}){q}", flush=True)
        else:
            print(f"{datetime.now():%H:%M:%S} relevé {i}: aucune requête (quota à économiser){q}", flush=True)
        i += 1
        time.sleep(max(0, args.interval - (time.time() - t0)))


if __name__ == "__main__":
    main()
