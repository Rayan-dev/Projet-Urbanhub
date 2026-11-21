# Taux de valeurs manquantes (Partie 1)

| Variable | Manquants avant nettoyage (%) | Manquants après nettoyage (%) | Manquants grille horaire ville (%) |
|---|---|---|---|
| Température (°C) | 3.5 | 3.7 | 1.6 |
| Vent (m/s) | 0.1 | 0.1 | 1.5 |
| Pression (hPa) | 66.2 | 66.2 | 14.9 |
| Visibilité (km) | 3.1 | 3.1 | 1.5 |
| Précipitations 1 h (mm) | 66.4 | 77.7 | 43.3 |

*Avant* = valeur absente ou sentinelle (999/9999/99999) ; *après* = + codes qualité 2/3/6/7 écartés + bornes physiques (+ cumul 1 h uniquement pour les précipitations). Pour les précipitations, l'absence de champ AA1 est comptée comme manquante. *Grille* = part d'heures sans valeur par ville après agrégation sur une grille horaire complète.
