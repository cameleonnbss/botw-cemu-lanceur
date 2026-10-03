"""Profils, ordre de chargement, manifestes : le coeur du travail."""
import io
import os
import zipfile

import pytest

from botw import config, deploy, profiles
from conftest import ecrire

MANIFESTE = """content:
- Pack/Bootup_USen.pack
- Menu/MainMenu/Home.szs
aoc:
- Common/Obj_Hearth_Awarded.bnmov
"""


class TestLectureProfil(object):
    def test_lit_les_mods(self, installation):
        p = profiles.load("boost")
        assert len(p.hashes) == 3
        assert ("Ancient Weaponry Mark II",
                "Ancient_Weaponry_Mark_II.zip") in p.hashes.values()

    def test_lit_le_load_order(self, installation):
        p = profiles.load("boost")
        assert p.order == ["12345", "67890", "11111"]

    def test_ordre_coherent(self, installation):
        assert profiles.load("boost").consistent()

    def test_ordre_different_si_manquant(self, installation):
        f = os.path.join(config.profiles_dir(), "boost", "profile.yml")
        texte = io.open(f, encoding="utf-8").read().replace("- 11111\n", "")
        ecrire(f, texte)
        assert not profiles.load("boost").consistent()

    def test_mod_hors_load_order_mis_a_la_fin(self, installation):
        """Un mod ajoute a la main n'est pas dans load_order : il ne doit
        pas disparaitre de la liste, sinon il ne serait jamais fusionne."""
        f = os.path.join(config.profiles_dir(), "boost", "profile.yml")
        texte = io.open(f, encoding="utf-8").read()
        texte = texte.replace("  12345:", "  99999:\n    meta:\n"
                                   "      name: Mod Main\n"
                                   "    path: C:\\mods\\Mod_Main.zip\n"
                                   "  12345:")
        ecrire(f, texte)
        p = profiles.load("boost")
        assert any(fn == "Mod_Main.zip" for _l, fn in p.hashes.values())
        assert p.ordered()[-1][1] == "Mod_Main.zip"

    def test_liste_des_profils(self, installation):
        assert profiles.existing() == ["boost"]

    def test_profil_inexistant(self, installation):
        with pytest.raises(IOError):
            profiles.load("fantome")


class TestOrdreDeChargement(object):
    def test_priorite_connue(self):
        assert profiles.PRIORITY[0] == "Second_Wind_(core).zip"
        assert profiles.PRIORITY[-1] == "The_Linkle_Mod_3.0.1.zip"

    def test_linkle_toujours_en_tete(self):
        """C'est la regle la plus importante : Linkle doit toujours gagner."""
        assert profiles.PRIORITY.index("The_Linkle_Mod_3.0.1.zip") == \
            len(profiles.PRIORITY) - 1

    def test_second_wind_avant_relics(self):
        assert profiles.PRIORITY.index("Second_Wind_(core).zip") < \
            profiles.PRIORITY.index("Relics_of_the_Past.zip")

    def test_reecriture_place_dans_l_ordre(self, installation):
        f = os.path.join(config.profiles_dir(), "boost", "profile.yml")
        texte = io.open(f, encoding="utf-8").read()
        # on inverse tout
        texte = texte.replace("load_order:\n- 12345\n- 67890\n- 11111\n",
                              "load_order:\n- 11111\n- 67890\n- 12345\n")
        ecrire(f, texte)
        p = profiles.load("boost").rewrite_order()
        assert [fn for _l, fn in p][-1] == "The_Linkle_Mod_3.0.1.zip"
        assert [fn for _l, fn in p][0] == "Second_Wind_(core).zip"

    def test_mod_inconnu_alphabetique_a_la_fin(self, installation):
        f = os.path.join(config.profiles_dir(), "boost", "profile.yml")
        texte = io.open(f, encoding="utf-8").read()
        texte = texte.replace("  12345:", "  99999:\n    meta:\n"
                                   "      name: Zzz Inconnu\n"
                                   "    path: C:\\mods\\Zzz_Inconnu.zip\n"
                                   "  12345:")
        ecrire(f, texte)
        p = profiles.load("boost").rewrite_order()
        assert p[-1][1] == "Zzz_Inconnu.zip"

    def test_reecriture_est_idempotente(self, installation):
        p = profiles.load("boost")
        un = [fn for _l, fn in p.rewrite_order()]
        deux = [fn for _l, fn in p.rewrite_order()]
        assert un == deux


