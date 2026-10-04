"""Le lanceur : dispatch des commandes, codes de sortie, menu interactif."""
import builtins
import io
import os
import re
import subprocess
import sys

import pytest

from botw import cli, config, i18n, ui

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def saisir(*reponses):
    """Remplace input() par une suite de reponses, puis par le vide."""
    it = iter(list(reponses) + [""] * 40)

    def faux_input(_prompt=""):
        try:
            return next(it)
        except StopIteration:
            return ""
    return faux_input


def numeros_du_menu(capsys, monkeypatch):
    """Les numeros affiches devant chaque option du menu principal.

    Le menu gagne une option a chaque nouvelle commande. Un test qui ecrirait
    « 8) langue » casserait sans qu'aucun bug soit corrige : on relit donc
    l'ecran tel qu'un humain le voit.
    """
    monkeypatch.setattr(builtins, "input", saisir("q"))
    ui.run(config.load())
    out = capsys.readouterr().out
    nums = {}
    for ligne in out.splitlines():
        m = re.match(r"\s*(\d+)\)\s+(.*\S)\s*$", ligne)
        if m:
            nums[m.group(1)] = m.group(2)
    return nums


def numero_de(capsys, monkeypatch, libelle):
    """Le numero de l'option dont le libelle est exactement `libelle`."""
    for n, lbl in numeros_du_menu(capsys, monkeypatch).items():
        if lbl == libelle:
            return n
    raise AssertionError("option absente du menu : %r" % libelle)


def _eof(_prompt=""):
    """Simule un stdin ferme : input() leve EOFError."""
    raise EOFError


