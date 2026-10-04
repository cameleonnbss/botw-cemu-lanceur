"""Le correctif du chargement infini : classification, ecriture, diagnostic.

Ces tests utilisent un faux settings.xml avec la vraie forme de la section
<GraphicPack> de Cemu, pour ne jamais toucher a la configuration reelle.
"""
import builtins
import io
import json
import os
import time

import pytest

from botw import builder, cemu, config, deploy, fix, newgame
from conftest import PROFIL_YML, SETTINGS_YML, ecrire

# Reproduit la section telle que Cemu 2.6 l'ecrit, y compris les entrees
# imbriquees avec <Preset>.
SETTINGS_ICU = """<?xml version="1.0" encoding="UTF-8"?>
<Config>
  <content>
    <GamePaths>
      <Entry>C:\\roms</Entry>
    </GamePaths>
    <GraphicPack>
        <Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>
        <Entry filename="graphicPacks/HD_Map_and_Icons/rules.txt"/>
        <Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Mods/ExtendedMemory/rules.txt">
            <Preset>
                <category>Enabled</category>
            </Preset>
        </Entry>
        <Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Mods/DrawDistance/rules.txt">
            <Preset>
                <category>Extremes</category>
            </Preset>
        </Entry>
        <Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Cheats/InfiniteStamina/rules.txt"/>
        <Entry filename="graphicPacks/downloadedGraphicPacks/WindWakerHD_Resolution/rules.txt"/>
        <Entry filename="graphicPacks/downloadedGraphicPacks/MarioKart8/rules.txt"/>
    </GraphicPack>
    <Input>
      <PadChannels>1</PadChannels>
    </Input>
  </content>
</Config>
"""


@pytest.fixture
def packs(installation):
    ecrire(config.cemu_settings(), SETTINGS_ICU)
    return True


@pytest.fixture
def packs_deployees(installation):
    """Le meme etat, mais apres un deploiement reussi.

    UKMM est configure avec deploy_config.auto = true : apres une fusion, les
    fichiers du profil sont bien presents dans le dossier du pack de Cemu.
    Sans ce refl ete, le diagnostic signalerait un deploiement incoherent et
    on ne pourrait plus distinguer « le pack bloque » de « le pack est deploye ».
    """
    ecrire(config.cemu_settings(), SETTINGS_ICU)
    gp = config.graphic_pack()
    merged = deploy.merged_dir("boost")
    ecrire(os.path.join(gp, "rules.txt"), "# regles UKMM\n")
    for base, _d, files in os.walk(merged):
        for nom in files:
            src_ = os.path.join(base, nom)
            rel = os.path.relpath(src_, merged)
            ecrire(os.path.join(gp, rel), "x")
    return True


class TestLecturePacks(object):
    def test_lit_la_liste(self, packs):
        assert len(cemu.active_packs()) == 7

    def test_nom_lisible(self, packs):
        assert cemu.nom_lisible(
            "graphicPacks/a/b/Mods/ExtendedMemory/rules.txt") == "ExtendedMemory"

    def test_classe_les_bloquants(self, packs):
        d, _o, _a = cemu.classer()
        assert sorted(n for _c, n in d) == ["ExtendedMemory", "HD_Map_and_Icons"]

    def test_classe_les_optionnels(self, packs):
        _d, o, _a = cemu.classer()
        assert [n for _c, n in o] == ["DrawDistance"]

    def test_ignore_les_autres_jeux(self, packs):
        """Les packs de Mario Kart ou Wind Waker ne sont ni dangereux ni
        optionnels : ils sont inoffensifs pour BOTW."""
        _d, o, a = cemu.classer()
        noms = [n for _c, n in o] + [n for _c, n in a]
        assert "Resolution" not in noms or len([c for c, _ in a]) == 0
        assert not any("MarioKart" in c for c, _ in o)

    def test_pack_botw_reconnu(self, packs):
        assert cemu.est_botw("graphicPacks/BreathOfTheWild_UKMM/rules.txt")
        assert not cemu.est_botw("graphicPacks/whatever/MarioKart8/rules.txt")

    def test_raison_ecrite(self, packs):
        for chemin, _nom in cemu.classer()[0]:
            assert len(cemu.raison(chemin)) > 40


class TestNettoyage(object):
    def test_retire_les_bloquants_et_les_optionnels(self, packs):
        retires, ukmm = cemu.nettoyer()
        assert sorted(retires) == ["DrawDistance", "ExtendedMemory", "HD_Map_and_Icons"]
        assert ukmm == "graphicPacks/BreathOfTheWild_UKMM/rules.txt"

    def test_garde_ukmm_et_les_triches(self, packs):
        cemu.nettoyer()
        restants = cemu.active_packs()
        assert "graphicPacks/BreathOfTheWild_UKMM/rules.txt" in restants
        assert any("InfiniteStamina" in c for c in restants)

    def test_garde_les_packs_des_autres_jeux(self, packs):
        cemu.nettoyer()
        restants = cemu.active_packs()
        assert any("WindWaker" in c for c in restants)
        assert any("MarioKart8" in c for c in restants)

    def test_optionnel_garde_si_demande(self, packs):
        cemu.nettoyer(keep_options=True)
        assert any("DrawDistance" in c for c in cemu.active_packs())

    def test_mode_minimal_enleve_les_triches(self, packs):
        cemu.nettoyer(keep_cheats=False)
        assert not any("InfiniteStamina" in c for c in cemu.active_packs())

    def test_xml_toujours_valide(self, packs):
        cemu.nettoyer()
        import xml.dom.minidom
        xml.dom.minidom.parse(config.cemu_settings())

    def test_padchannels_preserve(self, packs):
        """On ne touche qu'a la liste des packs : le reste du fichier doit
        rester intact, sinon Cemu perd ses reglages."""
        cemu.nettoyer()
        with io.open(config.cemu_settings(), encoding="utf-8") as f:
            t = f.read()
        assert "<PadChannels>1</PadChannels>" in t
        assert "C:\\roms" in t

    def test_sauvegarde_avant_ecriture(self, packs):
        cemu.nettoyer()
        assert os.path.isfile(config.cemu_settings() + ".botw-packs.bak")

    def test_idempotent(self, packs):
        cemu.nettoyer()
        une = cemu.active_packs()
        retires2, _ = cemu.nettoyer()
        assert retires2 == []
        assert cemu.active_packs() == une

    def test_refuse_si_cemu_ouvert(self, packs, monkeypatch):
        monkeypatch.setattr("botw.deploy.processes_named",
                            lambda n: [1] if n == "Cemu" else [])
        ok, msg = cemu.ecrire_packs([])
        assert not ok
        assert "Cemu" in msg

    def test_pas_de_settings(self, fausse_machine):
        assert cemu.active_packs() == []
        assert cemu.nettoyer() == ([], "")


