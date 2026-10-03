# Mods BOTW sur Cemu — guide court

> 📖 **La documentation complète, c'est [`LISEZ-MOI.txt`](LISEZ-MOI.txt)** (16
> sections : les mods, l'ordre de fusion, le blocage de l'écran de chargement,
> les sauvegardes, le dépannage). Ce fichier n'est qu'un résumé.

## Le plus simple : le lanceur

Double-clic sur **`Lanceur-BOTW.bat`**, dans ce dossier.

```
JOUER                        OUTILS
 1 Second Wind + TES MODS     7 Charger une partie
 2 TES MODS seuls             8 Jeu a deux
 3 Second Wind seul          9 Panneau des profils
 4 BOOST                     a Graphismes
 5 SANS ECHEC                b Verifier et reparer
 6 CHOISIR TES MODS          c Tester les profils
                             d Ouvrir UKMM
                             e Ouvrir Cemu
                             0 Quitter

botw  (la CLI, en anglais ; "botw lang fr" pour le francais)
 f Menu botw                g Nouvelle partie         h Documentation
```

Le menu affiche en permanence le **profil actif** et son nombre de mods. Si
Linkle n'apparaît pas en jeu, regarde cette ligne.

**Ferme Cemu avant toute option 1 à 6.** Le script refuse de travailler
sinon, et il te dit pourquoi.

| Touche | Profil UKMM | Mods en jeu |
|---|---|---|
| `1` | `combo` | Second Wind + tes 6 mods |
| `2` | `flo` | Linkle, îles, Relics, armes anciennes |
| `3` | `secondwind` | Second Wind seul |
| `4` | `boost` | 10 mods, sans Second Wind — le plus léger |
| `5` | `sur` | Second Wind + tout le reste qui a pu être vérifié |

L'option `6` est la pièce maîtresse : tu coches les mods que tu veux, UKMM
fusionne, redéploie, et tu joues.

## ⚠️ Une partie par profil

Charger une partie créée avec un autre jeu de mods **bloque l'écran de
chargement, indéfiniment, sans message d'erreur**. C'est le problème numéro un.

Le gestionnaire de sauvegardes note donc le profil UKMM actif au moment de
chaque enregistrement, et **refuse de te laisser charger une partie d'un autre
profil sans un avertissement explicite** (touche `7`).

## Sauvegardes

Le jeu n'a **qu'un seul emplacement de sauvegarde visible** (les dossiers `0` à `5`
de `user\80000001` sont des tampons internes). Pour plusieurs parties distinctes :
`Sauvegardes-BOTW.bat`, ou la touche `7` du lanceur.

```
1 Enregistrer ma partie    -> nom + description
2 CHARGER une partie
3 Charger une partie ET jouer
4 Changer le nom / la description
5 Supprimer une partie
```

Une restauration copie d'abord la partie en cours, puis **vérifie par MD5** que la
partie chargée est bien celle demandée.
## Ouvert : le menu `botw`

Touche **`f`** du lanceur, ou `python botw\botw.py` dans un terminal. C'est la
meme chose que le menu du lanceur, mais en anglais par defaut, et ca va plus
loin : tout ce que le lanceur fait est la une commande.

```
 1 Play a game with a profile     5 External tools
 2 Mods                           6 Health check
 3 Profiles                       7 Read this documentation
 4 Two players                    8 Change the language
 N start a NEW GAME               F Read the documentation in FRENCH
 Q Quit
```

Les trois commandes que tu utiliseras le plus :

```bat
python botwotw.py lang fr                   REM tout en francais, definitivement
python botwotw.py deploy sur --activate    REM fusionne, deploye, devient le defaut
python botwotw.py doctor                   REM 15 controles, dit ce qui ne va pas
```

Si tu prefere la ligne de commande, tout y est : `botw --help`.
Pour un seul lancement en francais, sans rien changer : `--lang fr`.

---

## Dépannage

La touche **`b` — Vérifier et réparer** regarde tout d'un coup (UKMM, profil
actif, `rules.txt`, pack de textes français, cohérence du déploiement,
sauvegardes, place disque) et dit ce qui ne va pas.

Pour savoir **quel mod** pose problème : touche `6`, et décocher un mod à la
fois

## Le chargement infini

Le jeu reste sur son écran de chargement. Aucun crash, aucune erreur. C'est le
problème le plus signalé, et il vient rarement de tes mods : ce sont les
**packs graphiques** de Cemu, listés dans `%APPDATA%\Cemu\settings.xml`.

| Pack | Pourquoi il bloque |
|---|---|
| `ExtendedMemory` | remappe +2 Go et exige le jeu **recompilé** |
| `HD_Map_and_Icons` | remplace des fichiers du jeu, interdit avec UKMM |

Les packs cosmétiques (`DrawDistance`, `FPS++`, `Enhancements`, `Graphics`)
sont désactivés aussi : ils prennent les mêmes fichiers que les mods.

**Depuis le lanceur :** touche **i** pour le diagnostic, **j** pour réparer.
Rien n'est supprimé, ta sauvegarde n'est pas touchée.

**En ligne de commande :**

```bat
python botw\botw.py check     :: dit ce qui bloque, ne change rien
python botw\botw.py fix       :: retire les packs bloquants, puis redeploie
```

`check` vérifie aussi que la sauvegarde a bien été créée par le profil actif.
Une sauvegarde ne s'ouvre qu'avec les mods qui l'ont créée, et le résultat
serait un chargement infini sans un seul message.

Si rien ne corrige le problème, une partie neuve sans perdre l'ancienne :

```bat
python botw\botw.py newgame
```


## Les graphismes

`botw fix` (touche **j**) coupe les packs graphiques en même temps que ceux
qui bloquent le chargement. Pour les remettre — résolution, anticrenelage et
**correction des couleurs** :

```bat
python botw\botw.py graphics
```

Ça active `Graphics` (résolution, anticrenelage, ombres), `Enhancements`
(**préréglages Clarity**, c'est-à-dire la correction des couleurs) et les
correctifs de compatibilité de Cemu (`Workarounds`). `Enhancements` applique
par défaut le préréglage de Serfrost, celui que Cemu recommande.

Les packs qui bloquent le chargement restent désactivés : la commande les
retire dans la même opération.

Touche **G** du menu `botw`, ou :
`python botw\botw.py graphics --off` pour revenir à l'image d'origine.
