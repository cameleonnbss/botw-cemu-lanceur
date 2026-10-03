"""Le point d'entree : un seul programme, des sous-commandes.

`botw <commande>` fait tout. Sans sous-commande, on ouvre le menu : une
personne qui ne veut pas taper en ligne de commande ne doit pas decouvrir
qu'il existe une ligne de commande.

Deux conventions tenues partout :

* `--lang fr` force la langue pour une seule execution, sans toucher a la
  configuration. `botw lang fr` la change definitivement.
* le code de sortie vaut 0 si tout va bien, 1 sinon. C'est ce qui permet
  d'enchainer dans un .bat et de voir rouge quand un controle echoue.
"""
import argparse
import os
import sys

from . import __version__, config, i18n

_ = i18n._


# --- outils ------------------------------------------------------------------

def _need(args, name):
    if not getattr(args, name, None):
        i18n.ko(_("err.need_arg", c=args.command))
        return False
    return True


def _pos_int(value):
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(_("err.bad_int", v=value))
    if n < 1:
        raise argparse.ArgumentTypeError(_("err.bad_int", v=value))
    return n


# --- commandes ---------------------------------------------------------------

def cmd_lang(args, cfg):
    i18n.title(_("lang.title"))
    if not args.code:
        i18n.ok(_("lang.current", lang=i18n.lang()))
        i18n.info(_("lang.available", list=", ".join(i18n.available())))
        return 0
    if args.code not in i18n.available():
        i18n.ko(_("lang.unknown", lang=args.code, list=", ".join(i18n.available())))
        return 1
    i18n.set_lang(args.code)
    cfg["lang"] = args.code
    config.save(cfg)
    i18n.ok(_("lang.chosen", lang=args.code))
    i18n.info(_("lang.current", lang=i18n.lang()))
    return 0


def cmd_doctor(args, cfg):
    from . import doctor
    return 0 if doctor.run(cfg).failures == 0 else 1


def cmd_deploy(args, cfg):
    from . import deploy, profiles
    nom = args.profile or cfg.get("game_profile") or "boost"
    if nom not in profiles.existing():
        i18n.ko(_("guard.profile", p=nom, list=", ".join(profiles.existing())))
        return 1
    try:
        res = deploy.deploy(nom, cfg, quiet=args.quiet)
    except deploy.GuardError as e:
        i18n.ko(str(e))
        return e.code
    i18n.ok(_("deploy.done", p=res["profile"], n=res["deployed"] + 1, m=res["merged"]))
    if args.activate:
        cfg["game_profile"] = nom
        config.save(cfg)
        i18n.info(_("deploy.activate", p=nom))
    return 0


def cmd_profile(args, cfg):
    from . import profiles
    action = args.action
    if action == "list":
        i18n.title(_("profile.list.title"))
        act = profiles.active()
        for p in profiles.existing():
            prof = profiles.load(p)
            mark = i18n.paint("*", "green+bold") if p == act else " "
            print("  %s %-16s %2d %s  %d %s" % (
                mark, p, len(prof.hashes), _("profile.mods"),
                prof.files_count(), _("profile.files")))
        i18n.info(_("profile.list.hint", p=act or "-"))
        return 0
    if action == "show":
        if not _need(args, "name"):
            return 1
        if args.name not in profiles.existing():
            i18n.ko(_("guard.profile", p=args.name, list=", ".join(profiles.existing())))
            return 1
        profiles.show(args.name)
        return 0
    if action == "use":
        if not _need(args, "name"):
            return 1
        try:
            profiles.switch(args.name)
        except ValueError as e:
            i18n.ko(str(e))
            return 1
        cfg["game_profile"] = args.name
        config.save(cfg)
        return 0
    if action == "create":
        if not _need(args, "name"):
            return 1
        try:
            profiles.create(args.name, args.mods or [], cfg)
        except ValueError as e:
            i18n.ko(str(e))
            return 1
        return 0
    if action == "delete":
        if not _need(args, "name"):
            return 1
        if not args.yes and not i18n.confirm(
                _("profile.confirm_delete", p=args.name), False):
            i18n.info(_("profile.delete_cancelled"))
            return 0
        try:
            profiles.delete(args.name)
        except ValueError as e:
            i18n.ko(str(e))
            return 1
        return 0
    if action == "verify":
        noms = [args.name] if args.name else profiles.existing()
        if not noms:
            i18n.ko(_("profile.none", path=config.profiles_dir()))
            return 1
        i18n.title(_("profile.verify.title"))
        ko = 0
        for p in noms:
            try:
                if not profiles.verify(p, args.verbose)[0]:
                    ko += 1
            except OSError as e:
                i18n.ko("%s: %s" % (p, e))
                ko += 1
        return 0 if ko == 0 else 1
    i18n.ko(_("err.unknown_command", c="profile " + str(action)))
    return 1


