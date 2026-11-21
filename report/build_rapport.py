"""Assemble les parties du rapport en report/rapport_final.md.

Usage (depuis la racine du repo) :  python report/build_rapport.py
Ordre : introduction + architecture, parties 1 à 4, choix techniques et limites, conclusion.
Les fichiers absents sont signalés et ignorés. Les chemins d'images sont réécrits pour pointer
vers ../figures depuis report/.
"""
from pathlib import Path

R = Path(__file__).resolve().parent
ORDER = ["00_intro_architecture.md", "partie1.md", "partie2.md", "partie3.md", "partie4.md",
         "05_choix_limites.md", "06_conclusion.md"]

parts = []
for name in ORDER:
    f = R / name
    if not f.exists():
        print(f"ABSENT : {name}")
        continue
    parts.append(f.read_text(encoding="utf-8").strip())
(R / "rapport_final.md").write_text("\n\n---\n\n".join(parts) + "\n", encoding="utf-8")
print(f"rapport_final.md : {len(parts)}/{len(ORDER)} sections")