class TestDiagnostic(object):
    def test_detecte_le_blocage(self, packs):
        rapport = fix.rapport()
        bloquants = [t for g, t in rapport if g >= 2]
        assert len(bloquants) >= 2
        assert fix.bloque()

    def test_ras_du_blocage_apres_nettoyage(self, packs_deployees):
        """Le scenario complet : une machine qui joue, avec les packs qui
        bloquent le chargement. Apres nettoyage, plus rien ne doit etre grave."""
        cemu.nettoyer()
        assert not fix.bloque(), fix.rapport()

    def test_compte_deploye_jamais_negatif(self, packs):
        """Le dossier du pack peut ne pas exister du tout.

        Compter ses fichiers puis retrancher rules.txt donnerait -1, et le
        diagnostic crierait alors a un deploiement incoherent qui n'existe pas.
        """
        assert fix.deposes() == 0
        for _g, texte in fix.rapport():
            assert "-1" not in texte, texte

    def test_deposes_compte_hors_rules(self, packs_deployees):
        """rules.txt est de Cemu, pas d'un mod : il ne doit pas gonfler le
        compte, sinon le deploiement paraitrait toujours incomplet d'un
        fichier."""
        assert fix.deposes() == deploy.count_files(deploy.merged_dir("boost"))

    def test_signale_le_pack_ukmm_manquant(self, packs):
        ecrire(config.cemu_settings(),
               SETTINGS_ICU.replace(
                   '<Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>\n', ""))
        assert any("UKMM" in t and "NOT" in t or "PAS" in t
                   for _g, t in fix.rapport())

    def test_signale_un_deploiement_incomplet(self, packs):
        # merged vide -> le profil n'a jamais ete fusionne
        assert any("merged" in t or "fusionne" in t
                   for _g, t in fix.rapport())


class TestDeploiementEnTropOuPas(object):
    """Un surplus de fichiers n'a jamais bloque Cemu ; un manque, si.

    Le compte compare le pack chez Cemu a la fusion. Les deux sens ne se
    valent pas : un SUR-ENSEMBLE donne au jeu tout ce qu'il attend, alors
    qu'un manque le fait tourner avec un jeu de mods incomplet. Les
    confondre annoncait « le jeu ne demarrera pas » sur un profil qui
    demarre, et `botw fix` partait alors dans un redeploiement qui
    reproduisait exactement le meme ecart.

    Le cas reel qui a ouvert ce test : UKMM livre 5614 fichiers alors que sa
    propre fusion en compte 5477. Le jeu demarre ; seul le diagnostic
    criait au gravy.
    """

    def _sans_packs_bloquants(self):
        """Retire les packs qui bloquent, pour n'observer que le decompte.

        Sans ca, `bloque()` verrait `ExtendedMemory` et `HD_Map_and_Icons` et
        le test echouerait pour une raison sans rapport avec le deploiement.
        """
        cemu.nettoyer()

    def _manque(self):
        """Retire chez Cemu un fichier que la fusion contient."""
        merged = deploy.merged_dir("boost")
        for base, _d, files in os.walk(merged):
            for nom in files:
                rel = os.path.relpath(os.path.join(base, nom), merged)
                os.remove(os.path.join(config.graphic_pack(), rel))
                return rel
        raise AssertionError("la fixture ne contient aucun fichier fusionne")

    def _surplus(self):
        """Ajoute chez Cemu un fichier qu'aucune fusion ne contient."""
        ecrire(os.path.join(config.graphic_pack(), "content", "EnTrop.sbfres"),
               "x")

    def test_fichiers_manquants_bloquent(self, packs_deployees):
        self._sans_packs_bloquants()
        self._manque()
        rapport = fix.rapport()
        assert fix.bloque(), "des fichiers fusionnes manquent : c'est grave"
        assert any(g == 2 and ("manquent" in t or "missing" in t)
                   for g, t in rapport), rapport

    def test_deploiement_complet_ne_bloque_pas(self, packs_deployees):
        self._sans_packs_bloquants()
        assert not fix.bloque(), fix.rapport()

    def test_fichiers_en_trop_ne_bloquent_pas(self, packs_deployees):
        self._sans_packs_bloquants()
        self._surplus()
        rapport = fix.rapport()
        sur = [(g, t) for g, t in rapport
               if "en trop" in t or "left over" in t]
        assert sur, ("le surplus doit etre signale, meme s'il ne bloque "
                     "pas : %r" % (rapport,))
        assert all(g == 0 for g, _t in sur), sur
        assert not fix.bloque(), rapport

    def test_le_message_du_surplus_donne_les_deux_comptes(self,
                                                          packs_deployees):
        self._sans_packs_bloquants()
        n = deploy.count_files(deploy.merged_dir("boost"))
        self._surplus()
        texte = " ".join(t for _g, t in fix.rapport())
        assert str(n) in texte and str(n + 1) in texte, texte
        assert "bloquant" in texte or "blocking" in texte, texte


def profiles_liste():
    """Les profils UKMM presents sur la fausse machine."""
    d = os.path.join(os.environ["LOCALAPPDATA"], "ukmm", "wiiu", "profiles")
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


class TestIsattyQuiMent(object):
    """Sous Git Bash, `sys.stdin.isatty()` renvoie vrai meme avec
    `< /dev/null`.

    MSYS resout la redirection lui-meme ; Windows voit un vrai flux. Un garde
    qui se fie a isatty() croit donc avoir un humain devant lui, pose les
    questions, n'en recoit aucune, et continue quand meme avec les valeurs par
    defaut. C'est exactement le chemin qui deployait un profil par accident et
    rendait la sauvegarde illisible.
    """

    @pytest.fixture
    def faux_terminal(self, monkeypatch):
        monkeypatch.delenv("BOTW_ASSUME_OUI", raising=False)
        monkeypatch.delenv("BOTW_NON_INTERACTIF", raising=False)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)

        def eof(_prompt=""):
            raise EOFError
        monkeypatch.setattr(builtins, "input", eof)
        return True

    def test_isatty_annonce_bien_un_terminal(self, faux_terminal):
        from botw import i18n
        assert i18n.interactive() is True

    def test_aucune_question_n_est_posee(self, faux_terminal):
        from botw import builder
        choix, posees = builder.poser_questions()
        assert posees == 0
        assert choix == builder.DEFAUTS

    def test_build_refuse_de_meme(self, faux_terminal, installation, capsys):
        """Le garde-fou ne doit pas dépendre de isatty()."""
        from botw import cli

        class _A(object):
            name = None
            yes = False
            no_deploy = False

        avant = set(profiles_liste())
        assert cli.cmd_build(_A(), config.load()) == 1
        assert set(profiles_liste()) == avant
        assert "botw build --yes" in capsys.readouterr().out

    def test_le_menu_sort_meme_ainsi(self, faux_terminal, installation, capsys):
        """Le menu a le meme probleme : il doit se refermer, pas boucler."""
        from botw import ui
        assert ui.run(config.load()) == 0


class Horloge(object):
    """Une horloge qu'on avance a la main.

    Deux deploiements a la meme seconde sont un etat que la machine ne produit
    pas : on joue entre les deux. Avec une horloge pilotee, le scenario reel
    (deployer, jouer, enregistrer, changer de profil) se reproduit en
    nanosecondes et sans `sleep`, et le test teste la logique, pas la vitesse
    du disque.
    """

    def __init__(self, depart=1000.0):
        self.t = float(depart)

    def __call__(self):
        return self.t

    def avancer(self, secondes):
        self.t += float(secondes)
        return self.t


