"""Le correctif du chargement infini, et le controle qui va avec.

`botw fix` fait trois choses, dans cet ordre, parce que les trois causes se
renforcent :

1. **Les packs graphiques de Cemu.** Un pack qui repoint la memoire
   (Extended Memory) ou qui remplace des fichiers (HD Map and Icons) a cote
   du pack UKMM suffit a faire boucler le chargement. Voir cemu.py pour la
   cause exacte et la source.

2. **La sauvegarde.** Une sauvegarde n'est lisible qu'avec les mods qui l'ont
   creee. Charger une partie 'boost' sous 'sur' bloque egalement, sans
   message. `doctor` le signale, et `newgame` met la partie de cote.

3. **Le deploiement.** Si le profil actif n'est pas deploye, ou pas entierement
   fusionne, le jeu demarre avec un melange de fichiers. C'est moins grave
   qu'un blocage, mais ca ne se voit pas non plus.

Aucun de ces trois-la n'est devinable a l'ecran : c'est precisement pour ca
que le diagnostic existe.
"""
import os

from . import cemu, config, deploy, i18n, newgame, profiles

_ = i18n._


def deposes(cfg=None):
    """Combien de fichiers sont reellement deployes dans le pack de Cemu.

    `rules.txt` est le fichier que Cemu lit pour detecter le pack : il ne vient
    d'aucun mod, donc il ne compte pas. Si le dossier n'existe pas encore - ou
    s'il est vide - il n'y a rien de deploye et le compte vaut 0. Sans cette
    garde, le "-1" de rules.txt produirait un compte negatif, et l'ecart avec
    le profil fusionne serait signale a tort.
    """
    gp = config.graphic_pack()
    if not os.path.isdir(gp):
        return 0
    return max(deploy.count_files(gp) - 1, 0)


def rapport(cfg=None):
    """Ce qui peut faire boucler le chargement. Retourne une liste de
    (gravite, texte). gravite 2 = bloquant, 1 = a surveiller, 0 = ok."""
    out = []

    # --- 1. packs graphiques --------------------------------------------
    dangereux, optionnels, _autres = cemu.classer()
    if dangereux:
        for chemin, nom in dangereux:
            out.append((2, _("cemu.blocker", n=nom, why=cemu.raison(chemin))))
    else:
        out.append((0, _("cemu.clean")))

    ukmm = [c for c in cemu.active_packs() if "UKMM" in c]
    if ukmm:
        out.append((0, _("cemu.ukmm.ok", p=ukmm[0])))
    else:
        out.append((2, _("cemu.ukmm.missing")))

    # --- 1b. reglages de packs qui dependent d'un pack absent -----------
    # Severite 1, pas 2 : le jeu demarre et tourne. Ce qui manque a l'ecran,
    # c'est ce qui est selectionne (armes, acteurs attaches). Bloquer le
    # lancement ici serait disproportionne ; ne rien dire serait pire.
    incomp = cemu.presets_incompatibles()
    if incomp:
        for _c, categorie, avant, apres in incomp:
            out.append((1, _("cemu.preset.bad", c=categorie,
                             a=avant, b=apres)))
    else:
        out.append((0, _("cemu.preset.ok")))

    # --- 1b. packs actives malgre l'absence de settings.xml --------------
    # Gravite 2 : ces packs ecrassent des fichiers du jeu alors qu'on croyait
    # les avoir retires. "HD Map and Icons" remplace toutes les icones
    # d'inventaire, et rien dans settings.xml ne permet de le voir.
    for _chemin, nom in cemu.packs_par_defaut():
        out.append((2, _("cemu.default.pack", n=nom)))

    # --- 2. sauvegarde et profil -----------------------------------------
    actif = profiles.active()
    if newgame.has_game():
        rows = newgame.read_index()
        out.append((0, _("cemu.save.here",
                         n=deploy.count_files(config.save_root()))))
        profil = newgame.profil_de_la_partie()
        if profil and actif and profil != actif:
            out.append((2, _("cemu.save.mismatch", a=profil, b=actif)))
        elif not profil and actif:
            out.append((1, _("cemu.save.unknown")))
    else:
        out.append((1, _("cemu.save.none")))

    # --- 3. deploiement --------------------------------------------------
    merged = deploy.merged_dir(actif) if actif else ""
    if merged and os.path.isdir(merged):
        n = deploy.count_files(merged)
        dp = deposes(cfg)
        if dp < n:
            # Des fichiers fusionnes manquent : la, ca bloque vraiment.
            out.append((2, _("cemu.deploy.missing_files", a=dp, b=n)))
        elif dp > n:
            # Un SUR-ENSEMBLE n'a jamais bloque Cemu : le jeu lit le pack et y
            # trouve tout ce qu'il attend. Le compter comme bloquant faisait
            # dire « le jeu ne demarrera pas » pour un profil qui demarre, et
            # `botw fix` partait alors dans un redeploiement qui reproduisait
            # le meme ecart.
            out.append((0, _("cemu.deploy.extra_files", a=dp, b=n)))
        else:
            out.append((0, _("cemu.deploy.ok", n=n)))
    else:
        out.append((2, _("cemu.deploy.missing", p=actif or "?")))

    return out


