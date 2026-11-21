# Choix techniques et limites

## Choix techniques

- **Pas de Kafka ni de MQTT.** Avec un délai de 24 h, l'ingestion se fait par interrogation régulière des API (scripts Python) et par stockage partitionné par date dans un data lake de fichiers (`data/raw`, `data/clean`). Kafka et MQTT seraient l'étape suivante pour une mise en production : ils apporteraient la vraie diffusion d'événements, la reprise après panne et la montée en charge.
- **Pandas et Parquet.** Les volumes (quelques millions de lignes) tiennent en mémoire. Le Parquet, colonnaire et compressé, limite l'espace disque et conserve les types (dont les dates avec fuseau).
- **Clés de jointure communes.** `city` (noms exacts de `config.py`) et `hour` (heure UTC arrondie) sont imposées aux trois flux et vérifiées par `check_city_hourly()` ; sans cela la partie 4 ne fonctionne pas.
- **Git sans données brutes.** Seules les petites tables `*_city_hourly.parquet` sont versionnées ; les données brutes restent hors dépôt.

## Limites

- **Pas d'historique vélos.** CityBikes ne fournit que l'état temps réel des stations : l'étude vélos porte sur la période de collecte (environ 23 h), d'où des « tendances observées » et non des conclusions.
- **Quota CityBikes et Paris.** L'API publique est limitée à 300 unités par heure ; le réseau de Paris, très coûteux, est lu directement dans le flux GBFS officiel de Vélib' Métropole. Marseille n'a pas pu être couverte pour les vélos.
- **Décalage de publication NOAA.** Les observations NOAA exploitables s'arrêtent le 24 août 2025, alors que les flux vélos et pollution portent sur octobre–novembre 2026 : l'analyse croisée s'appuie donc sur la météo Open-Meteo (plan B) pour la période récente.
- **Durée de collecte courte** : 30 jours pour la pollution, environ 23 h pour les vélos.
- **Couverture inégale des capteurs** : de 3 à 19 capteurs de PM2.5 selon la ville, CO mesuré dans 4 villes seulement.
- **Corrélation n'est pas causalité** : l'heure de la journée influence à la fois le trafic, la pollution, la température et l'usage des vélos.
