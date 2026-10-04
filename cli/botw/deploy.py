"""Deploiement d'un profil UKMM vers Cemu.

C'est le coeur du tool : la meme chaine que celle qui a ete verifiee 123 fois
par le banc d'essai, en Python cette fois.

    profil actif -> remerge -> deploy -> liens durs -> pack FR -> rules.txt

Trois pieges documentes ici, parce qu'ils font perdre des heures :

1. %APPDATA%\\ukmm\\settings.yml contient deploy_config.auto: true. Donc
   CHAQUE remerge deploie automatiquement le profil ACTIF. Re-fusionner un
   autre profil ecraserait le pack du joueur sans qu'il l'ait demande.
   D'ou l'etape 1 : on positionne le profil actif AVANT de merger.

2. UKMM n'ajoute que les fichiers du nouveau profil dans le dossier de
   deploiement ; ceux de l'ancien restent et les deux se melangent. D'ou
   l'etape 3 : on vide le dossier. Ce sont des liens durs, les fichiers
   sources du stockage UKMM ne sont pas affectes.

3. ukmm.exe est compile en sous-systeme GUI. Sous PowerShell, "& $ukmm" ne
   l'attend pas et laisse le code de sortie vide - donc un faux echec. En
   Python, subprocess.run attend le vrai processus et rend le vrai code.
"""
import os
import re
import shutil
import subprocess
import sys

from . import config, i18n

_ = i18n._

RULES_BODY = "\r\n".join([
    "[Definition]",
    "titleIds = 00050000101C9300,00050000101C9400,00050000101C9500",
    "name = UKMM",
    "path = The Legend of Zelda: Breath of the Wild/Mods/UKMM",
    "description = Provides U-King Mod Manager integration. Disable to turn off "
    "all UKMM mods. Do not use alongside BCML or file replacement graphic packs.",
    "version = 7",
    "default = true",
    "fsPriority = 9999",
    "",
])


class GuardError(Exception):
    """Un garde-fou a declenche : l'utilisateur doit intervenir."""

    def __init__(self, message, code):
        Exception.__init__(self, message)
        self.code = code


# --- processus ---------------------------------------------------------------

def processes_named(name):
    """PID des processus appeles 'name' (ex: 'Cemu').

    On passe par tasklist plutot que par psutil : pas de dependance, et
    tasklist est present sur toute installation Windows.
    """
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq %s.exe" % name],
                           capture_output=True, text=True, errors="replace")
    except OSError:
        return []
    out = []
    for line in (r.stdout or "").splitlines():
        m = re.search(r"^%s\.exe\s+(\d+)" % re.escape(name), line, re.I)
        if m:
            out.append(int(m.group(1)))
    return out


def guard_quiet():
    """Refuse de continuer si Cemu ou UKMM tournent.

    Cemu verrouille les fichiers deployes. UKMM garde le profil en memoire et,
    avec auto: true, redeploie a sa fermeture : il ecraserait par-dessus le
    profil qu'on vient d installer.
    """
    for name, code in (("Cemu", 2), ("ukmm", 3)):
        pids = processes_named(name)
        if pids:
            raise GuardError(_("guard.cemu", name=name, pid=", ".join(map(str, pids)))
                             if name == "Cemu"
                             else _("guard.ukmm", name=name, pid=", ".join(map(str, pids))),
                             code)


# --- settings UKMM -----------------------------------------------------------

def read_active_profile():
    path = config.ukmm_settings()
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read()
    except OSError:
        return ""
    m = re.search(r"(?m)^\s*profile:\s*(\S+)\s*$", raw)
    return m.group(1) if m else ""


def write_active_profile(name):
    """Ecrit le profil actif en UTF-8 SANS BOM : serde_yaml de UKMM refuse le BOM."""
    path = config.ukmm_settings()
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    new = re.sub(r"(?m)^(\s*profile:\s*).*$", lambda m: m.group(1) + name, raw)
    if new == raw:
        return False
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    return True


# --- appel UKMM --------------------------------------------------------------

