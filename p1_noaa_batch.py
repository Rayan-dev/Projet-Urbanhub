"""Partie 1 – Flux Batch : météo NOAA Global Hourly, stations françaises, 5 dernières années.

Usage :
    python p1_noaa_batch.py download      # téléchargement parallèle -> data/raw/noaa/
    python p1_noaa_batch.py clean         # nettoyage -> data/clean/weather.parquet
    python p1_noaa_batch.py all
"""
import io
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

import numpy as np
import pandas as pd
import requests

from config import RAW, CLEAN, nearest_city

BASE = "https://www.ncei.noaa.gov/data/global-hourly/access"
HISTORY = "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv"
YEARS = list(range(date.today().year - 5, date.today().year + 1))  # 5 ans + année en cours
OUT = RAW / "noaa"
WORKERS = 32

# Codes qualité NOAA considérés comme fiables (2,3,6,7 = suspect/erroné)
GOOD_Q = set("01459ACIMPRU")


def french_stations():
    hist = pd.read_csv(HISTORY, dtype=str)
    hist = hist[hist["CTRY"] == "FR"].copy()
    hist["END"] = pd.to_datetime(hist["END"], format="%Y%m%d", errors="coerce")
    hist = hist[hist["END"] >= f"{YEARS[0]}-01-01"]
    hist["station_id"] = hist["USAF"] + hist["WBAN"]
    return hist


def download_one(session, year, sid):
    dest = OUT / str(year) / f"{sid}.csv"
    if dest.exists():
        return "déjà là"
    r = session.get(f"{BASE}/{year}/{sid}.csv", timeout=120)
    if r.status_code == 404:
        return "absent"
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    return "ok"


def download():
    st = french_stations()
    RAW.mkdir(parents=True, exist_ok=True)
    st.to_csv(RAW / "noaa_stations_fr.csv", index=False)
    jobs = [(y, s) for y in YEARS for s in st["station_id"]]
    print(f"{len(st)} stations FR x {len(YEARS)} ans = {len(jobs)} fichiers, {WORKERS} en parallèle")
    session = requests.Session()
    session.mount("https://", requests.adapters.HTTPAdapter(pool_maxsize=WORKERS))
    stats = {}
    with ThreadPoolExecutor(WORKERS) as pool:
        futs = {pool.submit(download_one, session, y, s): (y, s) for y, s in jobs}
        for i, f in enumerate(as_completed(futs), 1):
            try:
                res = f.result()
            except Exception as e:  # on continue malgré une erreur réseau ponctuelle
                res = "erreur"
                print("ERREUR", futs[f], e)
            stats[res] = stats.get(res, 0) + 1
            if i % 200 == 0:
                print(f"{i}/{len(jobs)} {stats}")
    print("Terminé :", stats)


# ---------- Décodage des champs NOAA ----------
def _split(series, n):
    return series.fillna("").str.split(",", expand=True).reindex(columns=range(n))


def _num(s, missing, scale=1.0, q=None):
    v = pd.to_numeric(s, errors="coerce")
    v = v.where(v.abs() < missing) / scale
    if q is not None:
        v = v.where(q.isin(GOOD_Q))
    return v


def parse_file(path):
    cols = ["STATION", "DATE", "LATITUDE", "LONGITUDE", "NAME", "WND", "VIS", "TMP", "SLP", "AA1"]
    df = pd.read_csv(path, usecols=lambda c: c in cols, dtype=str, low_memory=False)
    out = pd.DataFrame({
        "station_id": df["STATION"],
        "station_name": df.get("NAME"),
        "latitude": pd.to_numeric(df["LATITUDE"], errors="coerce"),
        "longitude": pd.to_numeric(df["LONGITUDE"], errors="coerce"),
        "timestamp": pd.to_datetime(df["DATE"], utc=True, errors="coerce"),
    })
    # WND = direction(°),q,type,vitesse(m/s x10),q
    w = _split(df.get("WND", pd.Series(index=df.index, dtype=str)), 5)
    out["wind_direction"] = _num(w[0], 999, 1, w[1])
    out["wind_speed"] = _num(w[3], 9999, 10, w[4])                 # m/s
    # TMP = +0123,q  (°C x10)
    t = _split(df.get("TMP", pd.Series(index=df.index, dtype=str)), 2)
    out["temperature"] = _num(t[0], 9999, 10, t[1])               # °C
    # SLP = 10132,q (hPa x10)
    p = _split(df.get("SLP", pd.Series(index=df.index, dtype=str)), 2)
    out["pressure"] = _num(p[0], 99999, 10, p[1])                 # hPa
    # VIS = 016000,q,var,q (mètres)
    v = _split(df.get("VIS", pd.Series(index=df.index, dtype=str)), 4)
    out["visibility"] = _num(v[0], 999999, 1000, v[1])            # km
    # AA1 = période(h),hauteur(mm x10),cond,q
    a = _split(df.get("AA1", pd.Series(index=df.index, dtype=str)), 4)
    out["precipitation"] = _num(a[1], 9999, 10, a[3])             # mm
    out["precip_period_h"] = pd.to_numeric(a[0], errors="coerce")
    return out


def clean():
    files = sorted(OUT.glob("*/*.csv"))
    print(f"Nettoyage de {len(files)} fichiers…")
    with ThreadPoolExecutor(8) as pool:
        parts = list(pool.map(parse_file, files))
    df = pd.concat(parts, ignore_index=True)
    n0 = len(df)
    df = df.dropna(subset=["timestamp"]).drop_duplicates(["station_id", "timestamp"])
    # valeurs physiquement aberrantes
    df.loc[~df["temperature"].between(-40, 50), "temperature"] = np.nan
    df.loc[~df["pressure"].between(900, 1080), "pressure"] = np.nan
    df.loc[df["wind_speed"] > 75, "wind_speed"] = np.nan
    df.loc[df["precipitation"] > 300, "precipitation"] = np.nan
    df["city"] = [nearest_city(a, b) for a, b in zip(df["latitude"], df["longitude"])]
    df["year"] = df["timestamp"].dt.year
    CLEAN.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CLEAN / "weather.parquet", index=False)
    # agrégat horaire par ville, utilisé pour la partie 4
    hourly = (df.dropna(subset=["city"])
                .assign(hour=df["timestamp"].dt.floor("h"))
                .groupby(["city", "hour"])
                [["temperature", "wind_speed", "wind_direction", "pressure", "visibility", "precipitation"]]
                .mean().reset_index())
    hourly.to_parquet(CLEAN / "weather_city_hourly.parquet", index=False)
    print(f"{n0} lignes brutes -> {len(df)} lignes propres ; {len(hourly)} lignes ville/heure")
    print(df.isna().mean().round(3).rename("taux de manquants"))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("download", "all"):
        download()
    if cmd in ("clean", "all"):
        clean()
