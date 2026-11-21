"""Utilitaires communs UrbanHub.

check_city_hourly(df) : vérifie qu'une table « ville × heure » respecte les conventions
de l'équipe avant d'être écrite dans data/clean/*_city_hourly.parquet :
  - colonnes `city` et `hour` présentes ;
  - `city` = noms exacts de config.CITIES ;
  - `hour` = datetime UTC, arrondi à l'heure (dt.floor("h")) ;
  - pas de doublon (city, hour).
"""
import pandas as pd

from config import CITIES


def check_city_hourly(df: pd.DataFrame) -> pd.DataFrame:
    assert {"city", "hour"} <= set(df.columns), "colonnes city/hour manquantes"
    bad = set(df["city"].dropna()) - set(CITIES)
    assert not bad, f"villes hors config.py : {bad}"
    assert df["city"].notna().all(), "city contient des valeurs manquantes"
    assert pd.api.types.is_datetime64_any_dtype(df["hour"]), "hour doit être un datetime"
    assert str(df["hour"].dt.tz) == "UTC", "hour doit être en UTC (tz-aware)"
    assert (df["hour"] == df["hour"].dt.floor("h")).all(), "hour non arrondie à l'heure"
    assert not df.duplicated(["city", "hour"]).any(), "doublons (city, hour)"
    print(f"check_city_hourly OK : {len(df)} lignes, {df['city'].nunique()} villes, "
          f"{df['hour'].min()} -> {df['hour'].max()}")
    return df