def cmd_mods(args, cfg):
    from . import mods, profiles
    action = args.action
    if action == "list":
        i18n.title(_("mods.list.title"))
        mods.listing(cfg)
        return 0
    if action == "search":
        q = args.query
        i18n.title(_("mods.search.title"))
        rows = []
        for name, (label, _size, _lib) in sorted(mods.available(cfg).items()):
            if q.lower() in label.lower() or q.lower() in name.lower():
                rows.append((None, label))
        try:
            net = mods.search(q)
        except Exception:                                      # noqa: BLE001
            net = []
        rows += net
        if not rows:
            i18n.ko(_("mods.search.none", q=q))
            return 1
        for rid, label in rows:
            tag = ("id %s" % rid) if rid else _("mods.search.local")
            print("  %-52s %s" % (label[:52], i18n.paint(tag, "dim")))
        i18n.info(_("mods.search.hint"))
        return 0
    if action == "download":
        if not _need(args, "query"):
            return 1
        if not str(args.query).isdigit():
            i18n.ko(_("mods.need_id", v=args.query))
            return 1
        try:
            dest, ok = mods.download(args.query, args.out, cfg)
        except Exception as e:                                 # noqa: BLE001
            i18n.ko(_("mods.download.failed", e=e))
            return 1
        if not ok:
            return 1
        if args.install:
            return _install_mod(dest, args.profile or cfg.get("game_profile"), cfg)
        i18n.info(_("mods.download.next"))
        return 0
    if action == "install":
        if not _need(args, "query"):
            return 1
        return _install_mod(args.query, args.profile or cfg.get("game_profile"), cfg)
    if action == "uninstall":
        if not _need(args, "query"):
            return 1
        prof = args.profile or cfg.get("game_profile")
        try:
            mods.uninstall(prof, args.query, cfg)
        except ValueError as e:
            i18n.ko(str(e))
            return 1
        return 0
    i18n.ko(_("err.unknown_command", c="mods " + str(action)))
    return 1


def _install_mod(query, profile, cfg):
    from . import mods
    if not profile:
        i18n.ko(_("mods.no_profile"))
        return 1
    try:
        changed = mods.install(profile, query, cfg)
    except ValueError as e:
        i18n.ko(str(e))
        return 1
    i18n.info(_("mods.install.next", p=profile))
    return 0 if changed is not None else 1


def cmd_tools(args, cfg):
    from . import tools
    action = args.action
    if action == "list":
        tools.report(cfg)
        return 0
    if action == "install-ukmm":
        return 0 if tools.install_ukmm(args.force, cfg) or \
            os.path.isfile(config.ukmm_exe(cfg)) else 1
    if action == "install-bcml":
        return 0 if tools.install_bcml(args.distro) or \
            tools.bcml_state().get("installed") else 1
    if action == "ukmm":
        return 0 if tools.open_ukmm() else 1
    i18n.ko(_("err.unknown_command", c="tools " + str(action)))
    return 1


