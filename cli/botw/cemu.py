"""Ce que Cemu fait au demarrage, et ce qui bloque le chargement.

CAUSE DU CHARGEMENT INFINI, TROUVEE SUR CETTE MACHINE

Le log de Cemu affichait, au lancement du jeu, cinquante packs graphiques
actifs. Parmi eux :

    graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Mods/ExtendedMemory
    graphicPacks/HD_Map_and_Icons

`ExtendedMemory` etend la carte memoire de l'emulateur de 2 Go
(mapping0 0x10000000-0xA0000000 au lieu de 0x10000000-0x50000000). Son
propre rules.txt reconnait le probleme :

    # BotW (and other games might) require additional modifications to the
    # code to utilize this extra ram.
    # Also, it'd be appreciated if the code for this graphic pack wasn't
    # included inside of mods for the sake of mod compatibility.

Autrement dit : ce pack suppose que le jeu a ete recompile pour exploiter
cette memoire. UKMM, lui, remplace des morceaux du jeu. Les deux ensemble
donnent exactement le symptome constate : le titre demarre, la barre de
chargement avance, et le jeu ne finit jamais. Aucun message, aucun crash.

`HD_Map_and_Icons` est un pack de remplacement de fichiers : notre propre
rules.txt UKMM dit deja "Do not use alongside BCML or file replacement
graphic packs".

Ou sont memorises les packs actifs

Dans `%APPDATA%\\Cemu\\settings.xml`, section `<GraphicPack>`, une liste
d'entrees :

    <GraphicPack>
        <Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>
        <Entry filename="graphicPacks/.../ExtendedMemory/rules.txt">
            <Preset>...</Preset>
        </Entry>
    </GraphicPack>

Cemu ajoute une entree par pack qu'il trouve sur le disque, meme pour les
autres jeux : d'ou les cinquante. On ne touche qu'aux packs de BOTW, et on
laisse les reglages de l'utilisateur pour le reste.
"""
import io
import os
import re
import shutil

from . import config, i18n

_ = i18n._

BALISE = "GraphicPack"
ENTREE = re.compile(r'<Entry filename="([^"]+)"\s*(/>|>.*?</Entry>)', re.S)

# Packs qui cassent le chargement quand UKMM est actif.
# (motif dans le chemin, motif dans le nom, raison)
BLOCAGE_CHARGEMENT = [
    (r"/Mods/ExtendedMemory",
     "ExtendedMemory",
     "It remaps memory for +2 GB and needs the game recompiled to use it. "
     "With UKMM replacing game files, the game never finishes loading."),
    (r"graphicPacks/HD_Map_and_Icons",
     "HD_Map_and_Icons",
     "File-replacement pack: our own UKMM rules.txt already says not to use "
     "it alongside another mod loader."),
]

# Les packs officiels de Cemu pour BOTW. Aucun ne remplace un fichier du jeu :
# ils reglent la resolution, les shaders et la correction des couleurs. C'est
# ce que `botw graphics` reactive apres un `botw fix`.
#
# "Enhancements" porte dans sa section [Default] "$preset:int = 10", soit le
# prereglage Clarity de Serfrost - celui que Cemu recommande, et une vraie
# correction des couleurs. On l'active donc tel quel, sans ecrire de <Preset>
# dans settings.xml : on n'a jamais observe ce format, et le deviner serait
#piricalement plus risqué que de laisser Cemu appliquer son propre [Default].
OFFICIELS = [
    ("downloadedGraphicPacks/BreathOfTheWild/Workarounds/rules.txt",
     "Workarounds", "graphics.workarounds"),
    ("downloadedGraphicPacks/BreathOfTheWild/Graphics/rules.txt",
     "Graphics", "graphics.pack"),
    ("downloadedGraphicPacks/BreathOfTheWild/Enhancements/rules.txt",
     "Enhancements", "graphics.enhancements"),
]

# Packs tiers que `botw graphics --mods` peut remettre. Eux modifient le
# rendu plus franchement que les packs officiels : ils restent donc en dehors
# du comportement par defaut.
COSMETIQUES = ["DrawDistance", "FPS++", "DivineLaserBeam"]


# Packs qui ne bloquent pas le chargement mais partagent le meme perimetre
# que nos mods. Desactivables, pas dangereux.
OPTIONNELS = [
    ("/Mods/DrawDistance", "DrawDistance", "changes how far you see"),
    ("/Mods/FPS++", "FPS++", "unlocks the frame rate"),
    ("/Mods/DivineLaserBeam", "DivineLaserBeam", "adds a laser to the Guardian"),
    ("/Enhancements", "Survival of the Wild", "shaders and reflections"),
    ("/Graphics", "Graphics preset", "resolution and FXAA"),
]


