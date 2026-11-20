#!/usr/bin/env python
"""
p1_noaa_batch.py - Partie 1 UrbanHub : flux batch NOAA Global Hourly.

Commandes :
    python p1_noaa_batch.py download   # télécharge les CSV NOAA (parallèle, reprise possible)
    python p1_noaa_batch.py clean      # décode, nettoie, agrège -> data/clean/weather_city_hourly.parquet
    python p1_noaa_batch.py all        # download + clean

Sortie : data/clean/weather_city_hourly.parquet
    colonnes : city, hour (UTC, floor "h"), temp_c, wind_ms, slp_hpa, vis_km,
               precip_mm (cumul 1 h), precip_period_h (=1 quand precip_mm est renseigné), n_stations
Rapport : report/p1_missing_rates.md (taux de manquants avant/après)
"""
import argparse
import math
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
RAW = ROOT / "data" / "raw" / "noaa"
CLEAN = ROOT / "data" / "clean"
REPORT = ROOT / "report"
OUT = CLEAN / "weather_city_hourly.parquet"

ISD_URL = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
BASE_URL = "https://noaa-global-hourly-pds.s3.amazonaws.com/{year}/{sid}.csv"

WANT = {"STATION", "DATE", "LATITUDE", "LONGITUDE", "TMP", "WND", "SLP", "VIS", "AA1"}
BAD_Q = {"2", "3", "6", "7"}            # codes qualité suspects / erronés -> écartés
VARS = ["temp_c", "wind_ms", "slp_hpa", "vis_km", "precip_mm"]
LABELS = {"temp_c": "Température (°C)", "wind_ms": "Vent (m/s)", "slp_hpa": "Pression (hPa)",
          "vis_km": "Visibilité (km)", "precip_mm": "Précipitations 1 h (mm)"}


# ----------------------------------------------------------------------------- utilitaires
def progress(iterable, total, desc):
    try:
        from tqdm import tqdm
        return tqdm(iterable, total=total, desc=desc, unit="fichier")
    except ImportError:
        def gen():
            for i, x in enumerate(iterable, 1):
                if i % 50 == 0 or i == total:
                    print(f"{desc}: {i}/{total}", flush=True)
                yield x
        return gen()