def cmd_catalog(args, cfg):
    from . import catalog
    if not args.key:
        catalog.listing(cfg)
        return 0
    entry = catalog.get(args.key)
    if not entry:
        i18n.ko(_("catalog.unknown", k=args.key, list=", ".join(catalog.names())))
        return 1
    if args.show:
        i18n.title(_("catalog.title"))
        i18n.ok(_("catalog.combo"))
        i18n.info(entry[1])
        for m in entry[2]:
            print("    - %s" % m)
        i18n.info(_("catalog.files") + ": %d" % entry[3])
        return 0
    target = args.as_profile or args.key
    if not args.yes and not i18n.confirm(_("catalog.confirm", p=target), False):
        return 0
    try:
        nom = catalog.create(args.key, target, cfg, args.deploy)
    except ValueError as e:
        i18n.ko(str(e))
        return 1
    if nom:
        i18n.ok(_("catalog.done", p=nom))
    return 0 if nom else 1


def cmd_coop(args, cfg):
    from . import coop
    action = args.action
    if action == "status":
        coop.status()
        return 0
    if action == "enable":
        return 0 if coop.enable() else 1
    if action == "disable":
        return 0 if coop.disable() else 1
    if action == "radmin":
        coop.radmin_guide()
        return 0
    i18n.ko(_("err.unknown_command", c="coop " + str(action)))
    return 1


def cmd_newgame(args, cfg):
    from . import newgame
    return 0 if newgame.execute(args.rest) else 1


def cmd_config(args, cfg):
    """Lit et ecrit la configuration de l'outil."""
    if not args.action:
        i18n.title(_("config.title"))
        for cle in sorted(config.DEFAULTS):
            val = cfg.get(cle, "")
            if isinstance(val, str) and len(val) > 58:
                val = "..." + val[-55:]
            print("  %-20s %s" % (cle, val if val != "" else "-"))
        i18n.info(_("config.file", p=config.config_path()))
        return 0
    if args.action == "set":
        if not _need(args, "name"):
            return 1
        if args.name not in config.DEFAULTS:
            i18n.ko(_("err.bad_int", v=args.name))
            i18n.info(_("config.known", list=", ".join(sorted(config.DEFAULTS))))
            return 1
        try:
            config.set_value(args.name, args.value)
        except (KeyError, OSError) as e:
            i18n.ko(str(e))
            return 1
        if args.name == "lang":
            i18n.set_lang(args.value)
        i18n.ok(_("config.set", k=args.name, v=args.value))
        return 0
    if args.action == "reset":
        for cle in args.name or list(config.DEFAULTS):
            cfg.pop(cle, None)
        config.save(cfg)
        i18n.ok(_("config.reset"))
        return 0
    i18n.ko(_("err.unknown_command", c="config " + str(args.action)))
    return 1


def cmd_readme(args, cfg):
    from . import readme
    lang = args.lang_code or i18n.lang()
    if args.open:
        return 0 if readme.open_in_viewer(lang) else 1
    return 0 if readme.show(lang) else 1


def cmd_ui(args, cfg):
    from . import ui
    return ui.run(cfg)


def cmd_matrix(args, cfg):
    """Le banc d'essai, si le script est a cote."""
    racine = config.tool_root()
    script = os.path.join(racine, "Outils", "matrice.py")
    if not os.path.isfile(script):
        script = os.path.join(racine, "matrice.py")
    if not os.path.isfile(script):
        i18n.ko(_("matrix.missing", p=script))
        return 1
    import subprocess
    i18n.info(_("matrix.start", p=script))
    args_ = [sys.executable, script] + (args.suite or [])
    return subprocess.run(args_).returncode


