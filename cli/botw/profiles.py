"""Profils UKMM : lecture, creation, suppression, verification.

Le fichier profile.yml de UKMM est un YAML ecrit a la main par UKMM, mais sa
structure est stable et simple :

    mods:
      <hash>:
        meta:
          name: Nom lisible du mod
          ...
        path: ...\\mods\\fichier.zip
    load_order:
      - <hash>
      ...

Le nom lisible du mod est dans meta.name, mais le nom de FICHIER est ce que
UKMM manipule reellement. Les deux sont stockes ici parce que les commandes
acceptent indifféremment l'un ou l'autre.
"""
import io
import os
import re
import shutil
import zipfile

from . import config, deploy, i18n

_ = i18n._

# Priorite de fusion, du PLUS FAIBLE au PLUS FORT. UKMM empile les mods dans
# cet ordre et le DERNIER l'emporte pour les fichiers qu'il ne sait pas
# fusionner (crates/uk-mod/src/unpack.rs, build_file).
PRIORITY = [
    "Second_Wind_(core).zip",
    "Second_Wind_-_Shrine_Overhaul.zip",
    "Second_Wind_-_Eventide_Fix.zip",
    "Ancient_Weaponry_Mark_II.zip",
    "Relics_of_the_Past.zip",
    "Hyrule_Warriors_Weapon_Collection.zip",
    "Islands_Expansion_v1.2.zip",
    "Seamless_Warping.zip",
    "More_Korok_Seeds.zip",
    "Korok_Extra_Rewards.zip",
    "10x_Speed_Paraglider_v2.zip",
    "Farore's_Wind.zip",
    "Champion's_Leathers_and_Lowered_Hylian_Hood.zip",
    "The_Linkle_Mod_3.0.1.zip",
]


