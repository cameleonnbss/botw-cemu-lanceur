"""Recommencer une partie sans perdre l'ancienne.

Le bug le plus frustrant de tout le projet, et sa cause a ete trouvee : une
sauvegarde ne s'ouvre qu'avec le jeu qui l'a creee. Le fichier est chiffre,
et sa cle est derivee du profil de mods. Charger une partie 'boost' avec le
profil 'sur' fait rester le jeu sur l'ecran de chargement, indefiniement,
sans un seul message d'erreur.

La parade n'est pas technique : on deplace l'emplacement de sauvegarde
courant sur le cote, dans le dossier des parties, et on laisse Cemu creer un
emplacement vide. L'ancienne partie est dans le dossier, avec son nom, et
'botw newgame revert' la remet en place.
"""
import json
import os
import re
import shutil
import time

from . import config, deploy, i18n

_ = i18n._

INDEX = "nouvelle-partie.json"
SLOT = "slot.json"
DOSSIER = "NouvellePartie"
DATE = time.strftime("%Y-%m-%d_%H%M%S")


# On garde quelques deploiements d'historique. C'est ce qui permet de dire
# quel profil etait actif quand la sauvegarde a ete ecrite.
HISTORIQUE = 50

# Marge de tolerance entre l'ecriture de la sauvegarde et l'horodatage du
# deploiement : une seconde et une demi, parce que Cemu peut ecrire la partie
# alors que le deploiement vient de finir.
TOLERANCE = 2


def _slot_file():
    """Ou l'on note les deploiements successifs.

    Le fichier de sauvegarde est chiffre : rien dans le jeu ne dit quel profil
    l'a cree. On note donc nous-memes chaque deploiement, avec l'instant ou il
    a eu lieu.

    On garde un historique et non « le dernier profil » parce que l'ancien
    etait faux dans un cas tres courant : deploiement de 'boost', partie
    enregistree, puis deploiement d'un autre profil. En ne gardant que le
    dernier, la partie se retrouve attribuee au nouveau profil alors qu'elle
    appartient au precedent - et `botw check` annonce alors tout va bien
    alors que charger cette partie bloquera a l'infini.
    """
    return os.path.join(_archives(), SLOT)


