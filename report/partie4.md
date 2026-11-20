# Partie 4 — Analyse croisée météo × pollution × vélos

> Auteur : Rayan · Les passages **[À COMPLÉTER]** sont à remplir avec les chiffres réels après exécution de `notebooks/04_croisement.ipynb`.

## 1. Objectif

Croiser les trois flux d'UrbanHub (météo NOAA, pollution OpenAQ, vélos CityBikes) pour observer comment la météo est associée à la qualité de l'air et à l'usage des vélos en libre-service.

## 2. Méthode de jointure

- Les trois fichiers `data/clean/*_city_hourly.parquet` partagent les mêmes clés : `city` (noms exacts de `config.py`) et `hour` (heure UTC arrondie avec `.dt.floor("h")`). Chaque fichier est vérifié avec `urbanhub_utils.check_city_hourly()`.
- Jointures sur `(city, hour)` :
  - `wp` = météo × pollution
  - `wpb` = `wp` × vélos
- Tailles et bornes temporelles : [À COMPLÉTER : nombre de lignes et période de `wp` et `wpb`, nombre de villes couvertes.]
- **Plan B** : [À COMPLÉTER — « non utilisé » ou, si `wpb` était vide, « météo Open-Meteo (`weather_recent_city_hourly.parquet`) utilisée pour Q2 et Q3 uniquement, car les observations NOAA les plus récentes n'étaient pas disponibles »].

## 3. Précautions d'interprétation

- Les données vélos couvrent environ **20 heures** : nous parlons de **tendances observées**, non de lois générales.
- **Corrélation ≠ causalité.** L'**heure de la journée** est un facteur de confusion : le trafic, la pollution, la température et l'usage des vélos suivent tous un rythme quotidien. Pour la comparaison des mouvements de vélos, un indice relatif à l'heure comparable est utilisé (mouvements ÷ moyenne des mouvements de la même ville à la même heure locale).
- Les corrélations sont calculées avec le coefficient de **Spearman** (robuste aux distributions asymétriques et aux valeurs extrêmes).

## 4. Résultats

### Q1 — Vent ↔ NO2/PM, température ↔ O3, pluie ↔ PM
- **Méthode** : Spearman sur `wp`, heatmap + `sns.regplot`.
- **Graphiques** : `figures/p4_q1_heatmap.png`, `figures/p4_q1_regplots.png`
- **Chiffre clé** : [À COMPLÉTER : ρ et n pour chaque couple]
- **Interprétation** : [À COMPLÉTER, 2–3 phrases. Pistes à confirmer par les chiffres : le vent disperse les polluants primaires ; l'ozone, polluant secondaire, varie avec la température ; la pluie peut lessiver les particules.]

### Q2 — Mouvements de vélos selon la pluie et la température
- **Méthode** : indice de mouvements à heure comparable, boxplots pluie / pas de pluie et par tranche de température.
- **Graphique** : `figures/p4_q2_boxplots.png`
- **Chiffre clé** : [À COMPLÉTER : indice médian avec/sans pluie, effectifs, p-value Mann-Whitney]
- **Interprétation** : [À COMPLÉTER, 2–3 phrases. Préciser si l'échantillon « pluie » est petit.]

### Q3 — Meilleure combinaison pas de pluie × vent < 5 m/s × température
- **Méthode** : heatmap de l'indice moyen par combinaison, cellules < 10 observations masquées.
- **Graphique** : `figures/p4_q3_heatmap_combinaisons.png`
- **Chiffre clé** : [À COMPLÉTER : combinaison gagnante, indice, n]
- **Interprétation** : [À COMPLÉTER, 2–3 phrases.]

### Q4 — Vue d'ensemble pour Paris
- **Méthode** : z-scores superposés (mouvements, NO2, PM2.5, température) + heatmap de corrélation globale.
- **Graphiques** : `figures/p4_q4_zscores_paris.png`, `figures/p4_q4_heatmap_globale.png`
- **Chiffre clé** : [À COMPLÉTER : variable la plus corrélée aux mouvements, ρ]
- **Interprétation** : [À COMPLÉTER, 2–3 phrases. Rappeler que les co-variations reflètent en partie le cycle quotidien.]

## 5. Limites

- Fenêtre temporelle commune courte (~20 h) : résultats exploratoires.
- Un échantillon de pluie réduit rend les comparaisons fragiles.
- Stations de mesure ponctuelles supposées représentatives de la ville.
- Variables non mesurées (jour de la semaine, événements, trafic routier) pouvant expliquer une partie des tendances.

## 6. Conclusion

[À COMPLÉTER : 3–4 phrases de synthèse des 4 questions et ouverture (collecte plus longue, régression multivariée contrôlant l'heure de la journée).]