def bloque():
    """Vrai si quelque chose rend le chargement impossible."""
    return any(g >= 2 for g, _t in rapport())


def corriger(cfg=None, keep_options=False, keep_cheats=True, deploy_apres=True):
    """Fait tout ce qui peut etre fait sans toucher a la sauvegarde.

    Un seul cas n'est pas reparable automatiquement : la partie chargee
    n'appartient pas au jeu de mods actif. Aucun pack graphique n'y est pour
    rien - le jeu plante parce qu'il relit la partie a travers des fichiers de
    mods qui ne sont pas la. Refaire un deploiement coute deux minutes pour
    rien, et le dire « corrige » serait faux. On dit donc la verite, avec les
    deux seules commandes qui reglent le probleme.
    """
    cfg = cfg or config.load()
    actif = profiles.active()
    if newgame.has_game():
        provenance = newgame.profil_de_la_partie()
        if provenance and actif and provenance != actif:
            i18n.ko(_("cemu.save.mismatch", a=provenance, b=actif))
            i18n.info(_("fix.save.mismatch.1", b=actif))
            i18n.info(_("fix.save.mismatch.2", a=provenance))
            return 2

    retires, pack_ukmm = cemu.nettoyer(keep_cheats=keep_cheats,
                                      keep_options=keep_options, cfg=cfg)
    if retires:
        i18n.ok(_("cemu.fixed", n=len(retires), list=", ".join(retires)))
        sauvegarde = config.cemu_settings() + ".botw-packs.bak"
        if os.path.isfile(sauvegarde):
            i18n.info(_("cemu.backup", p=sauvegarde))
    else:
        i18n.ok(_("cemu.fixed.none"))

    presets = cemu.corriger_presets()
    if presets:
        i18n.ok(_("cemu.preset.fixed", n=len(presets),
                  list=", ".join("%s -> %s" % (a, p) for _c, a, p in presets)))

    desactives = cemu.desactiver_par_defaut()
    if desactives:
        i18n.ok(_("cemu.default.fixed", n=len(desactives),
                  list=", ".join(desactives)))

    if deploy_apres:
        actif = profiles.active()
        if actif in profiles.existing():
            try:
                deploy.deploy(actif, cfg, quiet=True)
                i18n.ok(_("deploy.done", p=actif,
                          n=deposes(cfg),
                          m=deploy.count_files(deploy.merged_dir(actif))))
            except deploy.GuardError as e:
                i18n.ko(str(e))
                return 1
    return 0


def avant_de_lancer(cfg=None):
    """Appele juste avant de demarrer Cemu.

    Si un pack bloquant est encore actif, on ne lance pas : le joueur
    verrait un chargement infini et en concluderait que le profil est casse.
    """
    dangereux, _o, _a = cemu.classer()
    if dangereux:
        for chemin, nom in dangereux:
            i18n.ko(_("cemu.blocker", n=nom, why=cemu.raison(chemin)))
        if not i18n.confirm(_("cemu.fix_first"), False):
            return False
        if not cemu.nettoyer(cfg=cfg)[0]:
            i18n.ko(_("cemu.open"))
            return False
        i18n.ok(_("cemu.fixed.none"))
    return True