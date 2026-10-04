"""Tests du lanceur de demarrage automatique.

Ce fichier n'est pas dans le paquet du projet : `demarrage-auto.py` est un
script pose a cote du chantier, pas un module. On le charge donc par son
chemin, comme le ferait le dossier Demarrage de Windows.

Trois decisions a couvrir, parce que ce sont elles qui evitent un plantage au
demarrage :

* un bloquant au chargement  -> rien ne se lance, on dit lequel ;
* une partie d'un autre jeu de mods -> rien ne se lance, c'est le crash d'ajout ;
* sinon -> Cemu demarre.

Et un piege : `Popen.returncode` n'est rempli qu'apres `communicate()`. Lu
avant, il vaut None, et None n'est pas zero.
"""
import importlib.util
import io
import os
import subprocess
import sys

import pytest

ICI = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(ICI, "demarrage-auto.py")
# Le programme est dans un dossier VOISIN : c'est ce que cherche
# racine_botw() en conditions reelles.
PROGRAMME = os.path.join(ICI, "botw-tools")
if PROGRAMME not in sys.path:
    sys.path.insert(0, PROGRAMME)

# Les modules du programme sont importes DANS main(), donc on les patche ici :
# le test exerce le vrai botw, pas une doublure.
from botw import config, newgame, profiles  # noqa: E402


