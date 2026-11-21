# UrbanHub – jumeau numérique Smart City (météo × vélos × pollution)

Trois flux de données sur 8 villes françaises (Paris, Lyon, Marseille, Toulouse, Lille, Bordeaux, Nantes, Strasbourg), un data lake de fichiers, quatre notebooks d'analyse et un rapport.

| Partie | Flux | Script | Notebook | Rapport |
|---|---|---|---|---|
| 1 – Météo | batch (NOAA Global Hourly) | `p1_noaa_batch.py` | `notebooks/01_meteo.ipynb` | `report/partie1.md` |
| 2 – Vélos | streaming (CityBikes + GBFS Vélib') | `p2_citybikes_stream.py` | `notebooks/02_velos.ipynb` | `report/partie2.md` |
| 3 – Pollution | IoT (OpenAQ API v3) | `p3_openaq_iot.py` | `notebooks/03_pollution.ipynb` | `report/partie3.md` |
| 4 – Croisement | jointure des 3 flux | `p4_openmeteo_fallback.py` (plan B météo) | `notebooks/04_croisement.ipynb` | `report/partie4.md` |

Le rapport complet est assemblé par `python report/build_rapport.py` → `report/rapport_final.md`.

## Installation

```
python -m venv .venv
.venv\Scripts\activate            # macOS / Linux : source .venv/bin/activate
pip install -r requirements.txt
```

## Collecte

| Qui | Commande | Durée |
|---|---|---|
| Météo (batch) | `python p1_noaa_batch.py all` | 30 min à 2 h selon la connexion |
| Vélos (streaming) | `python p2_citybikes_stream.py` | en continu |
| Pollution (IoT) | `OPENAQ_API_KEY` définie, puis `python p3_openaq_iot.py discover`, `backfill --days 30`, `stream` | discover : 1 min ; backfill : ~5 min ; stream : en continu |
| Plan B météo | `python p4_openmeteo_fallback.py` | quelques secondes |

OpenAQ limite à environ 60 requêtes par minute et par clé : lancer `stream` après la fin de `backfill`, ou utiliser deux clés.
Sous Windows, définir la clé une fois pour toutes avec `setx OPENAQ_API_KEY "..."` (puis ouvrir une nouvelle fenêtre PowerShell).

## Data lake

```
data/
  raw/                       données brutes, jamais modifiées (hors Git)
    noaa/<année>/<station>.csv
    citybikes/date=YYYY-MM-DD/snapshots.csv
    openaq/sensors.csv, history/*.csv, stream/date=YYYY-MM-DD/readings.csv
  clean/                     données nettoyées en Parquet
    weather.parquet, weather_city_hourly.parquet
    bikes.parquet, bikes_city_hourly.parquet
    pollution.parquet, pollution_city_hourly.parquet
    weather_recent_city_hourly.parquet     (plan B Open-Meteo)
figures/                     graphiques PNG (p<partie>_q<n>_*.png), style.py = charte commune
notebooks/                   01 à 04
report/                      parties du rapport + build_rapport.py
```

Seuls les fichiers `data/clean/*_city_hourly.parquet` sont versionnés (petits) ; le reste de `data/` est ignoré par Git.

## Conventions

- **Clés de jointure** : `city` = noms exacts de `config.py` ; `hour` = heure UTC arrondie avec `.dt.floor("h")`. Vérifier avant d'écrire un `*_city_hourly.parquet` :
  ```python
  from urbanhub_utils import check_city_hourly
  check_city_hourly(df)
  ```
- **Graphiques** : `from figures.style import apply_style, save_fig` ; PNG nommés `p<partie>_q<n>_<sujet>.png`, avec titre, axes, unités et légende.
- **Git** : une branche par fonctionnalité, PR vers `main`, pas de données brutes dans le dépôt.

## Choix techniques et limites (détails dans `report/05_choix_limites.md`)

- Pas de Kafka : interrogation régulière des API et stockage partitionné par date. Kafka/MQTT = étape suivante pour une mise en production.
- Pas d'historique vélos : CityBikes ne fournit que l'état temps réel, l'étude vélos couvre la période de collecte.
- Nettoyage météo : valeurs NOAA mises à l'échelle (÷10), sentinelles 9999/99999 traitées comme manquantes, codes qualité suspects écartés, valeurs impossibles filtrées.
- Décalage de publication NOAA : la météo récente de la partie 4 vient d'Open-Meteo (plan B).
