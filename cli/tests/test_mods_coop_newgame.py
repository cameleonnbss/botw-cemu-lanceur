"""Mods, catalogue, coop, nouvelle partie, documentation, outils."""
import io
import json
import os
import re
import shutil
import zipfile

import pytest

from botw import (catalog, cli, config, coop, deploy, i18n, mods, newgame,
                   readme, tools, ui)
from conftest import ecrire


class TestBibliotheque(object):
    def test_lit_meta_yml(self, installation):
        faux = os.path.join(config.mods_store(), "Avec_Meta.zip")
        with zipfile.ZipFile(faux, "w") as zf:
            zf.writestr("meta.yml", "name: Mon Beau Mod\nversion: 1.2\n")
        assert mods._readable_name(faux) == "Mon Beau Mod"

    def test_sans_meta_yml_utilise_le_nom_du_fichier(self, installation):
        faux = os.path.join(config.mods_store(), "Pas_De_Meta.zip")
        with zipfile.ZipFile(faux, "w") as zf:
            zf.writestr("lisezmoi.txt", "rien")
        assert mods._readable_name(faux) == "Pas_De_Meta"

    def test_recherche_exacte(self, installation):
        assert mods.find("Relics_of_the_Past.zip") == "Relics_of_the_Past.zip"

    def test_recherche_sans_extension(self, installation):
        assert mods.find("Relics_of_the_Past") == "Relics_of_the_Past.zip"

    def test_recherche_par_morceau(self, installation):
        assert mods.find("linkle") == "The_Linkle_Mod_3.0.1.zip"

    def test_recherche_insensible_a_la_casse(self, installation):
        assert mods.find("RELICS") == "Relics_of_the_Past.zip"

    def test_recherche_inconnue(self, installation):
        assert mods.find("mod qui existe pas") is None

    def test_recherche_vide(self, installation):
        assert mods.find("") is None

    def test_human(self):
        assert mods.human(0) == "0.0 B"
        assert mods.human(1024) == "1.0 KB"
        assert mods.human(1536) == "1.5 KB"
        assert mods.human(None) == "0.0 B"

    def test_marque_les_mods_hors_bibliotheque(self, installation):
        from botw import profiles
        prof = profiles.load("boost")
        assert len(prof.hashes) == 3
        # les trois sont a la fois en magasin et dans la bibliotheque
        for _l, fn in prof.hashes.values():
            assert fn in mods.available()


class TestInstallUninstall(object):
    def test_desinstalle_par_edition_du_fichier(self, installation, monkeypatch):
        """On n'appelle jamais 'ukmm uninstall' : cette commande ecrit dans le
        profil actif et supprime le zip, ce qui casse les autres profils."""
        from botw import deploy
        appele = []

        def faux_run(args, cfg=None):
            appele.append(args)
            return 0, ""
        monkeypatch.setattr(deploy, "run_ukmm", faux_run)
        mods.uninstall("boost", "Ancient_Weaponry_Mark_II")
        assert not any(a[0] == "uninstall" for a in appele)

    def test_le_zip_reste_dans_le_stock(self, installation):
        mods.uninstall("boost", "Ancient_Weaponry_Mark_II")
        assert os.path.isfile(os.path.join(config.mods_store(),
                                           "Ancient_Weaponry_Mark_II.zip"))

    def test_le_profil_actif_est_restaure(self, installation):
        from botw import deploy
        assert deploy.read_active_profile() == "boost"
        mods.uninstall("boost", "Ancient_Weaponry_Mark_II")
        assert deploy.read_active_profile() == "boost"

    def test_mod_inconnu_leve(self, installation):
        with pytest.raises(ValueError):
            mods.uninstall("boost", "jamais-vu")

    def test_mod_absent_du_profil_ne_echoue_pas(self, installation):
        ecrire(os.path.join(config.profiles_dir(), "boost", "profile.yml"),
               "mods: {}\nload_order: []\n")
        mods.uninstall("boost", "Relics_of_the_Past.zip")


class TestCatalogue(object):
    def test_les_cinq_profils_du_lanceur(self):
        assert catalog.names()[:5] == ["boost", "sur", "combo", "flo", "secondwind"]

    def test_chaque_combinaison_reference_un_mod_reel(self):
        connus = set(profiles_priorite())
        for cle in catalog.names():
            _t, _d, liste, _n = catalog.CATALOG[cle]
            assert liste, cle
            for m in liste:
                assert m.endswith(".zip"), (cle, m)

    def test_sur_exclut_relics(self):
        """Relics of the Past casse des quetes : le profil 'sur' doit s'en
        passer, c'est tout l'interet du profil."""
        _t, _d, liste, _n = catalog.CATALOG["sur"]
        assert "Relics_of_the_Past.zip" not in liste

    def test_sur_contient_second_wind(self):
        _t, _d, liste, _n = catalog.CATALOG["sur"]
        assert any(m.startswith("Second_Wind") for m in liste)

    def test_nombre_de_fichiers_connu(self):
        for cle in catalog.names():
            assert catalog.CATALOG[cle][3] > 0, cle

    def test_recherche_insensible(self):
        assert catalog.get("BOOST") is not None
        assert catalog.get("inconnu") is None
        assert catalog.get(None) is None


def profiles_priorite():
    from botw import profiles
    return profiles.PRIORITY


class TestCoop(object):
    def test_lit_le_nombre_de_manettes(self, settings_xml):
        assert coop.read_pad_channels() == 1

    def test_pas_de_settings(self, fausse_machine):
        assert coop.read_pad_channels() is None

    def test_active_deux_manettes(self, settings_xml):
        assert coop.write_pad_channels(2)[0]
        assert coop.read_pad_channels() == 2

    def test_sauvegarde_le_fichier(self, settings_xml):
        coop.write_pad_channels(2)
        assert os.path.isfile(settings_xml + ".botw.bak")

    def test_tag_absent_ne_l_invente_pas(self, fausse_machine):
        """Ecrire au hasard dans un fichier de configuration peut faire
        planter Cemu au demarrage : on refuse."""
        ecrire(config.cemu_settings(), "<Config><content></content></Config>")
        ok, msg = coop.write_pad_channels(2)
        assert not ok
        assert coop.read_pad_channels() is None

    def test_fichier_absent_refuse(self, fausse_machine):
        ok, _msg = coop.write_pad_channels(2)
        assert not ok

    def test_desactive(self, settings_xml):
        coop.write_pad_channels(2)
        assert coop.disable()
        assert coop.read_pad_channels() == 1


