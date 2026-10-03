#!/usr/bin/env python3
"""Lanceur de la CLI, a mettre dans le PATH ou sur le bureau.

Ce fichier ne contient aucune logique : il ajoute son propre dossier au
chemin Python pour que `import botw` marche meme quand on appelle le script
depuis un autre dossier (c'est exactement le cas quand le lanceur .bat
appelle `python "%~dp0botw.py" deploy` depuis le Bureau).

Executable :  python botw.py deploy sur
"""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
if ICI not in sys.path:
    sys.path.insert(0, ICI)

from botw.cli import main  # noqa: E402  (apres l'ajout au sys.path)

if __name__ == "__main__":
    sys.exit(main())
