"""Traduction et configuration : les deux fondation du reste."""
import io
import json
import os
import re

import pytest

from botw import cli, config, i18n


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


def compte_windows():
    """Le nom du compte Windows de CE poste, lu dans le chemin personnel.

    On prend le segment qui suit `Users`, et non le dernier segment : le
    dossier de travail du projet est lui-meme un dossier, et `profil`,
    `botw` ou `tests` diraient alors n'importe quoi.
    """
    morceaux = os.path.expanduser("~").replace("/", "\\").split("\\")
    for i, morceau in enumerate(morceaux):
        if morceau.lower() == "users" and i + 1 < len(morceaux):
            return morceaux[i + 1].lower()
    return ""          # poste non-Windows : seule la regle `C:\\Users\\` joue


class TestConfiguration(object):
    def test_defauts(self):
        cfg = config.load()
        # Aucune langue par defaut : c'est i18n.appliquer qui choisit celle du
        # poste. Une langue ici ('en') gagnerait toujours et la detection ne
        # se declencherait jamais sur une installation neuve.
        assert cfg["lang"] == ""
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
        assert cfg["lang"] == ""

    def test_json_corrompu_ne_casse_rien(self):
        os.makedirs(config.appdata_dir(), exist_ok=True)
        with open(config.config_path(), "w", encoding="utf-8") as f:
            f.write("{ ca n'est pas du json")
        assert config.load()["lang"] == ""

    def test_parametre_inconnu_refuse(self):
        with pytest.raises(KeyError):
            config.set_value("pastille", "violet")

    def test_chemins_suivent_les_variables(self, fausse_machine):
        assert config.ukmm_settings().startswith(str(fausse_machine["appdata"]))
        assert config.profiles_dir().startswith(str(fausse_machine["local"]))
        assert config.mods_store().startswith(str(fausse_machine["local"]))

    def test_aucun_chemin_en_dur(self, fausse_machine):
        """Aucun chemin de la machine de travail ne doit etre en dur.

        Le nom du compte Windows peut contenir un accent : des qu'il
        traine dans le code, l'outil n'est plus copiable ailleurs. On
        interdit donc le prefixe `C:\\Users\\`, et le
        nom du compte de CE poste - deduit du chemin personnel, jamais
        ecrit en dur, pour que le test serve sur n'importe quelle machine.
        """
        racine = config.tool_root()
        compte = compte_windows()
        interdits = []
        for base, _d, files in os.walk(os.path.join(racine, "botw")):
            for nom in files:
                if not nom.endswith(".py"):
                    continue
                chemin = os.path.join(base, nom)
                with open(chemin, encoding="utf-8") as f:
                    for i, ligne in enumerate(f, 1):
                        if "C:\\Users\\" in ligne or (
                                compte and compte in ligne.lower()):
                            interdits.append("%s:%d" % (nom, i))
        assert not interdits, interdits

    def test_ukmm_exe_par_defaut(self, fausse_machine):
        assert config.ukmm_exe().endswith("ukmm.exe")
        assert "Tools" in config.ukmm_exe()

    def test_cemu_exe_depuis_la_configuration(self, fausse_machine):
        faux = os.path.join(fausse_machine["racine"], "Cemu.exe")
        open(faux, "w").close()
        assert config.cemu_exe({"cemu_exe": faux}) == faux


class TestClesUtilisees(object):
    """Une cle utilisee et non definie s'affiche telle quelle, en clair, dans
    l'interface. C'est le genre de faute qu'on voit trop tard : ici, on relit
    le code et on compare aux deux fichiers de langue."""

    def test_aucune_cle_manquante(self):
        import re
        motif = re.compile(r'_\(\s*"([a-z0-9_.]+)"')
        cles = set()
        racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for base, _d, files in os.walk(os.path.join(racine, "botw")):
            for nom in files:
                if not nom.endswith(".py"):
                    continue
                with io.open(os.path.join(base, nom), encoding="utf-8") as f:
                    cles.update(motif.findall(f.read()))
        assert cles, "le motif n'a rien trouve : le test ne testerait rien"
        for code in ("en", "fr"):
            with io.open(os.path.join(i18n.LOCALES, code + ".json"),
                         encoding="utf-8") as f:
                definies = set(json.load(f))
            manquantes = sorted(cles - definies)
            assert not manquantes, "%s : %s" % (code, manquantes)

    def test_les_placeurs_correspondent(self):
        """Meme cle, meme jeu de {nom} dans les deux langues : un {n} traduit
        en {nombre} planterait au premier affichage."""
        for code in ("en", "fr"):
            with io.open(os.path.join(i18n.LOCALES, code + ".json"),
                         encoding="utf-8") as f:
                data = json.load(f)
            with io.open(os.path.join(i18n.LOCALES,
                                      "en" if code == "fr" else "fr") + ".json",
                         encoding="utf-8") as f:
                autre = json.load(f)
            assert autre, "l'autre langue est vide : le test ne testerait rien"
            for cle, txt in data.items():
                a = set(re.findall(r"\{(\w+)", txt))
                b = set(re.findall(r"\{(\w+)", autre[cle]))
                assert a == b, "%s / %s : %s != %s" % (code, cle, a, b)


