# -*- coding: utf-8 -*-
"""Demarrage automatique de Cemu au demarrage de Windows.

Le but : allumer le PC, retrouver le jeu pret a jouer sur le profil full mods,
sans passer par quatre menus.

Trois regles, dans cet ordre :

1. RIEN n'est deploie au boot. Un deploiement refusionne tout le profil
   (1,7 Go sur cette machine) : le faire a chaque allumage-userait cette place
   sur un disque deja serré, et le ferait echouer. Ce script ne fait que
   VERIFIER, et ne dit rien quand tout va bien.
2. Si la partie chargee n'appartient pas au profil actif, on ne lance rien et
   on explique pourquoi. Demarrer le jeu dans cet etat, c'est le crash a coup
   sur : c'est exactement ce que la sauvegarde d'aujourd'hui a fait.
3. Le motif est ecrit dans demarrage-auto.log, a cote de ce script. Un jeu qui
   ne demarre pas un samedi matin laisse une trace lisible, pas une excuse.

Usage :  python demarrage-auto.py             verifie puis lance Cemu
        python demarrage-auto.py --verifier   verifie seulement
"""
from __future__ import print_function

import io
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(ICI, "demarrage-auto.log")


def ecrire(texte, silencieux=False):
    ligne = time.strftime("%Y-%m-%d %H:%M:%S ") + texte
    try:
        with io.open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(ligne + "\n")
    except OSError:
        pass
    if not silencieux:
        try:
            print(ligne)
        except UnicodeEncodeError:
            print(ligne.encode("ascii", "replace").decode("ascii"))


def racine_botw():
    """Le dossier du programme, celui qui contient le paquet `botw`.

    Ce script vit dans le chantier, mais il est aussi copie dans le dossier
    utilisateur pour le demarrage automatique, ou le programme est livre plus
    loin. On essaie donc plusieurs endroits, le plus explicite d'abord.
    """
    parent = os.path.dirname(ICI)
    candidats = []
    if os.environ.get("BOTW_HOME"):
        candidats.append(os.environ["BOTW_HOME"])
    candidats += [ICI, os.path.join(ICI, "botw-tools"),
                  parent, os.path.join(parent, "botw")]
    for candidat in candidats:
        if candidat and os.path.isdir(os.path.join(candidat, "botw")):
            return candidat
    return None


def lancer_botw(racine, commande):
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        p = subprocess.Popen([sys.executable, "-m", "botw"] + commande,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=env, cwd=racine)
    except OSError as e:
        return 1, str(e)
    # communicate() D'ABORD : returncode n'est rempli qu'une fois le processus
    # terminé. Lire d'abord le code renvoyait None, et un None est un echec.
    sortie = p.communicate()[0] or b""
    return p.returncode, sortie.decode("utf-8", "replace")


def main(argv):
    seulement = "--verifier" in argv
    ecrire("---- demarrage ----")
    racine = racine_botw()
    if not racine:
        ecrire("Le programme botw est introuvable : rien ne peut etre verifie.")
        return 1
    if racine not in sys.path:
        sys.path.insert(0, racine)

    from botw import config, newgame, profiles

    profil = profiles.active() or "(aucun)"
    cfg = config.load()

    # 1. Ce qui bloquerait le chargement est plus grave qu'une partie
    #    incompatible : verifier d'abord.
    code, texte = lancer_botw(racine, ["check"])
    if code != 0:
        ecrire("Le jeu ne demarre pas dans l'etat actuel :")
        for ligne in texte.splitlines():
            marque = ligne.find("[KO ]")
            if marque >= 0:
                ecrire("    " + ligne[marque + 5:].strip())
        ecrire("Lance le lanceur (Lanceur-BOTW.bat), touche b, pour reparer.")
        return 1

    # 2. Une partie d'un autre jeu de mods ferait planter le jeu. On refuse
    #    de demarrer plutot que de laisser Cemu planter en silence.
    if newgame.has_game():
        provenance = newgame.profil_de_la_partie()
        if provenance and profil != "(aucun)" and provenance != profil:
            ecrire("La partie chargee vient du jeu de mods '%s' alors que '%s' "
                   "est actif : le jeu planterait. Cemu n'est pas lance."
                   % (provenance, profil))
            ecrire("Ouvre le lanceur, touche 7, et choisis la partie de '%s'."
                   % profil)
            return 1
        if provenance:
            ecrire("Partie chargee : '%s' - compatible avec '%s'."
                   % (provenance, profil))
        else:
            ecrire("Partie presente, jeu de mods d'origine inconnu.")
    else:
        ecrire("Aucune partie : Cemu en proposera une neuve sur '%s'." % profil)

    if seulement:
        ecrire("Verification terminee (--verifier : Cemu n'est pas lance).")
        return 0

    exe = config.cemu_exe(cfg)
    if not exe or not os.path.isfile(exe):
        ecrire("Cemu est introuvable (%s)." % (exe or "chemin non configure"))
        return 1
    ecrire("Cemu demarre...")
    try:
        subprocess.Popen([exe], cwd=os.path.dirname(exe))
    except OSError as e:
        ecrire("Cemu n'a pas demarre : %s" % e)
        return 1
    ecrire("---- fin ----")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))