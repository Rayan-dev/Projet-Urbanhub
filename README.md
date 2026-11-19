# UrbanHub – collecte des données

```
pip install -r requirements.txt
```

Lancez les 3 collectes **maintenant**, chacune dans son propre terminal, sur une machine qui reste allumée toute la nuit.

| Qui | Commande | Durée |
|---|---|---|
| A – Météo (batch) | `python p1_noaa_batch.py all` | 30 min à 2 h selon la connexion |
| B – Vélos (streaming) | `python p2_citybikes_stream.py` | en continu jusqu'au rendu |
| C – Pollution (IoT) | `export OPENAQ_API_KEY=...` puis `python p3_openaq_iot.py discover`, `python p3_openaq_iot.py backfill --days 30`, et enfin `python p3_openaq_iot.py stream` | discover : 1 min ; backfill : environ 1 s par capteur ; stream : en continu |

OpenAQ limite à environ 60 requêtes par minute et par clé. Pour lancer `backfill` et `stream` en même temps, utilisez deux clés différentes, par exemple celles de deux membres du groupe.

## Data lake

```
data/
  raw/                       données brutes, jamais modifiées
    noaa/<année>/<station>.csv
    citybikes/date=YYYY-MM-DD/snapshots.csv
    openaq/sensors.csv, history/*.csv, stream/date=YYYY-MM-DD/readings.csv
  clean/                     données nettoyées en Parquet
    weather.parquet, weather_city_hourly.parquet
```

Toutes les heures sont en UTC. `config.py` définit les 8 villes cibles, communes aux 3 flux, ce qui permet de croiser les données par ville et par heure dans la partie 4.

## Choix techniques à justifier dans le rendu

- **Pas de Kafka.** Avec un délai de 24 h, on a choisi l'ingestion par interrogation régulière de l'API et un stockage partitionné par date. Kafka et MQTT seraient l'étape suivante pour une mise en production.
- **Pas d'historique vélos.** CityBikes ne fournit que l'état temps réel des stations. La période d'étude commence donc au lancement de la collecte.
- **Nettoyage météo.** Les valeurs NOAA sont mises à l'échelle (÷10), les sentinelles 9999/99999 sont traitées comme manquantes, les codes qualité suspects sont écartés, et les valeurs physiquement impossibles sont filtrées.
