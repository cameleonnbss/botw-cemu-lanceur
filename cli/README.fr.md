# botw — Breath of the Wild sur Cemu

Tout ce qui entoure *The Legend of Zelda: Breath of the Wild* lancé sous Cemu
sur Windows : les mods, les profils, les sauvegardes, le jeu à deux, et un
bilan de santé qui dit ce qui ne va pas au lieu de vous laisser deviner.

**L'anglais est la langue par défaut.** Le français est à une commande :
`botw lang fr`. La même commande avec `en` revient en anglais.

```bat
botw                 :: ouvre le menu
botw check           :: le jeu va-t-il demarrer ? ne change rien
botw fix             :: repare le chargement infini
botw build           :: construit un profil en repondant a des questions
botw art             :: la Triforce et Linkle, en texte
botw graphics --restore <fichier> :: reprend les reglages des packs depuis
                                     un ancien settings.xml
botw doctor          :: bilan de santé complet
botw deploy sur      :: passe le jeu sur le profil « sans échec »
botw catalog         :: les combinaisons de mods prouvées
botw readme fr       :: ce document
```

---

## 1. Installation

Trois choses sont nécessaires. `botw tools` installe les deux premières.

| Outil | Rôle | Installé par |
|---|---|---|
| Python 3.9+ | fait tourner cet outil | vous |
| [UKMM](https://github.com/NiceneNerd/UKMM) | fusionne les mods | `botw tools install-ukmm` |
| Cemu 2.x | fait tourner le jeu | vous (avec votre propre dump) |
| BCML | *facultatif*, l'ancien gestionnaire, sous WSL | `botw tools install-bcml` |

Déposez le dossier où vous voulez. Rien à compiler, pas d'installateur, pas
de registre. Ouvrez un terminal dans le dossier et lancez :

```bat
botw.bat doctor
```

Si le menu s'ouvre et que le bilan est vert, tout est en place.

---

## 2. Le menu

`botw` sans argument ouvre le menu. Chaque commande ci-dessous est un bouton.

```
  1) Jouer avec un profil
  2) Mods
  3) Profils
  4) Deux joueurs
  5) Outils externes
  6) Bilan de santé
  7) Lire cette documentation
  8) Changer la langue
  N) commencer une NOUVELLE PARTIE (garde l'actuelle)
  F) Lire la documentation en FRANÇAIS
  Q) Quitter
```

---

## 3. Les mods

### La bibliothèque

Les mods sont dans `Desktop\BOTW\Mods`. UKMM en garde une copie dans
`%LOCALAPPDATA%\ukmm\wiiu\mods` ; les deux sont listées, et un mod présent
dans une seule est signalé.

```bat
botw mods list                  :: tout ce que vous avez, et où c'est utilisé
botw mods install -p sur "Relics of the Past.zip"
botw mods uninstall -p sur "Relics of the Past.zip"
```

Vous pouvez nommer un mod par son nom de fichier, par son nom affiché, ou par
n'importe quel fragment — `relics`, `Relics_of_the_Past.zip` et
`Relics of the Past` trouvent le même fichier.

### Téléchargement

```bat
botw mods search wind           :: cherche dans la bibliothèque, puis GameBanana
botw mods download 12345        ;; télécharge le mod 12345 et vérifie son MD5
botw mods download 12345 -i -p sur   ;; télécharge puis installe
```

Chaque téléchargement est comparé au MD5 publié par GameBanana. Un fichier
corrompu est refusé avant d'atteindre la fusion — sinon on s'en aperçoit des
heures plus tard, sous forme de plantage sans explication.

### Pourquoi `uninstall` édite un fichier au lieu d'appeler UKMM

`ukmm uninstall` écrit dans le profil **actif** et supprime le zip du stock.
C'est plus aimable que de ne rien faire, mais cela casse vos autres profils en
douceur. `botw mods uninstall` retire le mod de `profile.yml` : local,
réversible, et incapable de toucher un autre profil.

---

## 4. Les profils

Un profil est un ensemble de mods plus l'ordre de fusion. Cet ordre n'est pas
décoratif — voir §6.

```bat
botw profile list
botw profile show sur
botw profile use sur
botw profile verify sur         ;; chaque fichier déclaré est vraiment là
botw profile create speedrun "mod1.zip" "mod2.zip"
botw profile delete speedrun
```

### Combinaisons vérifiées

Le banc d'essai a fusionné, déployé et vérifié **123 combinaisons de mods,
fichier par fichier, sans aucun échec** : chaque mod seul, tous les couples,
Second Wind avec chaque autre mod, puis les cinq profils du lanceur. Ce sont
donc des résultats, pas desorantages :

```bat
botw catalog                    ;; la liste, avec le contenu de chacune
botw catalog sur --as hardcore --deploy
```

| Profil | Mods | Fichiers | Ce que c'est |
|---|---|---|---|
| `boost` | 10 | 1371 | le défaut : armes, koroks, îles, portails, tenues de champions |
| `sur` | 13 | 5614 | tout ce qui raccourcit le jeu ; pas de *Relics of the Past* |
| `combo` | 9 | 4780 | Second Wind + armes, koroks, îles, tenues |
| `flo` | 6 | 524 | le plus court : pas d'extension de carte, pas de Second Wind |
| `secondwind` | 3 | 4283 | Second Wind seul |

---

## 5. Le déploiement

`botw deploy <profil>` déroule toute la chaîne :

```
profil actif -> remerge -> deploy -> liens durs -> pack de textes FR -> rules.txt
```

Quatre points méritent d'être connus, parce que chacun a coûté des heures :

1. **`deploy_config.auto: true` est dans `%APPDATA%\ukmm\settings.yml`.**
   Chaque `remerge` déploie donc le profil **actif**. `botw` positionne le
   profil actif *avant* de fusionner, et remet votre profil par défaut après.
2. **UKMM n'ajoute que les fichiers du nouveau profil.** Ceux de l'ancien
   restent et les deux se mélangent. `botw` vide le dossier avant. Ce sont des
   liens durs : le stockage d'UKMM n'est pas touché et le coût disque est nul.
3. **`ukmm.exe` est compilé en sous-système GUI.** `& $ukmm` sous PowerShell
   ne l'attend pas et rend un code de sortie vide — un faux échec. `subprocess`
   attend le vrai processus et rend le vrai code.
4. **UKMM ne déploie jamais le pack de textes français.** Les mods qui
   ajoutent du texte déclarent `Pack/Bootup_XXxx.pack` ; sur un jeu français
   UKMM fusionne bien `Bootup_EUfr.pack` mais ne copie rien, car son manifeste
   nomme encore le fichier anglais. Résultat : noms d'objets et d'îles vides.
   `botw` pose le fichier lui-même.

`botw deploy` refuse de tourner si Cemu ou UKMM sont ouverts : Cemu verrouille
les fichiers déployés, et UKMM redéploie en sortant, ce qui écraserait ce que
vous venez d'installer.

---

## 6. L'ordre de chargement

UKMM empile les mods dans `load_order`, et **le dernier l'emporte** pour tout
fichier qu'il ne sait pas fusionner. Un mauvais ordre fait que le mod le plus
faible écrase silencieusement le plus fort.

L'ordre imposé par `botw`, du plus faible au plus fort :

```
Second Wind (core)          -> ses modules -> Ancient Weaponry -> Relics of the Past
-> armes Hyrule Warriors    -> îles -> Seamless Warping -> koroks
-> Paraglider x10           -> Farore's Wind -> Champion's Leathers -> Linkle
```

`Relics of the Past` est au-dessus d'Ancient Weaponry mais en dessous de
Linkle, et `botw profile verify` signale tout mod qui se retrouve loin de ses
fichiers.

---

## 7. Les sauvegardes

Le jeu ne voit qu'un seul emplacement de sauvegarde. Son `game_data.sav` est
**chiffré** : aucun outil — pas même celui-ci — ne peut lire un nom de
personnage ou une description. Ce sont ceux que vous tapez.

```bat
botw newgame status
botw newgame                ;; archive la partie actuelle, prépare une neuve
botw newgame revert         ;; remet la plus récente en place
botw newgame revert 2       ;; remet l'avant-dernière
```

### Le blocage sur l'écran de chargement

C'est la panne la plus déroutante de toute l'installation, et sa cause est
connue : **une sauvegarde ne s'ouvre qu'avec les mods qui l'ont créée.** Le
fichier est chiffré contre le profil. Charger une partie `boost` sous `sur`
pose le jeu indéfiniment sur l'écran de chargement, sans la moindre erreur.

D'où `botw newgame` : il met l'emplacement actuel sur le côté au lieu de le
supprimer, pour repartir à zéro sans rien perdre. Le gestionnaire de
sauvegardes `Sauvegardes-BOTW.ps1` note à quel profil appartient chaque
sauvegarde et prévient dans un cadre rouge avant d'en charger une qui ne
correspond pas.

---

## 8. Jouer à deux

**Sur le même canapé, deux manettes.** Cemu n'ouvre qu'une manette par
défaut. Une seule balise dans `%APPDATA%\Cemu\settings.xml` règle le problème :

```bat
botw coop enable             ;; PadChannels 1 -> 2
botw coop disable            ;; retour à une manette
botw coop status
```

Cemu réécrit `settings.xml` en sortant : fermez donc le jeu d'abord, `botw`
refuse de le modifier pendant que Cemu tourne.

**En réseau avec Radmin VPN.** `botw coop radmin` affiche l'adaptateur et
l'adresse trouvés, puis les cinq étapes. En bref : installez Radmin VPN sur les
deux machines, créez un réseau du même nom des deux côtés, connectez les deux,
et autorisez Cemu sur les réseaux privés dans le pare-feu Windows.

Les deux machines doivent tourner **la même version du jeu, les mêmes mods et
le même profil**. `botw profile show` l'affiche.

---

## 9. Les outils externes

```bat
botw tools list
botw tools install-ukmm      ;; depuis les versions GitHub officielles
botw tools install-bcml      ;; dans WSL, isolé, sans sudo
botw tools ukmm              ;; ouvrir le gestionnaire de mods
```

UKMM est téléchargé depuis sa version GitHub, et le SHA-256 publié à côté du
fichier est vérifié avant toute extraction — un UKMM à moitié écrit est pire
que pas d'UKMM du tout.

BCML n'a plus de version Windows : il va donc dans WSL. Pour éviter `sudo` et
toute modification du Python système, un CPython autonome est installé dans
`~/.local/python311` et BCML dans un venv `~/.local/bcml-venv`. La recette est
idempotente : la relancer n'installe rien et ne casse rien.

---

## 10. Quand ça ne marche pas

```bat
botw doctor
```

Quinze contrôles en sept groupes : UKMM et sa configuration, les programmes
qui doivent être fermés, si le profil actif est entièrement fusionné, ce que
Cemu va réellement lire, les sauvegardes, les outils externes, et l'espace
disque. La commande renvoie un code non nul si quelque chose a échoué, elle
fonctionne donc dans un script.

La cause d'échec la plus fréquente après l'installation de mods est **une
sauvegarde qui ne correspond pas au profil**. Voir §7.

---

## Les commandes

| Commande | Effet |
|---|---|
| `botw` | ouvre le menu |
| `botw doctor` | bilan de santé complet |
| `botw check` | ce qui peut bloquer le chargement, sans rien changer |
| `botw fix [-y] [--keep-cosmetics] [--no-cheats] [--no-deploy]` | repare le chargement infini |
| `botw build [--name <n>] [--yes] [--no-deploy]` | construit un profil en repondant a dix questions |
| `botw art` | la Triforce et Linkle, en texte |
| `botw graphics [--mods] [--off]` | resolution et correction des couleurs |
| `botw deploy <profil> [--activate]` | fusionne et déploie |
| `botw profile list\|show\|use\|create\|delete\|verify` | profils |
| `botw mods list\|search\|download\|install\|uninstall` | mods |
| `botw tools list\|install-ukmm\|install-bcml\|ukmm` | outils externes |
| `botw catalog [<nom>] [--as <profil>] [--deploy]` | combinaisons vérifiées |
| `botw coop status\|enable\|disable\|radmin` | deux joueurs |
| `botw newgame [revert <n>\|status]` | partie neuve, on garde l'ancienne |
| `botw readme [en\|fr] [-o]` | ce document |
| `botw matrix [suite]` | le banc d'essai |
| `botw lang [en\|fr]` | langue |
| `botw --lang fr <commande>` | une exécution en français |

---

## Limites connues

* Le texte ajouté par les mods est **en anglais uniquement**. Il n'existe pas
  de source française en amont : c'est une limite des mods, pas de l'outil.
* Le ray tracing est impossible sous Cemu avec la place disque disponible.
* Le point de recherche de GameBanana renvoie actuellement 404. `botw mods
  search` cherche quand même dans votre bibliothèque locale et signale
  l'échec au lieu de prétendre n'avoir rien trouvé.
* `botw newgame` déplace l'*emplacement*, pas les archives : vos autres
  sauvegardes gérées par `Sauvegardes-BOTW.ps1` ne sont pas touchées.

## Licence

MIT. Cet outil ne contient aucun élément du jeu.

---

## Le chargement infini

Le jeu reste sur son ecran de chargement et n'arrive jamais a la suite. Aucun
crash, aucune erreur, aucune ligne de log. C'est le probleme le plus signale,
et il vient rarement du profil de mods que tu viens de deployer.

**Ce sont les packs graphiques.** Cemu en garde la liste dans
`%APPDATA%\Cemu\settings.xml`. Deux familles cassent un jeu modde :

| Pack | Pourquoi il bloque |
|---|---|
| `ExtendedMemory` | repointe +2 Go de memoire et exige le *jeu* recompile. Son propre `rules.txt` le dit, et dit que le code ne doit pas vivre dans un mod. |
| `HD_Map_and_Icons` | remplace des fichiers du jeu, ce que les `rules.txt` d'UKMM interdisent avec un autre chargeur de mods. |

Les packs cosmetiques (`DrawDistance`, `FPS++`, `DivineLaserBeam`,
`Enhancements`, `Graphics`) ne sont pas dangereux, mais ils se disputent les
memes fichiers que les mods : ils sont donc desactives par defaut. Les
triches sont conservees : elles ne touchent pas au code du jeu.

```bat
botw check          :: dit ce qui bloque, ne change rien. Code 0 = tout va bien.
botw fix            :: retire les packs bloquants, redeploie, garde la sauvegarde
botw fix --minimal  :: idem, et desactive aussi les triches
```

Le lanceur fait la meme chose avec les touches **i** (diagnostic) et **j**
(reparation).

`botw check` regarde aussi deux choses invisibles depuis le jeu :

* **la sauvegarde**. Un fichier de sauvegarde ne s'ouvre qu'avec les mods qui
  l'ont cree : la cle est derivee du jeu de mods. `botw` note chaque
  deploiement, donc il peut te dire que la partie vient de `sur` alors que
  `boost` est actif. La charger bloque, en silence.
* **le deploiement**. Si le profil actif n'est pas entierement fusionne et
  deploye, Cemu demarre avec un melange de fichiers.

Le code de sortie vaut 0 si rien ne peut bloquer, 1 sinon : tu peux le mettre
dans un script.

### Si le jeu refuse toujours de demarrer

```bat
botw newgame        :: met l'emplacement de cote, le garde, part d'une neuve
```

C'est la reponse quand une sauvegarde refuse de se charger. L'ancienne est
*deplacee*, jamais supprimee ; `botw newgame revert` la remet en place.


---

## Graphismes et correction des couleurs

`botw fix` desactive les packs graphiques en meme temps que ceux qui bloquent
le chargement : un jeu bloque vaut moins qu'une image terne. Mais il ne
restait aucun moyen de les remettre. Le correctif etait irreversible.

```bat
botw graphics           :: resolution, anticrenelage, correction des couleurs
botw graphics --mods    :: aussi les packs tiers (DrawDistance, FPS++...)
botw graphics --off     :: retour a l'image d'origine
```

Ce que ca reactive :

| Pack | Ce que ca change |
|---|---|
| `Graphics` | resolution, anticrenelage, resolution des ombres |
| `Enhancements` | **correction des couleurs** (prereglages *Clarity*), reflets, filtrage anisotrope |
| `Workarounds/*` | les correctifs de compatibilite de Cemu : crash AMD/NVIDIA, cloudes, herbe, saccades CPU |

`Enhancements` porte deja `$preset:int = 10` dans sa section `[Default]`, soit
le prereglage *Clarity* de Serfrost - celui que Cemu recommande. La correction
des couleurs est donc appliquee sans qu'on devine le format XML des
prereglages. Tu veux un autre prereglage ? Choisis-le dans la fenetre des
packs graphiques de Cemu.

Deux garanties, couvertes par les tests :

* les packs qui causent le chargement infini (`ExtendedMemory`,
  `HD_Map_and_Icons`) sont **retires dans la meme operation**. Reactiver
  l'image ne peut jamais remettre le jeu dans l'etat qui le faisait boucler ;
* le pack UKMM reste en premier dans la liste : c'est lui qui porte tes mods,
  et l'ordre n'est pas neutre.

Les packs tiers restent coupes par defaut : `DrawDistance`, `FPS++` et
`DivineLaserBeam` changent l'image bien plus que les packs officiels.
Si une réécriture les remettait un jour à zéro, tes réglages sont encore dans
les sauvegardes que les outils laissent à côté de `settings.xml` :

```bat
botw graphics --restore "%APPDATA%\Cemu\settings.xml.avant-fix-botw"
```

Le fichier passé en argument est un ancien `settings.xml` : la commande
recopie ses entrées de packs **avec leurs préréglages**, donc la résolution,
la limite d'images, la distance d'affichage et les couleurs reviennent
exactement. Les packs qui bloquent le chargement ne sont jamais restaurés,
 quoi que contienne le fichier. Une copie de l'état courant est écrite à côté
avant, avec le suffixe `.avant-restauration`.