def _pack_officiel(nom):
    """Cree un pack officiel sur la fausse machine et renvoie son chemin."""
    relatif = {"Workarounds": "Workarounds", "Graphics": "Graphics",
               "Enhancements": "Enhancements"}[nom]
    chemin = os.path.join(config.cemu_appdata(), "graphicPacks",
                          "downloadedGraphicPacks", "BreathOfTheWild", relatif)
    ecrire(os.path.join(chemin, "rules.txt"), "[Definition]\nname = %s\n" % nom)
    return "downloadedGraphicPacks/BreathOfTheWild/%s/rules.txt" % relatif


# L'entree DrawDistance telle que le settings.xml de la fixture l'ecrit :
# imbriquee, avec son <Preset>. La retirer demande le texte exact.
DRAW = ('<Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild'
        '/Mods/DrawDistance/rules.txt">\n'
        '            <Preset>\n'
        '                <category>Extremes</category>\n'
        '            </Preset>\n'
        '        </Entry>\n')


class TestGraphismes(object):
    """`botw fix` retire les packs graphiques pour debloquer le chargement. Il
    faut pouvoir les remettre, sinon le correctif est irreversible."""

    @pytest.fixture
    def packs_avec_officiels(self, packs_deployees):
        """Installation reellement deployee, avec les packs officiels
        installes sur le disque mais encore desactives dans settings.xml."""
        _pack_officiel("Graphics")
        _pack_officiel("Enhancements")
        _pack_officiel("Workarounds")
        return packs_deployees

    def test_les_packs_officiels_sont_vus(self, packs_avec_officiels):
        noms = [n for _r, n, _c in cemu.disponibles()]
        assert noms == ["Workarounds", "Graphics", "Enhancements"]

    def test_absent_si_nothing_installe(self, packs):
        assert cemu.disponibles() == []

    def test_reactivation(self, packs_avec_officiels):
        assert cemu.disponibles()
        ok, msg, ajoutes = cemu.activer_graphismes()
        assert ok, msg
        assert sorted(ajoutes) == ["Enhancements", "Graphics", "Workarounds"]
        actifs = cemu.active_packs()
        for _r, nom, _c in cemu.disponibles():
            assert any(c.endswith("%s/rules.txt" % nom) for c in actifs)

    def test_ukmm_reste_en_premier(self, packs_avec_officiels):
        cemu.activer_graphismes()
        assert "UKMM" in cemu.active_packs()[0]

    def test_les_bloquants_ne_reviennent_pas(self, packs_avec_officiels):
        """La garantie qui compte : reactiver l'image ne doit jamais pouvoir
        remettre le jeu dans l'etat qui le faisait boucler."""
        cemu.activer_graphismes()
        actifs = cemu.active_packs()
        assert not any("ExtendedMemory" in c for c in actifs)
        assert not any("HD_Map" in c for c in actifs)
        assert not fix.bloque(), fix.rapport()

    def test_idempotent(self, packs_avec_officiels):
        cemu.activer_graphismes()
        ok, _msg, ajoutes = cemu.activer_graphismes()
        assert ok
        assert ajoutes == []

    def test_les_cosmetiques_restent_absents_par_defaut(self,
                                                         packs_avec_officiels):
        """Le settings.xml de la fixture a DrawDistance actif : on le coupe
        d'abord, sinon on testerait l'etat de depart et non la commande."""
        _pack_mod("DrawDistance")
        ecrire(config.cemu_settings(), SETTINGS_ICU.replace(DRAW, ""))
        assert not any("DrawDistance" in c for c in cemu.active_packs())
        cemu.activer_graphismes()
        assert not any("DrawDistance" in c for c in cemu.active_packs())

    def test_cosmetiques_sur_demande(self, packs_avec_officiels):
        """Le settings.xml de la fixture a deja DrawDistance actif : on le
        coupe d'abord, sinon la commande n'a rien a ajouter et le test
        verrait autre chose."""
        _pack_mod("DrawDistance")
        ecrire(config.cemu_settings(), SETTINGS_ICU.replace(DRAW, ""))
        assert not any("DrawDistance" in c for c in cemu.active_packs())
        ok, _msg, ajoutes = cemu.activer_graphismes(cosmetiques=True)
        assert ok
        assert "DrawDistance" in ajoutes
        assert any("DrawDistance" in c for c in cemu.active_packs())

    def test_aucun_pack_actif(self, fausse_machine):
        assert cemu.activer_graphismes() == (False, cemu._("cemu.nopacks"), [])

    def test_commande_retourne_0(self, packs_avec_officiels, capsys):
        from botw import cli
        assert cli.cmd_graphics(_Gfx(mods=False, off=False),
                                config.load()) == 0
        assert "Graphics" in capsys.readouterr().out

    def test_commande_off(self, packs_avec_officiels, capsys):
        from botw import cli
        cemu.activer_graphismes()
        assert cli.cmd_graphics(_Gfx(mods=False, off=True),
                                config.load()) == 0
        actifs = cemu.active_packs()
        assert not any("Enhancements" in c for c in actifs)
        assert any("UKMM" in c for c in actifs)

    def test_commande_sans_pack(self, packs, capsys):
        from botw import cli
        assert cli.cmd_graphics(_Gfx(mods=False, off=False),
                                config.load()) == 4

    def test_refuse_si_cemu_ouvert(self, packs_avec_officiels, monkeypatch):
        monkeypatch.setattr("botw.deploy.processes_named",
                            lambda n: [1] if n == "Cemu" else [])
        ok, msg, ajoutes = cemu.activer_graphismes()
        assert not ok
        assert "Cemu" in msg
        assert ajoutes == []


def _pack_mod(nom):
    """Cree un pack tiers sous Mods/ et renvoie son chemin relatif."""
    d = os.path.join(config.cemu_appdata(), "graphicPacks",
                     "downloadedGraphicPacks", "BreathOfTheWild", "Mods", nom)
    ecrire(os.path.join(d, "rules.txt"), "[Definition]\nname = %s\n" % nom)
    return "downloadedGraphicPacks/BreathOfTheWild/Mods/%s/rules.txt" % nom


def _workaround(nom, avec_rules=True):
    """Cree un sous-pack Workarounds."""
    d = os.path.join(cemu.racine_workarounds(), nom)
    os.makedirs(d, exist_ok=True)
    if avec_rules:
        ecrire(os.path.join(d, "rules.txt"), "[Definition]\nname = %s\n" % nom)
    else:
        os.makedirs(os.path.join(d, "sans-rules"), exist_ok=True)
    return d


