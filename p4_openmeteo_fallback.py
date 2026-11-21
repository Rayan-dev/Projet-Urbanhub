"""Plan B partie 4 : météo horaire récente via Open-Meteo (gratuit, sans clé).

À utiliser si la jointure météo NOAA × vélos est vide (la météo NOAA a quelques jours de
retard). Sortie : data/clean/weather_recent_city_hourly.parquet, même clés que les autres
tables (city, hour UTC), colonnes alignées sur weather_city_hourly.parquet :
    temp_c, wind_ms, precip_mm, precip_period_h (=1 : cumuls horaires)

Usage :
    python p4_openmeteo_fallback.py              # 7 derniers jours
    python p4_openmeteo_fallback.py --past-days 3
"""
import argparse

import pandas as pd
import requests

from config import CITIES, CLEAN
from urbanhub_utils import check_city_hourly

API = "https://api.open-meteo.com/v1/forecast"


def fetch_city(city, lat, lon, past_days):
    r = requests.get(API, timeout=60, params={
        "latitude": lat, "longitude": lon, "past_days": past_days, "forecast_days": 1,
        "hourly": "temperature_2m,precipitation,wind_speed_10m",
        "wind_speed_unit": "ms", "timezone": "UTC"})
    r.raise_for_status()
    h = r.json()["hourly"]
    df = pd.DataFrame({
        "city": city,
        "hour": pd.to_datetime(h["time"], utc=True),
        "temp_c": h["temperature_2m"],
        "wind_ms": h["wind_speed_10m"],
        "precip_mm": h["precipitation"],
    })
    df["precip_period_h"] = 1
    return df


def main(past_days):
    df = pd.concat([fetch_city(c, lat, lon, past_days) for c, (lat, lon) in CITIES.items()],
                   ignore_index=True)
    # on retire les heures futures : seule l'observation récente nous intéresse
    df = df[df["hour"] <= pd.Timestamp.now(tz="UTC").floor("h")].dropna(subset=["temp_c"])
    df["hour"] = df["hour"].dt.floor("h")
    df = check_city_hourly(df.sort_values(["city", "hour"]).reset_index(drop=True))
    CLEAN.mkdir(parents=True, exist_ok=True)
    out = CLEAN / "weather_recent_city_hourly.parquet"
    df.to_parquet(out, index=False)
    print(f"écrit : {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--past-days", type=int, default=7)
    main(ap.parse_args().past_days)