# --- lecture ----------------------------------------------------------------

def section_brute():
    """Le bloc <GraphicPack>...</GraphicPack>, ou ''."""
    try:
        with io.open(config.cemu_settings(), encoding="utf-8", errors="replace") as f:
            t = f.read()
    except OSError:
        return ""
    m = re.search(r"<%s>(.*?)</%s>" % (BALISE, BALISE), t, re.S)
    return m.group(0) if m else ""


def active_packs():
    """Liste des packs actuellement actives (chemins relatifs a graphicPacks)."""
    brut = section_brute()
    return [m.group(1) for m in ENTREE.finditer(brut)]


def _entrees_brutes():
    """[(chemin, bloc_xml_complet)] dans l'ordre du fichier."""
    brut = section_brute()
    out = []
    for m in ENTREE.finditer(brut):
        out.append((m.group(1), m.group(0)))
    return out


def nom_lisible(chemin):
    """'graphicPacks/.../Mods/ExtendedMemory/rules.txt' -> 'ExtendedMemory'."""
    parts = [p for p in chemin.replace("\\", "/").split("/") if p]
    if len(parts) >= 2 and parts[-1] == "rules.txt":
        return parts[-2]
    return parts[-1] if parts else chemin


def est_botw(chemin):
    c = chemin.replace("\\", "/")
    return ("BreathOfTheWild" in c or "HD_Map" in c
            or "UKMM" in c or "101c9500" in c)


def classer():
    """(dangereux, optionnels, autres_packs_botw) parmi les packs actifs.

    "Dangereux" = le jeu ne finit jamais de charger si on le laisse actif a
    cote du pack UKMM. "Optionnel" = sans effet sur le chargement, mais
    partage le meme perimetre que nos mods, donc deactivated par defaut.
    """
    dangereux, optionnels, autres = [], [], []
    for chemin in active_packs():
        if _bloque_chargement(chemin):
            dangereux.append((chemin, nom_lisible(chemin)))
        elif est_botw(chemin) and any(
                motif in chemin.replace("\\", "/")
                for motif, _a, _r in OPTIONNELS):
            optionnels.append((chemin, nom_lisible(chemin)))
        elif est_botw(chemin):
            autres.append((chemin, nom_lisible(chemin)))
    return dangereux, optionnels, autres


def _bloque_chargement(chemin):
    c = chemin.replace("\\", "/")
    return any(re.search(motif, c) for motif, _nom, _r in BLOCAGE_CHARGEMENT)


def raison(chemin):
    for motif, _nom, texte in BLOCAGE_CHARGEMENT:
        if re.search(motif, chemin.replace("\\", "/")):
            return texte
    return ""


# --- ecriture ---------------------------------------------------------------

def ecrire_packs(chemins, cfg=None):
    """Remplace la liste des packs actifs. Retourne (ok, message)."""
    chemin_fichier = config.cemu_settings()
    try:
        with io.open(chemin_fichier, encoding="utf-8", errors="replace") as f:
            t = f.read()
    except OSError:
        return False, _("cemu.nosettings", p=chemin_fichier)
    if deploy_ouvert(cfg):
        return False, _("cemu.open")
    if not re.search(r"<%s>" % BALISE, t):
        return False, _("cemu.nopacktag", p=chemin_fichier)
    sauvegarde = chemin_fichier + ".botw-packs.bak"
    if not os.path.isfile(sauvegarde):
        try:
            shutil.copy2(chemin_fichier, sauvegarde)
        except OSError:
            pass
    # On reapplique le bloc XML d'origine de chaque pack qui reste actif :
    # c'est lui qui porte les <Preset>, donc les reglages de l'utilisateur
    # (resolution, images par seconde, distance, couleurs). Ecrire une entree
    # nue les remettrait a zero - c'est ce qui est arrive une fois.
    # Attention au nom des variables : `chemin_fichier` designe settings.xml
    # et sert a l'ecriture finale plus bas.
    connus = {}
    for chemin_pack, bloc_xml in _entrees_brutes():
        connus[cle(chemin_pack)] = bloc_xml
    morceaux = []
    vus = set()
    for c in chemins:
        k = cle(c)
        if k in vus:
            continue
        vus.add(k)
        morceaux.append(connus.get(k) or '<Entry filename="%s"/>' % c)
    corps = "\n".join("        " + m for m in morceaux)
    nouveau = "<%s>\n%s\n    </%s>" % (BALISE, corps, BALISE)
    # On garde l'indentation d'origine du fichier : Cemu relit ce XML tel quel.
    t2 = re.sub(r"<%s>.*?</%s>" % (BALISE, BALISE), nouveau, t, count=1, flags=re.S)
    try:
        with io.open(chemin_fichier, "w", encoding="utf-8", newline="") as f:
            f.write(t2)
    except OSError as e:
        return False, str(e)
    return True, _("cemu.written", n=len(chemins))


