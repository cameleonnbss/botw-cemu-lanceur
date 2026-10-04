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
    """`botw lang` sans argument montre, `botw lang <code>` fige un choix,
    `botw lang auto` rend la main au poste. Le cas 'auto' existe parce que la
    langue suit normalement le systeme : il faut pouvoir y revenir apres avoir
    choisi une langue a la main, sans editer le fichier de configuration."""
    i18n.title(_("lang.title"))
    code = (args.code or "").lower()
    if code == "auto":
        cfg["lang"] = ""
        config.save(cfg)
        if i18n.appliquer(cfg):
            i18n.ok(_("lang.auto"))
            i18n.ok(_("lang.detected", lang=i18n.lang()))
        else:
            i18n.ok(_("lang.auto"))
            i18n.warn(_("lang.no_auto"))
    elif not code:
        # On affiche la langue *detectee*, pas seulement la langue active :
        # avec '--lang fr lang', les deux peuvent differer, et c'est la
        # detection qui est interesting a connaitre.
        trouvee = i18n.langue_systeme()
        if cfg.get("lang"):
            i18n.ok(_("lang.current", lang=i18n.lang()))
            i18n.info(_("lang.chosen", lang=cfg["lang"]))
        elif trouvee:
            i18n.ok(_("lang.detected", lang=trouvee))
        else:
            i18n.warn(_("lang.no_auto"))
        i18n.info(_("lang.available", list=", ".join(i18n.available())))
    elif code not in i18n.available():
        i18n.ko(_("lang.unknown", lang=code, list=", ".join(i18n.available())))
        return 1
    else:
        i18n.set_lang(code)
        cfg["lang"] = code
        config.save(cfg)
        i18n.ok(_("lang.chosen", lang=code))
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


def cmd_jeu(args, cfg):
    """`botw jeu [profil]` : passe a un autre jeu de mods sans rien perdre."""
    from . import newgame
    profil = args.profile or cfg.get("game_profile") or ""
    if not profil:
        newgame.status()
        return 0
    if not newgame.basculer(profil, cfg, force=getattr(args, "yes", False)):
        return 1
    cfg["game_profile"] = profil
    config.save(cfg)
    if args.launch:
        from . import ui
        # `basculer` vient de deployer ce profil : le repasser dans
        # `launch` ferait un deuxieme remerge complet pour rien.
        return ui.launch(profil, cfg, deja_deploye=True)
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


def cmd_installmods(args, cfg):
    """`botw installmods <fichier|lien> [-p profil]`.

    Le raccourcis qui manquait : la bibliotheque locale ne connait que les
    mods deja vus, et GameBanana ne repond plus a la recherche. On accepte
    donc directement ce que le joueur a sous la main - un .zip dans ses
    telechargements, ou le lien qu'il a trouve - et on fait le reste.
    """
    from . import mods, profiles
    if getattr(args, "list", False):
        i18n.title(_("installmods.title"))
        mods.listing(cfg)
        return 0
    source = args.source
    if not source:
        i18n.ko(_("installmods.how"))
        return 1
    profil = args.profile or profiles.active() or cfg.get("game_profile")
    if not profil:
        i18n.ko(_("mods.unknown", n=source))
        return 1
    if profil not in profiles.existing():
        i18n.ko(_("guard.profile", p=profil, list=", ".join(profiles.existing())))
        return 1
    i18n.title(_("installmods.title"))
    i18n.info(_("installmods.how"))
    try:
        mods.installer_fichier(profil, source, cfg)
    except (ValueError, OSError) as e:
        i18n.ko(str(e))
        return 1
    except KeyboardInterrupt:
        i18n.warn(_("err.interrupted"))
        return 1
    return 0


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


def cmd_graphics(args, cfg):
    """Les packs graphiques de Cemu : resolution et correction des couleurs.

    C'est la commande inverse de ce que fait `botw fix` sur ces packs. Elle
    ne peut pas remettre les packs qui bloquent le chargement : ils sont
    retires dans la meme operation.
    """
    from . import cemu
    i18n.title(_("graphics.title"))

    # La restauration passe en premier : relire une sauvegarde n'a pas besoin
    # que les packs officiels soient installes, et c'est justement le moment
    # ou on ne veut pas d'un garde-fou qui empeche de réparer.
    if args.restore:
        ok, msg, noms = cemu.restaurer_depuis(args.restore, cfg=cfg)
        (i18n.ok if ok else i18n.ko)(msg)
        if not ok:
            return 1
        i18n.ok(_("graphics.restored", n=len(noms)))
        dangereux, _o, _a = cemu.classer()
        for _chemin, nom in dangereux:
            i18n.ko(_("cemu.blocker", n=nom, why=cemu.raison(_chemin)))
        return 1 if dangereux else 0

    packs = cemu.disponibles()
    if not packs:
        i18n.ko(_("graphics.none"))
        return 4
    for _relatif, nom, cle in packs:
        i18n.info("%-13s %s" % (nom, _(cle) if cle else ""))

    if args.off:
        ordre = [c for c in cemu.active_packs()
                 if nom_packs(c) not in [n for _r, n, _c in packs]]
        ok, msg = cemu.ecrire_packs(ordre, cfg)
        (i18n.ok if ok else i18n.ko)(msg)
        return 0 if ok else 1

    ok, msg, ajoutes = cemu.activer_graphismes(cosmetiques=args.mods, cfg=cfg)
    if not ok:
        i18n.ko(msg)
        return 1
    if ajoutes:
        i18n.ok(_("graphics.added", n=len(ajoutes),
                  list=", ".join(ajoutes)))
    else:
        i18n.ok(_("graphics.already"))
    # On relit : ce que Cemu vera au prochain demarrage, pas ce qu'on croit
    # avoir ecrit.
    dangereux, _opt, _autres = cemu.classer()
    if dangereux:
        for _chemin, nom in dangereux:
            i18n.ko(_("cemu.blocker", n=nom, why=cemu.raison(_chemin)))
        return 1
    i18n.ok(_("graphics.done"))
    return 0


