"""Charte graphique commune UrbanHub.

Usage (script ou notebook) :
    from figures.style import apply_style, save_fig, CITY_COLORS, PALETTE
    apply_style()
    ...
    save_fig("p2_q1_top_stations")   # -> figures/p2_q1_top_stations.png (150 dpi)

Convention de nommage des PNG : p<partie>_q<question>_<sujet>.png
"""
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

FIG_DIR = Path(__file__).resolve().parent

# Couleurs principales UrbanHub
PALETTE = {
    "primary": "#534AB7",    # violet UrbanHub
    "secondary": "#1D9E75",  # vert (mobilité douce, valeurs « bonnes »)
    "accent": "#D85A30",     # corail (alertes, anomalies)
    "warning": "#BA7517",    # ambre (seuils)
    "neutral": "#5F5E5A",    # gris (texte secondaire, références)
    "light": "#F1EFE8",      # fond des encadrés
}

# Une couleur fixe par ville : la même dans TOUS les graphiques du projet
CITY_COLORS = {
    "Paris": "#534AB7",
    "Lyon": "#D85A30",
    "Marseille": "#1D9E75",
    "Toulouse": "#D4537E",
    "Lille": "#378ADD",
    "Bordeaux": "#993556",
    "Nantes": "#BA7517",
    "Strasbourg": "#5F5E5A",
}

# Échelle « état » : vide / moyen / plein (vélos), ou bon / moyen / mauvais (pollution)
STATE_COLORS = {"low": "#E24B4A", "mid": "#EF9F27", "high": "#639922"}

# Cartes de couleurs continues
CMAP_SEQ = "Purples"   # intensité (comptes, niveaux)
CMAP_DIV = "RdBu_r"    # corrélations, écarts à la normale (centrer sur 0)

_CYCLE = list(CITY_COLORS.values())


def apply_style():
    """À appeler une fois en haut de chaque notebook."""
    mpl.rcParams.update({
        "figure.figsize": (10, 5.5),
        "figure.dpi": 100,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.prop_cycle": mpl.cycler(color=_CYCLE),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#888780",
        "axes.grid": True,
        "grid.color": "#D3D1C7",
        "grid.linewidth": 0.6,
        "grid.alpha": 0.7,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "axes.labelsize": 11,
        "axes.labelcolor": "#2C2C2A",
        "xtick.color": "#5F5E5A",
        "ytick.color": "#5F5E5A",
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.frameon": False,
        "legend.fontsize": 10,
        "font.family": "sans-serif",
        "font.sans-serif": ["Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "lines.linewidth": 2,
        "savefig.bbox": "tight",
        "savefig.facecolor": "white",
    })


def city_color(city):
    return CITY_COLORS.get(city, PALETTE["neutral"])


def save_fig(name, fig=None, source=None):
    """Sauve la figure courante en PNG 150 dpi dans figures/<name>.png.

    source : texte optionnel ajouté en bas à droite (ex. "Source : CityBikes API").
    """
    fig = fig or plt.gcf()
    if source:
        fig.text(0.99, 0.005, source, ha="right", va="bottom", fontsize=8, color=PALETTE["neutral"])
    name = name[:-4] if name.endswith(".png") else name
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=150)
    print(f"Figure enregistrée : {path.relative_to(FIG_DIR.parent)}")
    return path