def deploy_ouvert(cfg=None):
    from . import deploy
    return bool(deploy.processes_named("Cemu"))


def _sur_le_disque(relatif):
    return os.path.isfile(os.path.join(config.cemu_appdata(), "graphicPacks",
                                       relatif))


PREFIXE = "graphicPacks/"


def cle(chemin):
    """L'identite d'un pack, independante de la maniere dont il est ecrit.

    Cemu ecrit "graphicPacks/a/b/rules.txt", notre code "a/b/rules.txt" :
    meme pack, deux chaines. Sans normalisation, le meme pack peut etre
    active deux fois - et il l'etait.
    """
    c = chemin.replace("\\", "/").lstrip("/")
    if c.lower().startswith(PREFIXE.lower()):
        c = c[len(PREFIXE):]
    return c.lower()


def racine_workarounds():
    """Le dossier des correctifs de compatibilite de Cemu.

    Calcule a l'appel et non a l'import : une constante de module serait
    figee sur le vrai %APPDATA%, avant que les tests ne le repointent sur
    une fausse machine. Les tests verraient alors les packs de la vraie
    installation, et le resultat de la suite dependrait de la machine.
    """
    return os.path.join(config.cemu_appdata(), "graphicPacks",
                        "downloadedGraphicPacks", "BreathOfTheWild",
                        "Workarounds")


def workarounds():
    """Les packs de compatibilite installes, un par sous-dossier.

    Cemu ne livre pas UN pack Workarounds mais un dossier de packs
    independants (crash AMD, cloudes NVIDIA, synchronisation CPU...). Chacun a
    son propre rules.txt, donc chacun doit etre ajoute a part.
    """
    racine = racine_workarounds()
    if not os.path.isdir(racine):
        return []
    trouve = []
    for nom in sorted(os.listdir(racine)):
        d = os.path.join(racine, nom)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "rules.txt")):
            trouve.append((
                "downloadedGraphicPacks/BreathOfTheWild/Workarounds/"
                "%s/rules.txt" % nom, nom, ""))
    return trouve


def disponibles():
    """Les packs officiels reellement installes : [(relatif, nom, cle_texte)]."""
    return ([(relatif, nom, cle)
             for relatif, nom, cle in OFFICIELS if _sur_le_disque(relatif)]
            + workarounds())


def restaurer_depuis(fichier, cfg=None):
    """Reprend les entrees - et leurs <Preset> - d'un ancien settings.xml.

    Le remede quand une reecriture a aplati les reglages : on relit une
    sauvegarde, on garde tout ce qui n'est pas bloquant, et on ecrit les
    blocs d'origine, presets compris. Les packs qui bloquent le chargement ne
    reviennent jamais, meme s'ils etaient dans la sauvegarde.

    Retourne (ok, message, [noms restaures]).
    """
    if not os.path.isfile(fichier):
        return False, _("cemu.nosettings", p=fichier), []
    try:
        with io.open(fichier, encoding="utf-8", errors="replace") as f:
            ancien = f.read()
    except OSError as e:
        return False, str(e), []

    m = re.search(r"<%s>(.*?)</%s>" % (BALISE, BALISE), ancien, re.S)
    if not m:
        return False, _("cemu.nopacktag", p=fichier), []

    ordre, blocs, noms, vus = [], {}, [], set()
    for mm in ENTREE.finditer(m.group(0)):
        chemin, bloc = mm.group(1), mm.group(0)
        k = cle(chemin)
        if k in vus or _bloque_chargement(chemin):
            continue
        vus.add(k)
        ordre.append(chemin)
        blocs[k] = bloc
        noms.append(nom_lisible(chemin))
    if not ordre:
        return False, _("cemu.nopacks"), []

    chemin_fichier = config.cemu_settings()
    if deploy_ouvert(cfg):
        return False, _("cemu.open"), []
    try:
        with io.open(chemin_fichier, encoding="utf-8", errors="replace") as f:
            t = f.read()
    except OSError:
        return False, _("cemu.nosettings", p=chemin_fichier), []
    if not re.search(r"<%s>" % BALISE, t):
        return False, _("cemu.nopacktag", p=chemin_fichier), []

    try:
        shutil.copy2(chemin_fichier, chemin_fichier + ".avant-restauration")
    except OSError:
        pass
    corps = "\n".join("        " + blocs[cle(c)] for c in ordre)
    nouveau = "<%s>\n%s\n    </%s>" % (BALISE, corps, BALISE)
    t2 = re.sub(r"<%s>.*?</%s>" % (BALISE, BALISE), nouveau, t,
                count=1, flags=re.S)
    try:
        with io.open(chemin_fichier, "w", encoding="utf-8", newline="") as f:
            f.write(t2)
    except OSError as e:
        return False, str(e), []
    return True, _("cemu.written", n=len(ordre)), noms


