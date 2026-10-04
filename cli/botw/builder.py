"""Construire un profil a son gout, en repondant a des questions.

Le lanceur propose cinq profils pret-a-porter. C'est bien, mais ca ne repond
pas a la vraie question, qui est : « je veux ca, mais pas ca ». Voici un
constructeur : on repond oui/non a une dizaine de questions, et l'outil
assemble le profil, le verifie, et le deploie.

Deux reglages meritent une explication, parce qu'ils sont les plus demandes :

* **Second Wind.** Il supprime les sanctuaires repetes et le Echec. Tres
  populaire, mais c'est de loin le mod le plus lourd : 4142 fichiers a lui
  seul, et il touche au coeur du scenario. Si le jeu bloque au chargement,
  c'est le premier suspect. Le constructeur propose donc de le garder ou de
  l'enlever, et dit ce que ca coute.

* **Linkle.** C'est le mod qui ajoute les objets du jeu (arc, bouclier,
  tenites...). On peut vouloir Linkle SANS Second Wind, ou l'inverse. Les
  deux sont pris en charge : le constructeur ne force rien.

Regle de securite appliquee par le constructeur : il n'assemble jamais un
profil dont il n'a pas verifie la presence des zips. Si un mod manque, il le
dit et propose de le telecharger, plutot que de creer un profil qui ne
demarrera pas.
"""
import os

from . import cemu, config, deploy, i18n, mods, profiles

_ = i18n._

# (cle du reglage, question EN, question FR, [mods concernes])
QUESTIONS = [
    ("linkle", "The Linkle mod (more bows, shields, clothes)?",
     "Le mod Linkle (plus d'arcs, boucliers, tenues) ?",
     ["The_Linkle_Mod_3.0.1.zip"]),
    ("secondwind", "Second Wind (shrines, no Failing)?",
     "Second Wind (sanctuaires etudes, pas d'echec) ?",
     ["Second_Wind_(core).zip", "Second_Wind_-_Shrine_Overhaul.zip",
      "Second_Wind_-_Eventide_Fix.zip"]),
    ("weapons", "Hyrule Warriors weapons and Champion's Leathers?",
     "Armes Hyrule Warriors et tenues de champions ?",
     ["Hyrule_Warriors_Weapon_Collection.zip",
      "Champion's_Leathers_and_Lowered_Hylian_Hood.zip"]),
    ("islands", "Islands Expansion (big new islands)?",
     "Islands Expansion (grosses iles en plus) ?",
     ["Islands_Expansion_v1.2.zip"]),
    ("warping", "Seamless Warping (portal anywhere)?",
     "Seamless Warping (portail ou tu veux) ?",
     ["Seamless_Warping.zip"]),
    ("korok", "More koroks (900 seeds, extra rewards)?",
     "Plus de koroks (900 graines, récompenses en plus) ?",
     ["More_Korok_Seeds.zip", "Korok_Extra_Rewards.zip"]),
    ("glide", "10x Paraglider (glide 10 times longer)?",
     "Paraglider x10 (planer 10 fois plus longtemps) ?",
     ["10x_Speed_Paraglider_v2.zip"]),
    ("wind", "Farore's Wind (cheat, extra updraft)?",
     "Farore's Wind (triche, coup de vent en plus) ?",
     ["Farore's_Wind.zip"]),
    ("relics", "Relics of the Past (687 files; 249 of them overwrite other mods)",
     "Relics of the Past (687 fichiers ; 249 ecrasent d'autres mods)",
     ["Relics_of_the_Past.zip"]),
    ("ancient", "Ancient Weaponry Mark II (old weapons recipe)?",
     "Ancient Weaponry Mark II (recettes d'armes anciennes) ?",
     ["Ancient_Weaponry_Mark_II.zip"]),
]

# Second Wind est decoche par defaut, et c'est un choix delibere : c'est le
# mod le plus lourd du lot (4142 fichiers a lui seul) et le premier suspect
# quand le chargement bloque. On prouve d'abord que le reste demarre, puis on
# l'ajoute. Le constructeur dit explicitement ce que ca coute.
DEFAUTS = {"linkle": True, "secondwind": False, "weapons": True,
           "islands": False, "warping": False, "korok": True,
           "glide": False, "wind": False, "relics": False,
           "ancient": True}


def _q(cle):
    """(question, mods) pour une cle de reglage."""
    for c, en, fr, liste in QUESTIONS:
        if c == cle:
            return (en, fr, liste)
    raise KeyError(cle)


