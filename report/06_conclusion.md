# Conclusion

UrbanHub démontre qu'un jumeau numérique de la qualité de vie urbaine peut être construit rapidement à partir de trois flux de nature différente (fichiers batch, API en continu, capteurs IoT), en s'appuyant sur des clés d'intégration simples (`city` × `hour` UTC) et un data lake de fichiers.

**Principaux indicateurs pour les décideurs**

- **Mobilité** : l'usage des vélos en libre-service est très concentré : à Lyon, une station atteint près de 20 rotations par place en 23 h, contre une médiane d'environ 2,5 (partie 2). Les stations des hypercentres et des pôles d'emploi sont les premières à devoir être rééquilibrées.
- **Qualité de l'air** : sur 30 jours d'automne, le NO2 culmine en fin de journée (pic à 20 h, ratio OMS 1,22) ; le PM2.5 et le NO2 sont les polluants dominants, et Lille cumule 14 jours au-dessus du seuil OMS de PM2.5, avec un pic d'environ 46 µg/m³ vers le 7 novembre (partie 3).
- **Météo et pollution** : le vent disperse les polluants (ρ = −0,56 avec le NO2), ce qui fait des journées sans vent les plus à risque (partie 4).
- **Météo et vélos** : la pluie s'accompagne d'un usage inférieur d'environ 14 % mais l'effet n'est pas significatif sur notre échantillon (partie 4).

**Pistes d'amélioration**

1. **Allonger la collecte** vélos à plusieurs semaines (et la rendre continue pour les 8 villes, Marseille comprise) pour séparer l'effet de la météo de celui de l'heure et du jour.
2. **Passer à une vraie architecture de streaming** (Kafka ou MQTT) avec reprise sur panne, plutôt que l'interrogation périodique d'API.
3. **Rafraîchir automatiquement la météo** (Open-Meteo ou NOAA) pour supprimer le décalage de publication qui a imposé le plan B.
4. **Modèle multivarié** (régression contrôlant heure, jour de la semaine, météo) et ajout du trafic routier pour passer de corrélations à des explications.
5. **Tableau de bord** (Streamlit) alimenté en continu pour les décideurs.