def activer_graphismes(cosmetiques=False, cfg=None):
    """Reactive les packs officiels de Cemu, et repare la liste des packs.

    Retourne (ok, message, [noms ajoutes]).

    Deux garanties :

    * les packs qui bloquent le chargement (ExtendedMemory, HD_Map_and_Icons)
      sont retires dans la meme operation. Reactiver l'image ne doit jamais
      pouvoir remettre le jeu dans l'etat qui le faisait boucler ;
    * le pack UKMM passe en premier : c'est lui qui porte les mods, et
      l'ordre de la liste n'est pas neutre.
    """
    avant = active_packs()
    if not avant:
        return False, _("cemu.nopacks"), []

    dangereux = set(c for c, _nom in classer()[0])
    ordre = [c for c in avant if "UKMM" in c]
    for c in avant:
        if c in dangereux or "UKMM" in c:
            continue
        if c not in ordre:
            ordre.append(c)

    presents = set(cle(c) for c in avant)
    ajoutes = []
    candidats = list(disponibles())
    for nom in (COSMETIQUES if cosmetiques else []):
        relatif = ("downloadedGraphicPacks/BreathOfTheWild/Mods/%s/rules.txt"
                   % nom)
        if _sur_le_disque(relatif):
            candidats.append((relatif, nom, ""))

    for relatif, nom, _texte in candidats:
        if cle(relatif) in presents:
            continue
        presents.add(cle(relatif))
        if relatif not in ordre:
            ordre.append(relatif)
            ajoutes.append(nom)

    # Deduplication finale : la liste peut contenir deja deux ecritures du
    # meme pack, introduites avant cette correction. On garde la premiere,
    # qui est celle de Cemu.
    vus = set()
    ordre = [c for c in ordre if not (cle(c) in vus or vus.add(cle(c)))]

    ok, msg = ecrire_packs(ordre, cfg)
    # Si l'ecriture a echoue, rien n'a ete ajoute : renvoyer la liste quand
    # meme ferait dire a l'utilisateur "3 packs actives" alors que
    # settings.xml est intact. C'est exactement le genre de mensonge que ce
    # projet evite partout ailleurs.
    return ok, msg, (ajoutes if ok else [])

# --- le correctif -----------------------------------------------------------

def nettoyer(keep_cheats=True, keep_options=False, cfg=None):
    """Retire les packs qui bloquent le chargement. Retourne (retires, nom_ukmm).

    On ne touche qu'aux packs de BOTW. Les packs des autres jeux restent :
    Cemu les a ajoutes tout seul, ils sont inoffensifs et l'utilisateur
    les a peut-etre coches pour son propre bonheur.
    """
    avant = active_packs()
    dangereux, optionnels, _autres = classer()
    a_retirer = [c for c, _n in dangereux]
    if not keep_options:
        a_retirer += [c for c, _n in optionnels]
    if not keep_cheats:
        a_retirer += [c for c in avant
                      if "/Cheats/" in c.replace("\\", "/")]
    # On garde toujours le pack UKMM.
    ukmm = [c for c in avant if "UKMM" in c]
    if not ukmm:
        return [], ""
    restants = [c for c in avant if c not in a_retirer]
    if len(restants) == len(avant):
        return [], ukmm[0]
    ok, msg = ecrire_packs(restants, cfg)
    if not ok:
        i18n.ko(msg)
        return [], ""
    return [nom_lisible(c) for c in a_retirer], ukmm[0]


# Petit utilite utilise par les tests : la liste finale telle que Cemu la
# lirait apres nettoyage.
def simuler(keep_cheats=True, keep_options=False):
    dangereux, optionnels, _ = classer()
    a_retirer = set(c for c, _ in dangereux)
    if not keep_options:
        a_retirer |= set(c for c, _ in optionnels if est_botw(c))
    if not keep_cheats:
        a_retirer |= set(c for c in active_packs() if "/Cheats/" in c)
    return [c for c in active_packs() if c not in a_retirer]