def question(cle, lang=None):
    en, fr, _liste = _q(cle)
    return fr if (lang or i18n.lang()) == "fr" else en


def assembling(choix):
    """Liste des zips du profil, dans l'ordre de priorite UKMM.

    UKMM empile les mods dans cet ordre et le DERNIER gagne pour les
    fichiers qu'il ne sait pas fusionner. On applique donc PRIORITY :
    sinon ce serait l'ordre des questions qui decide de l'ordre de
    fusion, et les questions ne sont pas triees par force.
    """
    vus, out = set(), []
    for cle, _en, _fr, liste in QUESTIONS:
        if not choix.get(cle):
            continue
        for m in liste:
            if m not in vus:
                vus.add(m)
                out.append(m)
    rang = {f: i for i, f in enumerate(profiles.PRIORITY)}
    return sorted(out, key=lambda f: (rang.get(f, len(rang)), f))


def noms(choix):
    """Nom de profil lisible, deduit des choix. Sert de nom par defaut."""
    morceaux = []
    if choix.get("linkle"):
        morceaux.append("linkle")
    if choix.get("secondwind"):
        morceaux.append("sw")
    morceaux.append("perso")
    return "-".join(morceaux)


def manque(choix, cfg=None):
    """Zips du profil absents de la bibliotheque."""
    dispo = mods.available(cfg)
    return [m for m in assembling(choix) if m not in dispo]


def resume(choix, cfg=None):
    """Texte de recapitulatif, par langue."""
    i18n.section(_("builder.summary"))
    for cle, _en, _fr, liste in QUESTIONS:
        if choix.get(cle):
            for m in liste:
                i18n.ok(m)
    absents = manque(choix, cfg)
    if absents:
        i18n.ko(_("builder.missing", n=len(absents)))
        for m in absents:
            i18n.info(m)
    return absents


def poser_questions(choix=None):
    """Pose les questions une par une.

    Retourne (reponses, posees) ou `posees` est le nombre de questions
    reellement posees a un humain.

    On ne peut pas se contenter de tester `i18n.interactive()` avant : sous
    Git Bash, `sys.stdin.isatty()` renvoie vrai meme avec `< /dev/null`, parce
    que la redirection est resolue par MSYS et non par Windows. Le seul signe
    fiable est `input()` qui leve EOFError. D'ou le compte.
    """
    choix = dict(choix or DEFAUTS)
    posees = 0
    for cle, _en, _fr, _liste in QUESTIONS:
        if not i18n.interactive():
            break
        defaut = DEFAUTS[cle]
        rep = i18n.ask(question(cle) + (" (Y/n)" if defaut else " (y/N)"),
                       "y" if defaut else "n")
        if rep is None:
            break
        posees += 1
        choix[cle] = rep.lower() in ("y", "yes", "o", "oui")
        if cle == "secondwind" and choix[cle]:
            i18n.warn(_("builder.sw_warning"))
    return choix, posees


def construire(nom, choix, cfg=None, deploy_apres=True):
    """Cree le profil, le verifie, et le deploie si demande.

    Retourne (nom, code_de_sortie). Le profil n'est deploye que si la
    verification de la fusion passe : deployer un profil incomplet, c'est
   un chargement infini.
    """
    cfg = cfg or config.load()
    absents = resume(choix, cfg)
    if absents and not i18n.confirm(_("builder.continue_anyway"), False):
        return nom, 1
    liste = assembling(choix)
    if nom in profiles.existing():
        i18n.ko(_("profile.exists", p=nom))
        return nom, 1
    prof = profiles.create(nom, liste, cfg)
    if not prof.hashes:
        i18n.ko(_("builder.empty"))
        return nom, 1
    ok, n = profiles.verify(nom, False)
    if not ok:
        i18n.ko(_("builder.not_verified", n=n))
        if not i18n.confirm(_("builder.deploy_broken"), False):
            return nom, 1
    if deploy_apres:
        try:
            deploy.deploy(nom, cfg, quiet=True)
        except deploy.GuardError as e:
            i18n.ko(str(e))
            return nom, e.code
    # Un profil qui remplace des fichiers du jeu ne doit pas cohabiter avec
    # un pack qui en remplace d'autres : on nettoie au passage.
    cemu.nettoyer(cfg=cfg)
    i18n.ok(_("builder.done", p=nom))
    return nom, 0