def haversine_km(lat, lon, lats, lons):
    lat, lon = math.radians(lat), math.radians(lon)
    lats, lons = np.radians(lats), np.radians(lons)
    a = np.sin((lats - lat) / 2) ** 2 + np.cos(lat) * np.cos(lats) * np.sin((lons - lon) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


def _ll(v):
    """Extrait (lat, lon) d'une valeur de config (tuple/liste ou dict)."""
    a = b = None
    if isinstance(v, (list, tuple)) and len(v) >= 2 and all(isinstance(x, (int, float)) for x in v[:2]):
        a, b = float(v[0]), float(v[1])
        if not (41 <= a <= 52 and -6 <= b <= 10) and (41 <= b <= 52 and -6 <= a <= 10):
            a, b = b, a                      # ordre (lon, lat) -> (lat, lon)
    elif isinstance(v, dict):
        a = next((v[k] for k in ("lat", "latitude", "LAT") if k in v), None)
        b = next((v[k] for k in ("lon", "lng", "long", "longitude", "LON") if k in v), None)
        if not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
            return None
        a, b = float(a), float(b)
    return (a, b) if a is not None and b is not None else None


def _parse_cities(obj):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            ll = _ll(v)
            if isinstance(k, str) and ll:
                out[k] = ll
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            if isinstance(v, dict):
                name = next((v[k] for k in ("name", "city", "nom", "ville") if k in v), None)
                ll = _ll(v)
                if isinstance(name, str) and ll:
                    out[name] = ll
    return out if len(out) >= 2 else None


def load_cities():
    """Villes et coordonnées depuis config.py (noms EXACTS conservés)."""
    try:
        import config
    except ImportError:
        sys.exit("config.py introuvable : lancez le script depuis la racine du projet.")
    names = [n for n in dir(config) if not n.startswith("_")]
    preferred = [n for n in ("CITIES", "CITY_COORDS", "VILLES", "CITY_LIST", "cities") if n in names]
    for n in preferred + [n for n in names if n not in preferred]:
        cities = _parse_cities(getattr(config, n))
        if cities:
            print(f"Villes lues dans config.{n} : {', '.join(cities)}")
            return cities
    sys.exit("Impossible de lire les villes dans config.py (attributs trouvés : "
             f"{names}). Envoyez-moi config.py et j'adapte load_cities().")


# ----------------------------------------------------------------------------- download
def list_stations(years, max_km, cities):
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / "isd-history.csv"
    if not cache.exists() or time.time() - cache.stat().st_mtime > 7 * 86400:
        print("Téléchargement de la liste des stations (isd-history.csv)…")
        req = urllib.request.Request(ISD_URL, headers={"User-Agent": "UrbanHub-student-project"})
        with urllib.request.urlopen(req, timeout=120) as r:
            cache.write_bytes(r.read())
    st = pd.read_csv(cache, dtype=str)
    st = st[st["CTRY"] == "FR"].copy()
    st["LAT"], st["LON"] = pd.to_numeric(st["LAT"], errors="coerce"), pd.to_numeric(st["LON"], errors="coerce")
    st = st.dropna(subset=["LAT", "LON"])
    today = date.today()
    start_ok = f"{today.year - years}0101"
    st = st[(st["BEGIN"] <= start_ok) & (st["END"] >= f"{today.year - 1}0101")]      # actives depuis N ans
    st["sid"] = st["USAF"] + st["WBAN"].str.zfill(5)
    clat = np.array([v[0] for v in cities.values()])
    clon = np.array([v[1] for v in cities.values()])
    keep = [bool(haversine_km(r.LAT, r.LON, clat, clon).min() <= max_km) for r in st.itertuples()]
    st = st[keep]
    print(f"{len(st)} stations FR actives depuis {years} ans à moins de {max_km} km d'une ville.")
    return st["sid"].tolist()


def fetch(task):
    year, sid = task
    dest = RAW / str(year) / f"{sid}.csv"
    if dest.exists() and dest.stat().st_size > 0:
        fresh = year < date.today().year or (time.time() - dest.stat().st_mtime) < 6 * 3600
        if fresh:
            return "déjà présent"
    url = BASE_URL.format(year=year, sid=sid)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "UrbanHub-student-project"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            if b"STATION" not in data[:300]:           # page d'erreur HTML, réponse tronquée…
                return "invalide"
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(dest)
            return "téléchargé"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "absent"
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return "échec"


def download(years=5, max_km=50, workers=32):
    cities = load_cities()
    sids = list_stations(years, max_km, cities)
    this = date.today().year
    tasks = [(y, s) for y in range(this - years, this + 1) for s in sids]
    print(f"{len(tasks)} fichiers à vérifier, {workers} téléchargements parallèles…")
    counts = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for res in progress(ex.map(fetch, tasks), len(tasks), "download"):
            counts[res] = counts.get(res, 0) + 1
    print("Bilan download :", counts)
    if counts.get("échec"):
        print("Des téléchargements ont échoué : relancez la même commande (reprise automatique).")


# ----------------------------------------------------------------------------- clean
def _col(df, c):
    return df[c] if c in df.columns else pd.Series(pd.NA, index=df.index, dtype="string")


def _split(s, n):
    return s.astype("string").str.split(",", expand=True).reindex(columns=range(n))


def _num(s):
    return pd.to_numeric(s, errors="coerce").astype("float64")


def _decode(v, q, sentinel, scale, lo, hi):
    """before = sentinelle -> NaN + mise à l'échelle ; after = + codes qualité écartés + bornes physiques."""
    before = v.where(v != sentinel) / scale
    q = q.astype("string").str.strip()
    badq = q.isin(BAD_Q).fillna(False).to_numpy(dtype=bool)
    after = before.mask(badq)
    after = after.where((after >= lo) & (after <= hi))
    return before, after


def parse_file(path):
    path = Path(path)
    try:
        df = pd.read_csv(path, usecols=lambda c: c in WANT, dtype=str, low_memory=False)
    except Exception as e:
        return {"path": str(path), "error": f"lecture impossible ({type(e).__name__})"}
    missing = [c for c in ("STATION", "DATE", "LATITUDE", "LONGITUDE") if c not in df.columns]
    if missing:
        return {"path": str(path), "error": f"colonnes absentes {missing}"}
    dt = pd.to_datetime(df["DATE"], errors="coerce", utc=True)
    df, dt = df[dt.notna()], dt[dt.notna()]
    if df.empty:
        return {"path": str(path), "error": "fichier vide"}
    lat, lon = _num(df["LATITUDE"]).median(), _num(df["LONGITUDE"]).median()
    if pd.isna(lat) or pd.isna(lon):
        return {"path": str(path), "error": "coordonnées absentes"}

    tmp, wnd = _split(_col(df, "TMP"), 2), _split(_col(df, "WND"), 5)
    slp, vis, aa = _split(_col(df, "SLP"), 2), _split(_col(df, "VIS"), 4), _split(_col(df, "AA1"), 4)

    dec = {
        "temp_c": _decode(_num(tmp[0]), tmp[1], 9999, 10, -70, 60),        # ×10 °C
        "wind_ms": _decode(_num(wnd[3]), wnd[4], 9999, 10, 0, 100),        # ×10 m/s
        "slp_hpa": _decode(_num(slp[0]), slp[1], 99999, 10, 850, 1100),    # ×10 hPa
        "vis_km": _decode(_num(vis[0]), vis[1], 999999, 1000, 0, 160),     # m -> km
    }
    pb, pa = _decode(_num(aa[1]), aa[3], 9999, 10, 0, 300)                 # ×10 mm
    period = _num(aa[0])
    dec["precip_mm"] = (pb, pa.where(period == 1))                         # seulement les cumuls sur 1 h

    o = pd.DataFrame({"hour": dt.dt.floor("h")}, index=df.index)
    stats = {}
    for v in VARS:
        before, after = dec[v]
        o[v] = after
        stats[v] = (len(df), int(before.isna().sum()), int(after.isna().sum()))
    g = o.groupby("hour", as_index=False).mean()
    return {"path": str(path), "station": path.stem, "lat": float(lat), "lon": float(lon), "data": g, "stats": stats}


def clean(max_km=50, keep_bad=False):
    cities = load_cities()
    cnames = list(cities)
    clat = np.array([cities[c][0] for c in cnames])
    clon = np.array([cities[c][1] for c in cnames])

    files = sorted(RAW.glob("*/*.csv"))
    if not files:
        sys.exit("Aucun CSV dans data/raw/noaa/ : lancez d'abord `python p1_noaa_batch.py download`.")
    print(f"Nettoyage de {len(files)} fichiers…")

    bad, frames, tot, far = [], [], {v: [0, 0, 0] for v in VARS}, set()
    with ProcessPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as ex:
        for res in progress(ex.map(parse_file, files, chunksize=4), len(files), "clean"):
            if "error" in res:
                bad.append((res["path"], res["error"]))
                continue
            d = haversine_km(res["lat"], res["lon"], clat, clon)
            i = int(d.argmin())
            if d[i] > max_km:
                far.add(res["station"])
                continue
            g = res["data"]
            g["city"] = cnames[i]
            frames.append(g)
            for v in VARS:
                for k in range(3):
                    tot[v][k] += res["stats"][v][k]

    if bad:
        log = RAW / "_fichiers_invalides.txt"
        log.write_text("\n".join(f"{p}\t{e}" for p, e in bad), encoding="utf-8")
        print(f"⚠️  {len(bad)} fichier(s) invalide(s) ignoré(s) (liste : {log}).")
        if not keep_bad:
            for p, _ in bad:
                Path(p).unlink(missing_ok=True)
            print("   Supprimés : relancez `python p1_noaa_batch.py download` pour les retélécharger.")
    if far:
        print(f"{len(far)} station(s) à plus de {max_km} km de toute ville : ignorées.")
    if not frames:
        sys.exit("Aucune donnée exploitable après nettoyage.")

    allh = pd.concat(frames, ignore_index=True)
    allh["_n"] = 1
    ch = allh.groupby(["city", "hour"], as_index=False).agg(
        temp_c=("temp_c", "mean"), wind_ms=("wind_ms", "mean"), slp_hpa=("slp_hpa", "mean"),
        vis_km=("vis_km", "mean"), precip_mm=("precip_mm", "mean"), n_stations=("_n", "sum"))
    ch["precip_period_h"] = np.where(ch["precip_mm"].notna(), 1.0, np.nan)
    ch = ch[["city", "hour", "temp_c", "wind_ms", "slp_hpa", "vis_km", "precip_mm", "precip_period_h", "n_stations"]]
    ch = ch.sort_values(["city", "hour"]).reset_index(drop=True)

    try:
        from urbanhub_utils import check_city_hourly
        check_city_hourly(ch)
        print("check_city_hourly : OK")
    except ImportError:
        print("urbanhub_utils introuvable : contrôle ignoré.")
    CLEAN.mkdir(parents=True, exist_ok=True)
    ch.to_parquet(OUT, index=False)
    print(f"✅ {OUT} : {len(ch)} lignes, {ch['city'].nunique()} villes, {ch['hour'].min()} -> {ch['hour'].max()}")
    print(ch.groupby("city").agg(heures=("hour", "size"), stations=("n_stations", "max")).to_string())

    # taux de manquants : observations (avant/après) + grille horaire complète par ville
    grid_na, grid_n = {v: 0 for v in VARS}, 0
    for _, sub in ch.groupby("city"):
        idx = pd.date_range(sub["hour"].min(), sub["hour"].max(), freq="h")
        g = sub.set_index("hour").reindex(idx)
        grid_n += len(g)
        for v in VARS:
            grid_na[v] += int(g[v].isna().sum())
    rows = ["| Variable | Manquants avant nettoyage (%) | Manquants après nettoyage (%) | Manquants grille horaire ville (%) |",
            "|---|---|---|---|"]
    for v in VARS:
        n, mb, ma = tot[v]
        rows.append(f"| {LABELS[v]} | {100 * mb / max(n, 1):.1f} | {100 * ma / max(n, 1):.1f} | {100 * grid_na[v] / max(grid_n, 1):.1f} |")
    table = "\n".join(rows)
    note = ("\n\n*Avant* = valeur absente ou sentinelle (999/9999/99999) ; *après* = + codes qualité 2/3/6/7 écartés "
            "+ bornes physiques (+ cumul 1 h uniquement pour les précipitations). Pour les précipitations, l'absence "
            "de champ AA1 est comptée comme manquante. *Grille* = part d'heures sans valeur par ville après "
            "agrégation sur une grille horaire complète.\n")
    REPORT.mkdir(exist_ok=True)
    (REPORT / "p1_missing_rates.md").write_text("# Taux de valeurs manquantes (Partie 1)\n\n" + table + note, encoding="utf-8")
    print("\nTaux de manquants :\n" + table)


# ----------------------------------------------------------------------------- CLI
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Flux batch NOAA Global Hourly (UrbanHub, Partie 1)")
    ap.add_argument("command", choices=["download", "clean", "all"])
    ap.add_argument("--years", type=int, default=5, help="profondeur historique (défaut 5)")
    ap.add_argument("--max-km", type=float, default=50, help="distance max station-ville (défaut 50 km)")
    ap.add_argument("--workers", type=int, default=32, help="téléchargements parallèles (défaut 32)")
    ap.add_argument("--keep-bad", action="store_true", help="ne pas supprimer les fichiers invalides")
    a = ap.parse_args()
    if a.command in ("download", "all"):
        download(a.years, a.max_km, a.workers)
    if a.command in ("clean", "all"):
        clean(a.max_km, a.keep_bad)