class TestWorkarounds(object):
    """Cemu ne livre pas UN pack Workarounds mais un dossier de packs
    independants, chacun avec son propre rules.txt."""

    def test_aucun_dossier(self, fausse_machine):
        assert cemu.workarounds() == []

    def test_decouverte(self, fausse_machine):
        _workaround("AMDShaderCrash")
        _workaround("GrassWorkaround")
        trouves = [nom for _r, nom, _c in cemu.workarounds()]
        assert trouves == ["AMDShaderCrash", "GrassWorkaround"]

    def test_sans_rules_txt_est_ignore(self, fausse_machine):
        _workaround("AMDShaderCrash")
        _workaround("PasUnPack", avec_rules=False)
        trouves = [nom for _r, nom, _c in cemu.workarounds()]
        assert "PasUnPack" not in trouves

    def test_le_chemin_est_calcule_a_l_appel(self, fausse_machine):
        """Une constante de module serait figee sur le vrai %APPDATA% : les
        tests verraient alors les packs de la vraie installation et le
        resultat dependrait de la machine qui lance la suite."""
        assert cemu.racine_workarounds().startswith(
            fausse_machine["appdata"].as_posix()[:20]) or \
            "AppData" in cemu.racine_workarounds()

    def test_actives_avec_les_autres(self, packs_deployees):
        """Un Workarounds s'active avec les packs officiels, dans la meme
        commande."""
        _workaround("GrassWorkaround")
        ok, _msg, ajoutes = cemu.activer_graphismes()
        assert ok
        assert "GrassWorkaround" in ajoutes
        assert any(c.endswith("Workarounds/GrassWorkaround/rules.txt")
                   for c in cemu.active_packs())
        assert any("UKMM" in c for c in cemu.active_packs())


class _Gfx(object):
    def __init__(self, mods=False, off=False, restore=None):
        self.mods = mods
        self.off = off
        self.restore = restore


class TestPresetsPreserves(object):
    """Chaque entree de Cemu peut porter un <Preset> : c'est la que sont
    ranges la resolution, le nombre d'images par seconde, la distance
    d'affichage et les couleurs. Reecrire une entree nue les remet a zero -
    c'est ce qui est arrive, et qui a rendu l'image 1280x720 au lieu de
    1440p."""

    AVEC_PRESET = (
        '<Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild'
        '/Graphics/rules.txt">\n'
        '            <Preset>\n'
        '                <category>Resolution</category>\n'
        '            </Preset>\n'
        '        </Entry>\n')

    def _settings_avec_preset(self):
        ecrire(config.cemu_settings(), SETTINGS_ICU.replace(
            '        <Entry filename="graphicPacks/downloadedGraphicPacks'
            '/BreathOfTheWild/Mods/DrawDistance/rules.txt">',
            '        <Entry filename="graphicPacks/downloadedGraphicPacks'
            '/BreathOfTheWild/Graphics/rules.txt">\n'
            '            <Preset>\n'
            '                <category>Resolution</category>\n'
            '            </Preset>\n'
            '        </Entry>\n'
            '        <Entry filename="graphicPacks/downloadedGraphicPacks'
            '/BreathOfTheWild/Mods/DrawDistance/rules.txt">'))

    def test_preset_survit_a_la_reecriture(self, packs_deployees):
        self._settings_avec_preset()
        cemu.activer_graphismes()
        t = io.open(config.cemu_settings(), encoding="utf-8").read()
        assert "Resolution" in t, "le preset a disparu"

    def test_nouvelle_entree_reste_nue(self, packs_deployees):
        """Un pack qui arrive pour la premiere fois n'a pas de preset : c'est
        normal, et ce n'est pas une perte."""
        ecrire(config.cemu_settings(), SETTINGS_ICU)
        _pack_officiel("Enhancements")      # il n'est pas encore actif
        assert not any("Enhancements" in c for c in cemu.active_packs())
        cemu.activer_graphismes()
        blocs = dict((cemu.cle(c), b) for c, b in cemu._entrees_brutes())
        nouveau = blocs[cemu.cle(
            "downloadedGraphicPacks/BreathOfTheWild/Enhancements/rules.txt")]
        assert "/>" in nouveau


class TestRestauration(object):
    def test_commande_restore(self, packs):
        from botw import cli
        d = os.path.join(os.environ["LOCALAPPDATA"], "sauvegardes")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "vieux.xml")
        ecrire(p, TestRestauration.ANCIEN)
        assert cli.cmd_graphics(_Gfx(mods=False, off=False, restore=p),
                                config.load()) == 0
        assert "Resolution" in io.open(config.cemu_settings(),
                                       encoding="utf-8").read()

    def test_commande_restore_fichier_absent(self, packs):
        from botw import cli
        assert cli.cmd_graphics(_Gfx(mods=False, off=False, restore="nope.xml"),
                                config.load()) == 1

    def _sauvegarde(self, contenu):
        d = os.path.join(os.environ["LOCALAPPDATA"], "sauvegardes")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "ancien-settings.xml")
        io.open(p, "w", encoding="utf-8", newline="").write(contenu)
        return p

    ANCIEN = SETTINGS_ICU.replace(
        '        <Entry filename="graphicPacks/downloadedGraphicPacks'
        '/BreathOfTheWild/Mods/DrawDistance/rules.txt">',
        '        <Entry filename="graphicPacks/downloadedGraphicPacks'
        '/BreathOfTheWild/Graphics/rules.txt">\n'
        '            <Preset>\n'
        '                <category>Resolution</category>\n'
        '            </Preset>\n'
        '        </Entry>\n'
        '        <Entry filename="graphicPacks/downloadedGraphicPacks'
        '/BreathOfTheWild/Mods/DrawDistance/rules.txt">')

    def test_restaure_les_presets(self, packs):
        p = self._sauvegarde(self.ANCIEN)
        ok, msg, noms = cemu.restaurer_depuis(p)
        assert ok, msg
        assert "Graphics" in noms
        t = io.open(config.cemu_settings(), encoding="utf-8").read()
        assert "Resolution" in t

    def test_ne_restaure_jamais_un_pack_bloquant(self, packs):
        """Un pack qui bloquait le chargement ne doit pas revenir, meme
        s'il etait present dans la sauvegarde."""
        p = self._sauvegarde(self.ANCIEN)
        ok, _msg, _noms = cemu.restaurer_depuis(p)
        assert ok
        dangereux, _o, _a = cemu.classer()
        assert dangereux == []

    def test_fichier_absent(self, packs):
        ok, msg, noms = cemu.restaurer_depuis("inexistant.xml")
        assert not ok
        assert noms == []

    def test_refuse_si_cemu_ouvert(self, packs, monkeypatch):
        p = self._sauvegarde(self.ANCIEN)
        monkeypatch.setattr("botw.deploy.processes_named",
                            lambda n: [1] if n == "Cemu" else [])
        ok, msg, noms = cemu.restaurer_depuis(p)
        assert not ok
        assert "Cemu" in msg

    def test_l_ukmm_reste_en_tete(self, packs):
        p = self._sauvegarde(self.ANCIEN)
        cemu.restaurer_depuis(p)
        assert "UKMM" in cemu.active_packs()[0]


