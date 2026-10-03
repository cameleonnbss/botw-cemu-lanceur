"""Tests du paquet botw, sans toucher a la vraie installation.

Tout se joue dans un dossier temporaire : on repoint les variables
d'environnement (APPDATA, LOCALAPPDATA, USERPROFILE) vers une fausse
machine. C'est la seule facon honnete de tester un outil qui manipule des
fichiers Windows sans risquer de casser une vraie sauvegarde.

Chaque test est donc hermetique : ce qu'il ecrit, il le supprime.
"""
import io
import json
import os
import sys

import pytest

ICI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ICI not in sys.path:
    sys.path.insert(0, ICI)

from botw import config, i18n                     # noqa: E402


@pytest.fixture(autouse=True)
def fausse_machine(tmp_path, monkeypatch):
    """Repointe %APPDATA%, %LOCALAPPDATA%, %USERPROFILE% vers tmp_path."""
    appdata = tmp_path / "AppData" / "Roaming"
    local = tmp_path / "AppData" / "Local"
    profil = tmp_path / "Profil"
    bureau = profil / "Desktop" / "BOTW"
    for d in (appdata, local, profil / "Tools" / "UKMM", bureau / "Mods",
              bureau / "Sauvegardes", bureau / "Outils"):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("USERPROFILE", str(profil))
    monkeypatch.setenv("SystemDrive", "C:")
    monkeypatch.delenv("BOTW_HOME", raising=False)
    i18n.set_lang("en")
    yield {
        "appdata": appdata,
        "local": local,
        "profil": profil,
        "bureau": bureau,
        "racine": tmp_path,
    }


def ecrire(path, texte, encoding="utf-8"):
    """Ecrit un fichier en creant les dossiers intermediaires."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding=encoding, newline="\n") as f:
        f.write(texte)
    return path


PROFIL_YML = """mods:
  12345:
    meta:
      name: Ancient Weaponry Mark II
      version: 1.0
    path: C:\\mods\\Ancient_Weaponry_Mark_II.zip
  67890:
    meta:
      name: The Linkle Mod 3.0.1
    path: C:\\mods\\The_Linkle_Mod_3.0.1.zip
  11111:
    meta:
      name: Second Wind (core)
    path: C:\\mods\\Second_Wind_(core).zip
load_order:
- 12345
- 67890
- 11111
"""

SETTINGS_YML = """launcher:
  theme: 0
version: 5
profile: boost
deploy_config:
  auto: true
  deploy_on_close: true
"""


@pytest.fixture
def installation(fausse_machine):
    """Une fausse installation UKMM : 2 profils, des mods, un mod en magasin."""
    profiles = os.path.join(fausse_machine["local"], "ukmm", "wiiu", "profiles")
    mods = os.path.join(fausse_machine["local"], "ukmm", "wiiu", "mods")
    os.makedirs(mods, exist_ok=True)

    ecrire(os.path.join(fausse_machine["appdata"], "ukmm", "settings.yml"),
           SETTINGS_YML)
    ecrire(os.path.join(profiles, "boost", "profile.yml"), PROFIL_YML)
    ecrire(os.path.join(profiles, "boost", "merged", "content", "Pack",
                        "Bootup_EUfr.pack"), "PACK")
    ecrire(os.path.join(profiles, "boost", "merged", "content",
                        "GameData", "gamedata.sarc"), "SARC")

    for nom in ("Ancient_Weaponry_Mark_II.zip", "The_Linkle_Mod_3.0.1.zip",
                "Second_Wind_(core).zip", "Relics_of_the_Past.zip"):
        chemin = os.path.join(mods, nom)
        with io.open(chemin, "wb") as f:
            f.write(b"PK\x03\x04")
        shutil_copie(chemin, os.path.join(fausse_machine["bureau"], "Mods", nom))
    return fausse_machine


def shutil_copie(src, dst):
    import shutil
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


@pytest.fixture
def settings_xml(fausse_machine):
    """Un settings.xml Cemu minimal avec la balise PadChannels."""
    path = config.cemu_settings()
    ecrire(path, '<?xml version="1.0" encoding="UTF-8"?>\n'
                 '<Config>\n  <content>\n    <Input>\n'
                 '      <PadChannels>1</PadChannels>\n'
                 '    </Input>\n  </content>\n</Config>\n')
    return path


@pytest.fixture
def index_parties(fausse_machine):
    """Un index de parties ecartees, comme newgame en ecrit un."""
    d = os.path.join(fausse_machine["bureau"], "Sauvegardes")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "parties.json")
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump([{"id": "x", "nom": "reference"}], f)
    return path


def sans_couleur(capsys):
    """Rend la sortie lisible dans un rapport de test."""
    out = capsys.readouterr().out
    return "\n".join(ligne for ligne in out.splitlines() if "----" not in ligne
                     or "=" not in ligne)