def nom_packs(chemin):
    """Raccourci : le nom lisible d'un chemin de pack."""
    from . import cemu
    return cemu.nom_lisible(chemin)


def cmd_fix(args, cfg):
    """Le correctif du chargement infini."""
    from . import cemu, fix
    if args.action in ("check", None) and args.action != "run":
        return cmd_check(args, cfg)
    i18n.title(_("fix.title"))
    avant = fix.rapport(cfg)
    for g, t in avant:
        (i18n.ko if g >= 2 else i18n.warn if g == 1 else i18n.ok)(t)
    if args.action == "check":
        return 0 if not fix.bloque() else 1
    i18n.info(_("fix.ask_mode"))
    mode = "safe"
    if args.keep_cosmetics:
        mode = "keep"
    elif args.minimal:
        mode = "minimal"
    i18n.info(_("cemu.mode", m=_("cemu.mode." + ("keep" if mode == "keep"
                                                 else "nocheat" if mode == "minimal"
                                                 else "safe"))))
    code = fix.corriger(cfg, keep_options=(mode == "keep"),
                        keep_cheats=(mode != "minimal"), deploy_apres=not args.no_deploy)
    if code == 0:
        i18n.ok(_("fix.done"))
    reste = fix.rapport(cfg)
    if not fix.bloque():
        return 0
    # Un code 2 signifie « pas reparable tout seul » (partie d'un autre jeu de
    # mods) : le message l'a deja explique, on sort juste en echec simple.
    return 1


def cmd_check(args, cfg):
    """Dis-dit : qu'est-ce qui peut empecher le jeu de charger ?"""
    from . import fix
    i18n.title(_("fix.title"))
    lignes = fix.rapport(cfg)
    for g, t in lignes:
        (i18n.ko if g >= 2 else i18n.warn if g == 1 else i18n.ok)(t)
    n = len([g for g, _ in lignes if g >= 2])
    if n:
        i18n.ko(_("fix.verdict.ko", n=n))
        return 1
    i18n.ok(_("fix.verdict.ok"))
    return 0


def cmd_build(args, cfg):
    """Le constructeur de profil."""
    from . import builder, config as cfgmod
    i18n.title(_("builder.title"))
    i18n.info(_("builder.intro"))
    choix, posees = builder.poser_questions()
    if not posees and not args.yes:
        # Personne n'a repondu : stdin est ferme. Les valeurs par defaut
        # construiraient alors un profil, le deployeraient, et surtout
        # basculeraient le profil actif - ce qui rendrait illisible la
        # sauvegarde du joueur, qui n'a pas ete faite avec ces mods. C'est le
        # pire resultat possible, et il est invisible : rien n'echoue.
        # On ne fait donc rien tant que --yes n'a pas ete demande.
        i18n.ko(_("builder.no_terminal"))
        i18n.info(_("builder.no_terminal.how"))
        return 1
    liste = builder.assembling(choix)
    if not liste:
        i18n.ko(_("builder.empty"))
        return 1
    nom = args.name or builder.noms(choix)
    if posees:
        nom = i18n.ask(_("builder.name"), nom) or nom
        if not args.yes and not i18n.confirm(_("builder.use", p=nom), True):
            return 0
    # construire() renvoie (nom, code) : sans decomposer le tuple, `code == 0`
    # n'est jamais vrai, le profil n'est donc jamais active et la commande
    # renvoie un tuple a sys.exit() - qui le refuse.
    nom_final, code = builder.construire(nom, choix, cfg,
                                         deploy_apres=not args.no_deploy)
    if code == 0:
        cfg["game_profile"] = nom_final or nom
        cfgmod.save(cfg)
        i18n.ok(_("deploy.activate", p=nom_final or nom))
    return code


