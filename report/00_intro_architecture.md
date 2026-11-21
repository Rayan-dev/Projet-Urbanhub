# UrbanHub – Jumeau numérique de la qualité de vie urbaine

*Projet Smart City · 8 villes françaises · météo × mobilité × pollution*

## 1. Introduction

Une ville intelligente repose sur des données urbaines collectées en continu : conditions météorologiques, usage des transports, qualité de l'air. Ces données arrivent sous des formes très différentes : fichiers historiques volumineux, API temps réel, capteurs IoT. UrbanHub est un prototype de **jumeau numérique** : il ingère ces trois types de flux, les stocke dans un data lake commun, les nettoie, puis les croise pour répondre à des questions de décideurs (où la mobilité douce est-elle freinée ? quand l'air est-il le plus dégradé ? la météo explique-t-elle une partie des comportements ?).

**Villes étudiées** (définies dans `config.py`, communes aux trois flux) : Paris, Lyon, Marseille, Toulouse, Lille, Bordeaux, Nantes, Strasbourg.

**Équipe et répartition** : Partie 1 (météo, flux batch) : Rayan. Partie 2 (vélos, flux streaming) : Redouane. Partie 3 (pollution, flux IoT) et assemblage du rapport : chef de projet. Partie 4 (analyse croisée) : Rayan, avec les trois membres.

## 2. Architecture

```
 SOURCES               INGESTION                 DATA LAKE (données brutes)
 NOAA Global Hourly -> p1_noaa_batch.py       -> data/raw/noaa/<année>/<station>.csv
 CityBikes + GBFS   -> p2_citybikes_stream.py -> data/raw/citybikes/date=AAAA-MM-JJ/
 OpenAQ API v3      -> p3_openaq_iot.py       -> data/raw/openaq/{sensors.csv, history/, stream/}
                                |
                                v   TRAITEMENT : nettoyage pandas (UTC, unités, doublons, ville)
                  data/clean/*.parquet  +  *_city_hourly.parquet
                  clés communes : city (config.py) x hour (UTC, dt.floor("h"))
                                |
                                v   ANALYSE : notebooks 01 à 04 (4 + 5 + 4 + 4 questions)
                  INDICATEURS : graphiques PNG, cartes folium, rapport, tableau de bord Streamlit
```

**Rôle des trois types de flux**

| Flux | Source | Mode | Fréquence | Rôle |
|---|---|---|---|---|
| Batch | NOAA Global Hourly | téléchargement de fichiers | une fois (reprise possible) | contexte climatique long (5 ans) |
| Streaming | CityBikes API / flux GBFS Vélib' | interrogation d'API | un relevé toutes les 150 s | usage des vélos en libre-service |
| IoT | OpenAQ API v3 (capteurs de qualité de l'air) | historique horaire + relevés « latest » | historique 30 jours, puis un relevé toutes les 10 min | niveaux de polluants |

**Principe d'intégration** : chaque flux produit une table `*_city_hourly.parquet` avec les mêmes clés (`city` = noms exacts de `config.py`, `hour` = heure UTC arrondie). La partie 4 se réduit alors à des jointures sur `(city, hour)`. Le script `urbanhub_utils.check_city_hourly()` vérifie ces conventions avant chaque écriture.
