"""Tableau de bord UrbanHub (optionnel).

Lancement depuis la racine du repo :
    pip install streamlit
    streamlit run app/streamlit_app.py
Affiche automatiquement tous les PNG figures/p<partie>_*.png et les cartes figures/*.html.
"""
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "figures"
CLEAN = ROOT / "data" / "clean"

PARTS = {
    "p1": "Partie 1 – Météo (batch)",
    "p2": "Partie 2 – Vélos (streaming)",
    "p3": "Partie 3 – Pollution (IoT)",
    "p4": "Partie 4 – Analyse croisée",
}

st.set_page_config(page_title="UrbanHub", layout="wide")
st.title("UrbanHub – jumeau numérique urbain")
st.caption("Météo NOAA · Vélos CityBikes · Pollution OpenAQ – 8 villes françaises")

# Indicateurs rapides à partir des tables ville × heure, si présentes
cols = st.columns(3)
for col, (fname, label, metric) in zip(cols, [
    ("weather_city_hourly.parquet", "Température moyenne", "temperature"),
    ("bikes_city_hourly.parquet", "Mouvements de vélos / h", "movements"),
    ("pollution_city_hourly.parquet", "NO2 moyen (µg/m³)", "no2"),
]):
    f = CLEAN / fname
    if f.exists():
        df = pd.read_parquet(f)
        if metric in df:
            col.metric(label, f"{df[metric].mean():,.1f}")

tabs = st.tabs(list(PARTS.values()))
for tab, prefix in zip(tabs, PARTS):
    with tab:
        pngs = sorted(FIG.glob(f"{prefix}_*.png"))
        maps = sorted(FIG.glob(f"{prefix}_*.html"))
        if not pngs and not maps:
            st.info("Pas encore de figures pour cette partie.")
        for i in range(0, len(pngs), 2):
            c1, c2 = st.columns(2)
            for c, p in zip((c1, c2), pngs[i:i + 2]):
                c.image(str(p), use_container_width=True)
        for m in maps:
            st.subheader(m.stem.replace("_", " "))
            components.html(m.read_text(encoding="utf-8"), height=550)
