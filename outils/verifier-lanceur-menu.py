# -*- coding: utf-8 -*-
"""Verifie le .bat du lanceur : le menu doit pointer vers des etiquettes reelles.

Le bug que ce script traque est celui qui fait disparaitre le lanceur sans
message : `goto vers` une etiquette absente ne leve aucune erreur, la fenetre
se ferme, et l'utilisateur voit « rien ne se passe ».

On verifie aussi que chaque touche annoncee est bien routee, et que chaque
etiquette de jeu appelle le bon profil. Un menu qui affiche « 1. ma partie
principale » doit reellement changer de jeu de mods ET de partie : c'est ce
que la ligne d'appel distingue d'un simple deploiement.

Usage :  python verifier-lanceur-menu.py <Lanceur-BOTW.bat>
"""
from __future__ import print_function

import io
import os
import re
import sys

# (touche, extrait du menu, etiquette attendue, profil attendu ou None)
ATTENDU = [
    ("1", "MA PARTIE PRINCIPALE", "principale", "secondwind"),
    ("2", "MA PARTIE FULL MODS", "fullmods", "sur"),
    ("3", "Second Wind seul", "sw", "secondwind"),
    ("4", "BOOST", "boost", "boost"),
    ("5", "TES MODS seuls", "flo", "flo"),
    ("6", "CHOISIR TES MODS", "choix", None),
    ("7", "Charger une partie", "sauvegardes", None),
    ("8", "Jeu a deux", "coop", None),
    ("9", "Panneau des profils", "panneau", None),
    ("a", "Graphismes", "graphismes", None),
    ("b", "Verifier et reparer", "verifier", None),
    ("c", "Tester les profils", "tester", None),
    ("d", "Ouvrir UKMM", "ukmm", None),
    ("e", "Ouvrir Cemu", "cemu", None),
    ("f", "botw menu", "botw", None),
    ("g", "New game", "nouvelle", None),
    ("h", "Documentation", "doc", None),
    ("i", "Le jeu demarre-t-il", "diagnostic", None),
    ("j", "Reparer", "reparer", None),
    ("0", "Quitter", None, None),
]

# Les deux touches "parties" doivent passer par la bascule complete.
BASCULE = {1: "secondwind", 2: "sur"}


