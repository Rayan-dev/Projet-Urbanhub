"""Configuration commune UrbanHub : villes cibles, chemins du data lake."""
from pathlib import Path

DATA = Path(__file__).parent / "data"
RAW = DATA / "raw"        # données brutes, telles que reçues
CLEAN = DATA / "clean"    # données nettoyées (Parquet)

# Villes étudiées, communes aux 3 flux (lat, lon)
CITIES = {
    "Paris": (48.8566, 2.3522),
    "Lyon": (45.7640, 4.8357),
    "Marseille": (43.2965, 5.3698),
    "Toulouse": (43.6047, 1.4442),
    "Lille": (50.6292, 3.0573),
    "Bordeaux": (44.8378, -0.5792),
    "Nantes": (47.2184, -1.5536),
    "Strasbourg": (48.5734, 7.7521),
}


def nearest_city(lat, lon, max_deg=0.5):
    """Rattache un point à la ville cible la plus proche (None si trop loin)."""
    best, dist = None, max_deg
    for name, (clat, clon) in CITIES.items():
        d = ((lat - clat) ** 2 + (lon - clon) ** 2) ** 0.5
        if d < dist:
            best, dist = name, d
    return best
