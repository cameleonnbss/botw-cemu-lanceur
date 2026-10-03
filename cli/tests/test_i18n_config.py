"""Traduction et configuration : les deux fondation du reste."""
import json
import os

import pytest

from botw import config, i18n


class TestTraductions(object):
    def test_anglais_par_defaut(self):
        assert i18n.DEFAULT == "en"
        assert i18n.available()[0] == "en"
        assert "fr" in i18n.available()

    def test_les_deux_langues_ont_les_memes_cles(self):
        with open(os.path.join(i18n.LOCALES, "en.json"), encoding="utf-8") as f:
            en = json.load(f)
        with open(os.path.join(i18n.LOCALES, "fr.json"), encoding="utf-8") as f:
            fr = json.load(f)
        assert set(en) == set(fr), (set(en) ^ set(fr))

    def test_aucune_placeur_manquant(self):
        """Un {nom} present en anglais et absent en francais se verrait a
        l'execution : on le detecte ici, sur les 266 cles."""
        import re
        with open(os.path.join(i18n.LOCALES, "en.json"), encoding="utf-8") as f:
            en = json.load(f)
        with open(os.path.join(i18n.LOCALES, "fr.json"), encoding="utf-8") as f:
            fr = json.load(f)
        trouves = set()
        for cle, txt in en.items():
            trouves |= set(re.findall(r"\{(\w+)\}", txt))
        for cle, txt in fr.items():
            trouves -= set(re.findall(r"\{(\w+)\}", txt))
        assert not trouves, sorted(trouves)

    def test_repli_sur_anglais(self):
        i18n.set_lang("fr")
        assert i18n._("doctor.title") != "doctor.title"
        i18n.set_lang("en")
        assert i18n._("doctor.title") != "doctor.title"

    def test_cle_inconnue_reste_elle_meme(self):
        """Mieux vaut afficher le nom de la cle qu'une exception en pleine
        commande ; le test verifie surtout qu'on ne leve pas."""
        assert i18n._("pas.une.cle") == "pas.une.cle"

    def test_langue_inconnue_retombe_sur_anglais(self):
        assert i18n.set_lang("de") == "en"

    def test_formatage(self):
        i18n.set_lang("en")
        assert "sur" in i18n._("profile.switch", p="sur")

    def test_placeur_manquant_ne_leve_pas(self):
        i18n.set_lang("en")
        # le texte attend {p}, on ne le fournit pas : pas de KeyError
        assert isinstance(i18n._("profile.switch"), str)


class TestConfiguration(object):
    def test_defauts(self):
        cfg = config.load()
        assert cfg["lang"] == "en"
        assert cfg["game_profile"] == "boost"
        assert cfg["deploy_method"] == "hardlink"

    def test_aller_retour(self, fausse_machine):
        cfg = config.load()
        cfg["lang"] = "fr"
        cfg["cemu_exe"] = r"C:\Jeux\Cemu.exe"
        assert config.save(cfg)
        relu = config.load()
        assert relu["lang"] == "fr"
        assert relu["cemu_exe"] == r"C:\Jeux\Cemu.exe"

    def test_fichier_absent_ne_casse_rien(self):
        assert not os.path.isfile(config.config_path())
        cfg = config.load()
        assert cfg["lang"] == "en"

    def test_json_corrompu_ne_casse_rien(self):
        os.makedirs(config.appdata_dir(), exist_ok=True)
        with open(config.config_path(), "w", encoding="utf-8") as f:
            f.write("{ ca n'est pas du json")
        assert config.load()["lang"] == "en"

    def test_parametre_inconnu_refuse(self):
        with pytest.raises(KeyError):
            config.set_value("pastille", "violet")

    def test_chemins_suivent_les_variables(self, fausse_machine):
        assert config.ukmm_settings().startswith(str(fausse_machine["appdata"]))
        assert config.profiles_dir().startswith(str(fausse_machine["local"]))
        assert config.mods_store().startswith(str(fausse_machine["local"]))

    def test_aucun_chemin_en_dur(self, fausse_machine):
        """Le nom du compte de la machine de travail contient un accent : s'il
        traine dans le code, l'outil ne sera pas copiable ailleurs."""
        racine = config.tool_root()
        interdits = []
        for base, _d, files in os.walk(os.path.join(racine, "botw")):
            for nom in files:
                if not nom.endswith(".py"):
                    continue
                chemin = os.path.join(base, nom)
                with open(chemin, encoding="utf-8") as f:
                    for i, ligne in enumerate(f, 1):
                        if "caméléon" in ligne or "cameleon" in ligne.lower() \
                                or "C:\\Users\\" in ligne:
                            interdits.append("%s:%d" % (nom, i))
        assert not interdits, interdits

    def test_ukmm_exe_par_defaut(self, fausse_machine):
        assert config.ukmm_exe().endswith("ukmm.exe")
        assert "Tools" in config.ukmm_exe()

    def test_cemu_exe_depuis_la_configuration(self, fausse_machine):
        faux = os.path.join(fausse_machine["racine"], "Cemu.exe")
        open(faux, "w").close()
        assert config.cemu_exe({"cemu_exe": faux}) == faux
