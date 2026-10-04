"""Tests de `installer.py`, l'installateur du depot.

L'installateur n'est pas dans le paquet livre a l'utilisateur : il vit a la
racine du depot et sert a installer le paquet. On le charge donc par son
chemin, comme le ferait un `git clone`.

Ce que ces tests verrouillent :

* le dossier de destination est normalise. Un utilisateur qui tape
  `--dest D:/BOTW` ne doit pas lire ensuite `D:/BOTW\\Lanceur-BOTW.bat` : ca
  marche, mais un installateur qui a l'air casse ne se relit pas ;
* `--check` n'ecrit rien, meme quand le dossier n'existe pas encore ;
* la copie est exacte, jusqu'au controle MD5 apres copie - une copie a moitie
  faite donne un lanceur qui semble marcher et qui execute du code vieux ;
* une installation reelle produit un lanceur jouable, et la relancer ne
  reecrit rien : une re-installation doit etre sans risque ni cout.
"""
from __future__ import print_function

import contextlib
import importlib.util
import io
import os
import shutil
import sys

import pytest

ICI = os.path.dirname(os.path.abspath(__file__))


def _racine_depot():
    """Le dossier qui contient `installer.py`, `lanceur/` et `cli/`.

    Ce test vit dans `outils/`, donc la racine est un cran plus haut - mais on
    la cherche plutot que de la deviner : un copier-coller du fichier dans un
    autre dossier ne doit pas transformer un test vert en test qui ne voit
    rien.
    """
    base = os.path.dirname(ICI)
    for _ in range(4):
        if (os.path.isfile(os.path.join(base, "installer.py"))
                and os.path.isdir(os.path.join(base, "lanceur"))
                and os.path.isdir(os.path.join(base, "cli"))):
            return base
        parent = os.path.dirname(base)
        if parent == base:
            break
        base = parent
    raise AssertionError(
        "racine du depot introuvable en partant de %s : il faut installer.py, "
        "lanceur/ et cli/ dans le meme dossier" % ICI)


RACINE = _racine_depot()
SCRIPT = os.path.join(RACINE, "installer.py")


