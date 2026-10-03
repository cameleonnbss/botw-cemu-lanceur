"""L'art ASCII. Parce que c'est censement etre agreable a utiliser.

Le Triforce est en ASCII strict : pas de risque. Le mot LINKLE, lui, utilise
les caracteres de bloc Unicode (les memes que dans le dessin d'origine), parce
qu'ils rendent bien mieux les lettres. i18n.use_utf8() force la console en
UTF-8 avant le premier affichage, et `botw.art.linkle(court=True)` retombe sur
une version 100% ASCII si la largeur de la console est etroite.

Les couleurs sont ajoutees a la volee : NO_COLOR les supprime proprement, sans
laisser de code d'echappement dans la sortie redirigee vers un fichier.

Chaque dessin a une largeur et un nombre de lignes fixes : c'est ce qui permet
de le centrer ou de le reutiliser dans un tableau.
"""

TRIFORCE = r"""
        ____          ____          ____
       /    \        /    \        /    \
      /______\      /______\      /______\
      \      /      \      /      \      /
       \____/        \____/        \____/
            \          ||          /
             \         ||         /
              \        ||        /
               \_______||_______/
"""


def triforce(couleur="yellow"):
    """La Triforce, en jaune si la console le permet."""
    from . import i18n
    for ligne in TRIFORCE.strip("\n").split("\n"):
        print(i18n.paint(ligne, couleur))


# Le mot LINKLE ecrit en caracteres de bloc, dessine a la main ligne par
# ligne. Chaque ligne a exactement la meme largeur pour rester alignee.
LINKLE = r"""
██╗      ██╗██╗███╗   ██╗██╗     ██╗     ██╗███████╗
██║      ██║██║████╗  ██║██║     ██║     ██║██╔════╝
██║      ██║██║██╔██╗ ██║██║     ██║     ██║█████╗
██║      ██║██║██║╚██╗██║██║     ██║     ██║██╔══╝
███████╗██║██║██║ ╚████║██║     ██║     ██║███████╗
╚══════╝╚═╝╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝╚══════╝
"""


# Version courte, pour quand la largeur de la console est etroite.
LIEN = r"""
 _ _      _     __     __
| (_)_ _ | |___|  \   /  |
| | | ' \| / - \ | |\/| |
|_|_|_||_|\___/ |_|  |_|   LINKLE
"""


def linkle(couleur="cyan", court=False):
    """LINKLE en gros caracteres."""
    from . import i18n
    art = LIEN if court else LINKLE
    for ligne in art.strip("\n").split("\n"):
        print(i18n.paint(ligne, couleur))


def banniere(couleur="cyan"):
    """Ce qui s'affiche au demarrage du menu."""
    from . import i18n
    triforce("yellow")
    print()
    linkle(couleur)
    print()


def compact():
    """Version courte pour une ligne d invite de commande."""
    from . import i18n
    return i18n.paint("[Triforce] ", "yellow") + i18n.paint("LINKLE", "cyan")