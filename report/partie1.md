# Partie 1 — Météo (flux batch NOAA Global Hourly)

> Auteur : Rayan · Branche `meteo` · Résultats issus de `notebooks/01_meteo.ipynb` (données NOAA du 1er janvier 2021 au 24 août 2025).

## 1. Objectif et source

Cette partie construit le flux **batch** météo d'UrbanHub à partir du jeu **NOAA Global Hourly** (observations horaires de stations). L'objectif est de produire, pour chacune des 8 villes du projet, une série météo horaire propre (`weather_city_hourly.parquet`) réutilisable par l'analyse croisée (Partie 4), puis d'en tirer 4 analyses (anomalies, visibilité, saisonnalité, jours extrêmes).

## 2. Architecture du flux batch

```
NOAA (un CSV par station et par année)
   │  python p1_noaa_batch.py download   (32 téléchargements parallèles, reprise possible)
   ▼
data/raw/noaa/<année>/<station>.csv      (données brutes, jamais sur Git)
   │  python p1_noaa_batch.py clean      (décodage, qualité, bornes, rattachement ville, agrégation horaire)
   ▼
data/clean/weather_city_hourly.parquet   (clés : city, hour UTC) → committé sur Git
```

- **Villes** : Paris, Lyon, Marseille, Toulouse, Lille, Bordeaux, Nantes, Strasbourg (noms lus dans `config.py`).
- **Sélection des stations** : stations françaises actives depuis 5 ans situées à **50 km au plus** d'une des 8 villes, soit **30 stations**. Période demandée : 2021 à 2026 (6 années), soit 180 fichiers.
- **Téléchargement** : 32 requêtes en parallèle (durée observée : environ 40 secondes). Résultat : **150 fichiers téléchargés et 30 absents** (code 404). Les données disponibles s'arrêtent au **24 août 2025** : aucun fichier 2026 n'était disponible lors du téléchargement.
- **Reprise** : un fichier déjà présent n'est pas retéléchargé ; la commande peut être relancée après une coupure.
- **Fiabilisation** : lors des premiers essais, le serveur a renvoyé des pages HTML au lieu de CSV. Le script vérifie désormais que le contenu est un CSV NOAA (en-tête `STATION`) avant de l'enregistrer, écrit d'abord dans un fichier temporaire (`.part`), puis signale les fichiers invalides au nettoyage sans les supprimer.
- **Volume des données brutes** : environ **0,93 Go** (931 Mo, 150 fichiers CSV de stations).

### Résultat du nettoyage

| Ville | Stations rattachées (max) | Heures dans le fichier final |
|---|---|---|
| Paris | 10 | 40 167 |
| Lyon | 5 | 40 133 |
| Marseille | 5 | 40 129 |
| Toulouse | 5 | 40 128 |
| Nantes | 2 | 40 141 |
| Bordeaux | 1 | 40 109 |
| Lille | 1 | 39 979 |
| Strasbourg | 1 | 40 104 |
| **Total** | **30** | **320 890 lignes** |