def _charger():
    spec = importlib.util.spec_from_file_location("installeur_botw", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _executer(installeur, argv):
    """Lance `main()` en capturant son ecran. -> (code, texte)"""
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        code = installeur.main(argv)
    return code, tampon.getvalue()


@pytest.fixture(scope="module")
def installeur():
    return _charger()


@pytest.fixture(scope="module")
def installe(installeur, tmp_path_factory):
    """Une installation reelle, faite UNE fois pour tous les tests.

    Le dossier est volontairement passe avec des barres obliques : c'est
    comme ça que les gens tapent `--dest D:/BOTW`, et c'est exactement le cas
    qui affichait un chemin melee avant la normalisation.
    """
    dest = str(tmp_path_factory.mktemp("dest") / "BOTW").replace("\\", "/")
    code, sortie = _executer(installeur, ["--dest", dest])
    return {"dest": dest, "code": code, "sortie": sortie}


class TestDestination(object):
    """Le dossier choisi, normalise une fois pour toutes."""

    def test_par_defaut_c_est_le_bureau(self, installeur):
        attendu = os.path.normpath(os.path.join(
            os.path.expanduser("~"), "Desktop", "BOTW"))
        assert installeur.destination() == attendu
        assert installeur.destination(None) == attendu
        # Une option vide est une option absente, pas la racine du disque.
        assert installeur.destination("") == attendu

    def test_les_barres_obliques_sont_normalisees(self, installeur):
        # C'est le bug : sans normpath, l'ecran final affichait
        # "D:/BOTW\Lanceur-BOTW.bat".
        assert installeur.destination("D:/BOTW") == "D:" + os.sep + "BOTW"
        assert "/" not in installeur.destination("D:/BOTW/Sous/Dossier")

    def test_une_barre_finale_ne_change_rien(self, installeur):
        assert installeur.destination("D:/BOTW/") == "D:" + os.sep + "BOTW"
        assert installeur.destination("D:\\BOTW\\") == "D:" + os.sep + "BOTW"

    def test_les_doublets_sont_reduits(self, installeur):
        assert installeur.destination("D:/BOTW/./mods/..") == \
            "D:" + os.sep + "BOTW"


class TestModeVerification(object):
    """--check ne doit toucher a rien."""

    def test_un_dossier_absent_est_signale_sans_ecrire(self, installeur,
                                                      tmp_path):
        inexistant = str(tmp_path / "pas-encore-la")
        code, sortie = _executer(installeur, ["--check", "--dest", inexistant])
        assert code == 1
        assert not os.path.exists(inexistant), "--check a cree le dossier"
        assert "rien ne sera ecrit" in sortie

    def test_rien_n_est_ecrit_dans_un_dossier_existant(self, installeur,
                                                        tmp_path):
        code, sortie = _executer(installeur,
                                 ["--check", "--dest", str(tmp_path)])
        assert code == 0
        assert os.listdir(str(tmp_path)) == []
        assert "rien n'a ete ecrit" in sortie


class TestCopieExacte(object):
    """Une copie a moitie faite est la panne la plus invisible du projet."""

    def test_une_destination_perimee_est_reparae(self, installeur, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "a.txt").write_bytes(b"contenu")
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.txt").write_bytes(b"vieille version")

        assert installeur.copier_verifie(str(source), str(dest), False) == (1, 1)
        assert (dest / "a.txt").read_bytes() == b"contenu"

    def test_une_destination_a_jour_n_est_pas_reecrite(self, installeur,
                                                       tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "a.txt").write_bytes(b"contenu")
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.txt").write_bytes(b"contenu")

        assert installeur.copier_verifie(str(source), str(dest), False) == (1, 0)

    def test_le_mode_verification_ecrit_moins_que_ca(self, installeur,
                                                     tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / "a.txt").write_bytes(b"contenu")
        dest = tmp_path / "dest"
        dest.mkdir()
        (dest / "a.txt").write_bytes(b"vieille version")

        assert installeur.copier_verifie(str(source), str(dest), True) == (1, 1)
        assert (dest / "a.txt").read_bytes() == b"vieille version", \
            "--check a modifie un fichier"

    def test_une_copie_abimee_est_refusee(self, installeur, tmp_path,
                                          monkeypatch):
        """Si ce qui arrive sur le disque ne correspond pas, on le dit."""
        source = tmp_path / "source"
        source.mkdir()
        (source / "a.txt").write_bytes(b"contenu")
        dest = tmp_path / "dest"

        def copie_truquee(src, dst, *args, **kwargs):
            shutil.copyfile(src, dst)
            with io.open(dst, "wb") as f:      # le disque "perd" des octets
                f.write(b"contenu tronque")
        monkeypatch.setattr(installeur.shutil, "copy2", copie_truquee)

        assert installeur.copier_verifie(str(source), str(dest), False) is None


class TestInstallationComplete(object):
    """Une installation reelle, puis une re-installation."""

    def test_le_code_de_sortie_est_zero(self, installe):
        assert installe["code"] == 0, installe["sortie"]

    def test_les_chemins_affiches_ne_sont_pas_melanges(self, installe):
        lignes = [l for l in installe["sortie"].splitlines()
                  if "jouer :" in l or "outillage :" in l]
        assert len(lignes) == 2, "l'ecran final doit nommer les deux outils"
        for ligne in lignes:
            chemin = ligne.split(":", 1)[1].strip()
            assert chemin, "un chemin vide : %r" % ligne
            assert "/" not in chemin, (
                "separateurs melanges dans %r : le dossier saisi avec des "
                "barres obliques n'a pas ete normalise" % ligne)
            assert os.path.isfile(chemin), "%r ne pointe sur rien" % ligne

    def test_le_lanceur_est_la(self, installe):
        dest = installe["dest"]
        for nom in ("Lanceur-BOTW.bat", "LISEZ-MOI.txt", "Sauvegardes-BOTW.bat"):
            assert os.path.isfile(os.path.join(dest, nom)), nom
        assert os.path.isfile(os.path.join(dest, "botw", "botw.py"))
        assert os.path.isfile(os.path.join(dest, "botw", "locales", "fr.json"))

    def test_les_fichiers_windows_sont_conformes(self, installeur, installe):
        # On controle la copie, pas la source : c'est la copie que Windows
        # va executer.
        assert installeur.controler_windows(installe["dest"]), (
            "l'installateur annonce une copie conforme mais "
            "controler_windows() refuse le resultat")

    def test_les_tests_sont_livres_avec_le_programme(self, installe):
        """Une installation doit pouvoir se verifier elle-meme."""
        sous_cli = os.path.join(installe["dest"], "botw")
        assert os.path.isdir(os.path.join(sous_cli, "tests")), (
            "les tests ne sont pas livres avec le programme")

    def test_reinstaller_ne_reecrit_rien(self, installeur, installe):
        code, sortie = _executer(installeur, ["--dest", installe["dest"]])
        assert code == 0
        ecrit = [l for l in sortie.splitlines() if "a ecrire" in l]
        assert len(ecrit) == 2, ecrit
        for ligne in ecrit:
            assert "0 a ecrire" in ligne, (
                "une re-installation a reecrit des fichiers : %r" % ligne)


class TestLePaquetEstPresent(object):
    """Sans `lanceur/` et `cli/`, l'installateur n'a rien a copier."""

    def test_les_sources_sont_la(self, installeur):
        assert os.path.isdir(installeur.LANCEUR), installeur.LANCEUR
        assert os.path.isdir(installeur.CLI), installeur.CLI

    def test_un_poste_sans_ukmm_installe_quand_meme(self, installeur,
                                                     monkeypatch):
        """UKMM et Cemu absents : on Previent, on n'empeche pas."""
        monkeypatch.setattr(installeur, "ou_ukmm", lambda: "")
        monkeypatch.setattr(installeur, "ou_cemu", lambda: "")
        assert installeur.verifier_outils() is False


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([os.path.abspath(__file__), "-v"]))