class TestInstallerMods(object):
    """`botw installmods <fichier ou lien>` : ce que le joueur a sous la main.

    La bibliotheque locale ne connait que les mods deja vus, et la recherche
    GameBanana ne repond plus. Le raccourci qui manquait est donc : un .zip
    dans ses telechargements, ou le lien qu'il a trouve.
    """

    def _zip(self, dossier, nom="Test.zip", meta="meta.yml"):
        """Un zip de mod minimal mais plausible."""
        import zipfile
        chemin = os.path.join(dossier, nom)
        with zipfile.ZipFile(chemin, "w") as z:
            if meta:
                z.writestr(meta, "name: Test Mod\nversion: 1.0\n")
            else:
                z.writestr("lisezmoi.txt", "pas un mod")
        return chemin

    def test_installe_depuis_un_fichier_local(self, installation, tmp_path,
                                              monkeypatch):
        src = self._zip(str(tmp_path), "MonMod.zip")
        vus = []
        monkeypatch.setattr("botw.mods.install",
                            lambda p, q, cfg=None: vus.append((p, q)) or True)
        assert mods.installer_fichier("boost", src, None)
        assert vus == [("boost", "MonMod.zip")]
        assert os.path.isfile(
            os.path.join(installation["bureau"], "Mods", "MonMod.zip"))

    def test_copie_dans_la_bibliotheque(self, installation, tmp_path,
                                        monkeypatch):
        """Le fichier est recopie : UKMM sait le lire, et l'utilisateur garde
        le sien ou il est."""
        src = self._zip(str(tmp_path), "MonMod.zip")
        import shutil
        dest = os.path.join(installation["bureau"], "Mods", "MonMod.zip")
        shutil.copy2(src, dest)
        # On remet l'original : la copie doit suffire.
        os.remove(src)
        monkeypatch.setattr("botw.mods.install", lambda p, q, cfg=None: True)
        assert mods.installer_fichier("boost", dest, None)

    def test_n_ecrase_pas_un_mod_de_meme_nom(self, installation, tmp_path,
                                              monkeypatch):
        src = self._zip(str(tmp_path), "Mod.zip")
        deja = self._zip(str(installation["bureau"] / "Mods"), "Mod.zip")
        import shutil
        shutil.copy2(src, deja)
        vus = []
        monkeypatch.setattr("botw.mods.install",
                            lambda p, q, cfg=None: vus.append(q) or True)
        assert mods.installer_fichier("boost", src, None)
        assert vus and vus[0] != "Mod.zip", "le mod deja present a ete ecrase"
        assert os.path.isfile(deja)

    def test_un_zip_sans_meta_est_refuse(self, installation, tmp_path):
        src = self._zip(str(tmp_path), "PasUnMod.zip", meta=None)
        with pytest.raises(ValueError):
            mods.installer_fichier("boost", src, None)

    def test_le_faux_mod_n_est_pas_laisse_dans_la_bibliotheque(self, installation,
                                                              tmp_path):
        """Sinon 'botw mods list' repropose a chaque fois un fichier qui ne
        peut pas etre installe."""
        src = self._zip(str(tmp_path), "PasUnMod.zip", meta=None)
        with pytest.raises(ValueError):
            mods.installer_fichier("boost", src, None)
        assert not os.path.exists(
            os.path.join(installation["bureau"], "Mods", "PasUnMod.zip"))

    def test_meta_dans_un_sous_dossier_est_accepte(self, installation,
                                                   tmp_path, monkeypatch):
        """La plupart des zip de GameBanana ont un dossier racine."""
        import zipfile
        src = os.path.join(str(tmp_path), "Emballage.zip")
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("MonMod/meta.yml", "name: Test Mod\n")
        dest = os.path.join(installation["bureau"], "Mods", "Emballage.zip")
        import shutil
        shutil.copy2(src, dest)
        monkeypatch.setattr("botw.mods.install", lambda p, q, cfg=None: True)
        assert mods.installer_fichier("boost", dest, None)

    def test_un_zip_corrompu_est_refuse(self, installation, tmp_path):
        src = os.path.join(str(tmp_path), "Corrompu.zip")
        with io.open(src, "wb") as f:
            f.write(b"ce n'est pas un zip")
        import shutil
        shutil.copy2(src, os.path.join(installation["bureau"], "Mods",
                                       "Corrompu.zip"))
        with pytest.raises(ValueError):
            mods.installer_fichier("boost", src, None)

    def test_source_inconnue_donne_un_message_clair(self, installation):
        with pytest.raises(ValueError) as e:
            mods.installer_fichier("boost", "C:/nulle/partie/x.zip", None)
        assert "x.zip" in str(e.value)

    def test_le_telechargement_eteleve_une_page_web(self, installation,
                                                   monkeypatch):
        """Un lien vers une page web donne du HTML. Le refuser evite de le
        coincer dans la bibliotheque."""
        import io as _io

        class _Faux(object):
            def __init__(self, data):
                self.data = data

            def read(self):
                return self.data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda *a, **k: _Faux(b"<html>page</html>"))
        with pytest.raises(ValueError):
            mods.installer_fichier("boost", "https://exemple/page", None)
        assert not os.path.exists(
            os.path.join(installation["bureau"], "Mods", "page.zip"))

    def test_le_telechargement_pose_un_vrai_zip(self, installation,
                                                monkeypatch):
        src = self._zip(str(installation["racine"]), "Telecharge.zip")

        class _Faux(object):
            def read(self):
                with io.open(src, "rb") as f:
                    return f.read()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen",
                            lambda *a, **k: _Faux())
        vus = []
        monkeypatch.setattr("botw.mods.install",
                            lambda p, q, cfg=None: vus.append(q) or True)
        assert mods.installer_fichier("boost", "https://exemple/Telecharge.zip",
                                      None)
        assert vus == ["Telecharge.zip"]

    def test_un_lien_mort_donne_un_message_lisible(self, installation,
                                                    monkeypatch):
        import urllib.error
        import urllib.request

        def _explode(*a, **k):
            raise urllib.error.URLError("dns")
        monkeypatch.setattr(urllib.request, "urlopen", _explode)
        with pytest.raises(ValueError) as e:
            mods.installer_fichier("boost", "https://exemple/x.zip", None)
        assert "exemple" in str(e.value)


