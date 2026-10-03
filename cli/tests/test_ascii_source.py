"""Aucune source ne doit contenir de caractere d'une ecriture etrangere.

Le projet est ecrit en francais sans accents, et ca se voit : « Verification »
plutot que « verification », « Echec » plutot que « echec ». C'est une
contrainte deliberee - une console Windows en cp1252 affiche n'importe quoi si
on lui donne du UTF-8.

Dans ce melange, il arrive qu'un caractere d'une ecriture qui n'a rien a y
faire se glisse dans une phrase : un ideogramme, une lettre cyrillique. Le
dossier de travail s'affiche en ASCII, donc on ne le voit pas, et le lecteur
non plus. Un test le rattrape, lui.

On tolere donc les accents et la ponctuation francaise ; on refuse tout ce qui
vient d'une autre ecriture.
"""
import io
import os
import re
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(os.path.dirname(ICI), "botw")

# CJK, kana, fullwidth, cyrillique, arabe, hebreu, devanagari, thai, hangul.
ETRANGERS = re.compile(
    "[\u0370-\u03ff\u0400-\u04ff\u0590-\u05ff\u0600-\u06ff"
    "\u0700-\u074f\u0900-\u097f\u0e00-\u0e7f\u3040-\u30ff"
    "\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uff00-\uffef]")


def fichiers():
    for rep, sous, noms in os.walk(CODE):
        sous[:] = [s for s in sous if s != "__pycache__"]
        for n in sorted(noms):
            if n.endswith(".py"):
                yield os.path.join(rep, n)


def _lignes(p):
    texte = io.open(p, encoding="utf-8", errors="replace").read()
    for i, ligne in enumerate(texte.splitlines(), 1):
        yield i, ligne


class TestEcrituresEtrangeres(object):
    def test_aucune_source_n_en_contient(self):
        coupables = []
        for p in fichiers():
            for i, ligne in _lignes(p):
                for m in ETRANGERS.finditer(ligne):
                    nom = unicodedata.name(m.group(0), "sans nom")
                    coupables.append("%s:%d U+%04X (%s)"
                                     % (os.path.basename(p), i,
                                        ord(m.group(0)), nom))
        assert not coupables, coupables

    def test_le_detecteur_reconnait_un_caractere_etranger(self):
        """Un garde-fou qui ne detecte rien ne protege rien."""
        assert ETRANGERS.search("le profil est 创 casse")
        assert ETRANGERS.search("\u0442\u0435\u0441\u0442")   # cyrillique
        assert not ETRANGERS.search("Verification : aucun bloc, meme a cote")
        assert ETRANGERS.search("\u30c6\u30b9\u30c8")      # kana
        assert not ETRANGERS.search("« guillemets », accents : é à ê ç")