def problemes(chemin):
    with io.open(chemin, encoding="ascii") as f:
        lignes = f.read().replace("\r\n", "\n").split("\n")
    texte = "\n".join(lignes)

    def trouve(aiguille):
        for i, l in enumerate(lignes):
            if l.strip() == aiguille or l.strip().startswith(aiguille + " "):
                return i
        return -1

    err = []

    # --- 1. tout goto vise une etiquette reelle ---------------------------
    # `:eof` est une etiquette implicite de cmd.exe : elle n'a pas besoin
    # d'etre declaree, et la traiter comme manquante ferait crier au vide.
    etiquettes = set(l.strip()[1:].strip().lower() for l in lignes
                     if re.match(r"^:[A-Za-z_][\w]*\s*$", l))
    etiquettes.add("eof")
    for i, l in enumerate(lignes):
        m = re.match(r"^\s*goto\s+:?([A-Za-z_]\w*)", l, re.I)
        if m and m.group(1).lower() not in etiquettes:
            err.append("ligne %d : goto %s -> aucune etiquette :'%s'"
                       % (i + 1, m.group(1), m.group(1)))
    # `call :etiquette` doit aussi exister.
    for i, l in enumerate(lignes):
        m = re.match(r"^\s*call\s+:?([A-Za-z_]\w*)", l, re.I)
        if m and m.group(1).lower() not in etiquettes:
            err.append("ligne %d : call %s -> aucune etiquette :'%s'"
                       % (i + 1, m.group(1), m.group(1)))

    # --- 2. le menu affiche exactement les touches annoncees --------------
    # Les lignes du menu commencent par « echo » : on l'enleve avant de
    # comparer, sinon aucune touche n'est jamais reconnue.
    menu = []
    for l in lignes:
        nu = re.sub(r"^\s*echo\.?\s+", "", l, flags=re.I)
        menu.append(nu)
    for touche, extrait, _e, _p in ATTENDU:
        motif = re.compile(r"^\s*%s\.\s*%s"
                           % (re.escape(touche), re.escape(extrait)))
        if not any(motif.match(l) for l in menu):
            err.append("menu : la touche %s n'annonce pas « %s »"
                       % (touche, extrait))

    # --- 3. chaque touche est bien routee --------------------------------
    # `choice /c <touches>` renvoie la POSITION, et les "if errorlevel" se
    # testent de la fin vers le debut. On reconstitue la position de chaque
    # touche pour verifier le routage, au lieu de croire le commentaire.
    #
    # On ne lit QUE le bloc de dispatch, celui qui suit le `choice` : le
    # fichier contient d'autres « if errorlevel 1 » (les `call :jouer`
    # testent le retour), et les confondre faisait croire que la touche 1
    # allait vers « echec ».
    ligne_choice = -1
    for i, l in enumerate(lignes):
        if l.strip().lower().startswith("rem"):
            continue
        if re.match(r"\s*choice\s+/c\s+([0-9a-z]+)", l, re.I):
            ligne_choice = i
            break
    if ligne_choice < 0:
        err.append("aucun « choice /c » actif dans le fichier")
        return err
    m = re.match(r"\s*choice\s+/c\s+([0-9a-z]+)", lignes[ligne_choice], re.I)
    touches = m.group(1)
    attendu_ordre = "".join(t for t, _, _, _ in ATTENDU
                            if t != "0") + "0"
    if touches.lower() != attendu_ordre.lower():
        err.append("choice /c %s ne correspond pas au menu annonce (%s)"
                   % (touches, attendu_ordre))

    routage = {}
    for l in lignes[ligne_choice + 1:ligne_choice + 2 + len(touches) + 2]:
        m = re.match(r"^\s*if\s+errorlevel\s+(\d+)\s+goto\s+:?(\w+)",
                     l, re.I)
        if m:
            routage[int(m.group(1))] = m.group(2).lower()
    for rang, touche in enumerate(touches.lower(), 1):
        if touche == "0":
            continue
        cible = routage.get(rang)
        attendu = next(e for t, _, e, _ in ATTENDU if t == touche)
        if cible is None:
            err.append("touche %s : aucune ligne « if errorlevel %d »"
                       % (touche, rang))
        elif cible != attendu.lower():
            err.append("touche %s : elle va vers :%s, le menu annonce :%s"
                       % (touche, cible, attendu))

    # --- 4. les deux touches de partie font vraiment la bascule ----------
    for _touche, _x, etiquette, profil in ATTENDU[:2]:
        i = trouve(":" + etiquette)
        if i < 0:
            continue                      # deja signale plus haut
        bloc = "\n".join(lignes[i:i + 4])
        if ":jouer_avec_partie %s" % profil not in bloc:
            err.append(":%s n'appelle pas « :jouer_avec_partie %s »"
                       % (etiquette, profil))
    i = trouve(":jouer_avec_partie")
    if i < 0:
        err.append("pas de :jouer_avec_partie (les touches 1 et 2 ne peuvent "
                   "changer de partie)")
    else:
        bloc = "\n".join(lignes[i:i + 12])
        if "jeu %1 --lancer" not in bloc:
            err.append(":jouer_avec_partie n'appelle pas « botw jeu %1 "
                       "--lancer » : il change le jeu de mods sans la partie")
        if "sans_botw" not in bloc:
            err.append(":jouer_avec_partie n'a pas de repli sans le dossier "
                       "botw")

    # --- 5. aucune etiquette de jeu orpheline -----------------------------
    for etiquette, _x, _e, _p in ATTENDU:
        if etiquette is None or etiquette in ("principale",):
            continue
        nom = ":" + etiquette
        if trouve(nom) < 0:
            continue
        utilisee = re.search(r"(goto|call)\s+:?%s\b" % re.escape(etiquette),
                             texte, re.I)
        if not utilisee:
            err.append("l'etiquette %s n'est jamais atteinte" % nom)

    # --- 6. le fichier reste lisible par cmd.exe ---------------------------
    with io.open(chemin, "rb") as f:
        brut = f.read()
    if brut[:3] == b"\xef\xbb\xbf":
        err.append("BOM UTF-8 : cmd.exe le lit comme du texte")
    if any(c > 127 for c in brut):
        err.append("octet non-ASCII : le fichier doit etre en ASCII pur")
    if b"\r\n" not in brut:
        err.append("fins de ligne LF : cmd.exe les execute mal")
    elif brut.count(b"\n") != brut.count(b"\r\n"):
        err.append("%d fin(s) de ligne LF isolee(s)"
                   % (brut.count(b"\n") - brut.count(b"\r\n")))

    return err


def main(argv):
    chemin = argv[0] if argv else os.path.join(
        os.path.expanduser("~"), "Desktop", "BOTW", "Lanceur-BOTW.bat")
    if not os.path.isfile(chemin):
        print("INTROUVABLE : %s" % chemin)
        return 2
    err = problemes(chemin)
    print("Menu du lanceur : %s" % chemin)
    if err:
        print("%d probleme(s) :" % len(err))
        for e in err:
            print("  ! %s" % e)
        return 1
    print("Les 20 touches du menu pointent vers une etiquette reelle,")
    print("et les touches 1 et 2 changent bien de jeu de mods ET de partie.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
