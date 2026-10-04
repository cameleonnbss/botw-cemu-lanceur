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


def prepare(profile=None, keep_backup=True):
    """Deplace la partie actuelle sur le cote. Retourne le chemin de l'archive.

    Le dossier de sauvegarde est copie, pas deplace : si Cemu tourne ou si le
    systeme s'arrete au milieu, l'emplacement reste valide. Le cout est
    negligeable (quelques Mo), le gain est qu'on ne peut pas perdre une partie
    par une manipulation de fichier.
    """
    if not has_game():
        i18n.info(_("newgame.nothing"))
        return None
    dest = os.path.join(_archives(), "partie_%s" % _stamp())
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
                 "octets": _size_of(dest)})
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
