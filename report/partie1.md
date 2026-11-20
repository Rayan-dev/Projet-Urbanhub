# Partie 1 — Météo (flux batch NOAA Global Hourly)

> Auteur : Rayan · Branche `meteo` · Les passages **[À COMPLÉTER]** sont à remplir avec les chiffres réels après exécution des notebooks.

## 1. Objectif et source

Cette partie construit le flux **batch** météo d'UrbanHub à partir du jeu **NOAA Global Hourly** (observations horaires de stations). L'objectif est de produire, pour chaque ville du projet, une série météo horaire propre (`weather_city_hourly.parquet`) réutilisable par l'analyse croisée (Partie 4), puis d'en tirer 4 analyses (anomalies, visibilité, saisonnalité, jours extrêmes).

## 2. Architecture du flux batch

```
NOAA (fichiers CSV par station et par année)
   │  python p1_noaa_batch.py download   (32 téléchargements parallèles, reprise possible)
   ▼
data/raw/noaa/<année>/<station>.csv      (données brutes, jamais sur Git)
   │  python p1_noaa_batch.py clean      (décodage, qualité, bornes, rattachement ville)
   ▼
data/clean/weather_city_hourly.parquet   (clés : city, hour UTC) → committé sur Git
```

- **Sélection des stations** : stations françaises actives depuis 5 ans.
- **Téléchargement** : 32 threads en parallèle, avec reprise (les fichiers déjà présents ne sont pas retéléchargés). [À COMPLÉTER : nombre de stations, volume total en Go, durée.]
- **Idempotence** : `python p1_noaa_batch.py all` rejoue toute la chaîne ; avant le rendu, `data/raw/noaa/2026/` est supprimé pour récupérer les derniers jours.

## 3. Décodage et nettoyage

Les champs NOAA sont des chaînes encodées (`valeur,code_qualité`). Le nettoyage applique :

| Champ | Format NOAA | Décodage | Valeur manquante |
|---|---|---|---|
| `TMP` | température en dixièmes de °C | ÷ 10 → °C | `+9999` |
| `WND` | direction, qualité, type, vitesse (dixièmes de m/s), qualité | vitesse ÷ 10 → m/s | `9999` (vitesse), `999` (direction) |
| `SLP` | pression au niveau de la mer en dixièmes de hPa | ÷ 10 → hPa | `99999` |
| `VIS` | visibilité en mètres | ÷ 1000 → km | `999999` |
| `AA1` | précipitations : durée (h), hauteur en dixièmes de mm, condition, qualité | hauteur ÷ 10 → mm, durée conservée dans `precip_period_h` | `9999` |

Règles complémentaires :
- **Sentinelles** (999 / 9999 / 99999…) converties en valeurs manquantes (`NaN`), jamais traitées comme des mesures.
- **Codes qualité** : les mesures de qualité **2, 3, 6, 7** (suspectes ou erronées, y compris après contrôle manuel) sont **écartées** ; seules les mesures validées sont conservées.
- **Bornes physiques** : valeurs hors plage plausible rejetées. [À COMPLÉTER avec les bornes du code : ex. température, vent, pression, visibilité.]
- **Précipitations** : le cumul est donné sur une durée variable (1, 3, 6, 12, 24 h). On ne somme donc les précipitations que si `precip_period_h == 1`, pour éviter tout double comptage.
- **Rattachement à la ville** : chaque station est rattachée à la **ville la plus proche** (distance géographique) ; la colonne `city` reprend les noms exacts de `config.py`. [À COMPLÉTER : seuil de distance éventuel.]
- **Agrégation** : une ligne par `(city, hour)` avec `hour` = heure UTC arrondie (`.dt.floor("h")`).

### Taux de valeurs manquantes avant / après nettoyage

[À COMPLÉTER : coller le tableau affiché par `python p1_noaa_batch.py clean`.]

| Variable | Manquants avant (%) | Manquants après (%) |
|---|---|---|
| Température | | |
| Vent | | |
| Pression | | |
| Visibilité | | |
| Précipitations (1 h) | | |

[À COMPLÉTER : 2–3 phrases — quelles variables perdent le plus de données et pourquoi (ex. visibilité et précipitations plus lacunaires).]

## 4. Analyses (notebook `01_meteo.ipynb`)

Les données sont agrégées par jour **en heure de Paris**. Les graphiques sont dans `figures/p1_*.png`.

### Q1 — Anomalies de température
- **Méthode** : z-score de la température moyenne journalière par rapport à la normale du mois et de la ville ; anomalie si |z| > 2,5.
- **Graphique** : `figures/p1_q1_anomalies_paris.png`
- **Chiffre clé** : [À COMPLÉTER]
- **Interprétation** : [À COMPLÉTER, 2–3 phrases]

### Q2 — Météo × visibilité
- **Méthode** : corrélations de Spearman, boxplot de visibilité pluie vs sec, brouillard (visibilité < 1 km et vent < 2 m/s).
- **Graphiques** : `p1_q2_heatmap_spearman.png`, `p1_q2_boxplot_visibilite_pluie.png`, `p1_q2_brouillard.png`
- **Chiffre clé** : [À COMPLÉTER]
- **Interprétation** : [À COMPLÉTER]

### Q3 — Saisonnalité
- **Méthode** : courbes mensuelles par ville (température et pluie) et tendance annuelle sur 5 ans (régression linéaire, années complètes).
- **Graphiques** : `p1_q3_saisonnalite.png`, `p1_q3_tendance_annuelle.png`
- **Chiffre clé** : [À COMPLÉTER]
- **Interprétation** : [À COMPLÉTER — préciser que 5 ans ne permettent pas de conclure à une tendance climatique]

### Q4 — Jours extrêmes
- **Méthode** : percentiles 1 et 99 par ville de tmax, tmin, vent max et précipitations journalières.
- **Graphique** : `p1_q4_jours_extremes_paris.png` ; tableau des 20 dernières dates dans `figures/p1_q4_20_dernieres_dates.csv`.
- **Chiffre clé** : [À COMPLÉTER]
- **Validation externe** : [À COMPLÉTER — 2–3 dates retrouvées dans l'actualité (canicule, tempête, vague de froid…).]
- **Interprétation** : [À COMPLÉTER]

## 5. Limites

- Couverture spatiale limitée aux stations proches des villes ; une station peut ne pas représenter toute l'agglomération.
- Visibilité et précipitations sont les variables les plus lacunaires.
- Cinq ans de données : la saisonnalité est visible, mais pas une tendance climatique.

## 6. Reproductibilité

```bash
python p1_noaa_batch.py all     # download + clean
jupyter nbconvert --to notebook --execute --inplace notebooks/01_meteo.ipynb
```
