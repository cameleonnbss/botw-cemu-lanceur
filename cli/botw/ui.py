"""Le menu, pour ceux qui ne tapent pas en ligne de commande.

Tout ce que la CLI sait faire est ici, avec un bouton. Le menu separe
volontairement l'ecran principal (on y revient souvent) des sous-ecrans :

    jeu      choisir un profil, le deployer, lancer Cemu
    check    ce qui bloque le chargement
    fix      corriger le chargement infini
    build    construire un profil en repondant a des questions
    mods     liste, installation, telechargement
    profils  creation depuis le catalogue, verification
    tools    UKMM, BCML, Cemu
    coop     deux joueurs

Quatre boutons sont hors de la liste numerotee, parce que ce sont les demandes
les plus frequentes et qu'elles ne doivent pas demander trois commandes :

    [N] nouvelle partie    le jeu est bloque sur l'ecran de chargement ?
    [C] le jeu demarre ?   repond en trois lignes
    [F] fixer le chargement le correctif en une commande
    [R] readme en francais  la doc, tout de suite
"""
import os
import subprocess
import sys

from . import config, i18n

_ = i18n._


def _status_line(cfg):
    from . import profiles
    act = profiles.active()
    if not act:
        return _("ui.no_profile")
    try:
        prof = profiles.load(act)
        return _("ui.status", p=act, n=len(prof.hashes))
    except OSError:
        return _("ui.status", p=act, n=0)


def launch(profile, cfg):
    """Deploie puis lance Cemu. Retourne le code de sortie.

    Avant de lancer, on verifie qu'aucun pack graphique ne peut bloquer le
    chargement. Un joueur qui voit un chargement infini en pense a son
    profil ; or la cause est presque toujours un pack, pas le profil.
    """
    from . import deploy, fix
    try:
        deploy.deploy(profile, cfg, quiet=True)
    except deploy.GuardError as e:
        i18n.ko(str(e))
        return e.code
    if not fix.avant_de_lancer(cfg):
        return 1
    cemu = config.cemu_exe(cfg)
    if not cemu:
        i18n.ko(_("doctor.tools.cemu", p=_("tool.cemu.missing")))
        return 4
    i18n.ok(_("ui.launching", p=cemu))
    try:
        subprocess.Popen([cemu])
    except OSError as e:
        i18n.ko(str(e))
        return 1
    return 0


# --- sous-menus --------------------------------------------------------------

def sub_play(cfg):
    from . import deploy, profiles
    while True:
        i18n.title(_("ui.play.title"))
        act = profiles.active()
        options = []
        for p in profiles.existing():
            mark = i18n.paint("*", "green") if p == act else " "
            options.append((p, "%s %-14s %s" % (mark, p, _describe(p, cfg))))
        options.append(("__open_ukmm", _("ui.play.ukmm")))
        options.append(("__back", _("ui.back")))
        choix = i18n.menu(options, _("ui.play.pick"))
        if choix is None or options[choix][0] == "__back":
            return
        key = options[choix][0]
        if key == "__open_ukmm":
            from . import tools
            tools.open_ukmm()
            continue
        if launch(key, cfg) != 0:
            return
        return


def _describe(p, cfg):
    from . import profiles
    try:
        prof = profiles.load(p)
        return _("ui.play.files", n=prof.files_count())
    except OSError:
        return "?"


def sub_mods(cfg):
    from . import mods, profiles
    while True:
        i18n.title(_("ui.mods.title"))
        options = [("__list", _("ui.mods.list")),
                   ("__install", _("ui.mods.install")),
                   ("__remove", _("ui.mods.remove")),
                   ("__search", _("ui.mods.search")),
                   ("__download", _("ui.mods.download")),
                   ("__back", _("ui.back"))]
        choix = i18n.menu(options, _("ui.mods.pick"))
        if choix is None or options[choix][0] == "__back":
            return
        act = options[choix][0]
        if act == "__list":
            mods.listing(cfg)
        elif act == "__search":
            q = i18n.ask(_("ui.mods.ask_search"), "paraglider")
            if q:
                from . import cli
                cli.cmd_mods(_Fake("search", query=q), cfg)
        elif act == "__download":
            q = i18n.ask(_("ui.mods.ask_id"), "0")
            if q:
                from . import cli
                cli.cmd_mods(_Fake("download", query=q, out=None, install=True,
                                   profile=None), cfg)
        else:
            prof = i18n.ask(_("ui.mods.ask_profile"), profiles.active() or "boost")
            if not prof:
                continue
            q = i18n.ask(_("ui.mods.ask_mod"), "")
            if not q:
                continue
            if act == "__install":
                mods.install(prof, q, cfg)
            else:
                mods.uninstall(prof, q, cfg)