class TestDeduplicationPacks(object):
    """Le meme pack ecrit deux fois quand Cemu met le prefixe
    "graphicPacks/" et que notre code ne le met pas. Sans normalisation, il
    etait active deux fois - et Cemu le chargeait deux fois."""

    def test_prefixe_ignore(self, fausse_machine):
        assert cemu.cle("graphicPacks/a/b/rules.txt") == cemu.cle("a/b/rules.txt")

    def test_casse_ignoree(self, fausse_machine):
        assert cemu.cle("GRAPHICpacks/A/B/rules.txt") == cemu.cle("a/b/rules.txt")

    def test_separateurs_ignores(self, fausse_machine):
        assert cemu.cle("a\\b\\rules.txt") == cemu.cle("a/b/rules.txt")

    def test_barre_obliche_debut_ignoree(self, fausse_machine):
        assert cemu.cle("/a/b/rules.txt") == cemu.cle("a/b/rules.txt")

    def test_packs_differents_restent_differents(self, fausse_machine):
        assert cemu.cle("a/rules.txt") != cemu.cle("b/rules.txt")

    def test_aucun_doublon_apres_reactivation(self, packs_deployees):
        """Le scenario reel : settings.xml contient une entree avec le prefixe,
        notre code en ajoute une sans. Le pack ne doit pas finir en double."""
        _pack_officiel("Graphics")
        ecrire(config.cemu_settings(), SETTINGS_ICU.replace(
            '<Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>',
            '<Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>\n'
            '        <Entry filename="graphicPacks/downloadedGraphicPacks'
            '/BreathOfTheWild/Graphics/rules.txt"/>'))
        cemu.activer_graphismes()
        cles = [cemu.cle(c) for c in cemu.active_packs()]
        assert len(cles) == len(set(cles)), "doublon : %s" % cles

    def test_ukmm_present_une_seule_fois(self, packs_deployees):
        cemu.activer_graphismes()
        ukmm = [c for c in cemu.active_packs() if "UKMM" in c]
        assert len(ukmm) == 1


class TestProfilDeLaSauvegarde(object):
    """Le profil d'une sauvegarde est celui qui etait actif quand elle a ete
    ecrite - pas celui du dernier deploiement.

    Ecraser l'ancien profil annulait l'avertissement dans un cas tres courant :
    deploiement de 'boost', partie enregistree, puis deploiement d'un autre
    profil. La partie se retrouvait attribuee au mauvais profil, et `botw check`
    annoncait tout va bien alors que la partie bloquerait a l'infini.
    """

    @pytest.fixture
    def horloge(self, installation, monkeypatch):
        h = Horloge()
        monkeypatch.setattr("botw.newgame.time.time", h)
        return h

    def _jouer(self, horloge, contenu="PARTIE"):
        """Ecrit une sauvegarde datee a l'heure de l'horloge."""
        chemin = config.main_save_file()
        ecrire(chemin, contenu)
        os.utime(chemin, (horloge(), horloge()))
        return horloge()

    def test_profil_du_deploiement_qui_precede_la_partie(self, horloge):
        newgame.noter_profil("boost")
        horloge.avancer(3600)               # on joue une heure
        self._jouer(horloge)
        assert newgame.profil_de_la_partie() == "boost"

    def test_redeployer_ne_detruit_pas_la_verite(self, horloge):
        """Le cas qui rendait le controle aveugle."""
        newgame.noter_profil("boost")
        horloge.avancer(3600)
        self._jouer(horloge)                 # partie enregistree sous boost
        horloge.avancer(3600)
        newgame.noter_profil("autre")        # puis on change de profil
        assert newgame.profil_de_la_partie() == "boost"

    def test_check_signale_le_decalage(self, horloge):
        """Le but de tout ca : `botw check` doit crier."""
        from botw import profiles
        assert profiles.active() == "boost"    # la fausse installation
        newgame.noter_profil("sur")            # partie faite avec « sur »
        horloge.avancer(3600)
        self._jouer(horloge)
        horloge.avancer(3600)
        newgame.noter_profil("boost")          # puis on bascule sur « boost »
        rapport = fix.rapport()
        assert any(g >= 2 and "sur" in t for g, t in rapport), rapport

    def test_partie_reecrite_prend_le_nouveau_profil(self, horloge):
        newgame.noter_profil("boost")
        horloge.avancer(3600)
        self._jouer(horloge)
        horloge.avancer(3600)
        newgame.noter_profil("autre")
        horloge.avancer(3600)
        self._jouer(horloge)                 # on rejoue et on enregistre
        assert newgame.profil_de_la_partie() == "autre"

    def test_partie_plus_belge_que_tout(self, horloge):
        """Une partie ecrite avant le premier deploiement connu : on ne sait
        pas, et on ne devine pas."""
        horloge.avancer(3600)
        self._jouer(horloge)
        horloge.avancer(3600)               # le deploiement vient apres
        newgame.noter_profil("boost")
        assert newgame.profil_de_la_partie() == ""

    def test_marge_tolerance(self, horloge):
        """Cemu peut ecrire la partie juste avant la fin du deploiement : une
        marge de quelques secondes evite de conclure qu'on ne sait pas."""
        horloge.avancer(3600)
        self._jouer(horloge)
        horloge.avancer(newgame.TOLERANCE / 4.0)
        newgame.noter_profil("boost")
        assert newgame.profil_de_la_partie() == "boost"

    def test_ancien_format_toujours_lisible(self, horloge):
        """Les slot.json deja ecrits sur le disque sont des objets, pas des
        listes : ils doivent rester lisibles."""
        d = newgame._archives()
        os.makedirs(d, exist_ok=True)
        with io.open(newgame._slot_file(), "w", encoding="utf-8") as f:
            json.dump({"profil": "boost", "quand": horloge() - 3600}, f)
        self._jouer(horloge)
        assert newgame.profil_de_la_partie() == "boost"

    def test_fichier_corrompu_ne_casse_rien(self, horloge):
        d = newgame._archives()
        os.makedirs(d, exist_ok=True)
        with io.open(newgame._slot_file(), "w", encoding="utf-8") as f:
            f.write("{pas du json")
        self._jouer(horloge)
        assert newgame.profil_de_la_partie() == ""

    def test_entree_absurde_ignoree(self, horloge):
        d = newgame._archives()
        os.makedirs(d, exist_ok=True)
        with io.open(newgame._slot_file(), "w", encoding="utf-8") as f:
            json.dump([{"profil": "boost", "quand": horloge() - 3600},
                       "pas un objet",
                       {"pas_de_profil": 1}], f)
        self._jouer(horloge)
        assert newgame.profil_de_la_partie() == "boost"

    def test_historique_borne(self, horloge):
        for i in range(newgame.HISTORIQUE + 20):
            horloge.avancer(1)
            newgame.noter_profil("p%d" % i)
        notes = newgame._lire_notes()
        assert len(notes) == newgame.HISTORIQUE
        assert notes[-1]["profil"] == "p%d" % (newgame.HISTORIQUE + 19)

    def test_profil_vide_refuse(self, horloge):
        assert newgame.noter_profil("") is False
        assert newgame._lire_notes() == []