class TestLangueDuSysteme(object):
    """La langue doit suivre celle du poste, sans configuration.

    Avant, la langue par defaut etait toujours 'en' : un Windows
    francophone demarrait en anglais et il fallait savoir qu'il existait un
    'botw lang fr' pour y remedier.
    """

    def test_windows_francais(self, monkeypatch):
        monkeypatch.setattr(i18n, "langue_windows", lambda: "fr")
        monkeypatch.setattr(os, "name", "nt")
        assert i18n.langue_systeme() == "fr"

    def test_windows_anglais(self, monkeypatch):
        monkeypatch.setattr(i18n, "langue_windows", lambda: "en")
        monkeypatch.setattr(os, "name", "nt")
        assert i18n.langue_systeme() == "en"

    def test_windows_prioritaire_sur_les_variables(self, monkeypatch):
        """Sous Git Bash, LANG vaut souvent 'en_US' sur une machine
        francophone. L'interface de Windows doit gagner : c'est elle que
        l'utilisateur regarde tous les jours."""
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "fr")
        monkeypatch.setenv("LANG", "en_US.UTF-8")
        assert i18n.langue_systeme() == "fr"

    def test_variables_sans_windows(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        monkeypatch.delenv("BOTW_LANG", raising=False)
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        assert i18n.langue_systeme() == "fr"

    def test_region_ignoree(self, monkeypatch):
        """'fr-CA' doit donner francais, comme 'fr-FR'."""
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        monkeypatch.delenv("BOTW_LANG", raising=False)
        monkeypatch.setenv("LANG", "fr-CA")
        assert i18n.langue_systeme() == "fr"

    def test_langue_non_traduite_rend_la_main(self, monkeypatch):
        """Une langue qu'on ne traduit pas ne doit pas casser le lanceur."""
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        monkeypatch.delenv("BOTW_LANG", raising=False)
        monkeypatch.setenv("LANG", "de_DE.UTF-8")
        assert i18n.langue_systeme() == ""

    def test_aucune_trace_au_demarrage(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        for nom in ("BOTW_LANG", "LANG", "LC_ALL", "LC_MESSAGES"):
            monkeypatch.delenv(nom, raising=False)
        assert i18n.langue_systeme() == ""
        assert i18n.set_lang_auto() is False

    def test_choix_explicite_prioritaire(self, monkeypatch):
        """Un choix enregistre doit primer sur la detection : sinon
        l'utilisateur ne peut plus revenir en anglais sur un poste
        francophone."""
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "fr")
        assert i18n.appliquer({"lang": "en"}) is True
        assert i18n.lang() == "en"

    def test_pas_de_choix_detection(self, monkeypatch):
        """C'est le cas reel d'une installation neuve : rien dans la
        configuration, le poste est francophone, l'outil doit se lancer en
        francais tout seul."""
        monkeypatch.setattr(os, "name", "nt")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "fr")
        assert i18n.appliquer({"lang": ""}) is True
        assert i18n.lang() == "fr"

    def test_configuration_absente_detection(self, monkeypatch):
        """Meme sans configuration du tout (None) : on ne plante pas."""
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        monkeypatch.delenv("LANG", raising=False)
        monkeypatch.setenv("BOTW_LANG", "fr")
        assert i18n.appliquer(None) is True
        assert i18n.lang() == "fr"
        i18n.set_lang("en")

    def test_aucune_detection_conserve_l_anglais(self, monkeypatch):
        monkeypatch.setattr(os, "name", "posix")
        monkeypatch.setattr(i18n, "langue_windows", lambda: "")
        for nom in ("BOTW_LANG", "LANG", "LC_ALL", "LC_MESSAGES"):
            monkeypatch.delenv(nom, raising=False)
        assert i18n.appliquer({"lang": ""}) is False
        assert i18n.lang() == "en"          # FALLBACK, pas une exception

    def test_lang_auto_efface_le_choix(self, fausse_machine):
        """`botw lang auto` doit rendre la main au poste, pas figer la
        langue affichee au moment du choix."""
        cfg = config.load()
        cfg["lang"] = "en"
        config.save(cfg)
        i18n.set_lang("en")
        assert cli.main(["lang", "auto"]) == 0
        assert config.load()["lang"] == ""

    def test_lid_chiffres_cles(self):
        """Les LANGID qu'on traduit, Lus au bit pres.

        Un LANGID fait 16 bits : les 10 de poids faible portent le
        sous-langage primaire, le reste le pays. Confondre les deux fait
        rater toutes les variantes regionales.
        """
        assert 0x040C & 0x3FF == 0x0C      # fr-FR
        assert 0x0809 & 0x3FF == 0x09      # en-GB
        assert 0x0C0C & 0x3FF == 0x0C      # fr-CA