class _Fake(object):
    """Un petit porteur d'arguments pour reutiliser les commandes CLI."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


def sub_profiles(cfg):
    from . import catalog, profiles
    while True:
        i18n.title(_("ui.profiles.title"))
        options = [("__catalog", _("ui.profiles.catalog")),
                   ("__verify", _("ui.profiles.verify")),
                   ("__use", _("ui.profiles.use")),
                   ("__back", _("ui.back"))]
        choix = i18n.menu(options, _("ui.profiles.pick"))
        if choix is None or options[choix][0] == "__back":
            return
        act = options[choix][0]
        if act == "__catalog":
            catalog.listing(cfg)
            key = i18n.ask(_("ui.profiles.ask_key"), "boost")
            if not key:
                continue
            target = i18n.ask(_("ui.profiles.ask_target"), key)
            if target and i18n.confirm(_("catalog.confirm", p=target), False):
                catalog.create(key, target, cfg, False)
        elif act == "__verify":
            nom = i18n.ask(_("ui.profiles.ask_verify"), profiles.active() or "")
            if nom:
                profiles.verify(nom, False)
        elif act == "__use":
            nom = i18n.ask(_("ui.profiles.ask_use"), profiles.active() or "")
            if not nom:
                continue
            try:
                profiles.switch(nom)
                cfg["game_profile"] = nom
                config.save(cfg)
            except ValueError as e:
                i18n.ko(str(e))


def sub_coop(cfg):
    from . import coop
    while True:
        options = [("__status", _("ui.coop.status")),
                   ("__enable", _("ui.coop.enable")),
                   ("__disable", _("ui.coop.disable")),
                   ("__radmin", _("ui.coop.radmin")),
                   ("__back", _("ui.back"))]
        i18n.title(_("ui.coop.title"))
        choix = i18n.menu(options, _("ui.coop.pick"))
        if choix is None or options[choix][0] == "__back":
            return
        act = options[choix][0]
        if act == "__status":
            coop.status()
        elif act == "__enable":
            coop.enable()
        elif act == "__disable":
            coop.disable()
        else:
            coop.radmin_guide()


def sub_tools(cfg):
    from . import tools
    i18n.title(_("ui.tools.title"))
    options = [("__ukmm", _("ui.tools.ukmm")),
               ("__bcml", _("ui.tools.bcml")),
               ("__status", _("ui.tools.status")),
               ("__back", _("ui.back"))]
    choix = i18n.menu(options, _("ui.tools.pick"))
    if choix is None or options[choix][0] == "__back":
        return
    act = options[choix][0]
    if act == "__ukmm":
        tools.install_ukmm(False, cfg)
    elif act == "__bcml":
        tools.install_bcml(None)
    else:
        tools.report(cfg)


# --- ecran principal ---------------------------------------------------------

def main_screen(cfg):
    from . import art, newgame, readme
    i18n.info(_status_line(cfg))
    options = [("play", _("ui.play")),
               ("check", _("ui.check")),
               ("build", _("ui.build")),
               ("mods", _("ui.mods")),
               ("profiles", _("ui.profiles")),
               ("coop", _("ui.coop")),
               ("tools", _("ui.tools")),
               ("doctor", _("ui.doctor")),
               ("readme", _("ui.readme")),
               ("lang", _("ui.lang"))]
    for i, (key, _l) in enumerate(options, 1):
        print("  " + i18n.paint("  %d) " % i, "bold+cyan") + _l)
    print("")
    for touche, libelle in (("C", _("ui.check.short")),
                            ("F", _("ui.fix.short")),
                            ("G", _("ui.graphics.short")),
                            ("N", _("ui.newgame")),
                            ("D", _("ui.readme_fr"))):
        print("  " + i18n.paint("  %s) " % touche, "bold+green") + libelle)
    print("  " + i18n.paint("  Q) ", "bold+dim") + _("ui.quit"))
    while True:
        raw = i18n.ask(_("ui.welcome"), "1")
        if raw is None:            # stdin ferme (Ctrl+D, tache, pipe) : on sort
            return None
        low = raw.lower()
        if low in ("q", "0"):
            return None
        if low == "n":
            return "newgame"
        if low == "d":
            return "readme_fr"
        if low == "c":
            return "check"
        if low == "f":
            return "fix"
        if low == "g":
            return "graphics"
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1][0]
        i18n.warn(_("ui.bad_choice", v=raw))


def run(cfg):
    """Boucle principale. Retourne 0.

    Sans terminal, on fait UN tour puis on sort. Sans cela la boucle
    receives toujours la meme reponse par defaut et tourne a l'infini - le
    symptome est un menu qui n'en finit pas de s'afficher.
    """
    from . import doctor, newgame, readme
    i18n.banner()
    une_seule_fois = not i18n.interactive()
    while True:
        quoi = main_screen(cfg)
        if quoi is None:
            print("")
            i18n.ok(_("ui.done"))
            return 0
        if une_seule_fois:
            i18n.warn(_("ui.not_interactive_stop"))
            return 0
        if quoi == "play":
            sub_play(cfg)
        elif quoi == "check":
            from . import cli
            cli.cmd_check(_Fake(), cfg)
        elif quoi == "fix":
            from . import cli
            cli.cmd_fix(_Fake(action="run", keep_cosmetics=False, minimal=False,
                              no_deploy=False, yes=False), cfg)
        elif quoi == "graphics":
            from . import cli
            cli.cmd_graphics(_Fake(mods=False, off=False, restore=None),
                             cfg)
        elif quoi == "build":
            from . import cli
            cli.cmd_build(_Fake(name=None, yes=False, no_deploy=False), cfg)
        elif quoi == "mods":
            sub_mods(cfg)
        elif quoi == "profiles":
            sub_profiles(cfg)
        elif quoi == "coop":
            sub_coop(cfg)
        elif quoi == "tools":
            sub_tools(cfg)
        elif quoi == "doctor":
            doctor.run(cfg)
        elif quoi == "newgame":
            newgame.execute([])
        elif quoi == "readme":
            readme.show(i18n.lang())
        elif quoi == "readme_fr":
            readme.show("fr")
        elif quoi == "lang":
            code = i18n.ask(_("ui.lang_ask"), i18n.lang())
            if code is None:
                pass
            elif code in i18n.available():
                i18n.set_lang(code)
                cfg["lang"] = code
                config.save(cfg)
                i18n.ok(_("lang.chosen", lang=code))
            else:
                i18n.ko(_("lang.unknown", lang=code,
                          list=", ".join(i18n.available())))
        else:
            i18n.ko(_("err.unknown_command", c=quoi))


if __name__ == "__main__":
    sys.exit(run(config.load()))