Période couverte : du **1er janvier 2021 00:00 UTC au 24 août 2025 21:00 UTC** (environ 40 700 heures par ville, soit une couverture d'environ 98,5 %).

## 3. Décodage et nettoyage

Les champs NOAA sont des chaînes encodées (`valeur,code_qualité`). Le nettoyage applique :

| Champ | Format NOAA | Décodage | Valeur manquante |
|---|---|---|---|
| `TMP` | température en dixièmes de °C | ÷ 10 → °C | `+9999` |
| `WND` | direction, qualité, type, vitesse (dixièmes de m/s), qualité | vitesse ÷ 10 → m/s | `9999` (vitesse), `999` (direction) |
| `SLP` | pression au niveau de la mer en dixièmes de hPa | ÷ 10 → hPa | `99999` |
| `VIS` | visibilité en mètres | ÷ 1000 → km | `999999` |
| `AA1` | précipitations : durée (h), hauteur en dixièmes de mm, condition, qualité | hauteur ÷ 10 → mm ; durée conservée (`precip_period_h`) | `9999` |

Règles complémentaires :
- **Sentinelles** (999 / 9999 / 99999 / 999999) converties en valeurs manquantes (`NaN`), jamais traitées comme des mesures.
- **Codes qualité** : les mesures de qualité **2, 3, 6, 7** (suspectes ou erronées, y compris après contrôle manuel) sont **écartées**.
- **Bornes physiques** : température −70 à 60 °C, vent 0 à 100 m/s, pression 850 à 1100 hPa, visibilité 0 à 160 km, précipitations 0 à 300 mm ; au-delà, la valeur est rejetée.
- **Précipitations** : le cumul est donné sur une durée variable (1, 3, 6, 12, 24 h). Seuls les cumuls sur **1 heure** (`precip_period_h == 1`) sont conservés, pour éviter tout double comptage.
- **Rattachement à la ville** : chaque station est rattachée à la **ville la plus proche** (distance de Haversine, seuil de 50 km) à partir de ses coordonnées dans les fichiers.
- **Agrégation** : d'abord par station et par heure, puis moyenne des stations de la même ville : une ligne par `(city, hour)`, avec `hour` = heure UTC arrondie (`.dt.floor("h")`).
- **Colonnes finales** : `city, hour, temp_c, wind_ms, slp_hpa, vis_km, precip_mm, precip_period_h, n_stations`.

### Taux de valeurs manquantes avant / après nettoyage

| Variable | Manquants avant nettoyage (%) | Manquants après nettoyage (%) | Manquants grille horaire par ville (%) |
|---|---|---|---|
| Température (°C) | 3,5 | 3,7 | 1,6 |
| Vent (m/s) | 0,1 | 0,1 | 1,5 |
| Pression (hPa) | 66,2 | 66,2 | 14,9 |
| Visibilité (km) | 3,1 | 3,1 | 1,5 |
| Précipitations 1 h (mm) | 66,4 | 77,7 | 43,3 |

*Avant* = valeur absente ou sentinelle ; *après* = + codes qualité écartés + bornes physiques (+ cumul sur 1 h seulement pour les précipitations) ; *grille* = part d'heures sans valeur par ville après agrégation sur une grille horaire complète.

Lecture :
- **Température, vent, visibilité** : quasi complètes ; le contrôle qualité n'écarte presque rien (+0,2 point pour la température).
- **Pression** : le champ `SLP` est absent de la majorité des observations (66,2 %), mais la fusion des stations et des rapports d'une même heure ramène le manque à 14,9 % par ville.
- **Précipitations** : le champ `AA1` est absent de 66,4 % des observations (l'absence de champ ne permet pas de distinguer « pas de pluie » de « non mesuré »). Le passage de 66,4 % à 77,7 % vient de la règle « cumul sur 1 h uniquement » (+11,3 points), qui est le choix délibéré pour éviter le double comptage.

## 4. Analyses (notebook `01_meteo.ipynb`)

Les données sont agrégées par jour **en heure de Paris** (jours avec au moins 18 heures de mesures) : **13 362 jours-ville** pour les 8 villes, de janvier 2021 à août 2025. Les graphiques sont dans `figures/p1_*.png`.

### Q1 — Anomalies de température
- **Méthode** : z-score de la température moyenne journalière par rapport à la normale du mois et de la ville ; anomalie si |z| > 2,5.
- **Graphique** : `figures/p1_q1_anomalies_paris.png`
- **Chiffre clé** : **99 jours-ville anormaux** sur 13 362 (0,7 %), dont **60 chauds et 39 froids**. Par ville : Nantes 18, Toulouse 17, Paris 15, Lille 13, Marseille 10, Strasbourg 10, Bordeaux 9, Lyon 7. Le plus extrême est Lille le 19/07/2022 : 30,0 °C pour une normale de juillet de 19,4 °C (z = 4,06) ; à Paris, le même jour : 30,4 °C contre 20,3 °C (z = 3,54).
- **Interprétation** : les anomalies chaudes dominent (61 %) et se concentrent sur quelques épisodes visibles dans le top 10 : **18–19 juillet 2022** (Nantes z = 3,91, Bordeaux z = 3,23, Lille, Paris) et le **1er juillet 2025** (Lille z = 3,77, Paris z = 3,44). Le 18 juillet 2022 correspond à la canicule historique de l'ouest de la France, où Nantes a battu son record absolu avec environ 42 °C (Brut, Connexion France). Les anomalies froides sont plus rares et moins intenses (par exemple Lille le 09/02/2021 : −5,1 °C, z = −3,28).

### Q2 — Météo × visibilité
- **Méthode** : corrélations de Spearman, boxplot de visibilité pluie vs sec, brouillard (visibilité < 1 km et vent < 2 m/s).
- **Graphiques** : `p1_q2_heatmap_spearman.png`, `p1_q2_boxplot_visibilite_pluie.png`, `p1_q2_brouillard.png`
- **Chiffre clé** : visibilité médiane de **12,3 km par temps de pluie contre 15,9 km par temps sec** ; corrélation de Spearman visibilité~pluie **ρ = −0,19**. Fréquence du brouillard : de 0,07 % des heures (Marseille) à **1,46 % (Strasbourg)**, puis Bordeaux 1,21 %, Lille 1,10 %, Toulouse 0,93 %, Nantes 0,51 %, Lyon 0,25 %, Paris 0,17 %. Heure locale la plus brumeuse (toutes villes) : **6 h**.
- **Interprétation** : la pluie réduit la visibilité, mais la corrélation reste faible : d'autres phénomènes (brume, humidité) jouent aussi. Le brouillard est rare et concerne surtout des villes de l'intérieur ou de plaine (Strasbourg, Bordeaux, Lille), avec un maximum en fin de nuit, quand le vent est faible et l'air le plus froid.

### Q3 — Saisonnalité
- **Méthode** : courbes mensuelles par ville (température et pluie) et tendance annuelle (régression linéaire) sur les **années complètes uniquement** : 4 années (2021 à 2024), car 2025 s'arrête en août.
- **Graphiques** : `p1_q3_saisonnalite.png`, `p1_q3_tendance_annuelle.png`
- **Chiffre clé** : amplitude entre le mois le plus chaud et le plus froid : Marseille 19,0 °C, Lyon et Toulouse 18,4 °C, Strasbourg 17,8 °C, Bordeaux 16,1 °C, Paris 15,8 °C, Lille 15,6 °C, **Nantes 13,9 °C**. Tendance annuelle : pentes positives de **+0,15 à +0,47 °C/an** selon la ville (Paris +0,27 °C/an, p = 0,49), **aucune significative** (p entre 0,30 et 0,74).
- **Interprétation** : la saisonnalité est nette et l'amplitude est la plus faible à Nantes, ville la plus océanique. Les pentes sont toutes positives mais statistiquement non significatives : avec seulement 4 années, elles ne permettent pas de conclure à une tendance climatique et restent descriptives.

### Q4 — Jours extrêmes
- **Méthode** : percentiles 1 et 99 par ville de tmax, tmin, vent max et précipitations journalières.
- **Graphique** : `p1_q4_jours_extremes_paris.png` ; tableau des 20 dernières dates dans `figures/p1_q4_20_dernieres_dates.csv`.
- **Chiffre clé** : environ 810 jours-ville extrêmes : jour très froid 139, chaleur extrême 139, nuit très chaude 138, nuit très froide 137, vent extrême 136, pluie extrême 121. Seuils de Paris : tmax P99 = 33,1 °C, tmin P99 = 19,6 °C. Les 20 dernières dates extrêmes sont toutes comprises entre le **13 et le 17 août 2025** (exemples : Bordeaux 39,0 °C le 15/08, seuil 37,0 °C ; Toulouse 38,8 °C le 13/08 ; Lyon 38,7 °C le 13/08 ; Marseille 38,3 °C le 16/08 et nuit à 26,0 °C le 17/08).
- **Validation externe** : ces dates correspondent à la **canicule d'août 2025** : vigilance rouge du 11 au 13 août dans le sud-ouest, puis nouveau pic les 15 et 16 août dans l'ouest et le sud (Santé publique France, Météo Paris). Le **18 juillet 2022** (Nantes, record absolu d'environ 42 °C) est également retrouvé en Q1.
- **Interprétation** : par construction, un percentile 1 et 99 produit un nombre de jours extrêmes voisin pour chaque type ; l'intérêt est la date. Les événements les plus récents sont tous des épisodes de chaleur, ce qui valide le nettoyage : un épisode connu est bien retrouvé dans les données. Les précipitations extrêmes sont moins nombreuses (121), car le cumul horaire n'est pas toujours renseigné.

## 5. Limites

- **Fin des données au 24 août 2025** : aucune donnée NOAA 2026. L'analyse croisée avec les flux collectés en 2026 (Partie 4) nécessite donc la météo de secours Open-Meteo.
- **Couverture inégale** : 10 stations pour Paris, mais une seule pour Bordeaux, Lille et Strasbourg ; une station peut ne pas représenter toute l'agglomération.
- **Précipitations** : seuls les cumuls sur 1 h sont retenus et l'absence de champ ne distingue pas « pas de pluie » de « non mesuré » ; les cumuls de pluie sont donc probablement sous-estimés.
- **Pression** : 14,9 % de manquants après agrégation.
- **Durée** : environ 4,7 ans de données ; la saisonnalité est visible, pas une tendance climatique.

## 6. Reproductibilité

```bash
python p1_noaa_batch.py all     # download + clean
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_meteo.ipynb
```