class Profile(object):
    def __init__(self, name):
        self.name = name
        self.path = os.path.join(config.profiles_dir(), name)
        self.hashes = {}          # hash -> (nom lisible, nom de fichier)
        self.order = []           # liste de hash, du plus faible au plus fort

    @property
    def profile_file(self):
        return os.path.join(self.path, "profile.yml")

    @property
    def merged(self):
        return os.path.join(self.path, "merged")

    def load(self):
        with io.open(self.profile_file, encoding="utf-8") as f:
            text = f.read()
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            m = re.match(r"^  (\d+):\s*$", lines[i])
            if not m:
                i += 1
                continue
            h = m.group(1)
            label, filename = "", ""
            j = i + 1
            while j < len(lines) and not re.match(r"^  \d+:\s*$", lines[j]) \
                    and not re.match(r"^\S", lines[j]):
                nm = re.match(r"^\s+name: (.+?)\s*$", lines[j])
                pp = re.match(r"^\s+path: .*\\([^\\\r\n]+)\s*$", lines[j])
                if nm:
                    label = nm.group(1)
                if pp:
                    filename = pp.group(1)
                j += 1
            self.hashes[h] = (label, filename)
            i = j
        lo = re.search(r"load_order:\n((?:- \d+\n?)+)", text)
        self.order = re.findall(r"- (\d+)", lo.group(1)) if lo else []
        return self

    def ordered(self):
        """[(nom lisible, fichier)] du plus faible au plus fort."""
        seen = set()
        out = []
        for h in self.order:
            if h in self.hashes and h not in seen:
                out.append(self.hashes[h])
                seen.add(h)
        for h, v in self.hashes.items():
            if h not in seen:
                out.append(v)
        return out

    def files_count(self):
        return deploy.count_files(self.merged)

    def consistent(self):
        return len(self.order) == len(self.hashes)

    def create_empty(self):
        if os.path.isdir(self.path):
            shutil.rmtree(self.path)
        os.makedirs(self.merged)
        with io.open(self.profile_file, "w", encoding="utf-8", newline="\n") as f:
            f.write("mods: {}\nload_order: []\n")
        return self

    def rewrite_order(self):
        """Ecrit le load_order en respectant PRIORITY."""
        rang = {}
        for _h, (_n, filename) in self.hashes.items():
            if filename not in rang:
                rang[filename] = len(rang)
        restants = sorted(f for f in rang if f not in PRIORITY)
        ordered = [f for f in PRIORITY if f in rang] + restants
        by_file = {}
        for h, (_n, filename) in self.hashes.items():
            by_file.setdefault(filename, h)
        corps = "load_order:\n" + "".join("- %s\n" % by_file[f] for f in ordered
                                          if f in by_file)
        with io.open(self.profile_file, encoding="utf-8") as f:
            text = f.read()
        text = re.sub(r"load_order:\n(?:- \d+\n?)+", corps, text)
        with io.open(self.profile_file, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        self.load()
        return self.ordered()


def load(name):
    return Profile(name).load()


def existing():
    return deploy.list_profiles()


def active():
    return deploy.read_active_profile()


def show(name):
    """Affiche un profil de facon lisible."""
    p = load(name)
    i18n.section("%s: %s" % (_("profile.header"), name))
    mods = p.ordered()
    print("  %s: %d    %s: %d" % (_("profile.mods"), len(mods),
                                  _("profile.files"), p.files_count()))
    if not p.consistent():
        i18n.warn("load_order incoherent: %d entries for %d mods"
                  % (len(p.order), len(p.hashes)))
    i18n.section(_("profile.order"))
    for i, (label, filename) in enumerate(mods, 1):
        print("   %2d. %-46s %s" % (i, label[:46], filename))
    i18n.info(_("profile.order.hint"))
    return p


def switch(name):
    if name not in existing():
        raise ValueError(_("guard.profile", p=name, list=", ".join(existing())))
    deploy.write_active_profile(name)
    i18n.ok(_("profile.switch", p=name))


def create(name, mod_files=None, cfg=None):
    """Cree un profil et y installe des mods (noms de fichiers de zip)."""
    p = Profile(name).create_empty()
    if not mod_files:
        i18n.ok(_("profile.created", p=name, n=0))
        return p
    avant = deploy.read_active_profile()
    deploy.write_active_profile(name)
    try:
        for f in mod_files:
            src = os.path.join(config.mods_store(), f)
            if not os.path.isfile(src):
                i18n.warn("%s %s" % (_("mods.unknown", n=f), f))
                continue
            code, _out = deploy.run_ukmm(["install", src, name], cfg)
            if code == 0:
                i18n.ok(_("mods.added", name=f))
            else:
                i18n.warn(_("mods.refused", name=f, c=code))
    finally:
        if avant:
            deploy.write_active_profile(avant)
    p.load()
    p.rewrite_order()
    i18n.ok(_("profile.created", p=name, n=len(p.hashes)))
    return p


def delete(name):
    if name == active():
        raise ValueError("cannot delete the active profile '%s': switch first" % name)
    path = os.path.join(config.profiles_dir(), name)
    if not os.path.isdir(path):
        raise ValueError(_("guard.profile", p=name, list=", ".join(existing())))
    shutil.rmtree(path)
    i18n.ok(_("profile.deleted", p=name))


# --- verification ------------------------------------------------------------

def _manifest_files(zip_path):
    """(chemins de contenu, chemins aoc) declares par un mod UKMM.

    Retourne (None, None) si le zip n'est pas lisible ou n'a pas de
    manifeste : un fichier corrompu dans la bibliotheque ne doit pas
    interrompre la verification des autres mods.
    """
    out_c, out_a = [], []
    try:
        with zipfile.ZipFile(zip_path) as zf:
            if "manifest.yml" not in zf.namelist():
                return None, None
            text = zf.read("manifest.yml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, OSError):
        return None, None
    sect, cur = {}, None
    for ln in text.splitlines():
        if re.match(r"^\s*[a-z_0-9]+:\s*$", ln) and not ln.strip().startswith("-"):
            cur = ln.strip().split(":")[0]
            sect.setdefault(cur, [])
            continue
        m = re.match(r"^\s*-\s+(.+?)\s*$", ln)
        if m and cur:
            sect[cur].append(m.group(1))
    out_c = ["content/" + x for x in sect.get("content", [])]
    out_a = ["aoc/0010/" + x for x in sect.get("aoc", [])]
    return out_c, out_a


def _tree(root):
    out = set()
    if not os.path.isdir(root):
        return out
    for base, _d, files in os.walk(root):
        for f in files:
            out.add(os.path.relpath(os.path.join(base, f), root).replace("\\", "/"))
    return out


def verify(name, verbose=False):
    """Verifie qu'un profil est entierement fusionne ET deploye.

    Pour chaque mod, on relit son manifest.yml (la liste des fichiers que le
    mod touche) et on verifie que chacun se retrouve tel quel dans merged/ puis
    dans le pack graphique deploye.

    Piege important : le pack graphique ne contient que le profil ACTIF. Verifier
    un autre profil donne donc des "fichiers manquants" qui n'ont rien de
    reproche au profil - ils sont simplement dans un autre paquet. On le dit
    explicitement plutot que de compter des problemes qui n'en sont pas.

    Retourne (ok, nombre_de_problemes).
    """
    p = load(name)
    merged = _tree(p.merged)
    deployed = _tree(config.graphic_pack())
    actif = active()
    est_deploye = (actif == name)
    if not est_deploye:
        i18n.warn(_("profile.verify.not_deployed", p=name, active=actif or "?"))
    problems = 0
    verifies = 0
    for h in p.order or list(p.hashes):
        label, filename = p.hashes[h]
        zip_path = os.path.join(config.mods_store(), filename)
        if not os.path.isfile(zip_path):
            i18n.ko("%s: %s" % (label, _("profile.verify.no_zip", f=filename)))
            problems += 1
            continue
        content, aoc = _manifest_files(zip_path)
        if content is None:
            i18n.ko("%s: %s" % (label, _("profile.verify.no_manifest")))
            problems += 1
            continue
        want = [x for x in content
                if not re.match(r"^content/Pack/Bootup_[A-Z]{2}[a-z]{2}\.pack$", x)]
        want += aoc
        miss_m = [x for x in want if x not in merged]
        miss_d = [x for x in want if x not in deployed]
        pct = 100.0 * (len(want) - len(miss_m)) / max(1, len(want))
        verifies += len(want)
        if not est_deploye:
            # On ne compte pas le deploiement : c'est un autre profil qui est
            # deploye, dire "manquant" serait faux.
            good = pct >= 99.0
        else:
            good = pct >= 99.0 and not miss_d
        if good:
            if verbose or not est_deploye:
                i18n.ok("%-44s %5d/%5d merge (%5.1f%%)"
                        % (label[:44], len(want) - len(miss_m), len(want), pct))
        else:
            problems += 1
            if est_deploye:
                i18n.ko("%-44s %5d/%5d merge (%5.1f%%), %5d/%5d deploye"
                        % (label[:44], len(want) - len(miss_m), len(want), pct,
                           len(want) - len(miss_d), len(want)))
            else:
                i18n.ko("%-44s %5d/%5d merge (%5.1f%%)"
                        % (label[:44], len(want) - len(miss_m), len(want), pct))
            for x in miss_m[:3]:
                i18n.info("missing: %s" % x)
    if problems:
        i18n.ko(_("profile.verify.ko", p=name, n=problems))
    elif est_deploye:
        i18n.ok(_("profile.verify.ok", p=name, m=len(p.order or p.hashes),
                  n=verifies))
    else:
        i18n.ok(_("profile.verify.merged_ok", p=name, n=verifies))
        i18n.info(_("profile.verify.deploy_hint", p=name))
    return problems == 0, problems