class TestConstructeur(object):
    def test_build_hors_ligne_ne_cree_rien(self, installation, monkeypatch,
                                          capsys):
        """Sans terminal, `botw build` ne doit NI creer de profil NI le
        deployer.

        Les reponses par defaut suffiraient a construire un profil et a le
        rendre actif. La sauvegarde du joueur a ete faite avec un autre
        profil : elle devient illisible, et `botw check` le signale apres
        coup, quand il est trop tard.
        """
        monkeypatch.delenv("BOTW_ASSUME_OUI", raising=False)
        monkeypatch.setenv("BOTW_NON_INTERACTIF", "1")

        class _A(object):
            name = None
            yes = False
            no_deploy = False

        from botw import cli
        avant = set(profiles_liste())
        assert cli.cmd_build(_A(), config.load()) == 1
        assert set(profiles_liste()) == avant
        out = capsys.readouterr().out
        assert "botw build --yes" in out

    def test_build_avec_yes_passe_le_garde_fou(self, installation, monkeypatch):
        """--yes est l'accord explicite : le garde-fou doit laisser passer,
        le profil cree doit devenir l' profil actif, et le code de sortie
        doit etre un entier - un tuple fait echouer sys.exit()."""
        monkeypatch.delenv("BOTW_ASSUME_OUI", raising=False)
        monkeypatch.setenv("BOTW_NON_INTERACTIF", "1")

        class _A(object):
            name = "sans-terminal"
            yes = True
            no_deploy = True

        from botw import cli
        vus = {}

        def faux_construire(nom, choix, cfg=None, deploy_apres=True):
            vus["nom"] = nom
            vus["deploy_apres"] = deploy_apres
            return nom, 0

        monkeypatch.setattr("botw.builder.construire", faux_construire)
        cfg = config.load()
        code = cli.cmd_build(_A(), cfg)
        assert code == 0
        assert isinstance(code, int)
        assert vus["nom"] == "sans-terminal"
        assert vus["deploy_apres"] is False
        assert config.load()["game_profile"] == "sans-terminal"

    def test_second_wind_decoche_par_defaut(self):
        """Le mod le plus lourd ne doit pas etre coche d'office : on prouve
        d'abord que le reste demarre."""
        assert builder.DEFAUTS["secondwind"] is False

    def test_linkle_coche_par_defaut(self):
        assert builder.DEFAUTS["linkle"] is True

    def test_avec_second_wind(self):
        choix = dict(builder.DEFAUTS, secondwind=True)
        liste = builder.assembling(choix)
        assert "Second_Wind_(core).zip" in liste
        assert "The_Linkle_Mod_3.0.1.zip" in liste

    def test_sans_second_wind_avec_linkle(self):
        choix = dict(builder.DEFAUTS, secondwind=False, linkle=True)
        liste = builder.assembling(choix)
        assert not any("Second_Wind" in m for m in liste)
        assert "The_Linkle_Mod_3.0.1.zip" in liste

    def test_linkle_seul(self):
        choix = {c: False for c in builder.DEFAUTS}
        choix["linkle"] = True
        liste = builder.assembling(choix)
        assert liste == ["The_Linkle_Mod_3.0.1.zip"]

    def test_aucun_mod(self):
        choix = {c: False for c in builder.DEFAUTS}
        assert builder.assembling(choix) == []

    def test_ordre_de_priorite_respecte(self):
        """Second Wind doit passer avant Linkle, quel que soit l'ordre des
        questions : c'est UKMM qui donne la priorite au dernier."""
        choix = dict(builder.DEFAUTS, secondwind=True, linkle=True)
        liste = builder.assembling(choix)
        assert liste.index("Second_Wind_(core).zip") < \
            liste.index("The_Linkle_Mod_3.0.1.zip")

    def test_chaque_question_a_des_mods(self):
        for cle, _en, _fr, liste in builder.QUESTIONS:
            assert liste, cle
            assert all(m.endswith(".zip") for m in liste), cle

    def test_mods_connus_de_la_bibliotheque(self, installation):
        """Les modifs proposees doivent exister dans la bibliotheque de
        reference, sinon le constructeur proposerait des zips fantomes."""
        connus = set()
        for _c, _en, _fr, liste in builder.QUESTIONS:
            connus |= set(liste)
        assert len(connus) == 14      # les 14 zips de la bibliotheque

    def test_nom_genere(self):
        assert "linkle" in builder.noms(dict(builder.DEFAUTS, secondwind=True))
        assert "sw" in builder.noms(dict(builder.DEFAUTS, secondwind=True))
        assert builder.noms(dict(builder.DEFAUTS, secondwind=False)) \
            .startswith("linkle")

# --- les armes invisibles : reglages qui dependent d'un pack absent ---------
#
# Le pack "Draw Distance" propose des options qui ne fonctionnent qu'avec le
# pack Extended Memory. Or ce pack ne peut pas tourner avec UKMM : les
# options choisies font donc disparaitre les acteurs attaches a Link, donc
# l'arme qu'il tient en main. Le jeu demarre, tourne, et n'affiche rien.

# Extrait fidele du rules.txt livre avec le pack : c'est un fichier de
# configuration Ini, pas du XML comme settings.xml.
RULES_DRAWDISTANCE = """[Definition]
titleIds = 00050000101C9500
name = Draw Distance
version = 6

[Preset]
name = Medium (1x)
category = NPC, Enemies And Other Entities
default = 1
$actor = 1.0

[Preset]
name = High (1.25x)
category = NPC, Enemies And Other Entities
$actor = 1.25

[Preset]
name = Ultra (1.5x)
category = NPC, Enemies And Other Entities
$actor = 1.5

[Preset]
name = Extreme (2x, requires Extended Memory pack!)
category = NPC, Enemies And Other Entities
$actor = 2

[Preset]
name = High (1.25x)
category = Terrain, Buildings, Bushes And Other Objects
$object = 1.25

[Preset]
name = Ultra (1.5x, requires Extended Memory pack!)
category = Terrain, Buildings, Bushes And Other Objects
$object = 1.5

[Preset]
name = Medium (Default)
category = Trees (2D Billboards)
default = 1
$tree = 0.5*1.0
"""

DD = ("graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Mods/"
      "DrawDistance/rules.txt")

SETTINGS_ARMES_INVISIBLES = """<?xml version="1.0" encoding="UTF-8"?>
<Config>
  <content>
    <GraphicPack>
        <Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>
        <Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Mods/DrawDistance/rules.txt">
            <Preset>
                <category>NPC, Enemies And Other Entities</category>
                <preset>Extreme (2x, requires Extended Memory pack!)</preset>
            </Preset>
            <Preset>
                <category>Terrain, Buildings, Bushes And Other Objects</category>
                <preset>Ultra (1.5x, requires Extended Memory pack!)</preset>
            </Preset>
            <Preset>
                <category>Trees (2D Billboards)</category>
                <preset>Medium (Default)</preset>
            </Preset>
        </Entry>
        <Entry filename="graphicPacks/downloadedGraphicPacks/BreathOfTheWild/Graphics/rules.txt">
            <Preset>
                <category>Resolution</category>
                <preset>2560x1440 (2K)</preset>
            </Preset>
        </Entry>
    </GraphicPack>
    <Input>
      <PadChannels>1</PadChannels>
    </Input>
  </content>
</Config>
"""


