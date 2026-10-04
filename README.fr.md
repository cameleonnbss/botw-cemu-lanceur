# BOTW sur Cemu — lanceur, profils de mods, sauvegardes

[![Français](README.fr.md) ![English](README.md)

```
                                 .:.
                               __   ___    __    ___    __    ___
                              / /  / __ \  / /__  / __ \  / /  / __ \
                             / /  / /_/ /  / / _ \/ / / / / /  / /_/ /
                            / /__/ /  __/  / /_/ / /_/ / / /__/ /  __/
                            \____/_/   \_\/ ____/ \___/ \___/_____/  \_\

                       _   _         __     ___                 __
                      | | | |       / /    / __ \   __  __ ___  / /
                      | |_| |      / /    / / / /  / / / //_/  / /
                      |  _  |     / /___ / /_/ /  / /_/ / ,<   / /
                      |_| |_|    /_____/\____/  /_/\__,_/_/|_| /_/

                        B R E A T H   O F   T H E   W I L D
                        - - - - - - - - - - - - - - -
                        mods, profils, sauvegardes, Cemu
```

Un outil pour faire tourner *The Legend of Zelda: Breath of the Wild* sur
**Cemu** avec des mods : il installe des combinaisons de mods qui **marchent
vraiment**, les déploie, tient une sauvegarde par jeu de mods, et répare le
célèbre chargement infini.

Aucun réglage à la main. Aucune partie déplacée sans prévenir.

---

## Sommaire

- [Installation](#installation)
- [Jouer](#jouer)
- [L'outil en ligne de commande](#loutil-en-ligne-de-commande)
- [Les profils livrés](#les-profils-livrés)
- [Une partie par profil](#-une-partie-par-profil)
- [Les quatre causes du chargement infini](#les-quatre-causes-du-chargement-infini)
- [Le chargeur de sauvegardes](#le-chargeur-de-sauvegardes)
- [Construire son propre profil](#construire-son-propre-profil)
- [Deux joueurs](#deux-joueurs)
- [Graphismes](#graphismes)
- [Ce que le banc d'essai a trouvé](#ce-que-le-banc-dessai-a-trouvé)
- [Tests](#tests)
- [Arborescence](#arborescence)
- [Dépannage](#dépannage)
- [Crédits](#crédits-et-licences)

---

## Installation

Il faut [Python 3.8+](https://www.python.org/downloads/). Rien d'autre :
UKMM et Cemu sont **vérifiés**, pas installés en douce.

```bash
git clone https://github.com/cameleonnbss/botw-cemu-lanceur.git
cd botw-cemu-lanceur
python installer.py
```

L'installateur, étape par étape :

1. **vérifie Python** ;
2. **copie** le lanceur et l'outil vers `%USERPROFILE%\Desktop\BOTW` ;
3. **contrôle chaque fichier copié par MD5** — une copie à moitié faite
   produit un lanceur qui semble marcher et qui exécute du code vieux de
   trois semaines : c'est la panne la plus invisible du projet ;
4. **vérifie les fichiers que Windows exécute** : `.bat`, `.cmd` et `.ps1`
   doivent être ASCII, sans BOM, en fins de ligne CRLF. PowerShell 5.1 lit
   un `.ps1` sans BOM en ANSI, et un `.bat` en LF peut s'arrêter sur une
   ligne au hasard ;
5. **cherche UKMM et Cemu**, et dit exactement quoi installer sinon.

Options :

| Option | Effet |
|---|---|
| `--dest D:\BOTW` | installe ailleurs que sur le bureau |
| `--check` | vérifie sans écrire un seul octet |
| `--shortcut` | ajoute le lanceur au démarrage de Windows |

**Re-lancer `installer.py` ne détruit rien.** Aucun profil, aucune partie,
aucun mod n'est touché : c'est une réinstallation par-dessus une installation.

### Ce qu'il faut aussi

| Programme | Où le mettre |
|---|---|
| **[UKMM](https://github.com/SuperKEDITachi/ukmm)** | `ukmm.exe` dans `%USERPROFILE%\Tools\UKMM\` |
| **[Cemu 2.x](https://cemu.info/)** | laisse-le dans ton dossier `Downloads` |

L'installateur les cherche et te dit ce qui manque. Il ne les télécharge pas
tout seul : ce sont des logiciels tierces, avec leurs propres licences.

---

## Jouer

Double-clic sur `Lanceur-BOTW.bat`.

| Touche | Action |
|---|---|
| **`1`** | **Ma partie principale** — Second Wind + vos cheats, *avec sa partie* |
| **`2`** | **Ma partie FULL MODS** — les 13 mods, *avec sa partie* |
| `3` | Second Wind seul (profil `secondwind`) |
| `4` | **BOOST** — armes, téléportation, vol rapide (le plus léger) |
| `5` | Vos mods seuls — Linkle, îles, armes anciennes (profil `flo`) |
| `6` | **Choisis tes mods** — tu coches ce que tu veux |
| `7` | Charger une partie — avec nom et description |
| `8` | Jeu à deux |
| `9` | Panneau des profils |
| `a` | Graphismes — mode *Léger* ou *Complet* |
| `b` | **Vérifier et réparer** — dit exactement ce qui ne va pas |
| `c` | **Tester les profils** — rejoue et vérifie chaque profil |
| `d` | Ouvrir UKMM |
| `e` | Ouvrir Cemu |
| `0` | Quitter |

### Les deux touches du quotidien

Une touche suffit parce qu'elle fait les trois choses dans l'ordre :

1. elle met la partie en cours **de côté** ;
2. elle déploie le bon jeu de mods ;
3. elle remet **la partie qui va avec**.

**L'autre partie n'est jamais perdue** : elle est archivée, et l'autre touche
la reprend.

> ⚠️ Une sauvegarde créée avec un jeu de mods ne s'ouvre pas avec un autre.
> Le jeu reste bloqué sur l'écran de chargement, **sans un seul message
> d'erreur**. Changer les mods sans changer la partie, c'est exactement le bug
> qui bloque ton jeu — c'est pourquoi ces deux touches font les deux ensemble.

Si le profil demandé est déjà actif et que la partie lui appartient, rien
n'est redéployé : l'outil compte les fichiers et vérifie que le déploiement
correspond à la fusion. Mesuré sur la machine de développement, la même
bascule passe de **34,4 s à 0,33 s**.

Les deux jeux de mods sont **configurables** — ce dépôt est universel, et
Second Wind n'est le bon choix que chez ceux qui l'ont installé :

```bash
botw config set raccourcis '{"jeu_1":"boost","jeu_2":"sur"}'
```

---

## L'outil en ligne de commande

`botw` couvre tout ce que fait le lanceur. La langue est **celle de ton
système** : français sur un poste français, anglais ailleurs.

```bash
botw lang fr      # forcer le français
botw lang en      # forcer l'anglais
botw lang auto    # revenir à la détection automatique
```

| Commande | Ce qu'elle fait |
|---|---|
| `botw jeu <profil> --lancer` | change de jeu de mods **et** de partie, puis lance Cemu |
| `botw check` | le jeu va-t-il démarrer ? trois lignes, rien ne change |
| `botw fix -y` | retire les packs qui bloquent le chargement, redéploie |
| `botw doctor` | bilan de santé complet |
| **`botw installmods <fichier\|lien>`** | **installe un mod depuis un `.zip` ou une URL** |
| `botw mods list` | la bibliothèque locale |
| `botw mods search <mot>` | recherche en ligne |
| `botw mods download <id>` | télécharge un mod sans l'installer |
| `botw catalog <nom> --deploy` | recrée une combinaison testée |
| `botw catalog` | la liste des combinaisons |
| `botw profile list` | les profils et leur nombre de fichiers |
| `botw profile verify <nom>` | vérifie qu'un profil est complet |
| `botw newgame [revert]` | repart de zéro sans perdre la partie |
| `botw graphics` | mode rapide ou belle image |
| `botw coop` | deux manettes |
| `botw tools install-ukmm` | installe UKMM |
| `botw ui` | le menu, avec des boutons |
| `botw readme fr` | cette documentation, en français |

### `installmods` — le mod que tu as sous la main

La bibliothèque locale ne connaît que les mods déjà vus, et la recherche en
ligne ne répond plus. Donc :

```bash
botw installmods "C:\Users\toi\Downloads\MonMod.zip"   # un fichier du disque
botw installmods "https://exemple.org/monmod.zip"      # un lien
botw installmods "MonMod.zip" -p sur                   # dans quel profil
botw installmods --list                                # la bibliothèque
```

Le fichier est **copié** dans la bibliothèque, ou **téléchargé** s'il s'agit
d'un lien. Deux garde-fous :

- un zip sans `meta.yml` est refusé, **et retiré** — sinon `botw mods list`
  le reproposerait à chaque fois ;
- un lien vers une page web (du HTML) est refusé pareil.

Le mod entre dans `profile.yml`, donc le retrait est trivial et réversible.

---

## Les profils livrés

Ce ne sont pas des listes de mods : ce sont des combinaisons **réellement
fusionnées, déployées et jouées**.

| Profil | Mods | Fichiers | Ce que c'est |
|---|---|---|---|
| `sur` | 13 | 5 614 | Second Wind + tout le reste de vérifié — **sans échec** |
| `boost` | 10 | 1 371 | armes Hyrule Warriors, koroks en nombre, îles, portails instantanés |
| `flo` | 6 | 524 | le plus court : koroks, armes, îles et tenues |
| `secondwind` | 3 | 4 283 | Second Wind seul : sanctuaires étudiés, aucun échec |

`botw catalog` en liste d'autres, avec leur nombre de fichiers.

### Ce qui est volontairement exclu

Un seul mod de la bibliothèque est écarté : `Relics_of_the_Past`. Il
remplace **249 fichiers** que UKMM ne sait pas fusionner, donc il efface
purement et simplement ce qu'un autre mod fournissait — et il casse des
quêtes en cours. Un mod qui gagne en effaçant les autres n'est pas une
combinaison, c'est un pari.

L'outil le refuse et te dit pourquoi, plutôt que de produire un profil qui
plante trois heures plus tard.

---

## ⚠️ Une partie par profil

**Charger une partie créée avec un autre jeu de mods bloque l'écran de
chargement, indéfiniment, sans message d'erreur.**

Le jeu relit la sauvegarde à travers les fichiers de mods installés. Si le mod
qui l'a créée n'est plus là — ou si le set a changé — la lecture plante en
silence.

`botw jeu` fait donc les deux ensemble, dans cet ordre :

1. la partie courante est **archivée d'abord**, étiquetée avec le profil qui
   peut la charger ;
2. le nouveau profil est déployé ;
3. la partie de *ce* profil-là est remise en place, si elle existe.

Si l'étape 2 échoue, la partie est déjà de côté. **L'archive est une copie** :
l'original n'est jamais déplacé.

`botw newgame revert <n>` remet n'importe quelle partie archivée en place.

---

## Les quatre causes du chargement infini

Toutes signalées par `botw check`, toutes réparées par `botw fix`.

| Cause | Symptôme | Réparation |
|---|---|---|
| `Extended Memory` | le jeu ne finit jamais de charger | le pack est retiré |
| `HD Map and Icons` | **toutes** les icônes d'inventaire invisibles | `default = true` → `false` |
| `Draw Distance` | l'arme que Link tient est invisible | réglages ramenés à des valeurs sûres |
| un mod seul, qui n'écrase rien | le mod « fait » mais ne fait rien | signalé par `botw profile verify` |

Le cas `HD Map and Icons` est le plus vicieux : son `rules.txt` porte
`default = true`, donc **Cemu l'active à chaque lancement, même après l'avoir
retiré de `settings.xml`**. Le retirer de la liste ne servait à rien — le pack
revenait, et le fichier paraissait parfaitement propre. L'outil regarde
désormais ce qu'il y a **sur le disque**.

---

## Le chargeur de sauvegardes

`Sauvegardes-BOTW.bat` — tes parties avec un **nom** et une **description**,
parce que le jeu les chiffre : impossible d'en lire la date soi-même.

- il affiche, pour chaque partie, **les mods qui peuvent la charger** ;
- si tu charges une partie qui n'a pas été créée avec le profil actif, il
  **propose de basculer tout seul**, dans l'ordre sûr ;
- il archive avant de déployer, donc un échec ne coûte pas ta partie ;
- il refuse une archive à moitié copiée : un dossier interrompu existe bel et
  bien, et le remettre en place ferait perdre la partie sans un seul message.

---

## Construire son propre profil

Deux façons, et les deux demandent des questions :

```bash
botw build                 # quelques questions, il construit et déploie
botw catalog combo --deploy
```

L'option **6** du lanceur (« Choisis tes mods ») va plus loin : une liste de
cases à cocher avec **tous** tes mods, lus dans le dossier `Mods\`. Tu tapes
les numéros à cocher ou décocher, et UKMM fusionne, redéploie, et tu joues.

```bash
botw profile verify <profil>  # signale les mods qui n'écrasent rien
```

---

## Deux joueurs

```bash
botw coop status     # combien de manettes sont configurées
botw coop enable     # passe à deux manettes
botw coop disable
```

Sur une connexion locale, un VPN comme Radmin VPN évite de passer par le
réseau de la partie. `botw coop radmin` affiche la marche à suivre.

---

## Graphismes

```bash
botw graphics         # mode rapide ou belle image
```

Deux modes, parce que tout ne peut pas être activé en même temps : Cemu ne
sait pas exécuter les shaders en même temps que tout le reste. Le mode
rapide garde le jeu fluide ; le mode belle image garde les ombres et la
distance d'affichage.

---

## Ce que le banc d'essai a trouvé

`outils/matrice.py` rejoue chaque combinaison avec la vraie chaîne — fusion,
déploiement, vérification fichier par fichier. Les rapports sont dans
[`docs/`](docs/).

Ce que ça a donné, en clair :

- deux mods ne faisaient **rien du tout** ;
- UKMM ne fusionnait pas **tous** les fichiers ;
- un mod pouvait ne rien faire, **sans lever la moindre erreur** ;
- le mod le plus dangereux était celui qu'on aurait gardé.

---

## Tests

```bash
cd cli && python -m pytest tests -q                  # 334 tests : l'outil botw
python -m pytest outils/tests_installeur.py -q      # 18 tests : l'installateur
```

L'installateur se teste en l'installant, dans un dossier temporaire : un
dossier de destination tapé avec des `/`, un `--check` qui ne doit rien écrire,
une copie abîmée après coup, et une seconde installation qui ne doit rien
réécrire. `outils/verifier-doc-cli.py` fait passer chaque commande citée dans
les deux README par le vrai analyseur d'arguments — une documentation qui cite
une commande inexistante est pire que pas de documentation.

Le projet prend les fichiers Windows très au sérieux : `.bat`, `.cmd` et
`.ps1` doivent être ASCII, sans BOM, en CRLF. `outils/verifier-lanceur-menu.py`
vérifie en plus que **chaque touche du menu atteint une étiquette réelle** —
un `goto` vers une étiquette inexistante ne lève aucune erreur : la fenêtre se
ferme et l'utilisateur ne voit rien.

---

## Arborescence

```
installer.py         l'installateur, à lancer en premier
lanceur/             les .bat et .ps1
cli/                 l'outil botw, ses tests et ses langues
outils/              scripts de vérification et de banc d'essai
docs/                rapports des campagnes de test
```

---

## Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| chargement infini | profil ≠ profil de la partie | touche `1` ou `2`, ou `botw jeu <profil>` |
| chargement infini | pack bloquant | `botw check` puis `botw fix` |
| icônes invisibles | `HD Map and Icons` | `botw fix` (réversible) |
| « profil inconnu » | le profil a été supprimé | `botw catalog <nom> --deploy` |
| mods en jeu vides | pack de langue non déployé | `botw fix` |
| rien ne s'ouvre au double-clic | PowerShell 5.1 et l'encodage | `python installer.py` répare tout |

---

## Crédits et licences

- *The Legend of Zelda: Breath of the Wild* — Nintendo. Ce dépôt **n'inclut
  aucun fichier de jeu**.
- [Cemu](https://cemu.info/) — émulateur Wii U, sous licence GPLv3.
- [UKMM](https://github.com/SuperKEDITachi/ukmm) — gestionnaire de mods.
- [BCML](https://github.com/RoadKill64/Bcml) — chargeur de mods.
- Les mods sont distribués sur GameBanana et appartiennent à leurs auteurs.

Voir [LICENSE](LICENSE).
