# Partie 4 — Analyse croisée météo × pollution × vélos

> Auteur : Rayan, finalisé par le chef de projet · Résultats issus de `notebooks/04_croisement.ipynb`.

## 1. Objectif

Croiser les trois flux d'UrbanHub (météo NOAA, pollution OpenAQ, vélos CityBikes) pour observer comment la météo est associée à la qualité de l'air et à l'usage des vélos en libre-service.

## 2. Méthode de jointure

- Les trois fichiers `data/clean/*_city_hourly.parquet` partagent les mêmes clés : `city` (noms exacts de `config.py`) et `hour` (heure UTC arrondie avec `.dt.floor("h")`). Chaque fichier est vérifié avec `urbanhub_utils.check_city_hourly()`.
- Jointures sur `(city, hour)` :
  - `wp` = météo × pollution
  - `wpb` = `wp` × vélos
- Tailles et bornes temporelles : `wp` = 1 336 lignes, du 14/11/2026 0 h au 21/11/2026 13 h UTC, 8 villes ; `wpb` = 117 lignes, du 19/11/2026 18 h au 20/11/2026 13 h UTC, 7 villes (Marseille n'a pas de données vélos).
- **Plan B utilisé pour toute la partie 4** : les observations NOAA s'arrêtent le 24/08/2025, alors que la pollution (22/10–21/11/2026) et les vélos (19–20/11/2026) sont récentes ; la jointure météo NOAA × pollution est donc vide. La météo horaire provient d'**Open-Meteo** (`weather_recent_city_hourly.parquet`, 14–21/11/2026), la période commune étant limitée à la semaine couverte par ce fichier. Les quatre questions utilisent cette météo..

## 3. Précautions d'interprétation

- Les données vélos couvrent environ **20 heures** : nous parlons de **tendances observées**, non de lois générales.
- **Corrélation ≠ causalité.** L'**heure de la journée** est un facteur de confusion : le trafic, la pollution, la température et l'usage des vélos suivent tous un rythme quotidien. Pour la comparaison des mouvements de vélos, un indice relatif à la tranche de journée est utilisé (mouvements ÷ moyenne des mouvements de la même ville dans la même tranche : nuit, matin, après-midi, soir). Un indice « par heure » n'est pas possible : sur ~20 h de collecte il n'y a qu'une observation par ville et par heure.
- Les corrélations sont calculées avec le coefficient de **Spearman** (robuste aux distributions asymétriques et aux valeurs extrêmes).

## 4. Résultats

### Q1 — Vent ↔ NO2/PM, température ↔ O3, pluie ↔ PM
- **Méthode** : Spearman météo × polluants sur `wp`, heatmap + `regplot`.
- **Graphiques** : `figures/p4_q1_heatmap.png`, `figures/p4_q1_regplots.png`
- **Chiffre clé** : ρ vent ↔ NO2 = −0,56 (n = 1 274) ; vent ↔ PM2.5 = −0,42 (n = 1 312) ; vent ↔ PM10 = −0,33 (n = 1 250) ; température ↔ O3 = +0,28 (n = 1 242) ; pluie ↔ PM2.5 = −0,22 (n = 1 312) ; pluie ↔ PM10 = −0,31 (n = 1 250). Tous significatifs (p < 0,001).
- **Interprétation** : Plus le vent est fort, plus NO2 et particules sont faibles : le vent disperse les polluants primaires, l'effet le plus net (NO2). L'ozone est plus élevé quand il fait plus chaud (formation photochimique), l'association restant modérée. La pluie va avec des particules plus faibles, compatible avec un lessivage. Corrélation ≠ causalité : température, vent et pluie varient aussi avec le cycle quotidien.

### Q2 — Mouvements de vélos selon la pluie et la température
- **Méthode** : indice de mouvements relatif à la même ville et à la même tranche de journée ; boxplots pluie / pas de pluie et par tranche de température.
- **Graphique** : `figures/p4_q2_boxplots.png`
- **Chiffre clé** : indice médian 0,86 sous la pluie (n = 36) contre 1,00 sans pluie (n = 81) ; test de Mann-Whitney p = 0,22 (non significatif). Par température : 0,96 entre 5 et 10 °C (n = 33) et 0,98 entre 10 et 15 °C (n = 84), seules tranches observées.
- **Interprétation** : Les mouvements semblent environ 14 % plus faibles sous la pluie, mais la différence n'est pas statistiquement significative sur cet échantillon. La température n'a pas d'effet net sur une plage aussi étroite (5 à 15 °C). Tendance observée sur ~20 h seulement.

### Q3 — Meilleure combinaison pas de pluie × vent < 5 m/s × température
- **Méthode** : heatmap de l'indice moyen par combinaison pluie × vent × température, cellules de moins de 10 observations masquées.
- **Graphique** : `figures/p4_q3_heatmap_combinaisons.png`
- **Chiffre clé** : meilleure combinaison observée : pluie, vent < 5 m/s, 5–10 °C, indice 1,08 (n = 14) ; sans pluie, vent < 5 m/s : 1,02 (5–10 °C) et 1,00 (10–15 °C). Aucune cellule « vent ≥ 5 m/s » n'atteint 10 observations.
- **Interprétation** : Les écarts entre combinaisons sont faibles (indice entre 0,88 et 1,08) et ne permettent pas de désigner de condition clairement favorable ; le résultat « pluie » en tête est un artefact d'échantillon (n = 14), pas un effet réel. L'effet du vent fort ne peut pas être testé. Il faudrait une collecte de plusieurs semaines.

### Q4 — Vue d'ensemble pour Paris
- **Méthode** : z-scores superposés (mouvements, NO2, PM2.5, température) pour Paris + heatmap de corrélation globale.
- **Graphiques** : `figures/p4_q4_zscores_paris.png`, `figures/p4_q4_heatmap_globale.png`
- **Chiffre clé** : corrélations de Spearman avec les mouvements de vélos : NO2 +0,55, PM10 +0,37, CO +0,35, température +0,32, O3 −0,40, pluie −0,21, vent −0,08, PM2.5 −0,01. Fenêtre commune : 19/11 18 h → 20/11 13 h UTC (117 lignes, 7 villes).
- **Interprétation** : Les vélos co-varient surtout avec le NO2 (+0,55) : tous deux suivent le trafic urbain, donc le rythme quotidien (facteur de confusion) plutôt qu'un lien causal entre l'usage du vélo et la pollution. La corrélation négative avec l'ozone reflète l'inverse du cycle jour/nuit. Tendances observées uniquement, sur une seule journée de collecte.

## 5. Limites

- Fenêtre temporelle commune courte (~20 h) : résultats exploratoires.
- Un échantillon de pluie réduit rend les comparaisons fragiles.
- Stations de mesure ponctuelles supposées représentatives de la ville.
- Variables non mesurées (jour de la semaine, événements, trafic routier) pouvant expliquer une partie des tendances.

## 6. Conclusion

Le croisement des trois flux montre surtout un effet net de la météo sur la pollution : le vent disperse le NO2 (ρ = −0,56) et les particules, la pluie s'accompagne de particules plus faibles, la chaleur d'un ozone plus élevé. Pour les vélos, la pluie va avec un usage inférieur d'environ 14 % mais sans significativité (p = 0,22), et aucune combinaison de conditions ne ressort clairement. Ces résultats, obtenus sur une seule journée de collecte vélos et avec une météo Open-Meteo, sont exploratoires. Pour aller plus loin : collecter les vélos sur plusieurs semaines et estimer un modèle multivarié contrôlant l'heure de la journée et le jour de la semaine.
