"""Afficher la documentation, dans la langue choisie.

Deux fichiers au meme endroit : README.md (anglais, celui de GitHub) et
README.fr.md (francais). On cherche dans le dossier de l'outil, puis dans
celui du lanceur, parce que les deux sont installs cote a cote sur le
bureau.

Si le fichier n'est pas la, on ne se contente pas d'un message d'erreur : on
dit ou il a ete cherche, et on rappelle que le francais existe.
"""
import io
import os
import subprocess
import sys

from . import config, i18n

_ = i18n._


def search_roots():
    """Dossiers ou un README peut se trouver, du plus probable au moins probable."""
    here = config.tool_root()
    out = [here,
           os.path.dirname(here),
           os.path.join(os.path.expanduser("~"), "Desktop", "BOTW"),
           os.getcwd()]
    seen, res = set(), []
    for d in out:
        if d and d not in seen and os.path.isdir(d):
            seen.add(d)
            res.append(d)
    return res


def find(lang=None):
    """Chemin du README pour une langue, ou None."""
    lang = (lang or i18n.lang()).lower()
    names = {"en": ["README.md"], "fr": ["README.fr.md", "LISEZ-MOI.txt"]}
    wanted = names.get(lang, ["README.%s.md" % lang])
    for root in search_roots():
        for n in wanted:
            p = os.path.join(root, n)
            if os.path.isfile(p):
                return p
    return None


def exists(lang=None):
    return find(lang) is not None


def show(lang=None, pager=True):
    """Affiche le README. Retourne True s'il a ete trouve."""
    lang = (lang or i18n.lang()).lower()
    path = find(lang)
    if not path:
        i18n.ko(_("readme.missing", lang=lang, path=os.pathsep.join(search_roots())))
        i18n.info(_("readme.tip"))
        return False
    i18n.title(_("readme.title", lang=lang))
    i18n.info(_("readme.from", p=path))
    text = _read(path)
    _emit(text, pager)
    other = "fr" if lang != "fr" else "en"
    if exists(other):
        i18n.info(_("readme.other", lang=other))
    return True


def _read(path):
    try:
        with io.open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _emit(text, pager):
    """Ecrit page par page si la sortie est un terminal, sinon d'un bloc.

    Un README de plusieurs centaines de lignes qu'on balance d'un coup dans
    un terminal est illisible : on paginaite. Redirige vers un fichier, on ne
    paginaite pas, sinon la redirection serait vide.
    """
    if not pager or not sys.stdout.isatty():
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return
    lignes = text.splitlines()
    page = int(os.environ.get("BOTW_PAGE", "0") or 0) or _term_height() - 2
    if page < 10:
        page = 10
    i = 0
    while i < len(lignes):
        sys.stdout.write("\n".join(lignes[i:i + page]) + "\n")
        i += page
        if i >= len(lignes):
            break
        try:
            rep = input(i18n.paint("  -- more (Enter) / q ", "dim"))
        except (EOFError, KeyboardInterrupt):
            print("")
            return
        if rep.strip().lower().startswith("q"):
            return


def _term_height():
    try:
        import shutil
        return shutil.get_terminal_size((80, 25)).lines
    except Exception:                                          # noqa: BLE001
        return 25


def open_in_viewer(lang=None):
    """Ouvre le README avec le programme par defaut du systeme."""
    path = find(lang)
    if not path:
        i18n.ko(_("readme.missing", lang=lang or i18n.lang(),
                  path=os.pathsep.join(search_roots())))
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)                                  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", path])
    except OSError as e:
        i18n.ko(_("readme.open_failed", e=e))
        return False
    i18n.ok(_("readme.opened", p=path))
    return True