class TestManifeste(object):
    def _zip(self, tmp_path, texte=MANIFESTE, nom="Test.zip"):
        chemin = str(tmp_path / nom)
        with zipfile.ZipFile(chemin, "w") as zf:
            zf.writestr("manifest.yml", texte)
            zf.writestr("content/Menu/MainMenu/Home.szs", "x")
        return chemin

    def test_lit_le_manifeste(self, tmp_path):
        contenu, aoc = profiles._manifest_files(self._zip(tmp_path))
        # le manifeste nomme des chemins SANS le prefixe du zip : c'est UKMM
        # qui rajoute content/ et aoc/0010/ au moment du deploiement.
        assert contenu == ["content/Pack/Bootup_USen.pack",
                           "content/Menu/MainMenu/Home.szs"]
        assert aoc == ["aoc/0010/Common/Obj_Hearth_Awarded.bnmov"]

    def test_aoc_vide(self, tmp_path):
        chemin = str(tmp_path / "NoAoc.zip")
        with zipfile.ZipFile(chemin, "w") as zf:
            zf.writestr("manifest.yml", "content:\n- Pack/A.pack\naoc: []\n")
        assert profiles._manifest_files(chemin) == (["content/Pack/A.pack"], [])

    def test_zip_sans_manifeste(self, tmp_path):
        chemin = str(tmp_path / "Vide.zip")
        with zipfile.ZipFile(chemin, "w") as zf:
            zf.writestr("lisezmoi.txt", "rien")
        assert profiles._manifest_files(chemin) == (None, None)


class TestVerification(object):
    def test_profil_complet_passe(self, installation, capsys):
        # les trois mods du profil doivent declarer des fichiers presents
        for nom, rel in (("Ancient_Weaponry_Mark_II.zip", "Menu/Home.szs"),
                         ("The_Linkle_Mod_3.0.1.zip", "Menu/Home.szs"),
                         ("Second_Wind_(core).zip", "Menu/Home.szs")):
            faux = os.path.join(config.mods_store(), nom)
            with zipfile.ZipFile(faux, "w") as zf:
                zf.writestr("manifest.yml", "content:\n- %s\n" % rel)
        ecrire(os.path.join(config.graphic_pack(), "content", "Menu",
                            "Home.szs"), "x")
        ecrire(os.path.join(config.graphic_pack(), "rules.txt"), "x")
        ecrire(os.path.join(config.profiles_dir(), "boost", "merged", "content",
                            "Menu", "Home.szs"), "x")
        ok, n = profiles.verify("boost")
        assert ok and n == 0, capsys.readouterr().out

    def test_zip_corrompu_ne_casse_pas_la_verification(self, installation, capsys):
        """Un mod corrompu doit etre signale, pas faire planter la commande."""
        faux = os.path.join(config.mods_store(), "Ancient_Weaponry_Mark_II.zip")
        with open(faux, "wb") as f:
            f.write(b"ceci n est pas un zip")
        ok, n = profiles.verify("boost")
        assert not ok
        assert n >= 1
        assert "manifest" in capsys.readouterr().out.lower()


class TestDeploiement(object):
    def test_regles_txt_bien_forme(self):
        assert deploy.RULES_BODY.startswith("[Definition]")
        assert "00050000101C9500" in deploy.RULES_BODY
        assert "fsPriority = 9999" in deploy.RULES_BODY
        assert "\r\n" in deploy.RULES_BODY   # Cemu lit du CRLF ici

    def test_compte_fichiers(self, installation):
        n = deploy.count_files(os.path.join(config.profiles_dir(), "boost",
                                            "merged"))
        assert n == 2

    def test_compte_sur_dossier_absent(self):
        assert deploy.count_files(r"C:\nulle_part\ici") == 0

    def test_profil_actif(self, installation):
        assert deploy.read_active_profile() == "boost"

    def test_ecriture_profil_actif(self, installation):
        os.makedirs(os.path.join(config.profiles_dir(), "sur"), exist_ok=True)
        ecrire(os.path.join(config.profiles_dir(), "sur", "profile.yml"), "mods: {}\n")
        assert deploy.write_active_profile("sur")
        assert deploy.read_active_profile() == "sur"

    def test_garde_fou_refuse_un_profil_inconnu(self, installation):
        with pytest.raises(deploy.GuardError) as e:
            deploy.deploy("fantome")
        assert e.value.code == 1

    def test_garde_fou_cemu_ferme(self, installation, monkeypatch):
        monkeypatch.setattr(deploy, "processes_named",
                            lambda n: [4242] if n == "Cemu" else [])
        with pytest.raises(deploy.GuardError) as e:
            deploy.deploy("boost")
        assert e.value.code == 2

    def test_garde_fou_ukmm_ferme(self, installation, monkeypatch):
        monkeypatch.setattr(deploy, "processes_named",
                            lambda n: [7] if n == "ukmm" else [])
        with pytest.raises(deploy.GuardError) as e:
            deploy.deploy("boost")
        assert e.value.code == 3

    def test_garde_fou_passe_si_rien_ne_tourne(self, installation, monkeypatch):
        monkeypatch.setattr(deploy, "processes_named", lambda n: [])
        deploy.guard_quiet()

    def test_liens_durs(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        ecrire(str(src / "a" / "b.txt"), "bonjour")
        n = deploy._hardlink_tree(str(src), str(dst))
        assert n == 1
        assert (dst / "a" / "b.txt").read_text() == "bonjour"

    def test_lien_dur_reutilise_si_present(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        ecrire(str(src / "b.txt"), "x")
        deploy._hardlink_tree(str(src), str(dst))
        assert deploy._hardlink_tree(str(src), str(dst)) == 0