# --- construction du parseur -------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        prog="botw", add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=_("cli.description"),
        epilog=_("cli.epilog"))
    p.add_argument("--lang", dest="lang_opt", metavar="en|fr",
                   help=_("cli.help.langone"))
    p.add_argument("--version", action="version",
                   version="botw %s" % __version__)
    s = p.add_subparsers(dest="command", metavar=_("cli.metavar"))

    lp = s.add_parser("lang", help=_("cli.help.lang"))
    lp.add_argument("code", nargs="?", default=None,
                    help=_("cli.help.langcode"))

    s.add_parser("doctor", help=_("cli.help.doctor"))

    d = s.add_parser("deploy", help=_("cli.help.deploy"))
    d.add_argument("profile", nargs="?", default=None)
    d.add_argument("--activate", action="store_true",
                   help=_("cli.help.activate"))
    d.add_argument("-q", "--quiet", action="store_true")

    pr = s.add_parser("profile", help=_("cli.help.profile"))
    pr.add_argument("action", nargs="?",
                    choices=["list", "show", "use", "create", "delete", "verify"],
                    default="list")
    pr.add_argument("name", nargs="?", default=None)
    pr.add_argument("mods", nargs="*", default=None)
    pr.add_argument("-v", "--verbose", action="store_true")
    pr.add_argument("-y", "--yes", action="store_true",
                    help=_("cli.help.yes"))

    m = s.add_parser("mods", help=_("cli.help.mods"))
    m.add_argument("action", nargs="?",
                   choices=["list", "search", "download", "install", "uninstall"],
                   default="list")
    m.add_argument("query", nargs="?", default=None)
    m.add_argument("-p", "--profile", default=None)
    m.add_argument("-o", "--out", default=None)
    m.add_argument("-i", "--install", action="store_true")

    t = s.add_parser("tools", help=_("cli.help.tools"))
    t.add_argument("action", nargs="?", default="list",
                   choices=["list", "install-ukmm", "install-bcml", "ukmm"])
    t.add_argument("-f", "--force", action="store_true")
    t.add_argument("-d", "--distro", default=None)

    c = s.add_parser("catalog", help=_("cli.help.catalog"))
    c.add_argument("key", nargs="?", default=None)
    c.add_argument("--as", dest="as_profile", default=None)
    c.add_argument("--deploy", action="store_true")
    c.add_argument("-s", "--show", action="store_true")
    c.add_argument("-y", "--yes", action="store_true",
                   help=_("cli.help.yes"))

    co = s.add_parser("coop", help=_("cli.help.coop"))
    co.add_argument("action", nargs="?", default="status",
                    choices=["status", "enable", "disable", "radmin"])

    ng = s.add_parser("newgame", help=_("cli.help.newgame"))
    ng.add_argument("rest", nargs="*", default=None)

    cf = s.add_parser("config", help=_("cli.help.config"))
    cf.add_argument("action", nargs="?", default=None,
                    choices=["set", "reset"])
    cf.add_argument("name", nargs="?", default=None)
    cf.add_argument("value", nargs="?", default=None)

    rd = s.add_parser("readme", help=_("cli.help.readme"))
    rd.add_argument("lang_code", nargs="?", default=None)
    rd.add_argument("-o", "--open", action="store_true")

    s.add_parser("ui", help=_("cli.help.ui"))

    mx = s.add_parser("matrix", help=_("cli.help.matrix"))
    mx.add_argument("suite", nargs="*", default=None)

    return p


HANDLERS = {
    "lang": cmd_lang,
    "doctor": cmd_doctor,
    "deploy": cmd_deploy,
    "profile": cmd_profile,
    "mods": cmd_mods,
    "tools": cmd_tools,
    "catalog": cmd_catalog,
    "coop": cmd_coop,
    "newgame": cmd_newgame,
    "config": cmd_config,
    "readme": cmd_readme,
    "ui": cmd_ui,
    "matrix": cmd_matrix,
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    i18n.use_utf8()
    cfg = config.load()
    # La langue est choisie avant meme de construire l'aide : 'botw --help'
    # doit etre en francais si la configuration est en francais.
    i18n.set_lang(cfg.get("lang", "en"))
    if "--lang" in argv:
        i = argv.index("--lang")
        if i + 1 < len(argv):
            i18n.set_lang(argv[i + 1])
        else:
            i18n.ko(_("cli.need_value", opt="--lang"))
            return 2
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.lang_opt:
        i18n.set_lang(args.lang_opt)
        cfg = dict(cfg, lang=args.lang_opt)
    if not args.command:
        from . import ui
        return ui.run(cfg)
    handler = HANDLERS.get(args.command)
    if handler is None:
        i18n.ko(_("err.unknown_command", c=args.command))
        return 2
    try:
        return int(handler(args, cfg) or 0)
    except KeyboardInterrupt:
        print("")
        i18n.warn(_("err.interrupted"))
        return 130
    except (ValueError, OSError) as e:
        i18n.ko(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main())
