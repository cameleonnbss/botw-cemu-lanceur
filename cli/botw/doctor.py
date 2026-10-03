"""Le "doctor" : un coup d'oeil complet sur l'etat de l'installation.

Meme controles que le script PowerShell du lanceur, mais en un seul endroit,
appelables depuis la CLI et desdepuis l'interface. Chaque controle renvoie
True ou False, et le total est affiche en clair : c'est le genre de commande
qu'on lance quand "le jeu ne demarre pas".
"""
import os
import re
import shutil
import sys

from . import config, deploy, i18n, mods, profiles

_ = i18n._


class Report(object):
    def __init__(self):
        self.checks = []

    def add(self, good, good_msg, bad_msg=None):
        self.checks.append(bool(good))
        if good:
            i18n.ok(good_msg)
        else:
            i18n.ko(bad_msg if bad_msg else good_msg)
        return good

    @property
    def failures(self):
        return len(self.checks) - sum(1 for c in self.checks if c)

    @property
    def total(self):
        return len(self.checks)

    def verdict(self):
        print("")
        if self.failures == 0:
            i18n.ok_all(self.total)
        else:
            i18n.ko_count(self.failures, self.total - self.failures)
        print("")


def _radmin_state():
    """(nom de l'adaptateur Radmin VPN, adresse IP) ou ('', '')."""
    from . import coop
    return coop.radmin_state()


def run(cfg=None):
    cfg = cfg or config.load()
    rep = Report()
    i18n.title(_("doctor.title"))

    # --- 1. UKMM ------------------------------------------------------------
    i18n.section(_("doctor.section.ukmm"))
    exe = config.ukmm_exe(cfg)
    rep.add(os.path.isfile(exe), _("doctor.ukmm.ok", path=exe))
    settings = config.ukmm_settings()
    rep.add(os.path.isfile(settings), _("doctor.config.ok"),
            _("doctor.config.missing", path=settings))

    act = deploy.read_active_profile()
    if os.path.isfile(settings):
        with open(settings, encoding="utf-8") as f:
            raw = f.read()
        if re.search(r"(?m)^\s*auto:\s*true", raw):
            i18n.info(_("doctor.auto_deploy"))
    if act and act in profiles.existing():
        rep.add(True, _("doctor.profile.ok", p=act))
    else:
        rep.add(False, _("doctor.profile.unknown", p=act or "?"))

    # --- 2. processus ------------------------------------------------------
    i18n.section(_("doctor.section.procs"))
    for name in ("Cemu", "ukmm"):
        pids = deploy.processes_named(name)
        if pids:
            i18n.info(_("doctor.proc.open", name=name, pid=", ".join(map(str, pids))))
        else:
            rep.add(True, _("doctor.proc.closed", name=name))

    # --- 3. fusion ----------------------------------------------------------
    i18n.section(_("doctor.section.merge"))
    merged = deploy.merged_dir(act) if act else ""
    if not merged or not os.path.isdir(merged):
        rep.add(False, _("doctor.merge.missing", path=merged or "?"))
    else:
        n = deploy.count_files(merged)
        rep.add(n > 0, _("doctor.merge.count", n=n), _("doctor.merge.empty"))

    # --- 4. pack deploye ---------------------------------------------------
    i18n.section(_("doctor.section.pack"))
    gp = config.graphic_pack()
    if not os.path.isdir(gp):
        rep.add(False, _("doctor.pack.missing", path=gp))
    else:
        rep.add(True, _("doctor.deploy.ok", n=deploy.count_files(gp) - 1))
        rep.add(os.path.isfile(os.path.join(gp, "rules.txt")),
                _("doctor.rules.ok"), _("doctor.rules.missing"))
        packdir = os.path.join(gp, "content", "Pack")
        packs = []
        if os.path.isdir(packdir):
            packs = sorted(n for n in os.listdir(packdir)
                           if n.startswith("Bootup_") and n.endswith(".pack"))
        if packs:
            for n in packs:
                rep.add(True, _("doctor.frpack.ok", name=n))
        else:
            rep.add(False, _("doctor.frpack.missing"))
        if merged and os.path.isdir(merged):
            a = deploy.count_files(gp) - 1
            b = deploy.count_files(merged)
            if a != b:
                i18n.ko(_("doctor.deploy.mismatch", a=a, b=b))
                rep.checks.append(False)
            else:
                i18n.ok(_("doctor.deploy.same", n=b))

    # --- 5. sauvegardes ----------------------------------------------------
    i18n.section(_("doctor.section.saves"))
    root = config.save_root()
    if os.path.isdir(root):
        n = deploy.count_files(root)
        rep.add(True, _("doctor.saves.count", n=n), _("doctor.saves.none"))
    else:
        i18n.info(_("doctor.saves.none"))
    rep.add(os.path.isfile(os.path.join(config.shots_dir(), "parties.json")),
            _("doctor.saves.index"))

    # --- 6. outils ---------------------------------------------------------
    i18n.section(_("doctor.section.tools"))
    rep.add(True, _("doctor.tools.py", v=sys.version.split()[0]))
    cemu = config.cemu_exe(cfg)
    rep.add(bool(cemu), _("doctor.tools.cemu", p=cemu or "not found"))
    name, ip = _radmin_state()
    rep.add(bool(name), _("doctor.tools.radmin",
                          s=_("coop.radmin.found", name=name, ip=ip)
                          if name else _("coop.radmin.missing")))

    # --- 7. disque ----------------------------------------------------------
    i18n.section(_("doctor.section.disk"))
    drive = (os.environ.get("SystemDrive", "C:") + "\\")
    free = config.free_bytes(drive)
    gb = free / (1024.0 ** 3)
    rep.add(gb >= 2, _("doctor.disk.ok", n="%.1f" % gb, d=drive),
            _("doctor.disk.low", n="%.1f" % gb, d=drive))

    rep.verdict()
    return rep


if __name__ == "__main__":
    cfg = config.load()
    i18n.set_lang(cfg.get("lang", "en"))
    sys.exit(0 if run(cfg).failures == 0 else 1)