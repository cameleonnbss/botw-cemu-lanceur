"""Configuration et chemins.

Deux choses a retenir ici.

1. AUCUN chemin en dur. Le nom du compte Windows contient un accent et le
   dossier utilisateur change selon la machine : tout passe par
   %APPDATA%, %LOCALAPPDATA%, %USERPROFILE% et le dossier du script. C'est ce
   qui rend l'outil copiable sur un autre poste.

2. La configuration de l'outil est un fichier JSON dans %APPDATA%. Il n'est
   pas cree tant qu'on n'a rien a y ecrire : un fichier vide derange moins
   qu'un fichier rempli de valeurs par defaut qu'on ne maitrise pas.
"""
import json
import os

APP_DIR_NAME = "botwcli"
CONFIG_NAME = "config.json"

DEFAULTS = {
    "lang": "en",
    "cemu_exe": "",
    "ukmm_exe": "",
    "library_dir": "",          # ou sont ranges les mods telecharges
    "game_profile": "boost",    # profil joue par defaut
    "deploy_method": "hardlink",
    "confirm_destructive": True,
}


def appdata_dir():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME)


def config_path():
    return os.path.join(appdata_dir(), CONFIG_NAME)


def load():
    cfg = dict(DEFAULTS)
    try:
        with open(config_path(), encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg.update(data)
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg):
    d = appdata_dir()
    try:
        os.makedirs(d, exist_ok=True)
        tmp = config_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False, sort_keys=True)
            f.write("\n")
        os.replace(tmp, config_path())
        return True
    except OSError:
        return False


def set_value(key, value):
    if key not in DEFAULTS:
        raise KeyError("unknown setting: %s" % key)
    cfg = load()
    cfg[key] = value
    return save(cfg)


# --- chemins du jeu ----------------------------------------------------------

def ukmm_dir():
    return os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")),
                        "Tools", "UKMM")


def ukmm_exe(cfg=None):
    cfg = cfg or load()
    if cfg.get("ukmm_exe") and os.path.isfile(cfg["ukmm_exe"]):
        return cfg["ukmm_exe"]
    return os.path.join(ukmm_dir(), "ukmm.exe")


def ukmm_settings():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                        "ukmm", "settings.yml")


def ukmm_wiiu():
    return os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                        "ukmm", "wiiu")


def profiles_dir():
    return os.path.join(ukmm_wiiu(), "profiles")


def mods_store():
    return os.path.join(ukmm_wiiu(), "mods")


def cemu_exe(cfg=None):
    """Cherche Cemu.exe dans les emplacements habituels."""
    cfg = cfg or load()
    if cfg.get("cemu_exe") and os.path.isfile(cfg["cemu_exe"]):
        return cfg["cemu_exe"]
    home = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    roots = [
        os.path.join(home, "Downloads"),
        os.path.join(home, "AppData", "Local", "Programs"),
        os.path.join(home, "Desktop"),
        os.environ.get("LOCALAPPDATA", ""),
        "C:\\Program Files",
        "C:\\Program Files (x86)",
    ]
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for base, dirs, files in os.walk(root):
                # On ne descend pas indefiniment : Cemu est au plus 3 niveaux
                # sous Downloads, et un balayage complet de Program Files est
                # long et inutile.
                if base[len(root):].count(os.sep) > 3:
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs if not d.lower().startswith(".")]
                for f in files:
                    if f.lower() == "cemu.exe":
                        return os.path.join(base, f)
        except OSError:
            continue
    return ""


def cemu_appdata():
    return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Cemu")


def cemu_settings():
    return os.path.join(cemu_appdata(), "settings.xml")


def graphic_pack():
    return os.path.join(cemu_appdata(), "graphicPacks", "BreathOfTheWild_UKMM")


def save_root():
    return os.path.join(cemu_appdata(), "mlc01", "usr", "save", "00050000",
                        "101c9500")


def main_save_file():
    return os.path.join(save_root(), "user", "80000001", "0", "game_data.sav")


def shots_dir():
    """Dossier des parties, a cote du lanceur."""
    return os.path.join(os.path.expanduser("~"), "Desktop", "BOTW", "Sauvegardes")


def library_dir(cfg=None):
    cfg = cfg or load()
    if cfg.get("library_dir"):
        return cfg["library_dir"]
    # A cote du lanceur, pour que tout le dossier reste transportable.
    return os.path.join(os.path.expanduser("~"), "Desktop", "BOTW", "Mods")


def tool_root():
    """Racine du projet (utile pour trouver README.fr.md, docs, tests)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_bytes(drive=None):
    drive = drive or (os.environ.get("SystemDrive", "C:") + "\\")
    try:
        import shutil
        return shutil.disk_usage(drive).free
    except Exception:                                          # noqa: BLE001
        return 0