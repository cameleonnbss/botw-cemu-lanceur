"""Le catalogue des combinaisons verifiees.

Le banc d'essai (Outils\\matrice.py) a fusionne, deploye et verifie fichier
par fichier 123 combinaisons de mods : les 14 mods seuls, tous les couples,
Second Wind avec chaque autre mod, puis les 5 profils du lanceur.
123 reussies, 0 echec.

Ce module transforme ce resultat en catalogue : des combinaisons nommees, avec
les mods qu'elles contiennent, pour recreer en une commande un profil qui a
ete prouve fonctionnel. C'est la partie du travail la plus longue a obtenir,
et la plus facile a perdre - autant la mettre a portee de commande.

Chaque entree porte le nombre de fichiers fusionnes lors du test : c'est ce
qui permet de verifier d'un coup d'oeil qu'un profil correspond bien a ce
qui a ete mesure.
"""
from . import i18n

_ = i18n._

# cle -> (titre, description, [mods], fichiers fusionnes lors du test)
CATALOG = {
    "boost": (
        "boost",
        "Le profil par defaut : armes d'Hyrule Warriors, koroks en nombre, "
        "iles, portals instantanes, vent, tenues de champions.",
        ["Ancient_Weaponry_Mark_II.zip",
         "Hyrule_Warriors_Weapon_Collection.zip",
         "More_Korok_Seeds.zip",
         "Korok_Extra_Rewards.zip",
         "Islands_Expansion_v1.2.zip",
         "Seamless_Warping.zip",
         "10x_Speed_Paraglider_v2.zip",
         "Farore's_Wind.zip",
         "Champion's_Leathers_and_Lowered_Hylian_Hood.zip",
         "The_Linkle_Mod_3.0.1.zip"],
        1371),
    "sur": (
        "sur",
        "SANS ECHEC : tout ce qui raccourcit le jeu, et pas de Relics of the "
        "Past (249 fichiers non fusionnables : il efface ce que les autres "
        "mods fournissent et casse des quêtes). 13 mods.",
        ["Second_Wind_(core).zip",
         "Second_Wind_-_Shrine_Overhaul.zip",
         "Second_Wind_-_Eventide_Fix.zip",
         "Ancient_Weaponry_Mark_II.zip",
         "Hyrule_Warriors_Weapon_Collection.zip",
         "More_Korok_Seeds.zip",
         "Korok_Extra_Rewards.zip",
         "Islands_Expansion_v1.2.zip",
         "Seamless_Warping.zip",
         "10x_Speed_Paraglider_v2.zip",
         "Farore's_Wind.zip",
         "Champion's_Leathers_and_Lowered_Hylian_Hood.zip",
         "The_Linkle_Mod_3.0.1.zip"],
        5614),
    "combo": (
        "combo",
        "Second Wind (peu de sanctuaires a repetition) + armes, koroks, "
        "iles et tenues.",
        ["Second_Wind_(core).zip",
         "Second_Wind_-_Shrine_Overhaul.zip",
         "Second_Wind_-_Eventide_Fix.zip",
         "Ancient_Weaponry_Mark_II.zip",
         "More_Korok_Seeds.zip",
         "Korok_Extra_Rewards.zip",
         "Islands_Expansion_v1.2.zip",
         "Champion's_Leathers_and_Lowered_Hylian_Hood.zip",
         "The_Linkle_Mod_3.0.1.zip"],
        4780),
    "flo": (
        "flo",
        "Le plus court : koroks, armes, iles et tenues, sans extension de "
        "carte ni Second Wind.",
        ["Ancient_Weaponry_Mark_II.zip",
         "More_Korok_Seeds.zip",
         "Korok_Extra_Rewards.zip",
         "Islands_Expansion_v1.2.zip",
         "Champion's_Leathers_and_Lowered_Hylian_Hood.zip",
         "The_Linkle_Mod_3.0.1.zip"],
        524),
    "secondwind": (
        "secondwind",
        "Uniquement Second Wind : sanctuaires etudes, aucun Echec.",
        ["Second_Wind_(core).zip",
         "Second_Wind_-_Shrine_Overhaul.zip",
         "Second_Wind_-_Eventide_Fix.zip"],
        4283),
}

ORDER = ["boost", "sur", "combo", "flo", "secondwind"]


def names():
    return [k for k in ORDER if k in CATALOG] + \
           [k for k in sorted(CATALOG) if k not in ORDER]


def get(key):
    """(titre, description, mods, fichiers) ou None."""
    if not key:
        return None
    k = key.strip().lower()
    if k in CATALOG:
        return CATALOG[k]
    for name, entry in CATALOG.items():
        if name.lower() == k:
            return entry
    return None


def missing_mods(key, cfg=None):
    """Mods de la combinaison absents de la bibliotheque locale."""
    from . import mods                                          # import tardif
    entry = get(key)
    if not entry:
        return []
    dispo = mods.available(cfg)
    return [m for m in entry[2] if m not in dispo]


def listing(cfg=None):
    i18n.title(_("catalog.title"))
    i18n.info(_("catalog.intro"))
    for key in names():
        _t, desc, mods_list, nfiles = CATALOG[key]
        print("")
        print("  " + i18n.paint(key, "bold+green") + i18n.paint(
            "  (%d " % len(mods_list) + _("catalog.mods") + ", "
            + "%d " % nfiles + _("catalog.files") + ")", "dim"))
        i18n.info(desc)
        manquants = missing_mods(key, cfg)
        for m in mods_list:
            marque = i18n.paint("x", "red") if m in manquants else i18n.paint("-", "dim")
            print("    %s %s" % (marque, m))
        if manquants:
            i18n.warn(_("catalog.missing", n=len(manquants)))
    i18n.info(_("catalog.hint"))
    return names()


def create(key, profile=None, cfg=None, deploy_after=False):
    """Recree une combinaison verifiee dans un profil, puis le deploye."""
    from . import deploy, profiles
    entry = get(key)
    if not entry:
        raise ValueError(_("catalog.unknown", k=key, list=", ".join(names())))
    _t, _d, mods_list, _n = entry
    nom = profile or key
    if nom in profiles.existing():
        raise ValueError(_("profile.exists", p=nom))
    manquants = missing_mods(key, cfg)
    if manquants:
        i18n.ko(_("catalog.missing", n=len(manquants)))
        for m in manquants:
            i18n.info(m)
        if not i18n.confirm(_("catalog.continue_anyway"), False):
            return None
    profiles.create(nom, mods_list, cfg)
    if deploy_after:
        deploy.deploy(nom, cfg)
    return nom