class TestAide(object):
    def test_aide_en_anglais_par_defaut(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])
        out = capsys.readouterr().out
        assert "full health check" in out
        assert "doctor" in out

    def test_aide_suivant_la_langue(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--lang", "fr", "--help"])
        out = capsys.readouterr().out
        assert "bilan de sante" in out
        assert "doctor" in out

    def test_affiche_toutes_les_commandes(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--help"])
        out = capsys.readouterr().out
        for c in ("lang", "doctor", "deploy", "profile", "mods", "tools",
                  "catalog", "coop", "newgame", "readme", "ui"):
            assert c in out, c

    def test_version(self, capsys):
        with pytest.raises(SystemExit):
            cli.main(["--version"])
        assert "botw" in capsys.readouterr().out


class TestCodesDeSortie(object):
    """0 = tout va bien, 1 = probleme. C'est ce qui permet au .bat
    d'afficher quelque chose de rouge."""

    def test_unknown_command(self, capsys):
        with pytest.raises(SystemExit) as e:
            cli.main(["nimporte_quoi"])
        assert e.value.code == 2

    def test_profil_inexistant(self, installation, capsys):
        assert cli.main(["deploy", "fantome"]) == 1
        assert "Unknown profile" in capsys.readouterr().out

    def test_mod_inconnu(self, installation, capsys):
        assert cli.main(["mods", "install", "-p", "boost", "jamais-vu"]) == 1

    def test_arg_manquant(self, installation, monkeypatch, capsys):
        """'botw deploy' sans nom utilise le profil par defaut de la config ;
        'botw profile show' sans nom est refuse."""
        monkeypatch.setattr("botw.deploy.run_ukmm", lambda args, cfg=None: (0, ""))
        monkeypatch.setattr("botw.deploy.processes_named", lambda n: [])
        assert cli.main(["deploy"]) == 0
        assert cli.main(["profile", "show"]) == 1

    def test_ukmm_absent_donne_un_code_clair(self, installation, capsys):
        """Pas d'UKMM = code 4, pas un echec generique : le .bat peut dire
        'installe UKMM' plutot que 'erreur inconnue'."""
        assert cli.main(["deploy", "boost"]) == 4

    def test_doctor_echec_signale(self, fausse_machine, capsys):
        assert cli.main(["doctor"]) == 1

    def test_doctor_index_de_sauvegardes(self, fausse_machine, capsys):
        """L'index des noms de parties ne doit etre signale QUE s'il y a une
        partie a nommer. Sinon `doctor` rate son verdict sur un poste qui n'a
        jamais joue, et le message affichait 'presents' en rouge : le controle
        etait a la fois faux et incomprehensible."""
        from botw import doctor
        assert not os.path.isfile(os.path.join(config.shots_dir(),
                                               "parties.json"))
        assert not os.path.isdir(config.save_root())
        doctor.run(config.load())
        out = capsys.readouterr().out
        assert i18n._("doctor.saves.noindex") in out
        assert "[KO ] " + i18n._("doctor.saves.noindex") not in out
        assert "[KO ] " + i18n._("doctor.saves.index") not in out
        # Le message du cas present ne doit jamais etre affiche en rouge.
        assert i18n._("doctor.saves.index") not in out.split("Saves")[-1]

    def test_doctor_index_absent_avec_une_partie(self, fausse_machine, capsys):
        """La, au contraire, une partie sans noms doit etre signalee."""
        from botw import doctor
        os.makedirs(config.save_root(), exist_ok=True)
        doctor.run(config.load())
        out = capsys.readouterr().out
        assert "[KO ] " + i18n._("doctor.saves.noindex") in out

    def test_doctor_index_present(self, fausse_machine, capsys):
        from botw import doctor
        os.makedirs(config.shots_dir(), exist_ok=True)
        with io.open(os.path.join(config.shots_dir(), "parties.json"),
                     "w", encoding="utf-8") as f:
            f.write("[]")
        os.makedirs(config.save_root(), exist_ok=True)
        doctor.run(config.load())
        out = capsys.readouterr().out
        assert "[OK ] " + i18n._("doctor.saves.index") in out
        assert i18n._("doctor.saves.noindex") not in out

    def test_langue_inconnue(self, capsys):
        assert cli.main(["lang", "de"]) == 1
        assert "auto" in capsys.readouterr().out

    def test_lang_auto_rend_la_main_au_poste(self, monkeypatch, capsys):
        """Le cas reel : le poste est francophone, on avait fige l'anglais.
        `botw lang auto` doit suivre le poste, pas figer ce qu'on voyait."""
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "fr")
        cli.main(["lang", "en"])
        assert cli.main(["lang", "auto"]) == 0
        assert config.load()["lang"] == ""
        assert i18n.lang() == "fr"          # la detection a bien eu lieu
        # Le message est ecrit dans la langue qui vient d'etre appliquee :
        # on le relit avec la meme source de verite.
        assert i18n._("lang.detected", lang="fr") in capsys.readouterr().out
        cli.main(["lang", "en"])

    def test_lang_auto_sans_detection_ne_plante_pas(self, monkeypatch, capsys):
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        for nom in ("BOTW_LANG", "LANG", "LC_ALL", "LC_MESSAGES"):
            monkeypatch.delenv(nom, raising=False)
        assert cli.main(["lang", "auto"]) == 0
        out = capsys.readouterr().out
        assert i18n._("lang.no_auto") in out
        assert config.load()["lang"] == ""
        i18n.set_lang("en")

    def test_lang_annonce_la_source(self, monkeypatch, capsys):
        """Un choix enregistre et une detection ne se presentent pas de la
        meme facon : sinon l'utilisateur ne sait pas lequel des deux agit."""
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "fr")
        i18n.set_lang("en")
        cli.main(["lang", "en"])
        assert cli.main(["lang"]) == 0
        out = capsys.readouterr().out
        assert i18n._("lang.chosen", lang="en") in out
        assert i18n._("lang.detected", lang="fr") not in out
        cfg = config.load()
        cfg["lang"] = ""
        config.save(cfg)
        assert cli.main(["lang"]) == 0
        assert i18n._("lang.detected", lang="fr") in capsys.readouterr().out
        cli.main(["lang", "en"])

    def test_menu_propose_auto(self, installation, monkeypatch, capsys):
        """Le menu doit pouvoir rendre la main au poste lui aussi."""
        n = numero_de(capsys, monkeypatch, i18n._("ui.lang"))
        monkeypatch.setattr(builtins, "input", saisir(n, "auto", "q"))
        ui.run(config.load())
        assert config.load()["lang"] == ""

    def test_langue_possee_est_memorisee(self, capsys):
        assert cli.main(["lang", "fr"]) == 0
        assert config.load()["lang"] == "fr"
        cli.main(["lang", "en"])
        assert config.load()["lang"] == "en"

    def test_option_lang_sans_valeur(self, capsys):
        assert cli.main(["--lang"]) == 2

    def test_readme_trouve(self, capsys):
        assert cli.main(["readme", "fr"]) == 0


