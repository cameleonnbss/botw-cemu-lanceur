"""Localisation.

L'outil parle anglais par defaut. Le francais est une langue optionnelle :
elle se choisit une fois (`botw lang fr`) et tout suit - y compris les
messages d'erreur et l'aide.

Les chaines sont dans locales/<langue>.json. Plutot que de disperser des
`if lang == 'fr'` partout, chaque module demande une cle et l'i18n
s'occupe du reste. Une cle absente d'une langue retombe sur l'anglais :
on prefere un message en anglais a un message vide.

L'affichage terminal est ici aussi, plutot que dans chaque module : le meme
prefixe [OK ] / [KO ] partout rend la sortie lisible d'un coup d'oeil.
"""
import json
import os
import sys

LOCALES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "locales")
DEFAULT = "en"
FALLBACK = "en"

_cache = {}


def available():
    """Langues disponibles, la langue par defaut en premier."""
    out = []
    try:
        for nom in sorted(os.listdir(LOCALES)):
            if nom.endswith(".json"):
                out.append(nom[:-5])
    except OSError:
        pass
    if DEFAULT in out:
        out.remove(DEFAULT)
    return [DEFAULT] + out


def _load(code):
    if code in _cache:
        return _cache[code]
    path = os.path.join(LOCALES, code + ".json")
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    _cache[code] = data
    return data


class Translator(object):
    def __init__(self, code=DEFAULT):
        self.set(code)

    def set(self, code):
        if code not in available():
            code = DEFAULT
        self.code = code
        self.data = _load(code)
        self.base = _load(FALLBACK)
        return self.code

    def __call__(self, key, **kw):
        txt = self.data.get(key)
        if txt is None:
            txt = self.base.get(key, key)
        if kw:
            try:
                return txt.format(**kw)
            except (KeyError, IndexError, ValueError):
                return txt
        return txt

    def fmt(self, key, **kw):
        return self(key, **kw)

    def has(self, key):
        return key in self.data or key in self.base


# Instance utilisee par les modules. cli.py la met a jour apres avoir lu la
# configuration, et --lang force une langue pour une seule invocation.
t = Translator(DEFAULT)


def set_lang(code):
    return t.set(code)


def lang():
    return t.code


def _(key, **kw):
    return t(key, **kw)


# --- sortie terminal ---------------------------------------------------------
# Pas de dependance externe : on gere soi-meme les couleurs, et on les coupe
# si la sortie n'est pas un terminal (pipé dans un fichier) ou si la
# variable NO_COLOR est definie. Sans ca, les rapports records en contain
# des codes d'echappement illisibles.
_COLOR = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
}


def use_utf8():
    """Force la sortie console en UTF-8.

    La console Windows utilise cp1252 par defaut : des accents ou un emoji
    y provoceraient une UnicodeEncodeError en pleine commande, apres tout le
    travail deja fait. On ne touche a rien si l'utilisateur a choisi autre
    chose (PYTHONIOENCODING) : ce qui compte est de ne jamais planter.
    """
    for flux in (sys.stdout, sys.stderr):
        try:
            if (getattr(flux, "encoding", "") or "").lower().replace("-", "") \
                    not in ("utf8", "cp65001", "utf8mb4"):
                flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass


def color_enabled():
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    try:
        return sys.stdout.isatty()
    except Exception:                                          # noqa: BLE001
        return False


def paint(text, style=None):
    if not style or not color_enabled():
        return text
    return "".join(_COLOR.get(s, "") for s in style.split("+")) + text + _COLOR["reset"]


def title(text):
    print("")
    print(paint("=" * 70, "cyan"))
    print("  " + paint(text, "bold"))
    print(paint("=" * 70, "cyan"))


def banner():
    """En-tete commun : nom de l'outil + accroche, dans la langue choisie."""
    print("")
    print("  " + paint("botw", "bold+cyan") + "  -  " + _("app.tagline"))
    print("  " + paint(_("lang.current", lang=lang()), "dim"))


def section(text):
    print("")
    print(paint("  " + text, "cyan+bold"))


def ok(text):
    print("  " + paint("[OK ] ", "green") + text)


def ko(text):
    print("  " + paint("[KO ] ", "red") + text)


def info(text):
    print("  " + paint("[ --] ", "dim") + text)


def warn(text):
    print("  " + paint("[!! ] ", "yellow") + text)


def rule(char="-"):
    print(paint(char * 70, "dim"))


def ok_all(n):
    """Bandeau final quand tout va bien."""
    print("  " + paint("  " + _("doctor.ok_all", n=n), "green+bold"))


def ko_count(n, ok_):
    """Bandeau final quand il reste des problemes."""
    print("  " + paint("  " + _("doctor.ko_count", n=n, ok=ok_), "red+bold"))


def bullet(text, style=None):
    print("  " + paint("- ", style or "dim") + text)


def step(n, total, text):
    print("  " + paint("%d/%d " % (n, total), "bold") + text)


# --- interaction -------------------------------------------------------------

def ask(prompt, default=None):
    """Question posee sur une seule ligne, avec une valeur par defaut.

    Renvoie None quand il n'y a personne pour repondre : pas de terminal, ou
    stdin ferme (Ctrl+D, tache planifiee, sortie redirigee). C'est distinct de
    la valeur par defaut, et c'est indispensable : sinon le menu recoit toujours
    la meme reponse et tourne a l'infini.
    """
    suffix = paint(" [%s]" % default, "dim") if default else ""
    if not interactive():
        warn(_("ui.not_interactive", v=default if default is not None else ""))
        return default if default is not None else ""
    try:
        raw = input("  " + paint("?", "cyan") + " " + prompt + suffix + " : ")
    except (EOFError, KeyboardInterrupt):
        print("")
        return None
    print("")            # l'utilisateur a deja tape Enter : on ne laisse pas
    raw = raw.strip()    # la ligne suivante se coller a sa reponse
    return raw or (default if default is not None else "")


def interactive():
    """Vrai si on peut poser une question a un humain."""
    if os.environ.get("BOTW_ASSUME_OUI"):
        return True
    if os.environ.get("BOTW_NON_INTERACTIF"):
        return False
    try:
        return sys.stdin.isatty()
    except Exception:                                          # noqa: BLE001
        return False


def confirm(prompt, default=False):
    """Confirmation oui/non. Le defaut est 'non' : on ne casse rien par surprise.

    Si personne ne peut repondre (pas de terminal, stdin ferme), on renvoie le
    defaut : mieux vaut ne rien faire que bloquer ou deviner.
    """
    ans = ask(prompt + " (y/N)" if not default else prompt + " (Y/n)", None)
    if ans is None:
        return default
    ans = ans.lower()
    if not ans:
        return default
    return ans in ("y", "yes", "o", "oui")


def menu(options, prompt=None):
    """Affiche un menu numerote et renvoie l'index choisi (None = quit).

    `options` = [(cle, libelle), ...]. On boucle jusqu'a une reponse valide :
    une faute de frappe ne doit pas terminer le programme. Sans terminal, on
    renvoie None immediatement plutot que de bloquer.
    """
    if not interactive():
        warn(_("ui.not_interactive", v="0"))
        return None
    prompt = prompt or _("ui.welcome")
    for i, (_key, label) in enumerate(options, 1):
        print("  " + paint("  %d) " % i, "bold+cyan") + label)
    while True:
        raw = ask(prompt, "0")
        if raw is None:            # stdin ferme : on sort, on ne boucle pas
            return None
        if raw in ("0", "q", "Q"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        warn(_("ui.bad_choice", v=raw))