def _installer_draw_distance():
    """Ecrit le rules.txt du pack sous graphicPacks/.

    DD porte deja le prefixe 'graphicPacks/', comme Cemu l'ecrit dans
    settings.xml ; le repertoire du pack, lui, s'appelle graphicPacks une
    seule fois. On retire donc le prefixe avant de joindre.
    """
    relatif = cemu._sans_prefixe(DD).replace("/", os.sep)
    ecrire(os.path.join(config.cemu_appdata(), "graphicPacks", relatif),
           RULES_DRAWDISTANCE)


@pytest.fixture
def draw_distance(fausse_machine):
    """Le pack Draw Distance installe, avec son rules.txt reel."""
    _installer_draw_distance()
    ecrire(config.cemu_settings(), SETTINGS_ARMES_INVISIBLES)
    return draw_distance


class TestArmesInvisibles(object):

    def test_options_lues_avec_ou_sans_prefixe(self, draw_distance):
        """Le meme pack, ecrit comme Cemu l'ecrit ou comme le code le stocke."""
        avec = cemu.options_du_pack(DD)
        sans = cemu.options_du_pack(DD.replace("graphicPacks/", "", 1))
        assert avec == sans
        assert avec, "aucune option lue : le rules.txt n'a pas ete trouve"

    def test_les_deux_categories_sont_signalees(self, draw_distance):
        trouves = cemu.presets_incompatibles()
        assert len(trouves) == 2
        categories = sorted(c for _p, c, _a, _s in trouves)
        assert categories == ["NPC, Enemies And Other Entities",
                              "Terrain, Buildings, Bushes And Other Objects"]

    def test_propose_la_meilleure_option_sure(self, draw_distance):
        """Acteurs : Ultra (1.5x) ne demande rien. Objets : il faut redescendre."""
        par_cat = {c: s for _p, c, _a, s in cemu.presets_incompatibles()}
        assert par_cat["NPC, Enemies And Other Entities"] == "Ultra (1.5x)"
        assert par_cat["Terrain, Buildings, Bushes And Other Objects"] \
            == "High (1.25x)"

    def test_rien_a_signaler_si_extended_memory_est_actif(self, draw_distance):
        """Avec le pack present, l'option choisie est legitime."""
        t = io.open(config.cemu_settings(), encoding="utf-8").read()
        t = t.replace(
            '<Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>',
            '<Entry filename="graphicPacks/BreathOfTheWild_UKMM/rules.txt"/>\n'
            '        <Entry filename="graphicPacks/downloadedGraphicPacks/'
            'BreathOfTheWild/Mods/ExtendedMemory/rules.txt"/>')
        ecrire(config.cemu_settings(), t)
        assert cemu.presets_incompatibles() == []

    def test_corriger_ecret_la_valeur_sure(self, draw_distance):
        ecrits = cemu.corriger_presets()
        assert len(ecrits) == 2
        reste = cemu.presets_du_bloc(cemu._bloc_de(DD))
        assert reste["NPC, Enemies And Other Entities"] == "Ultra (1.5x)"
        assert reste["Terrain, Buildings, Bushes And Other Objects"] \
            == "High (1.25x)"

    def test_corriger_est_idempotent(self, draw_distance):
        cemu.corriger_presets()
        assert cemu.corriger_presets() == []
        assert cemu.presets_incompatibles() == []

    def test_corriger_preserve_la_resolution(self, draw_distance):
        """On ne touche qu'a la valeur visee : 1440p doit survivre."""
        cemu.corriger_presets()
        t = io.open(config.cemu_settings(), encoding="utf-8").read()
        assert "2560x1440 (2K)" in t
        assert "PadChannels" in t
        assert "UKMM" in t

    def test_corriger_garantit_une_sauvegarde(self, draw_distance):
        cemu.corriger_presets()
        assert os.path.isfile(config.cemu_settings() + ".botw-presets.bak")

    def test_corriger_refuse_pendant_que_cemu_tourne(self, draw_distance,
                                                     monkeypatch):
        monkeypatch.setattr("botw.deploy.processes_named",
                            lambda n: ["Cemu.exe"])
        assert cemu.corriger_presets() == []
        assert "Extreme (2x" in io.open(config.cemu_settings(),
                                        encoding="utf-8").read()

    def test_le_diagnostic_signale_sans_bloquer(self, draw_distance):
        """Gravite 1 : le jeu demarre, il ne manque que des choses a l'ecran.

        On verifie la gravite des lignes qui parlent de presets, pas
        `bloque()` dans son ensemble : sur cette fausse machine il n'y a ni
        sauvegarde ni deploiement, donc le rapport signale aussi ces absences
        la, et ce n'est pas ce que ce test veut mesurer.
        """
        graves = [(g, t) for g, t in fix.rapport() if "INCOMPATIBLE" in t]
        assert len(graves) == 2
        for g, t in graves:
            assert g == 1, "un reglage incompatible ne doit pas etre bloquant"
            assert "Extended Memory" in t

    def test_fix_repare_les_armes(self, draw_distance):
        fix.corriger(deploy_apres=False)
        assert cemu.presets_incompatibles() == []

    def test_un_reglage_normal_ne_declenche_rien(self, fausse_machine):
        """Des valeurs qui n'exigent rien ne doivent rien declencher."""
        _installer_draw_distance()
        t = SETTINGS_ARMES_INVISIBLES.replace(
            "Extreme (2x, requires Extended Memory pack!)", "Ultra (1.5x)")
        t = t.replace(
            "Ultra (1.5x, requires Extended Memory pack!)", "High (1.25x)")
        ecrire(config.cemu_settings(), t)
        assert cemu.presets_incompatibles() == []
        assert cemu.corriger_presets() == []


# --- un pack actif sans etre dans settings.xml ------------------------------
#
# "HD Map and Icons" porte `default = true` dans son rules.txt : Cemu l'active
# meme apres l'avoir retire de settings.xml. Il remplace 1558 icones
# d'inventaire, et le jeu perd toutes ses icones - alors que les 49 entrees
# de settings.xml sont parfaitement propres. C'est ce que regarde cette
# famille de tests : ce qu'il y a SUR LE DISQUE, pas ce que le fichier dit.

RULES_PAR_DEFAUT = """[Definition]
titleIds = 00050000101C9500
name = HD Map and Icons
version = 4
default = true
"""

RULES_SANS_DEFAUT = """[Definition]
titleIds = 00050000101C9500
name = Un Pack Neutre
version = 1
default = false
"""


def _installer(nom, rules, avec_contenu=True):
    base = os.path.join(config.cemu_appdata(), "graphicPacks", nom)
    ecrire(os.path.join(base, "rules.txt"), rules)
    if avec_contenu:
        ecrire(os.path.join(base, "content", "UI", "StockItem",
                            "Weapon_Sword_001.sbitemico"), "Yaz0")
    return nom


