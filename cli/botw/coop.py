"""Jouer a deux.

Le jeu ne change pas : BOTW trouve une partie locale avec deux manettes, ou
sur le reseau local. Ce que la console change, c'est un seul tag dans
settings.xml :

    <PadChannels>1</PadChannels>

Cemu n'ouvre qu'une manette par defaut. A 2, il ouvre deux emplacements et
BOTW detecte le second joueur. Le tag se trouve sous <content>, dans la
partie "Input" de la configuration.

Piege connu : Cemu ecrit settings.xml en sortant. Modifier le fichier pendant
que le jeu tourne est donc inutile - le retour a l'ecran d'accueil ecrase la
valeur. D'ou le garde-fou sur les processus dans deploy.guard_quiet().

Pour le reseau, il faut un reseau virtuel entre les deux PC. Radmin VPN est
celui qui marche le mieux ici : il cree un adaptateur 26.x.x.x, ne demande
aucun transfert de port, et les deux machines se voient comme si elles
etaient sur le meme cable.
"""
import os
import re
import subprocess

from . import config, i18n

_ = i18n._

PAD_TAG = "PadChannels"


# --- settings.xml -----------------------------------------------------------

def read_pad_channels():
    """Nombre de manettes lu dans settings.xml, ou None si le tag n'existe pas."""
    try:
        with open(config.cemu_settings(), encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError:
        return None
    m = re.search(r"<%s>\s*(\d+)\s*</%s>" % (PAD_TAG, PAD_TAG), raw)
    return int(m.group(1)) if m else None


def write_pad_channels(n):
    """Ecrit PadChannels dans settings.xml. Retourne (ok, message).

    Si le tag est absent (version de Cemu differente), on ne l'invente pas
    au hasard : on le signale, parce qu'un mauvais endroit dans un fichier de
    configuration fait planter Cemu au demarrage.
    """
    path = config.cemu_settings()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = f.read()
    except OSError:
        return False, _("coop.pad.no_settings", p=path)
    new = raw
    if re.search(r"<%s>\s*\d+\s*</%s>" % (PAD_TAG, PAD_TAG), raw):
        new = re.sub(r"<%s>\s*\d+\s*</%s>" % (PAD_TAG, PAD_TAG),
                     "<%s>%d</%s>" % (PAD_TAG, n, PAD_TAG), raw)
    else:
        return False, _("coop.pad.missing")
    if new == raw:
        return True, _("coop.pad.already", n=n)
    backup = path + ".botw.bak"
    if not os.path.isfile(backup):
        try:
            with open(backup, "w", encoding="utf-8", newline="") as f:
                f.write(raw)
        except OSError:
            pass
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new)
    except OSError as e:
        return False, str(e)
    return True, _("coop.pad.set", n=n)


def running():
    """Cemu est ouvert ?"""
    from . import deploy
    return bool(deploy.processes_named("Cemu"))


# --- Radmin -----------------------------------------------------------------

def radmin_state():
    """(nom de l'adaptateur, adresse IP) ou ('', '')."""
    try:
        r = subprocess.run(["ipconfig"], capture_output=True, text=True,
                           errors="replace", timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return "", ""
    lines = (r.stdout or "").splitlines()
    for i, line in enumerate(lines):
        if "radmin" not in line.lower():
            continue
        nom = line.strip().rstrip(":").strip()
        for j in range(i, min(i + 8, len(lines))):
            m = re.search(r"IPv4[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)",
                          lines[j])
            if m:
                return nom, m.group(1)
        return nom, ""
    return "", ""


def radmin_installed():
    """Radmin VPN est-il installe ? (adaptateur ou programme)"""
    _nom, ip = radmin_state()
    if ip:
        return True
    roots = [os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
             os.environ.get("ProgramFiles", r"C:\Program Files")]
    for root in roots:
        if root and os.path.isdir(os.path.join(root, "Radmin VPN")):
            return True
    return False


# --- commandes ---------------------------------------------------------------

def status():
    i18n.title(_("coop.title"))
    n = read_pad_channels()
    if n is None:
        i18n.ko(_("coop.pad.missing"))
        i18n.info(_("coop.pad.hint", p=config.cemu_settings()))
    elif n >= 2:
        i18n.ok(_("coop.active"))
        i18n.info(_("coop.status", n=n))
    else:
        i18n.info(_("coop.inactive"))
        i18n.info(_("coop.status", n=n))
        i18n.info(_("coop.enable_hint"))
    if running():
        i18n.warn(_("coop.cemu_open"))
    nom, ip = radmin_state()
    if ip:
        i18n.ok(_("coop.radmin.found", name=nom, ip=ip))
    elif radmin_installed():
        i18n.warn(_("coop.radmin.not_connected"))
    else:
        i18n.info(_("coop.radmin.missing"))
    return n


def enable():
    if running():
        i18n.ko(_("coop.cemu_open"))
        return False
    ok_, msg = write_pad_channels(2)
    (i18n.ok if ok_ else i18n.ko)(msg)
    return ok_


def disable():
    if running():
        i18n.ko(_("coop.cemu_open"))
        return False
    ok_, msg = write_pad_channels(1)
    (i18n.ok if ok_ else i18n.ko)(msg)
    return ok_


def radmin_guide():
    """Les etapes, dans la langue choisie. C'est la partie qu'on ne devine pas."""
    i18n.title(_("coop.radmin.title"))
    nom, ip = radmin_state()
    if ip:
        i18n.ok(_("coop.radmin.found", name=nom, ip=ip))
    elif radmin_installed():
        i18n.warn(_("coop.radmin.not_connected"))
    else:
        i18n.info(_("coop.radmin.missing"))
    for i, key in enumerate(["coop.radmin.step1", "coop.radmin.step2",
                             "coop.radmin.step3", "coop.radmin.step4",
                             "coop.radmin.step5"], 1):
        i18n.step(i, 5, _(key))
    i18n.info(_("coop.radmin.firewall"))
    return nom, ip