class TestCommandeInstallMods(object):
    """La commande exposee : options, profil cible, code de sortie."""

    def _args(self, argv):
        return cli.build_parser().parse_args(argv)

    def test_un_argument_source(self):
        assert self._args(["installmods", "x.zip"]).source == "x.zip"

    def test_par_defaut_le_profil_actif(self, fausse_machine, monkeypatch):
        vus = {}
        monkeypatch.setattr("botw.mods.installer_fichier",
                            lambda p, s, cfg=None: vus.update(p=p, s=s))
        monkeypatch.setattr("botw.profiles.active", lambda: "sur")
        monkeypatch.setattr("botw.profiles.existing", lambda: ["sur"])
        args = self._args(["installmods", "x.zip"])
        assert cli.cmd_installmods(args, {}) == 0
        assert vus == {"p": "sur", "s": "x.zip"}

    def test_un_profil_choisi_prime(self, fausse_machine, monkeypatch):
        vus = {}
        monkeypatch.setattr("botw.mods.installer_fichier",
                            lambda p, s, cfg=None: vus.update(p=p))
        monkeypatch.setattr("botw.profiles.existing", lambda: ["sur", "boost"])
        args = self._args(["installmods", "x.zip", "-p", "boost"])
        assert cli.cmd_installmods(args, {}) == 0
        assert vus["p"] == "boost"

    def test_profil_inconnu_sort_en_erreur(self, fausse_machine, monkeypatch,
                                           capsys):
        monkeypatch.setattr("botw.profiles.existing", lambda: ["sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "sur")
        args = self._args(["installmods", "x.zip", "-p", "inexistant"])
        assert cli.cmd_installmods(args, {}) == 1

    def test_echec_de_copie_sort_en_erreur(self, fausse_machine, monkeypatch,
                                           capsys):
        def _boom(p, s, cfg=None):
            raise ValueError("pas un mod")
        monkeypatch.setattr("botw.mods.installer_fichier", _boom)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "sur")
        args = self._args(["installmods", "x.zip"])
        assert cli.cmd_installmods(args, {}) == 1
        assert "pas un mod" in capsys.readouterr().out


class TestNouvellePartie(object):
    def test_aucune_partie(self, fausse_machine):
        assert not newgame.has_game()
        assert newgame.prepare() is None

    def test_archive_la_partie(self, fausse_machine):
        slot = config.save_root()
        ecrire(config.main_save_file(), "SAUVEGARDE CHIFFREE")
        dest = newgame.prepare(profile="boost")
        assert dest and os.path.isdir(dest)
        assert io.open(os.path.join(dest, "user", "80000001", "0",
                                    "game_data.sav"),
                       encoding="utf-8").read() == "SAUVEGARDE CHIFFREE"

    def test_l_emplacement_est_vide_apres(self, fausse_machine):
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare()
        assert not newgame.has_game()
        assert os.path.isdir(config.save_root())

    def test_index_ecrit(self, fausse_machine):
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare(profile="sur")
        lignes = newgame.read_index()
        assert len(lignes) == 1
        assert lignes[0]["profil"] == "sur"

    def test_index_separe_de_celu_du_gestionnaire(self, index_parties, fausse_machine):
        """Le gestionnaire PowerSQL tient deja un parties.json : le nouvel
        index ne doit pas le-ecraser."""
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare()
        with io.open(index_parties, encoding="utf-8") as f:
            assert json.load(f)[0]["nom"] == "reference"
        assert newgame._index_path() != index_parties

    def test_revert(self, fausse_machine):
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare(profile="boost")
        ecrire(config.main_save_file(), "NOUVELLE")
        assert newgame.revert(force=True)
        assert io.open(config.main_save_file(), encoding="utf-8").read() == "SAUVEGARDE"

    def test_revert_refuse_sans_confirmation(self, fausse_machine, monkeypatch):
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare()
        ecrire(config.main_save_file(), "NOUVELLE")
        import builtins
        monkeypatch.setattr(builtins, "input", lambda _p="": "n")
        assert newgame.revert() is None
        assert io.open(config.main_save_file(), encoding="utf-8").read() == "NOUVELLE"

    def test_revert_sans_archive(self, fausse_machine):
        assert newgame.revert() is None

    def test_statut_sans_jeu(self, fausse_machine, capsys):
        newgame.status()
        assert capsys.readouterr().out.strip() != ""

    def test_revert_dans_un_emplacement_vide(self, fausse_machine):
        """Regression : le cas exact que `newgame` laisse derriere lui.

        `prepare` laisse un emplacement VIDE mais existant. Restaure dans
        ce dossier, `shutil.move(archive, emplacement)` glisse l'archive
        DANS l'emplacement : la partie se retrouve un niveau trop bas, et
        Cemu n'en voit plus aucune. La commande annoncait pourtant la
        restauration - c'est le pire genre de succes trompeur, parce que
        l'utilisateur croit sa partie sauve.
        """
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare()
        assert not newgame.has_game()
        assert newgame.revert(force=True)
        # la partie doit etre DIRECTEMENT dans l'emplacement
        assert io.open(config.main_save_file(), encoding="utf-8").read() == "SAUVEGARDE"
        assert newgame.has_game()
        # Aucun sous-dossier parasite : la partie est DIRECTEMENT dans
        # l'emplacement. `meta` y est attendu - c'est l'icone du jeu, et
        # `prepare` reconstruit un emplacement structuré pour que Cemu
        # sache l'ouvrir meme sans partie.
        contenu = sorted(os.listdir(config.save_root()))
        assert contenu == ["meta", "user"], contenu
        assert not os.path.isdir(os.path.join(config.save_root(), "user",
                                              "user"))

    def test_revert_conserve_meta(self, fausse_machine):
        """Le dossier `meta` accompagne la partie : il doit revenir aussi."""
        slot = config.save_root()
        ecrire(config.main_save_file(), "SAUVEGARDE")
        ecrire(os.path.join(slot, "meta", "meta.xml"), "<meta/>")
        newgame.prepare()
        assert newgame.revert(force=True)
        assert io.open(os.path.join(slot, "meta", "meta.xml"),
                       encoding="utf-8").read() == "<meta/>"

    def test_revert_idempotent_sur_index(self, fausse_machine):
        """Apres un revert reussi, l'archive sort de l'index."""
        ecrire(config.main_save_file(), "SAUVEGARDE")
        newgame.prepare()
        assert len(newgame.read_index()) == 1
        assert newgame.revert(force=True)
        assert newgame.read_index() == []


class TestNouvellePartieCli(object):
    """`botw newgame -y` doit etre accepte.

    Regression : l'option etait documentee et implementee dans
    newgame.execute, mais pas declaree sur le sous-analyseur. argparse
    rejetait donc `-y` avant que la commande ne le voie, et l'utilisateur
    devait repondre a une question a laquelle il ne pouvait pas repondre
    depuis un script.
    """

    def test_le_moins_y_est_accepte(self):
        from botw import cli
        args = cli.build_parser().parse_args(["newgame", "-y"])
        assert args.yes is True

    def test_le_yes_long_est_accepte(self):
        from botw import cli
        args = cli.build_parser().parse_args(["newgame", "--yes"])
        assert args.yes is True

    def test_sans_option_le_moins_y_est_faux(self):
        from botw import cli
        args = cli.build_parser().parse_args(["newgame", "status"])
        assert args.yes is False
        assert args.rest == ["status"]

    def test_le_moins_y_arrive_a_la_commande(self, fausse_machine, monkeypatch):
        """cmd_newgame doit retransmettre -y a newgame.execute."""
        from botw import cli
        vu = {}

        def faux_execute(rest):
            vu["rest"] = list(rest)
            return True

        monkeypatch.setattr(newgame, "execute", faux_execute)
        ecrire(config.main_save_file(), "SAUVEGARDE")
        args = cli.build_parser().parse_args(["newgame", "-y"])
        assert cli.cmd_newgame(args, config.load()) == 0
        assert "-y" in vu["rest"]

    def test_sans_option_le_moins_y_n_est_pas_ajoute(self, fausse_machine,
                                                     monkeypatch):
        from botw import cli
        vu = {}
        monkeypatch.setattr(newgame, "execute",
                            lambda rest: vu.setdefault("rest", list(rest)) or True)
        args = cli.build_parser().parse_args(["newgame", "revert"])
        assert cli.cmd_newgame(args, config.load()) == 0
        assert vu["rest"] == ["revert"]

    def test_reellement_aucune_question_posee(self, fausse_machine, capsys):
        """Le vrai chemin : `botw newgame -y` agit sans lire l'entree."""
        import botw.cli as cli

        ecrire(config.main_save_file(), "SAUVEGARDE")
        rc = cli.main(["newgame", "-y"])
        assert rc == 0
        assert not newgame.has_game()
        assert newgame.read_index()


class TestReadme(object):
    def test_trouve_le_readme(self):
        assert readme.exists("en")
        assert readme.exists("fr")

    def test_langue_inconnue(self):
        assert readme.find("de") is None

    def test_affiche(self, capsys):
        assert readme.show("fr", pager=False)
        assert "botw" in capsys.readouterr().out

    def test_fichier_absent_signale(self, fausse_machine, monkeypatch):
        monkeypatch.setattr(readme, "search_roots", lambda: [])
        assert not readme.show("en", pager=False)


class TestOutils(object):
    def test_ukmm_absent_signale(self, fausse_machine):
        etat = tools.ukmm_state()
        assert not etat["installed"]

    def test_version_lue_dans_le_changelog(self, tmp_path):
        ecrire(str(tmp_path / "CHANGELOG.md"),
               "# Changelog\n\n## [0.17.1] 2026-07-01\n\n- chose\n")
        assert tools.ukmm_version(str(tmp_path)) == "0.17.1"

    def test_version_absente(self, tmp_path):
        assert tools.ukmm_version(str(tmp_path)) == ""

    def test_ukmm_present_est_reconnu(self, fausse_machine):
        exe = config.ukmm_exe()
        ecrire(exe, "PE")
        ecrire(os.path.join(os.path.dirname(exe), "CHANGELOG.md"),
               "# Changelog\n\n## [0.17.1] 2026-07-01\n")
        etat = tools.ukmm_state()
        assert etat["installed"] and etat["version"] == "0.17.1"

    def test_script_bcml_sans_sudo(self):
        """La recette BCML ne doit appeler ni sudo ni apt-get install : elle
        s'execute dans un WSL partage, avec un utilisateur normal. On ignore
        les commentaires, qui parlent justement de ne pas utiliser sudo."""
        commandes = [l.strip() for l in tools._BCML_SCRIPT.splitlines()
                     if l.strip() and not l.strip().startswith("#")]
        assert not any(l.startswith(("sudo", "apt-get", "apt "))
                       for l in commandes), commandes
        assert "bcml-venv" in tools._BCML_SCRIPT

    def test_assets_ukmm_connus(self):
        assert tools.UKMM_ASSET in ("ukmm-x86_64-pc-windows-msvc.zip",)
        assert "windows" in tools.UKMM_ASSET

    def test_human(self):
        assert tools.mods_human(1024) == "1.0 KB"


class TestRaccourcisDeLangue(object):
    """Les locales sont ecrites sans accents (ASCII) pour rester lisibles
    dans une console Windows : on ne peut donc pas les relire a l'ceil nu.
    On cherche des mots francais entiers. Volontairement absent :
    « Sauv- », parce que Sauvegardes/ est un vrai nom de dossier - un chemin
    legitime ne doit pas etre signale comme du francais.
    """

    _MOTIFS = re.compile(
        r"\b(?:avec|pour|les|des|une|vous|votre|cette|dans|faut|aussi|est|"
        r"sont|pas|qui|que|aucun|aucune|etre|meme|probleme|seulement|choix|"
        r"profil)\b"
        r"|\b(?:repon|deploi|fusionn)\w*", re.I)

    def _francais(self, texte):
        return bool(self._MOTIFS.search(texte))

    def test_le_detecteur_reconnait_le_francais(self):
        """Un detecteur qui ne trouve rien ne prouve rien : on le met en
        echec sur du francais reel avant de l'appliquer aux 349 cles."""
        for phrase in ("Le profil actif est entierement fusionne et deploye",
                       "Repondez par oui ou non",
                       "aucun pack graphique actif",
                       "la sauvegarde vient de 'sur' et 'boost' est actif"):
            assert self._francais(phrase), phrase

    def test_le_detecteur_laisse_passer_l_anglais(self):
        for phrase in ("Verification found 2 problem(s).",
                       "Nothing to fix: no pack can stop the loading.",
                       "save folder: Sauvegardes/NouvellePartie",
                       "LOADING BLOCKER: ExtendedMemory - needs the game"
                       " recompiled",
                       "the UKMM pack is active:"
                       " graphicPacks/BreathOfTheWild_UKMM"):
            assert not self._francais(phrase), phrase

    def test_aucune_chaine_ne_reste_en_francais_en_mode_anglais(self):
        """Toutes les chaines 'en' doivent etre en anglais : on verifie
        qu'aucune n'a ete laissee en francais par megarde."""
        with io.open(os.path.join(i18n.LOCALES, "en.json"), encoding="utf-8") as f:
            en = json.load(f)
        suspects = [k for k, v in en.items() if self._francais(v)]
        assert not suspects, suspects

    def test_les_deux_locales_ont_le_meme_nombre_de_cles(self):
        """Une cle presente dans une seule langue s'affiche brute dans
        l'autre : le menu devient illisible au lieu d'echouer."""
        with io.open(os.path.join(i18n.LOCALES, "en.json"), encoding="utf-8") as f:
            en = set(json.load(f))
        with io.open(os.path.join(i18n.LOCALES, "fr.json"), encoding="utf-8") as f:
            fr = set(json.load(f))
        assert en == fr, sorted(en ^ fr)

    def test_aucune_chaine_ne_reste_en_anglais_en_mode_francais(self):
        with io.open(os.path.join(i18n.LOCALES, "fr.json"), encoding="utf-8") as f:
            fr = json.load(f)
        for cle in ("doctor.title", "deploy.done", "ui.welcome", "coop.title"):
            assert fr[cle] != cle


# --- une partie par jeu de mods --------------------------------------------
#
# Le joueur veut souvent deux jeux de mods et deux parties : une partie tres
# avancee avec peu de mods, et une partie neuve avec tous les mods. Ce qui
# rendait ca impossible, c'est que changer de profil ne touchait pas a
# l'emplacement de sauvegarde : le profil change, la partie restait, et plus
# rien ne pouvait la charger.
#
# `basculer` fait les deux ensemble, et l'ordre est la securite entiere :
# la partie part a l'archive AVANT le deploiement. Si le deploiement echoue,
# elle est deja de cote.

class _Deploie(object):
    """Faux deploiement : on note l'ordre des etapes, sans toucher UKMM."""

    def __init__(self, echoue=False):
        self.echoue = echoue
        self.appele = False
        self.avant = None      # la partie etait-elle encore la ? au deploiement

    def __call__(self, profil, cfg=None, quiet=False):
        from botw import deploy as vrai
        self.appele = True
        self.avant = newgame.has_game()
        if self.echoue:
            raise vrai.GuardError("deploiement refuse", 2)
        os.makedirs(os.path.join(config.graphic_pack(), "content"),
                    exist_ok=True)
        return {"profile": profil, "deployed": 0, "merged": 0}


class _Actif(object):
    """Le profil actif, variable comme dans la vraie vie.

    Un `lambda: "boost"` fige ment `basculer` : apres une bascule reussie, le
    profil actif change, et c'est meme ce que UKMM fait. Les tests qui
    enchainent deux bascules doivent donc le bouger.
    """

    def __init__(self, nom):
        self.nom = nom

    def __call__(self):
        return self.nom


class TestBasculeDePartie(object):

    def test_profil_inconnu_ne_touche_a_rien(self, fausse_machine):
        ecrire(config.main_save_file(), "MA PARTIE")
        assert not newgame.basculer("inconnu", force=True)
        assert newgame.has_game(), "la partie a disparu"

    def test_refuse_pendant_que_cemu_tourne(self, fausse_machine,
                                            monkeypatch):
        from botw import deploy
        monkeypatch.setattr(deploy, "processes_named", lambda n: ["Cemu.exe"])
        ecrire(config.main_save_file(), "MA PARTIE")
        assert not newgame.basculer("boost", force=True)
        assert newgame.has_game(), "la partie a disparu"

    def test_archives_avant_de_deployer(self, fausse_machine, monkeypatch):
        """L'ordre est la securite : le deploiement ne doit jamais voir la
        partie d'origine, et celle-ci doit deja etre archivee quand il
        s'execute."""
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        ecrire(config.main_save_file(), "MA PARTIE")
        assert newgame.basculer("sur", force=True)
        assert faux.appele
        assert faux.avant is False, "le deploiement a vu une partie"
        archives = [p for p in newgame.parties() if p["existe"]]
        assert len(archives) == 1
        assert io.open(os.path.join(archives[0]["path"], "user", "80000001",
                                    "0", "game_data.sav"),
                       encoding="utf-8").read() == "MA PARTIE"

    def test_la_partie_archives_est_taguee_du_profil_courant(
            self, fausse_machine, monkeypatch):
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        ecrire(config.main_save_file(), "MA PARTIE")
        newgame.basculer("sur", force=True)
        assert newgame.parties()[0]["profil"] == "boost"

    def test_deploiement_echoue_ne_perd_pas_la_partie(
            self, fausse_machine, monkeypatch):
        faux = _Deploie(echoue=True)
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        ecrire(config.main_save_file(), "MA PARTIE")
        assert not newgame.basculer("sur", force=True)
        # la partie est de cote, et encore lisible
        archives = [p for p in newgame.parties() if p["existe"]]
        assert len(archives) == 1
        assert io.open(os.path.join(archives[0]["path"], "user", "80000001",
                                    "0", "game_data.sav"),
                       encoding="utf-8").read() == "MA PARTIE"
        assert newgame.revert(force=True)
        assert io.open(config.main_save_file(),
                       encoding="utf-8").read() == "MA PARTIE"

    def test_profil_sans_partie_propose_une_nouvelle(
            self, fausse_machine, monkeypatch):
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        ecrire(config.main_save_file(), "MA PARTIE")
        assert newgame.basculer("sur", force=True)
        assert not newgame.has_game(), "Cemu doit trouver un emplacement vide"
        assert os.path.isdir(config.save_root())

    def test_revenir_en_arriere_retrouve_la_partie(self, fausse_machine,
                                                   monkeypatch):
        """Le test qui compte : A -> B -> A doit rendre la partie de A, intacte."""
        faux = _Deploie()
        actif = _Actif("boost")
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", actif)
        ecrire(config.main_save_file(), "PARTIE DE A")
        assert newgame.basculer("sur", force=True)
        actif.nom = "sur"          # UKMM bascule vraiment, lui aussi
        ecrire(config.main_save_file(), "PARTIE DE B")
        actif.nom = "sur"
        assert newgame.basculer("boost", force=True)
        assert io.open(config.main_save_file(),
                       encoding="utf-8").read() == "PARTIE DE A"
        # B n'a pas disparu pour autant : sa partie est reste de cote, et
        # elle aussi est retrouvable. ('revert' consomme l'archive qu'il
        # remet en place : la partie revient dans l'emplacement de Cemu,
        # elle n'est pas supprimee.)
        b = [p for p in newgame.parties() if p["existe"]]
        assert len(b) == 1
        assert io.open(os.path.join(b[0]["path"], "user", "80000001", "0",
                                    "game_data.sav"),
                       encoding="utf-8").read() == "PARTIE DE B"

    def test_partie_du_profil_retrouvee(self, fausse_machine):
        ecrire(config.main_save_file(), "A")
        newgame.prepare("boost")
        ecrire(config.main_save_file(), "B")
        newgame.prepare("sur")
        assert newgame._partie_du_profil("sur")["profil"] == "sur"
        assert newgame._partie_du_profil("boost")["profil"] == "boost"
        assert newgame._partie_du_profil("combo") is None

    def test_archive_manquante_ignoree(self, fausse_machine):
        """Une archive fantome ne doit pas bloquer : on propose du neuf."""
        import shutil
        ecrire(config.main_save_file(), "A")
        dest = newgame.prepare("boost")
        shutil.rmtree(os.path.join(dest, "user"))
        assert newgame._partie_du_profil("boost") is None
        assert [p for p in newgame.parties() if not p["existe"]]

    def test_nombre_de_parties(self, fausse_machine):
        ecrire(config.main_save_file(), "A")
        newgame.prepare("boost")
        ecrire(config.main_save_file(), "B")
        newgame.prepare("sur")
        assert len(newgame.parties()) == 2


class TestDejaPret(object):
    """Rejouer sa partie du jour ne doit pas couter une re-fusion.

    Le cas le plus frequent n'est pas « je change de jeu de mods », c'est
    « je veux rejouer ma partie principale » : le profil est deja actif, la
    partie lui appartient, le deploiement est complet. Sans court-circuit,
    chaque relance coute deux minutes de remerge pour un jeu identique.
    """

    def _deployed(self, monkeypatch, profil, n=7, aoc=True):
        """Simule un profil entierement deploye (n fichiers des deux cotes).

        `aoc` reproduit le cas reel du profil 'sur' : la fusion contient un
        dossier `aoc` a cote de `content`. Comparer `content` a la fusion
        entiere donnerait alors un compte faux, et le court-circuit ne prendrait
        jamais - c'est exactement le bug que ce parametre empeche de revenir.
        """
        gp = config.graphic_pack()
        os.makedirs(gp, exist_ok=True)
        ecrire(os.path.join(gp, "rules.txt"), "rules")
        for sous in ("content",) + (("aoc",) if aoc else ()):
            for racine in (os.path.join(gp, sous),
                           deploy.merged_dir(profil) + os.sep + sous):
                os.makedirs(racine, exist_ok=True)
                # Le nom porte le sous-dossier : sinon `content/f0` et
                # `aoc/f0` sont deux fois le meme nom, et supprimer l'un
                # laisse l'autre : on croit avoir retire un fichier de la
                # fusion alors qu'il est toujours la.
                for i in range(n):
                    ecrire(os.path.join(racine, "%s-f%d" % (sous, i)), "x")

    def test_le_pack_entier_compte_son_rules_txt(self, fausse_machine,
                                                 monkeypatch):
        """Le pack chez Cemu contient rules.txt en plus ; la fusion, non."""
        self._deployed(monkeypatch, "boost", n=7)
        assert newgame._deploiement_complet("boost")

    def test_profil_deja_actif_ne_remerge_pas(self, fausse_machine,
                                              monkeypatch):
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        self._deployed(monkeypatch, "boost")
        assert newgame.basculer("boost", force=True)
        assert not faux.appele, "un remerge a ete refait pour rien"

    def test_profil_deja_actif_avec_sa_partie(self, fausse_machine,
                                              monkeypatch):
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        self._deployed(monkeypatch, "boost")
        ecrire(config.main_save_file(), "MA PARTIE")
        assert newgame.basculer("boost", force=True)
        assert not faux.appele
        assert io.open(config.main_save_file(),
                       encoding="utf-8").read() == "MA PARTIE", "partie touchee"

    def test_deploiement_incomplet_remerge_quand_meme(self, fausse_machine,
                                                      monkeypatch):
        """Le court-circuit ne dispense d'aucune verification : si le profil
        n'est pas entierement deploye, on repasse par la voie normale."""
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        gp = config.graphic_pack()
        os.makedirs(os.path.join(gp, "content"), exist_ok=True)
        ecrire(os.path.join(gp, "rules.txt"), "rules")
        ecrire(os.path.join(gp, "content", "seulement-un"), "x")   # 1 sur 14
        # La fusion, elle, a bien ses 14 fichiers.
        for sous in ("content", "aoc"):
            for i in range(7):
                ecrire(os.path.join(deploy.merged_dir("boost"), sous,
                                    "f%d" % i), "x")
        assert not newgame._deploiement_complet("boost")
        assert newgame.basculer("boost", force=True)
        assert faux.appele, "un deploiement incomplet doit etre refait"

    def test_partie_d_un_autre_profil_bascule_quand_meme(self, fausse_machine,
                                                          monkeypatch):
        """Le profil actif est le bon, mais la partie chargee vient d'ailleurs :
        c'est exactement le plantage a l'ecran de chargement. Ca doit basculer."""
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        self._deployed(monkeypatch, "boost")
        # La partie appartient a 'sur' : on le note dans l'historique.
        newgame.noter_profil("sur")
        ecrire(config.main_save_file(), "PARTIE DE SUR")
        assert newgame.profil_de_la_partie() == "sur"
        assert newgame.basculer("boost", force=True)
        assert faux.appele, "il fallait basculer, pas court-circuiter"
        assert not newgame.has_game(), "la partie de sur doit etre mise de cote"

    def test_compte_les_fichiers_du_bon_repertoire(self, fausse_machine,
                                                   monkeypatch):
        self._deployed(monkeypatch, "boost", n=7)
        assert newgame._deploiement_complet("boost")
        # Un fichier de trop : le deploiement est un SUR-ENSEMBLE, donc il
        # reste complet. Le jeu y trouve tout ce qu'il attend.
        ecrire(os.path.join(config.graphic_pack(), "content", "en trop"), "x")
        assert newgame._deploiement_complet("boost")
        # ... mais un fichier fusionne MANQUANT, la, c'est incomplet.
        os.remove(os.path.join(config.graphic_pack(), "content", "content-f0"))
        assert not newgame._deploiement_complet("boost")

    def test_un_surplus_ne_redemande_pas_de_remerge(self, fausse_machine,
                                                     monkeypatch):
        """UKMM laisse deriver des fichiers d'une fusion anterieure.

        Le cas reel : 5614 fichiers deployes pour 5477 fusionnes. Un compte
        strict jugeait ca incomplet, donc CHAQUE `botw jeu sur` refaisait une
        re-fusion de plusieurs dizaines de secondes - pour un jeu deja en
        place. Le surplus ne manque a rien : il ne doit pas non plus faire
        redonder le deploiement.
        """
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        self._deployed(monkeypatch, "boost", n=7)
        for i in range(3):      # trois fichiers d'une fusion anterieure
            ecrire(os.path.join(config.graphic_pack(), "content",
                                "ancien%d" % i), "x")
        assert newgame._deploiement_complet("boost")
        assert newgame.basculer("boost", force=True)
        assert not faux.appele, "un surplus a provoke une re-fusion"

    def test_un_surplus_ne_cache_pas_un_manquant(self, fausse_machine,
                                                  monkeypatch):
        """Le surplus ne pardonne pas un fichier fusionne manquant."""
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        self._deployed(monkeypatch, "boost", n=7)
        for i in range(5):
            ecrire(os.path.join(config.graphic_pack(), "content",
                                "ancien%d" % i), "x")
        # ... mais un fichier de la fusion disparait du pack.
        os.remove(os.path.join(config.graphic_pack(), "content", "content-f0"))
        assert not newgame._deploiement_complet("boost")

    def test_aoc_manquant_ne_passe_pas(self, fausse_machine, monkeypatch):
        """Un dossier `aoc` non depose est un deploiement incomplet."""
        import shutil
        self._deployed(monkeypatch, "boost", n=7)
        assert newgame._deploiement_complet("boost")
        shutil.rmtree(os.path.join(config.graphic_pack(), "aoc"))
        assert not newgame._deploiement_complet("boost")


class TestLancementSansDoubleDeploiement(object):
    """`botw jeu X --lancer` ne doit pas re-fusionner deux fois.

    `newgame.basculer` finit par un deploiement ; repasser ensuite par
    `ui.launch` en refaisait un deuxième, deux minutes perdues.
    """

    def test_le_cli_passe_le_drapeau(self, fausse_machine, monkeypatch):
        vu = {}

        def faux_launch(profil, cfg, deja_deploye=False):
            vu["profil"] = profil
            vu["deja"] = deja_deploye
            return 0

        monkeypatch.setattr("botw.ui.launch", faux_launch)
        monkeypatch.setattr("botw.newgame.basculer",
                            lambda p, cfg=None, force=False: True)
        monkeypatch.setattr("botw.config.save", lambda cfg: None)
        args = cli.build_parser().parse_args(["jeu", "sur", "--lancer", "-y"])
        assert cli.cmd_jeu(args, {"game_profile": "boost"}) == 0
        assert vu == {"profil": "sur", "deja": True}

    def _jouer(self, monkeypatch, actif, choisi):
        """Joue le sous-menu 'jeu' en choisissant `choisi` dans la liste.

        Renvoie la liste des (profil, deja_deploye) vus par `ui.launch`.
        """
        vu = []

        def faux_launch(profil, cfg, deja_deploye=False):
            vu.append((profil, deja_deploye))
            return 1          # valeur non nulle : le sous-menu s'arrete

        disponibles = [actif] + [p for p in ("boost", "sur") if p != actif]
        index = disponibles.index(choisi)
        monkeypatch.setattr("botw.ui.launch", faux_launch)
        monkeypatch.setattr("botw.newgame.basculer",
                            lambda p, cfg=None, force=False: True)
        monkeypatch.setattr("botw.config.save", lambda cfg: None)
        monkeypatch.setattr("botw.profiles.existing", lambda: disponibles)
        monkeypatch.setattr("botw.profiles.active", lambda: actif)
        monkeypatch.setattr("botw.profiles.load", lambda p: _FauxProfil(1))
        monkeypatch.setattr("botw.i18n.menu",
                            lambda options, question=None: index)
        ui.sub_play({"game_profile": actif})
        return vu

    def test_menu_profil_actif_redemande_un_deploiement(self, fausse_machine,
                                                        monkeypatch):
        """Rien a basculer : `launch` doit deployer comme d'habitude."""
        assert self._jouer(monkeypatch, "sur", "sur") == [("sur", False)]

    def test_menu_apres_bascule_ne_redeploye_pas(self, fausse_machine,
                                                  monkeypatch):
        assert self._jouer(monkeypatch, "sur", "boost") == [("boost", True)]


class _FauxProfil(object):
    def __init__(self, n):
        self.hashes = list(range(n))

    def files_count(self):
        return len(self.hashes)


class TestNomDePartie(object):
    """Une partie archivee doit garder son nom lisible.

    Le dossier d'archive s'appelle partie_<date> : sans nom, l'utilisateur
    voit une suite de chiffres et ne sait plus laquelle est sa vraie partie.
    """

    def test_nom_enregistre(self, fausse_machine):
        ecrire(config.main_save_file(), "MA PARTIE")
        newgame.prepare("secondwind", nom="Principale Second Wind")
        assert newgame.parties()[0]["nom"] == "Principale Second Wind"

    def test_sans_nom_la_chaine_vide(self, fausse_machine):
        ecrire(config.main_save_file(), "MA PARTIE")
        newgame.prepare("boost")
        assert newgame.parties()[0]["nom"] == ""

    def test_nom_conserve_apres_bascule(self, fausse_machine, monkeypatch):
        faux = _Deploie()
        monkeypatch.setattr("botw.deploy.deploy", faux)
        monkeypatch.setattr("botw.profiles.existing", lambda: ["boost", "sur"])
        monkeypatch.setattr("botw.profiles.active", lambda: "boost")
        ecrire(config.main_save_file(), "PARTIE DE A")
        newgame.basculer("sur", force=True)
        noms = [p["nom"] for p in newgame.parties() if p["existe"]]
        assert noms == [""], "une bascule ne doit pas inventer de nom"
        # le nom survit a une relecture complete de l'index
        assert newgame.read_index()[0]["nom"] == ""

class TestRestaurationAuBonEndroit(object):
    """Regression : la partie doit atterrir LA ou Cemu la cherche.

    Le cas reproduit est celui de la vraie machine. Apres un `newgame`,
    l'emplacement est vide ; Cemu le relance, il recree `user/80000001/0/` et
    `user/common/`. La touche 1 restaure alors la partie principale dans un
    emplacement qui n'est plus vide, et le `shutil.move` glissait l'archive
    DANS le `user` deja present :

        .../101c9500/user/user/80000001/0/game_data.sav

    Cemu ne la voyait pas : nouvelle partie au lieu de la tienne, et plantage
    en lisant le compte - alors que la commande annoncait "Previous game
    restored".
    """

    @staticmethod
    def _emplacement_avec_user():
        """L'emplacement dans l'etat ou Cemu le laisse apres un lancement."""
        for sous in ("user/80000001/0", "user/common", "meta/meta"):
            os.makedirs(os.path.join(config.save_root(), *sous.split("/")),
                        exist_ok=True)
        ecrire(os.path.join(config.save_root(), "user", "80000001", "0",
                            "caption.sav"), "NEUF")

    @staticmethod
    def _archive():
        ecrire(config.main_save_file(), "MA PARTIE")
        archive = newgame.prepare("secondwind")
        assert archive, "aucune archive produite"
        return archive

    def test_emplacement_vide(self, fausse_machine):
        archive = self._archive()
        shutil.rmtree(config.save_root(), ignore_errors=True)
        os.makedirs(config.save_root(), exist_ok=True)
        assert newgame.revert(archive, force=True)
        assert os.path.isfile(config.main_save_file())

    def test_emplacement_deja_peuple_par_cemu(self, fausse_machine):
        """LE CAS REEL : l'emplacement contient deja `user/`."""
        archive = self._archive()
        self._emplacement_avec_user()
        assert newgame.revert(archive, force=True)
        assert os.path.isfile(config.main_save_file()), (
            "partie invisible pour le jeu : elle a ete mise dans %s"
            % os.path.join(config.save_root(), "user", "user"))

    def test_aucun_niveau_en_trop(self, fausse_machine):
        archive = self._archive()
        self._emplacement_avec_user()
        assert newgame.revert(archive, force=True)
        en_trop = os.path.join(config.save_root(), "user", "user")
        assert not os.path.exists(en_trop), (
            "l'archive a ete glissee dans le `user` existant : %s" % en_trop)

    def test_la_partie_reste_chargeable(self, fausse_machine):
        archive = self._archive()
        self._emplacement_avec_user()
        assert newgame.revert(archive, force=True)
        assert newgame.has_game()
        assert newgame.profil_de_la_partie() == "secondwind", (
            "la partie restauree doit rester attribuee au bon profil")


class TestAnnonceHonnete(object):
    """Si la partie n'est pas la ou Cemu la cherche, on ne dit pas que c'est
    fait : un « restauration reussie » alors que le jeu ne voit rien, c'est la
    panne la plus breve et la plus trompeuse du projet."""

    def test_une_restauration_qui_echoue_ne_dit_pas_oui(self, fausse_machine,
                                                         monkeypatch):
        archive = TestRestaurationAuBonEndroit._archive()
        shutil.rmtree(config.save_root(), ignore_errors=True)
        os.makedirs(config.save_root(), exist_ok=True)
        monkeypatch.setattr(newgame, "_restaurer", lambda src: None)
        assert newgame.revert(archive, force=True) is None

    def test_une_restauration_partielle_est_signalee(self, fausse_machine,
                                                      monkeypatch):
        """Une copie arretee en route doit etre refusee, pas annoncee."""
        archive = TestRestaurationAuBonEndroit._archive()
        shutil.rmtree(config.save_root(), ignore_errors=True)
        os.makedirs(config.save_root(), exist_ok=True)

        vraie = newgame._restaurer

        def copie_tronquee(src):
            vraie(src)
            # Le disque a filled en plein copier-coller : les dossiers sont
            # la, le fichier de partie, non.
            fichier = os.path.join(config.save_root(), "user", "80000001",
                                   "0", "game_data.sav")
            if os.path.isfile(fichier):
                os.remove(fichier)
        monkeypatch.setattr(newgame, "_restaurer", copie_tronquee)
        assert newgame.revert(archive, force=True) is None