class TestPackActifParDefaut(object):

    def test_detecte_un_pack_actif_sans_settings(self, fausse_machine):
        _installer("HD_Map_and_Icons", RULES_PAR_DEFAUT)
        trouves = [n for _c, n in cemu.packs_par_defaut()]
        assert trouves == ["HD_Map_and_Icons"]

    def test_ignore_un_pack_sans_contenu(self, fausse_machine):
        """Un pack purely graphique (resolution, anticrenelage) n'ecrase rien :
        le laisser s'activer est son usage normal."""
        _installer("UnPackGraphique", RULES_PAR_DEFAUT, avec_contenu=False)
        assert cemu.packs_par_defaut() == []

    def test_ignore_default_false(self, fausse_machine):
        _installer("PackNeutre", RULES_SANS_DEFAUT)
        assert cemu.packs_par_defaut() == []

    def test_ignore_notre_propre_pack(self, fausse_machine):
        """Le pack UKMM est actif par defaut, et c'est voulu : il porte les
        mods. Le signaler ferait disparaitre les mods du jeu."""
        _installer("BreathOfTheWild_UKMM", RULES_PAR_DEFAUT)
        assert cemu.packs_par_defaut() == []

    def test_desactiver_arrete_le_signalement(self, fausse_machine):
        _installer("HD_Map_and_Icons", RULES_PAR_DEFAUT)
        assert cemu.desactiver_par_defaut() == ["HD_Map_and_Icons"]
        assert cemu.packs_par_defaut() == []
        texte = io.open(os.path.join(config.cemu_appdata(), "graphicPacks",
                                     "HD_Map_and_Icons", "rules.txt"),
                        encoding="utf-8").read()
        assert "default = false" in texte

    def test_desactiver_garde_le_pack_installe(self, fausse_machine):
        """La manoeuvre doit etre reversible : on ne supprime rien."""
        _installer("HD_Map_and_Icons", RULES_PAR_DEFAUT)
        cemu.desactiver_par_defaut()
        base = os.path.join(config.cemu_appdata(), "graphicPacks",
                            "HD_Map_and_Icons")
        assert os.path.isfile(os.path.join(base, "rules.txt"))
        assert os.path.isfile(os.path.join(base, "content", "UI", "StockItem",
                                           "Weapon_Sword_001.sbitemico"))

    def test_desactiver_est_idempotent(self, fausse_machine):
        _installer("HD_Map_and_Icons", RULES_PAR_DEFAUT)
        cemu.desactiver_par_defaut()
        assert cemu.desactiver_par_defaut() == []

    def test_le_diagnostic_bloque_le_lancement(self, fausse_machine):
        _installer("HD_Map_and_Icons", RULES_PAR_DEFAUT)
        ecrire(config.cemu_settings(), SETTINGS_ICU)
        lignes = [(g, t) for g, t in fix.rapport() if "HD_Map_and_Icons" in t]
        assert lignes, "le pack actif par defaut doit etre signale"
        assert lignes[0][0] == 2, "un pack qui ecrase le jeu est bloquant"

    def test_fix_le_desactive(self, fausse_machine):
        _installer("HD_Map_and_Icons", RULES_PAR_DEFAUT)
        ecrire(config.cemu_settings(), SETTINGS_ICU)
        fix.corriger(deploy_apres=False)
        assert cemu.packs_par_defaut() == []


class TestPartieDUnAutreJeuDeMods(object):
    """La partie d'un autre jeu de mods ne se repare pas toute seule.

    Aucun pack graphique n'y est pour rien : le jeu plante parce qu'il relit
    la sauvegarde a travers des fichiers de mods absents. Avant, `botw fix`
    annoncait quand meme « Lancez : botw fix », puis refaisait un deploiement
    de deux minutes qui ne changeait rien a la cause reelle.
    """

    def _machine_avec_une_partie(self, fausse_machine, profil_partie,
                                 profil_actif):
        """Une sauvegarde ecrite au moment du deploiement `profil_partie`."""
        from botw import deploy
        ecrire(os.path.join(fausse_machine["appdata"], "ukmm", "settings.yml"),
               SETTINGS_YML.replace("profile: boost", "profile: " + profil_actif))
        os.makedirs(config.save_root(), exist_ok=True)
        ecrire(config.main_save_file(), "SAV")
        # slot.json dit quel etait le profil au moment de l'ecriture ; le
        # fichier doit donc porter cette date-la, c'est ainsi que l'outil
        # retrouve le jeu de mods d'origine.
        quand = os.path.getmtime(config.main_save_file()) - 60
        slot = os.path.join(fausse_machine["bureau"], "Sauvegardes",
                            "NouvellePartie")
        os.makedirs(slot, exist_ok=True)
        with io.open(os.path.join(slot, "slot.json"), "w",
                     encoding="utf-8") as f:
            json.dump([{"profil": profil_partie, "quand": quand}], f)
        # Un profil actif doit exister sur le disque, sinon deploy.merged_dir
        # ne trouve rien et le rapport tombe sur un autre cas.
        prof = os.path.join(fausse_machine["local"], "ukmm", "wiiu",
                            "profiles", profil_actif)
        os.makedirs(os.path.join(prof, "merged", "content"), exist_ok=True)
        ecrire(os.path.join(prof, "profile.yml"), PROFIL_YML)
        assert deploy.count_files(config.save_root()) > 0

    def test_signale_et_ne_declenche_aucun_deploiement(self, fausse_machine,
                                                        monkeypatch, capsys):
        from botw import newgame, profiles
        self._machine_avec_une_partie(fausse_machine, "secondwind", "sur")
        assert profiles.active() == "sur"
        assert newgame.profil_de_la_partie() == "secondwind"

        appele = []
        monkeypatch.setattr(deploy, "deploy",
                            lambda *a, **k: appele.append(a) or {})
        code = fix.corriger(deploy_apres=True)
        assert code == 2, "un cas non reparable doit le dire"
        assert not appele, "il ne faut surtout pas redployer : deux minutes pour rien"
        out = capsys.readouterr().out
        assert "botw jeu" in out, "la sortie doit proposer la vraie commande"

    def test_ne_declenche_rien_si_ca_vaut(self, fausse_machine, monkeypatch,
                                          capsys):
        from botw import newgame, profiles
        self._machine_avec_une_partie(fausse_machine, "sur", "sur")
        assert newgame.profil_de_la_partie() == "sur"
        assert profiles.active() == "sur"
        appele = []
        monkeypatch.setattr(deploy, "deploy",
                            lambda *a, **k: appele.append(a) or {})
        assert fix.corriger(deploy_apres=True) == 0
        assert appele, "quand tout va bien, le redploiement a bien lieu"

    def test_la_commande_sort_en_echec_simple(self, fausse_machine, capsys):
        from botw import cli
        self._machine_avec_une_partie(fausse_machine, "secondwind", "sur")
        assert cli.main(["fix", "-y"]) == 1