class TestCommandesLeves(object):
    @pytest.mark.parametrize("argv", [
        ["lang"], ["doctor"], ["profile", "list"], ["mods", "list"],
        ["tools", "list"], ["catalog"], ["coop", "status"],
        ["newgame", "status"], ["readme"], ["profile", "show", "boost"],
        ["profile", "use", "boost"], ["profile", "verify", "boost"],
        ["mods", "search", "linkle"],
    ])
    def test_ne_leve_pas(self, installation, argv, monkeypatch, capsys):
        """Appeler chaque commande avec des arguments realistes doit
        fonctionner, quitte a ne pas deployer : c'est le test qui garantit
        qu'aucun sous-module n'a une faute de frappe dans son nom."""
        monkeypatch.setattr("botw.deploy.run_ukmm", lambda args, cfg=None: (0, ""))
        monkeypatch.setattr("botw.deploy.processes_named", lambda n: [])
        monkeypatch.setattr(ui, "launch", lambda p, c: 0)
        cli.main(argv)
        assert capsys.readouterr().out.strip() != ""

    def test_recherche_dans_la_bibliotheque(self, installation, capsys):
        cli.main(["mods", "search", "linkle"])
        out = capsys.readouterr().out
        assert "Linkle" in out
        assert "library" in out


class TestMenu(object):
    @pytest.fixture(autouse=True)
    def _terminal(self, monkeypatch):
        """Ces tests simulent un humain : le menu doit se croire devant un
        terminal, sinon ask() renvoie sa valeur par defaut sans appeler le
        faux input() qu'on a installe."""
        monkeypatch.setenv("BOTW_ASSUME_OUI", "1")

    def test_ecran_principal_affiche_les_boutons(self, installation, monkeypatch,
                                                capsys):
        monkeypatch.setattr(ui, "launch", lambda p, c: 0)
        monkeypatch.setattr(builtins, "input", saisir("q"))
        assert ui.run(config.load()) == 0
        out = capsys.readouterr().out
        for bouton in ("NEW GAME", "FRENCH", "Two players", "Mods"):
            assert bouton in out, bouton

    def test_bouton_q_quitte(self, installation, monkeypatch, capsys):
        monkeypatch.setattr(builtins, "input", saisir("q"))
        assert ui.run(config.load()) == 0

    def test_bouton_francais_affiche_le_readme(self, installation, monkeypatch,
                                              capsys):
        """Le raccourci D ouvre la doc en francais, meme depuis le mode
        anglais : c'est le bouton du lanceur .bat."""
        monkeypatch.setattr(builtins, "input", saisir("d", "q"))
        ui.run(config.load())
        assert "sur Cemu" in capsys.readouterr().out

    def test_bouton_nouvelle_partie(self, installation, monkeypatch, capsys):
        monkeypatch.setattr(builtins, "input", saisir("n", "n", "q"))
        ui.run(config.load())
        assert "NEW GAME" in capsys.readouterr().out

    def test_mauvaise_reponse_redemande(self, installation, monkeypatch, capsys):
        monkeypatch.setattr(ui, "launch", lambda p, c: 0)
        seen = []

        def faux(_prompt="", default=None):
            seen.append(_prompt)
            return "zzz" if len(seen) == 1 else "q"
        monkeypatch.setattr(builtins, "input", faux)
        ui.run(config.load())
        assert "not one of the choices" in capsys.readouterr().out

    def test_changement_de_langue(self, installation, monkeypatch, capsys):
        n = numero_de(capsys, monkeypatch, i18n._("ui.lang"))
        monkeypatch.setattr(builtins, "input", saisir(n, "fr", "q"))
        ui.run(config.load())
        assert config.load()["lang"] == "fr"
        assert "Deux joueurs" in capsys.readouterr().out

    def test_langue_revenue_en_anglais(self, installation, monkeypatch, capsys):
        """Aller-retour complet : revenir a l'anglais depuis l'anglais ne
        prouverait rien, le defaut etant deja l'anglais."""
        n = numero_de(capsys, monkeypatch, i18n._("ui.lang"))
        monkeypatch.setattr(builtins, "input", saisir(n, "fr", n, "en", "q"))
        ui.run(config.load())
        assert config.load()["lang"] == "en"

    def test_sans_terminal_le_menu_ne_boucle_pas(self, installation, capsys,
                                                  monkeypatch):
        """Sans terminal, le menu doit se refermer tout seul : sinon il
        affiche le meme ecran indefiniment."""
        monkeypatch.delenv("BOTW_ASSUME_OUI", raising=False)
        assert ui.run(config.load()) == 0
        assert "closes after one screen" in capsys.readouterr().out

    def test_stdin_ferme_le_menu_quitte(self, installation, monkeypatch,
                                        capsys):
        """stdin ferme (Ctrl+D, tache planifiee) alors que le terminal parait
        disponible : c'est le cas qui faisait boucler le menu a l'infini."""
        monkeypatch.setenv("BOTW_ASSUME_OUI", "1")
        monkeypatch.setattr(builtins, "input", _eof)
        assert ui.run(config.load()) == 0

    def test_stdin_ferme_ne_confirme_jamais(self, installation, monkeypatch):
        """Pas de reponse ne doit valoir accord : une confirmation par
        defaut a 'non' evite de detruire une sauvegarde sur un script."""
        from botw import i18n
        monkeypatch.setattr(builtins, "input", _eof)
        assert i18n.confirm("detruire ?") is False

    def test_ask_renvoie_none_sur_eof(self, monkeypatch):
        from botw import i18n
        monkeypatch.setenv("BOTW_ASSUME_OUI", "1")
        monkeypatch.setattr(builtins, "input", _eof)
        assert i18n.ask("nom ?", "defaut") is None