def cmd_newgame(args, cfg):
    from . import newgame
    # `-y` doit etre declare sur le sous-analyseur, sinon argparse le refuse
    # avant que newgame.execute ne le voie. On le retransmet tel quel.
    rest = list(args.rest or [])
    if getattr(args, "yes", False):
        rest.append("-y")
    return 0 if newgame.execute(rest) else 1


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
    from . import art, readme
    lang = args.lang_code or i18n.lang()
    if args.open:
        return 0 if readme.open_in_viewer(lang) else 1
    art.linkle("cyan")
    print("")
    return 0 if readme.show(lang) else 1


def cmd_art(args, cfg):
    """Les deux dessins, pour le plaisir."""
    from . import art
    art.banniere()
    return 0


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

    j = s.add_parser("jeu", help=_("cli.help.jeu"),
                     description=_("cli.help.jeulong"))
    j.add_argument("profile", nargs="?", default=None)
    j.add_argument("--lancer", dest="launch", action="store_true",
                   help=_("cli.help.jeulancer"))
    j.add_argument("-y", "--yes", action="store_true", help=_("cli.help.yes"))

    pr = s.add_parser("profile", help=_("cli.help.profile"))
    pr.add_argument("action", nargs="?",
                    choices=["list", "show", "use", "create", "delete", "verify"],
                    default="list")
    pr.add_argument("name", nargs="?", default=None)
    pr.add_argument("mods", nargs="*", default=None)
    pr.add_argument("-v", "--verbose", action="store_true")
    pr.add_argument("-y", "--yes", action="store_true",
                    help=_("cli.help.yes"))

    im = s.add_parser("installmods",
                       help=_("cli.help.installmods"))
    im.add_argument("source", nargs="?", default=None,
                    help=_("cli.help.installmods.source"))
    im.add_argument("-p", "--profile", default=None,
                    help=_("cli.help.installmods.profile"))
    im.add_argument("-l", "--list", action="store_true",
                    help=_("cli.help.installmods.list"))

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
    ng.add_argument("-y", "--yes", action="store_true")

    bd = s.add_parser("build", help=_("cli.help.build"))
    bd.add_argument("name", nargs="?", default=None)
    bd.add_argument("-y", "--yes", action="store_true")
    bd.add_argument("--no-deploy", action="store_true")

    ck = s.add_parser("check", help=_("cli.help.check"),
                      description=_("cli.help.checklong"))
    ck.set_defaults(_handler=cmd_check)

    gr = s.add_parser("graphics", help=_("cli.help.graphics"),
                      description=_("cli.help.graphicslong"))
    gr.add_argument("--mods", action="store_true",
                    help=_("cli.help.graphicsmods"))
    gr.add_argument("--off", action="store_true",
                    help=_("cli.help.graphicsoff"))
    gr.add_argument("--restore", metavar="FILE", default=None,
                    help=_("cli.help.graphicsrestore"))

    fx = s.add_parser("fix", help=_("cli.help.fix"))
    fx.add_argument("action", nargs="?", default="run",
                    choices=["check", "run"])
    fx.add_argument("-y", "--yes", action="store_true")
    fx.add_argument("--keep-cosmetics", action="store_true",
                    help=_("cli.help.cosmetics"))
    fx.add_argument("--minimal", action="store_true")
    fx.add_argument("--no-deploy", action="store_true")

    cf = s.add_parser("config", help=_("cli.help.config"))
    cf.add_argument("action", nargs="?", default=None,
                    choices=["set", "reset"])
    cf.add_argument("name", nargs="?", default=None)
    cf.add_argument("value", nargs="?", default=None)

    rd = s.add_parser("readme", help=_("cli.help.readme"))
    rd.add_argument("lang_code", nargs="?", default=None)
    rd.add_argument("-o", "--open", action="store_true")

    s.add_parser("ui", help=_("cli.help.ui"))
    s.add_parser("art", help=_("cli.help.art"))

    mx = s.add_parser("matrix", help=_("cli.help.matrix"))
    mx.add_argument("suite", nargs="*", default=None)

    return p


HANDLERS = {
    "lang": cmd_lang,
    "doctor": cmd_doctor,
    "deploy": cmd_deploy,
    "jeu": cmd_jeu,
    "profile": cmd_profile,
    "mods": cmd_mods,
    "installmods": cmd_installmods,
    "tools": cmd_tools,
    "catalog": cmd_catalog,
    "coop": cmd_coop,
    "newgame": cmd_newgame,
    "fix": cmd_fix,
    "graphics": cmd_graphics,
    "check": cmd_check,
    "build": cmd_build,
    "config": cmd_config,
    "readme": cmd_readme,
    "ui": cmd_ui,
    "art": cmd_art,
    "matrix": cmd_matrix,
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    i18n.use_utf8()
    cfg = config.load()
    # La langue est choisie avant meme de construire l'aide : 'botw --help'
    # doit etre dans la bonne langue. i18n.appliquer() fait les deux dans
    # l'ordre : choix explicite enregistre, sinon langue du poste.
    i18n.appliquer(cfg)
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
    handler = getattr(args, "_handler", None) or HANDLERS.get(args.command)
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