def _charger():
    spec = importlib.util.spec_from_file_location("demarrage_auto", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def auto(monkeypatch, tmp_path):
    """Le script charge, avec son journal ecrit dans un fichier jetable."""
    module = _charger()
    journal = tmp_path / "demarrage-auto.log"
    monkeypatch.setattr(module, "JOURNAL", str(journal))
    monkeypatch.setattr(module, "racine_botw", lambda: PROGRAMME)
    return module


def _sans_bloquant(auto, monkeypatch):
    """`botw check` reussit : aucun pack ne peut bloquer le chargement."""
    monkeypatch.setattr(auto, "lancer_botw",
                        lambda racine, cmd: (0, "  [OK ] Rien ne peut bloquer\n"))


class TestProgrammeIntrouvable(object):
    def test_refuse_de_demarrer(self, monkeypatch, tmp_path):
        module = _charger()
        monkeypatch.setattr(module, "JOURNAL", str(tmp_path / "j.log"))
        monkeypatch.setattr(module, "racine_botw", lambda: None)
        assert module.main([]) == 1
        assert "introuvable" in io.open(str(tmp_path / "j.log"),
                                        encoding="utf-8").read()


class TestBloquantAuChargement(object):
    def test_rien_ne_demarre_et_le_motif_est_donne(self, auto, monkeypatch):
        """Un pack bloquant est plus grave qu'une partie incompatible : le jeu
        planterait sur l'ecran de chargement. Cemu ne doit pas partir."""
        texte = ("  [OK ] le pack UKMM est actif\n"
                 "  [KO ] LA SAUVEGARDE VIENT DE 'x' ET 'y' EST ACTIF\n"
                 "  [KO ] 1 probleme(s) bloquant(s)\n")
        monkeypatch.setattr(auto, "lancer_botw", lambda r, c: (1, texte))
        demarres = []
        monkeypatch.setattr(subprocess, "Popen",
                            lambda *a, **k: demarres.append(a))
        assert auto.main([]) == 1
        assert not demarres, "rien ne doit etre lance"
        journal = io.open(auto.JOURNAL, encoding="utf-8").read()
        assert "LA SAUVEGARDE VIENT DE" in journal


class TestPartieDUnAutreJeuDeMods(object):
    """C'est le plantage du 4 octobre : la sauvegarde vient de 'secondwind',
    le profil actif est 'sur', et Cemu a plante en demarrant."""

    def _faux_etat(self, auto, monkeypatch, provenance, actif):
        _sans_bloquant(auto, monkeypatch)
        monkeypatch.setattr(profiles, "active", lambda: actif)
        monkeypatch.setattr(newgame, "has_game", lambda: True)
        monkeypatch.setattr(newgame, "profil_de_la_partie",
                            lambda: provenance)

    def test_refuse_et_n_explique_pas(self, auto, monkeypatch):
        self._faux_etat(auto, monkeypatch, "secondwind", "sur")
        demarres = []
        monkeypatch.setattr(subprocess, "Popen",
                            lambda *a, **k: demarres.append(a))
        assert auto.main([]) == 1
        assert not demarres, "lancer Cemu la ferait planter"
        journal = io.open(auto.JOURNAL, encoding="utf-8").read()
        assert "planterait" in journal
        assert "secondwind" in journal and "sur" in journal

    def test_profil_inconnu_ne_bloque_pas(self, auto, monkeypatch):
        """On ne devine jamais. Sans profil connu, on demarre : c'est au
        joueur de savoir ce qu'il fait, et bloquer sur un doute le laisserait
        sans jeu du tout."""
        self._faux_etat(auto, monkeypatch, "", "sur")
        demarres = []
        monkeypatch.setattr(subprocess, "Popen",
                            lambda *a, **k: demarres.append(a) or None)
        assert auto.main(["--verifier"]) == 0
        assert not demarres, "--verifier ne lance jamais Cemu"
        assert "inconnu" in io.open(auto.JOURNAL, encoding="utf-8").read()


class TestDemarrageNormal(object):
    def test_verifier_ne_lance_rien(self, auto, monkeypatch):
        _sans_bloquant(auto, monkeypatch)
        monkeypatch.setattr(profiles, "active", lambda: "sur")
        monkeypatch.setattr(newgame, "has_game", lambda: False)
        demarres = []
        monkeypatch.setattr(subprocess, "Popen",
                            lambda *a, **k: demarres.append(a))
        assert auto.main(["--verifier"]) == 0
        assert not demarres
        journal = io.open(auto.JOURNAL, encoding="utf-8").read()
        assert "sur" in journal

    def test_cemu_demarre(self, auto, monkeypatch):
        _sans_bloquant(auto, monkeypatch)
        monkeypatch.setattr(profiles, "active", lambda: "sur")
        monkeypatch.setattr(newgame, "has_game", lambda: False)
        faux = os.path.join(PROGRAMME, "Cemu.exe")
        open(faux, "wb").close()
        monkeypatch.setattr(config, "cemu_exe", lambda cfg: faux)
        demarres = []
        monkeypatch.setattr(subprocess, "Popen",
                            lambda *a, **k: demarres.append(a) or None)
        try:
            assert auto.main([]) == 0
        finally:
            os.remove(faux)
        assert demarres, "Cemu doit etre lance"
        assert faux in demarres[0][0]
        assert "---- fin ----" in io.open(auto.JOURNAL, encoding="utf-8").read()

    def test_cemu_introuvable_dit_quoi_faire(self, auto, monkeypatch):
        _sans_bloquant(auto, monkeypatch)
        monkeypatch.setattr(profiles, "active", lambda: "sur")
        monkeypatch.setattr(newgame, "has_game", lambda: False)
        monkeypatch.setattr(config, "cemu_exe", lambda cfg: "")
        assert auto.main([]) == 1
        assert "introuvable" in io.open(auto.JOURNAL, encoding="utf-8").read()


class TestRetourDuSousProcessus(object):
    """Le piege qui a fait dire "le jeu ne demarre pas" a une machine
    parfaitement saine : returncode lu avant communicate() vaut None."""

    class _Faux(object):
        def __init__(self, code):
            self.returncode = None
            self._code = code

        def communicate(self):
            self.returncode = self._code        # rempli par la fin du processus
            return [b"  [OK ] Rien ne peut bloquer\n"]

    def test_le_code_est_bien_relu(self, auto, monkeypatch):
        def faux_popen(*a, **k):
            return TestRetourDuSousProcessus._Faux(0)
        monkeypatch.setattr(subprocess, "Popen", faux_popen)
        code, texte = auto.lancer_botw(PROGRAMME, ["check"])
        assert code == 0, "un code 0 ne doit pas devenir un echec"
        assert "Rien ne peut bloquer" in texte

    def test_un_vrai_echec_est_conserve(self, auto, monkeypatch):
        def faux_popen(*a, **k):
            return TestRetourDuSousProcessus._Faux(1)
        monkeypatch.setattr(subprocess, "Popen", faux_popen)
        code, _t = auto.lancer_botw(PROGRAMME, ["check"])
        assert code == 1