class TestLanceurs(object):
    def test_bat_en_ascii_crlf_sans_bom(self):
        chemin = os.path.join(RACINE, "botw.bat")
        data = open(chemin, "rb").read()
        assert data[:3] != b"\xef\xbb\xbf", "BOM : PowerShell 5.1 casse"
        assert all(c < 128 for c in data), "caractere non ASCII"
        assert b"\r\n" in data
        assert b"\n" not in data.replace(b"\r\n", b"")

    def test_py_ajoute_son_dossier_au_chemin(self):
        texte = io.open(os.path.join(RACINE, "botw.py"), encoding="utf-8").read()
        assert "sys.path.insert" in texte

    def test_module_executable(self):
        """python -m botw doit fonctionner depuis n'importe quel dossier."""
        r = subprocess.run([sys.executable, "-m", "botw", "--version"],
                           cwd=RACINE, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert "botw" in r.stdout

    def test_fonctionne_hors_du_dossier(self, tmp_path):
        r = subprocess.run([sys.executable, os.path.join(RACINE, "botw.py"),
                            "--version"],
                           cwd=str(tmp_path), capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


class TestRaccourcis(object):
    def test_help_de_chaque_sous_commande(self, installation, capsys):
        for cmd in ("lang", "doctor", "deploy", "profile", "mods", "tools",
                    "catalog", "coop", "newgame", "readme", "matrix"):
            with pytest.raises(SystemExit):
                cli.main([cmd, "--help"])
            out = capsys.readouterr().out
            assert out.strip(), cmd


class TestPartieAffichee(object):
    """L'ecran « Jouer » dit quelle partie va avec quel jeu de mods.

    C'est l'information qui manquait pour ne plus confondre deux profils :
    sans elle, un profil sans partie et un profil avec dix heures de jeu
    s'affichaient exactement pareil, et choisir le mauvais ne se decouvrait
    qu'apres avoir change les mods.
    """

    def test_profil_sans_partie(self, fausse_machine):
        i18n.set_lang("fr")
        assert ui._partie_de("sur") == i18n._("ui.partie.non")

    def test_profil_avec_partie(self, fausse_machine):
        from botw import config, newgame
        from conftest import ecrire
        i18n.set_lang("fr")
        ecrire(config.main_save_file(), "MA PARTIE")
        newgame.prepare("sur")
        assert ui._partie_de("sur") == i18n._("ui.partie.oui")
        assert ui._partie_de("boost") == i18n._("ui.partie.non")

    def test_archive_videe_ne_compte_pas(self, fausse_machine):
        """Une archive a moitie copiee n'est pas une partie."""
        import shutil
        from botw import config, newgame
        from conftest import ecrire
        i18n.set_lang("fr")
        ecrire(config.main_save_file(), "MA PARTIE")
        dest = newgame.prepare("sur")
        shutil.rmtree(os.path.join(dest, "user"))
        assert ui._partie_de("sur") == i18n._("ui.partie.non")

    def test_le_menu_se_construit(self, fausse_machine):
        """L'ecran ne doit pas planter meme sans aucun profil installe."""
        i18n.set_lang("fr")
        sauvegarde = i18n.menu
        i18n.menu = lambda options, question: None
        try:
            ui.sub_play({})
        finally:
            i18n.menu = sauvegarde
