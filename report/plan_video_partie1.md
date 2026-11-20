# Plan vidéo — Démo-UrbanHubPartie1.mp4 (3 à 5 min)

| Temps | Séquence | À montrer à l'écran | Ce que vous dites (idée) |
|---|---|---|---|
| 0:00–0:30 | Intro et architecture | Schéma NOAA → download → clean → parquet → notebooks | « UrbanHub est un jumeau numérique Smart City. Ma partie : le flux batch météo NOAA. » |
| 0:30–1:30 | Téléchargement parallèle | Terminal : `python p1_noaa_batch.py download`, barre de progression (la capture H0:30) | « 32 téléchargements en parallèle, reprise possible. X stations, Y Go. » |
| 1:30–2:15 | Nettoyage | Terminal : `python p1_noaa_batch.py clean`, tableau des manquants avant/après | « Décodage ×10, sentinelles, codes qualité 2/3/6/7 écartés, bornes physiques, rattachement à la ville la plus proche. » |
| 2:15–2:45 | Résultat | `weather_city_hourly.parquet` (`df.head()`, `check_city_hourly`) | « Clés `city` et `hour` UTC, prêtes pour la jointure. » |
| 2:45–4:30 | Notebook et 4 réponses | `01_meteo.ipynb` : un graphique et un chiffre clé par question (Q1 à Q4) | « Q1 : X anomalies. Q2 : … Q3 : … Q4 : date extrême retrouvée dans l'actualité. » |
| 4:30–5:00 | Conclusion | Repo GitHub, branche `meteo`, PR | « Chaîne reproductible : `python p1_noaa_batch.py all`. » |

## Conseils d'enregistrement
- Enregistrer les captures du téléchargement dès H0:30 (la progression est longue : accélérer en montage).
- Terminal avec grande police, fenêtre propre, pas de données personnelles visibles.
- Exécuter le notebook avant l'enregistrement pour ne montrer que des sorties déjà calculées.
- Exporter en `.mp4` et le nommer exactement `Démo-UrbanHubPartie1.mp4`.