def _lire_notes():
    """L'historique des deploiements. Lit aussi l'ancien format {profil,
    quand} : les fichiers deja ecrits sur le disque restent lisibles."""
    try:
        with open(_slot_file(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    notes = data if isinstance(data, list) else [data]
    return [n for n in notes
            if isinstance(n, dict) and n.get("profil")
            and isinstance(n.get("quand"), (int, float))]


def noter_profil(profil):
    """Ajoute un deploiement a l'historique."""
    if not profil:
        return False
    notes = _lire_notes()
    notes.append({"profil": profil, "quand": time.time()})
    try:
        os.makedirs(_archives(), exist_ok=True)
        with open(_slot_file(), "w", encoding="utf-8", newline="\n") as f:
            json.dump(notes[-HISTORIQUE:], f, indent=2)
        return True
    except OSError:
        return False


def profil_de_la_partie():
    """Le profil qui etait deploye quand la sauvegarde a ete ecrite.

    Ou '' si on ne peut pas le dire. On ne devine jamais : une sauvegarde
    chargee avec les mauvais mods bloque a l'infini, et Cemu ne dit rien.
    """
    notes = _lire_notes()
    if not notes or not has_game():
        return ""
    try:
        mtime = os.path.getmtime(config.main_save_file())
    except OSError:
        return ""
    avant = [n for n in notes if float(n["quand"]) <= mtime + TOLERANCE]
    if not avant:
        return ""       # la partie est plus ancienne que tout ce qu'on sait
    return str(max(avant, key=lambda n: float(n["quand"]))["profil"])


def _slot():
    """Le dossier de la partie actuelle (celui que Cemu lit)."""
    return config.save_root()


def _archives():
    """Dossier des parties ecartees.

    Volontairement un sous-dossier et un index a part : le gestionnaire de
    sauvegardes PowerShell tient deja un parties.json avec ses propres cles
    (id, nom, description). Deux index dans le meme fichier finiraient par se
    marched dessus, et on perdrait la liste des parties de l'utilisateur.
    """
    return os.path.join(config.shots_dir(), DOSSIER)


def _stamp():
    return DATE


def _dest_archive():
    """Un dossier d'archive libre, et son nom.

    `_stamp()` est fige au moment ou le module est importe : deux parties
    mises de cote dans la meme seconde donnaient donc le meme nom, et la
    seconde se faisait refuser ('an archive with this name already exists').
    C'etait invisible en usage normal - on n'archive pas deux fois dans la
    meme seconde - mais reachable des qu'on bascule entre deux jeux de mods,
    qui archive puis restaure puis rearchive.
    """
    base = os.path.join(_archives(), "partie_%s" % _stamp())
    dest = base
    suffixe = 2
    while os.path.exists(dest):
        dest = "%s_%d" % (base, suffixe)
        suffixe += 1
    return dest


def _index_path():
    return os.path.join(_archives(), INDEX)


def read_index():
    try:
        with open(_index_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def write_index(rows):
    try:
        os.makedirs(_archives(), exist_ok=True)
        tmp = _index_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
        os.replace(tmp, _index_path())
        return True
    except OSError:
        return False


def has_game():
    return os.path.isfile(config.main_save_file())


def _size_of(root):
    total = 0
    for base, _d, files in os.walk(root):
        for n in files:
            try:
                total += os.path.getsize(os.path.join(base, n))
            except OSError:
                pass
    return total


def prepare(profile=None, keep_backup=True, nom=None):
    """Deplace la partie actuelle sur le cote. Retourne le chemin de l'archive.

    Le dossier de sauvegarde est copie, pas deplace : si Cemu tourne ou si le
    systeme s'arrete au milieu, l'emplacement reste valide. Le cout est
    negligeable (quelques Mo), le gain est qu'on ne peut pas perdre une partie
    par une manipulation de fichier.
    """
    if not has_game():
        i18n.info(_("newgame.nothing"))
        return None
    dest = _dest_archive()
    if os.path.exists(dest):
        i18n.ko(_("newgame.exists", path=dest))
        return None
    os.makedirs(_archives(), exist_ok=True)
    shutil.copytree(_slot(), dest)
    if not keep_backup:
        shutil.rmtree(_slot(), ignore_errors=True)
    else:
        # On ne laisse qu'un emplacement vide et valide pour Cemu.
        shutil.rmtree(_slot(), ignore_errors=True)
        os.makedirs(_slot(), exist_ok=True)
    rows = read_index()
    rows.append({"date": _stamp(), "profil": profile or "", "path": dest,
                 "nom": nom or "", "octets": _size_of(dest)})
    write_index(rows)
    noter_profil(profile or "")
    i18n.ok(_("newgame.backup", path=dest))
    i18n.ok(_("newgame.done"))
    return dest

def revert(path=None, force=False):
    """Remet en place la partie la plus recente (ou celle demandee).

    `force` repond oui a la place de l'utilisateur quand une partie existe
    deja : c'est ce qu'utilise 'botw newgame revert -y', et les tests.
    """
    rows = read_index()
    if not rows:
        i18n.ko(_("newgame.no_archive"))
        return None
    if path is None:
        chosen = sorted(rows, key=lambda r: r.get("date", ""))[-1]
    else:
        chosen = None
        for r in rows:
            if os.path.basename(r.get("path", "")) == os.path.basename(path) \
                    or os.path.basename(r.get("path", "")) == path:
                chosen = r
                break
        if chosen is None:
            i18n.ko(_("newgame.not_found", p=path))
            return None
    src = chosen["path"]
    if not os.path.isdir(src):
        i18n.ko(_("newgame.not_found", p=src))
        return None
    if has_game():
        i18n.warn(_("newgame.will_replace"))
        if not force and not i18n.confirm(_("newgame.confirm_replace"), False):
            return None
        extra = src + "_remplacee_%s" % _stamp()
        shutil.move(_slot(), extra)
        i18n.info(_("newgame.replaced", path=extra))
    # On deplace le CONTENU de l'archive dans l'emplacement, pas l'archive
    # elle-meme. `shutil.move(src, _slot())` glisse l'archive DANS le
    # dossier existant : l'emplacement se retrouvait avec un sous-dossier
    # 'partie_...' a l'interieur, et Cemu n'y voyait plus aucune partie -
    # alors que la commande annoncait la restauration. C'est exactement ce
    # qui se passe apres `newgame`, qui laisse un emplacement vide valide.
    os.makedirs(_slot(), exist_ok=True)
    for nom in os.listdir(src):
        shutil.move(os.path.join(src, nom), os.path.join(_slot(), nom))
    try:
        os.rmdir(src)
    except OSError:
        pass
    write_index([r for r in rows if r is not chosen])
    i18n.ok(_("newgame.revert", path=_slot()))
    return _slot()


def status():
    i18n.title(_("newgame.title"))
    if has_game():
        st = os.stat(config.main_save_file())
        i18n.ok(_("newgame.current", n=deploy.count_files(_slot()),
                  d=time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))))
        p = profil_de_la_partie()
        if p:
            i18n.info(_("newgame.current_profile", p=p))
        else:
            i18n.warn(_("newgame.current_unknown"))
    else:
        i18n.info(_("newgame.nothing"))
    rows = read_index()
    if rows:
        i18n.section(_("newgame.archive"))
        for i, r in enumerate(sorted(rows, key=lambda x: x.get("date", "")), 1):
            print("  %2d. %-18s %-10s %s" % (i, r.get("date", "?"),
                                             r.get("profil") or "-",
                                             r.get("path", "")))
        i18n.info(_("newgame.revert_hint"))
    else:
        i18n.info(_("newgame.no_archive"))
    i18n.info(_("newgame.explain"))


def _contient_une_partie(chemin):
    """Vrai si le dossier d'archive contient vraiment le fichier de partie.

    Un dossier a moitie copie - une coupure, un disque plein, un arret du
    systeme - existe bel et bien. Le traiter comme une archive valide ferait
    la remettre en place, Cemu y trouverait un emplacement sans partie et
    proposerait d'en creer une nouvelle : une partie perdue, sans un seul
    message. On verifie donc la presence du fichier, pas seulement du dossier.
    """
    try:
        rel = os.path.relpath(config.main_save_file(), config.save_root())
    except ValueError:
        return False
    if rel.startswith(os.pardir):
        return False
    return os.path.isfile(os.path.join(chemin, rel))


def parties():
    """Les parties ecartees, les plus recentes d'abord.

    Une ligne par partie archivée, avec le profil qui peut la charger. Une
    partie dont le fichier n'est plus la est quand meme listee, avec `existe`
    a faux : la cacher ferait croire qu'elle n'a jamais existe, alors que
    l'index, lui, sait qu'elle a ete perdue.
    """
    out = []
    for r in sorted(read_index(), key=lambda x: x.get("date", ""), reverse=True):
        chemin = r.get("path", "")
        out.append({"profil": r.get("profil") or "",
                    "date": r.get("date", ""),
                    "nom": r.get("nom") or "",
                    "path": chemin,
                    "existe": _contient_une_partie(chemin)})
    return out


def _partie_du_profil(profil):
    """La partie archivée la plus recente de ce profil, ou None.

    On ignore les archives dont le dossier n'existe plus : les remettre en
    place echouerait, et mieux vaut proposer une nouvelle partie que
    bloquer sur une archive fantome.
    """
    for p in parties():
        if p["existe"] and p["profil"] == profil:
            return p
    return None


def _deploiement_complet(profil):
    """Vrai si le profil demande est deja entierement deploye chez Cemu.

    C'est exactement la verification que fait `doctor` : le pack graphique
    moins `rules.txt` doit contenir autant de fichiers que la fusion. Compter
    coute un parcours de repertoire, pas une re-fusion ; sans cela, « je veux
    rejouer ma partie principale » coute deux minutes de remerge a chaque fois
    alors que rien n'a change sur le disque.

    On compare le pack ENTIER, pas seulement son sous-dossier `content` : la
    fusion contient aussi `aoc`, et comparer `content` a l'ensemble donnait
    un compte faux des que le profil avait un seul fichier AOC - donc jamais.
    """
    from . import deploy
    gp = config.graphic_pack()
    if not os.path.isdir(gp):
        return False
    n_deployes = deploy.count_files(gp) - 1      # -1 : rules.txt
    fusion = deploy.merged_dir(profil)
    n_fusionnes = deploy.count_files(fusion)
    if n_deployes < n_fusionnes:
        return False                             # il manque des fichiers
    # Le pack peut en contenir PLUS que la fusion : c'est normal apres une
    # re-fusion, UKMM laisse deriver des fichiers d'une fusion anterieure.
    # Le jeu y trouve tout ce qu'il attend, donc redeployer serait inutile.
    # Mais un compte egal ne prouve rien : un fichier fusionne peut manquer
    # pendant qu'un fichier etranger occupe sa place. On verifie donc toujours
    # le contenu, ce qui coute un parcours de repertoire et non une
    # re-fusion.
    return _contient(fusion, gp)


def _contient(source, destination):
    """Vrai si tout fichier de `source` existe dans `destination`."""
    for base, _d, fichiers in os.walk(source):
        for nom in fichiers:
            rel = os.path.relpath(os.path.join(base, nom), source)
            if not os.path.exists(os.path.join(destination, rel)):
                return False
    return True


def basculer(profil, cfg=None, force=False):
    """Passe a un autre jeu de mods, sans perdre la partie d'ici.

    C'est l'operation que le joueur fait sans y penser - « je veux jouer avec
    les 13 mods » - et c'est celle qui cassait tout : changer de profil tout
    en gardant l'emplacement de sauvegarde donne une partie que rien ne peut
    charger. L'ordre est donc impose :

        1. on met la partie de cote, avec le profil qui peut la charger ;
        2. on deploie le nouveau profil ;
        3. on remet la partie de ce profil-la, si elle existe.

    Si le deploiement echoue a l'etape 2, la partie est deja|archivee et
    l'emplacement est vide : rien n'est perdu, et 'botw newgame revert' la
    ramene. L'ordre inverse - deploiement puis copie - laisserait le deploiement
    echouer apres avoir touche a la partie.

    Le cas le plus frequent est aussi le plus simple : le profil demande est
    deja actif, la partie lui appartient, et le deploiement est complet. Les
    trois etapes ne feraient alors rien changer, et le joueur attendrait deux
    minutes pour demarrer le jeu exactement comme avant. On le detecte et on
    sort tout de suite. Le court-circuit ne dispense d'aucune verification : si
    le deploiement est incomplet, on repasse par la voie normale.

    Retourne True si le profil est en place et pret a jouer.
    """
    from . import deploy, profiles

    if profil not in profiles.existing():
        i18n.ko(_("newgame.unknown_profile", p=profil))
        i18n.info(_("catalog.available",
                    list=", ".join(sorted(profiles.existing()))))
        return False
    if deploy.processes_named("Cemu"):
        i18n.ko(_("cemu.open"))
        return False

    if profiles.active() == profil and _deploiement_complet(profil) \
            and (not has_game() or profil_de_la_partie() in ("", profil)):
        i18n.ok(_("newgame.switch_ready", p=profil))
        return True

    if not force and not i18n.confirm(_("newgame.switch_confirm", p=profil),
                                      False):
        return False

    # Le profil de la partie doit etre lu AVANT prepare() : apres, il n'y a
    # plus de partie, et donc plus rien a quoi comparer l'historique.
    if has_game():
        proprietaire = profil_de_la_partie() or profiles.active() or ""
        if proprietaire and proprietaire != profil:
            i18n.info(_("newgame.switch_archive", p=proprietaire))
        if prepare(proprietaire) is None:
            return False

    try:
        deploy.deploy(profil, cfg, quiet=True)
    except deploy.GuardError as e:
        i18n.ko(str(e))
        return False

    if os.path.isdir(os.path.join(config.graphic_pack(), "content")):
        i18n.ok(_("newgame.switch_deployed", p=profil))
    else:
        i18n.ko(_("deploy.nothing", p=profil))
        return False

    existante = _partie_du_profil(profil)
    if existante is not None:
        if revert(existante["path"], force=True):
            i18n.ok(_("newgame.switch_restored", p=profil))
        else:
            return False
    else:
        i18n.info(_("newgame.switch_new", p=profil))
    return True


def execute(args=None):
    """Point d'entree : `botw newgame [revert|status] [-y]`."""
    args = args or []
    action = "new"
    force = False
    for a in args:
        if a in ("revert", "status", "new"):
            action = a
        elif a in ("-y", "--yes"):
            force = True
        elif re.match(r"^\d+$", a):
            rows = sorted(read_index(), key=lambda x: x.get("date", ""))
            if 1 <= int(a) <= len(rows):
                return revert(rows[int(a) - 1]["path"], force) is not None
            i18n.ko(_("err.bad_int", v=a))
            return False
    if action == "status":
        status()
        return True
    if action == "revert":
        return revert(force=force) is not None
    i18n.title(_("newgame.title"))
    i18n.info(_("newgame.explain"))
    if not force and not i18n.confirm(_("newgame.confirm"), False):
        return False
    return prepare() is not None
