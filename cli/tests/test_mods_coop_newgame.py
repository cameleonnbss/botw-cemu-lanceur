"""Mods, catalogue, coop, nouvelle partie, documentation, outils."""
import io
import json
import os
import re
import zipfile

import pytest

from botw import catalog, config, coop, i18n, mods, newgame, readme, tools
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