def run_ukmm(args, cfg=None):
    exe = config.ukmm_exe(cfg)
    if not exe or not os.path.isfile(exe):
        raise GuardError(_("doctor.ukmm.missing", path=exe), 4)
    r = subprocess.run([exe] + list(args),
                       cwd=os.path.dirname(exe),
                       capture_output=True, text=True, errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# --- liens durs --------------------------------------------------------------

def _hardlink_tree(src_root, dst_root):
    if not os.path.isdir(src_root):
        return 0
    n = 0
    for base, _dirs, files in os.walk(src_root):
        for name in files:
            src = os.path.join(base, name)
            rel = os.path.relpath(src, src_root)
            dst = os.path.join(dst_root, rel)
            parent = os.path.dirname(dst)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            if not os.path.exists(dst):
                try:
                    os.link(src, dst)
                    n += 1
                except OSError:
                    # Volumes differents ou droits insuffisants : on retombe sur une
                    # copie, plus couteuse mais fonctionnelle.
                    shutil.copy2(src, dst)
                    n += 1
    return n


def count_files(root):
    if not os.path.isdir(root):
        return 0
    n = 0
    for _b, _d, files in os.walk(root):
        n += len(files)
    return n


# --- deploiement -------------------------------------------------------------

def deploy(profile, cfg=None, quiet=False):
    """Deploie 'profile' vers Cemu. Retourne un dict de resultat.

    Leve GuardError si un garde-fou declenche (code 2, 3 ou 4).
    """
    cfg = cfg or config.load()
    pdir = os.path.join(config.profiles_dir(), profile)
    if not os.path.isdir(pdir):
        raise GuardError(_("guard.profile", p=profile, list=list_profiles()), 1)

    guard_quiet()

    def say(key, **kw):
        if not quiet:
            i18n.info(_(key, **kw))

    say("deploy.start", p=profile)
    write_active_profile(profile)

    gp = config.graphic_pack()

    say("deploy.merge")
    code, out = run_ukmm(["remerge"], cfg)
    if code != 0:
        raise GuardError(_("deploy.failed.merge", c=code) + "\n" + out.strip()[-800:], 5)

    # UKMM n ajoute que les fichiers du nouveau profil : sans nettoyage, ceux
    # de l ancien restent deployes et les deux se melangent. Ce sont des liens
    # durs, le stockage UKMM n est pas affecte.
    if os.path.isdir(gp):
        shutil.rmtree(gp, ignore_errors=True)

    say("deploy.deploy")
    code, out = run_ukmm(["deploy"], cfg)
    if code != 0:
        raise GuardError(_("deploy.failed.deploy", c=code) + "\n" + out.strip()[-800:], 5)

    merged = os.path.join(pdir, "merged")

    # --- deploiement dur, independant de l etat interne de UKMM -----------
    # UKMM ne deploie que les fichiers listes dans wiiu\pending.yml. Ce
    # journal peut devenir incoherent : "deploy" repond alors "No changes
    # pending" et ne copie RIEN, sans lever d erreur. Le seul moyen de le
    # reconstruire dans UKMM (reset_pending) n existe pas en ligne de
    # commande. On pose donc les liens durs nous-memes.
    linked = _hardlink_tree(os.path.join(merged, "content"),
                            os.path.join(gp, "content"))
    linked += _hardlink_tree(os.path.join(merged, "aoc"), os.path.join(gp, "aoc"))
    say("deploy.hardlinks", n=linked)

    # --- pack de textes --------------------------------------------------
    # Les mods qui ajoutent du texte declarent Pack/Bootup_XXxx.pack. Sur un
    # jeu FR, UKMM fusionne bien le pack en Bootup_EUfr.pack, mais son
    # manifeste reprend le nom anglais : le fichier n est donc jamais copie.
    # Resultat : noms d objets et d iles vides en jeu. On le pose a la main.
    src_pack = os.path.join(merged, "content", "Pack")
    for name in sorted(os.listdir(src_pack)) if os.path.isdir(src_pack) else []:
        if not (name.startswith("Bootup_") and name.endswith(".pack")):
            continue
        dest_dir = os.path.join(gp, "content", "Pack")
        dest = os.path.join(dest_dir, name)
        if os.path.exists(dest):
            continue
        os.makedirs(dest_dir, exist_ok=True)
        try:
            os.link(os.path.join(src_pack, name), dest)
        except OSError:
            shutil.copy2(os.path.join(src_pack, name), dest)
        say("deploy.frpack", name=name)

    # --- rules.txt -------------------------------------------------------
    # Cemu ne detecte le pack que grace a rules.txt. Comme on a vide le
    # dossier, UKMM ne le recree pas s il n a rien a redployer.
    rules = os.path.join(gp, "rules.txt")
    if not os.path.isfile(rules):
        os.makedirs(gp, exist_ok=True)
        with open(rules, "w", encoding="utf-8", newline="") as f:
            f.write(RULES_BODY)
        say("deploy.rules")

    n_deployed = count_files(gp) - 1          # -1 : rules.txt
    n_merged = count_files(merged)
    # On note le profil : c'est le seul moyen de savoir, plus tard, si une
    # sauvegarde a ete creee avec ce profil-la. Voir newgame.profil_de_la_partie.
    from . import newgame
    newgame.noter_profil(profile)
    return {"profile": profile, "merged": n_merged, "deployed": n_deployed,
            "hardlinks": linked}


def list_profiles():
    root = config.profiles_dir()
    if not os.path.isdir(root):
        return []
    out = []
    for name in sorted(os.listdir(root)):
        if name.startswith("_") or name == "Default":
            continue
        if os.path.isfile(os.path.join(root, name, "profile.yml")):
            out.append(name)
    return out


def merged_dir(profile):
    return os.path.join(config.profiles_dir(), profile, "merged")


if __name__ == "__main__":          # usage direct : python -m botw.deploy <profil>
    i18n.appliquer(config.load())
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if not name:
        i18n.title(_("app.name"))
        for p in list_profiles():
            print("  " + p)
        sys.exit(0)
    try:
        res = deploy(name)
    except GuardError as e:
        i18n.ko(str(e))
        sys.exit(e.code)
    i18n.ok(_("deploy.done", p=res["profile"], n=res["deployed"] + 1,
              m=res["merged"]))