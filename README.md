# 🎮 Lanceur Zelda BOTW pour Cemu

Un lanceur Windows qui installe, combine, active et vérifie des mods pour
**The Legend of Zelda: Breath of the Wild** sur **[Cemu](https://cemuulator.net/)**,
sans passer par BCML ni par des dossiers à recopier à la main.

> 🌐 English summary — A Windows launcher that deploys and verifies
> Breath of the Wild mods on Cemu, using [UKMM](https://github.com/NiceneNerd/UKMM).
> It includes a save manager, a mod picker, a graphics toggle, a self-diagnostic
> and an automated combination test bench. French documentation.

---

## Le problème que ce lanceur résout

Cemu ne sait pas charger les mods de BOTW tout seul : il faut un gestionnaire
de mods ([UKMM](https://github.com/NiceneNerd/UKMM)), et UKMM n'explique nulle
part ce qui se passe quand deux mods touchent le même fichier. Résultat
habituel : le jeu démarre, puis **bloque indéfiniment sur l'écran de
chargement**, sans le moindre message.

Ce dépôt contient :

* un **lanceur** qui installe et active un profil de mods en une touche,
* un **banc d'essai** qui rejoue réellement chaque combinaison de mods
  (fusion UKMM + déploiement vers Cemu + vérification fichier par fichier),
* une **analyse de conflits** lue dans le code source d'UKMM, qui dit quels
  mods s'écrasent mutuellement et lequel doit passer en dernier,
* des **outils de réparation** pour les mods livrés avec un manifeste cassé.

---

## Ce que fait le lanceur

| Touche | Action |
|---|---|
| `1` | Second Wind + tes mods (profil `combo`) |
| `2` | Tes mods seuls (profil `flo`) |
| `3` | Second Wind seul (profil `secondwind`) |
| `4` | **BOOST** — armes, téléportation, vol rapide (profil `boost`, le plus léger) |
| `5` | **SANS ÉCHEC** — profil `sur` : Second Wind + tout le reste de vérifié |
| `6` | **Choisis tes mods** — tu coches ce que tu veux |
| `7` | Charger une partie — tes sauvegardes, avec nom et description |
| `8` | Jeu à deux — deux manettes |
| `9` | Panneau des profils — créer / dupliquer / supprimer |
| `a` | Graphismes — mode *Léger* ou *Complet* |
| `b` | **Vérifier et réparer** — dit exactement ce qui ne va pas |
| `c` | **Tester les profils** — rejoue chaque profil et le vérifie |
| `d` | Ouvrir UKMM |
| `e` | Ouvrir Cemu |
| `0` | Quitter |

### Gestion des sauvegardes

Les parties sont chiffrées par le jeu : impossible d'en lire le nom ou la date.
Le lanceur les **renomme donc à la main** : chaque sauvegarde a un nom et une
description que tu écris, conservés dans `Sauvegardes/parties.json`. La table
liste tes parties, marque celle en cours (`<-- en cours`), et sait restaurer,
renommer ou supprimer. Chaque restauration est suivie d'une **vérification MD5**
— si la sauvegarde n'est pas rendue à l'identique, le script le dit.

**Et surtout : chaque partie retient le profil UKMM qui était actif quand tu
l'as enregistrée.** Charger une partie d'un autre profil affiche un avertissement
encadré et redemande confirmation. C'est la façon la plus fiable d'éviter le
blocage de l'écran de chargement, qui ne produit aucun message d'erreur.

---

## ⚠️ La règle d'or : une partie par profil

**Charger une partie créée avec un autre jeu de mods bloque l'écran de
chargement, indéfiniment, sans message d'erreur.**

Le jeu relit la partie à travers les fichiers de mods installés. Si le mod qui
a créé la partie n'est plus là (ou si le set de mods a changé), la lecture
plante en silence.

Conséquence : **quand tu changes de profil, tu commences une nouvelle partie.**
Le lanceur te le rappelle à l'écran après chaque déploiement.

---

## Ce que le banc d'essai a trouvé

### 1. Deux mods ne faisaient rien du tout

Un mod UKMM n'applique que les fichiers listés dans son `manifest.yml`. Deux de
nos mods annonçaient `Pack/TitleBG.pack` alors que leurszip ne contenait
rien de ce genre :

* `10x Speed Paraglider v2` — le zip ne contient que
  `Actor/AIProgram/Player_Link.baiprog` ;
* `Second Wind - Eventide Fix` — 21 fichiers (modèles, physique, sons), tous
  ignorés.

Résultat : **le vol à ×10 n'existait pas**, et le correctif Eventide n'était
jamais appliqué. `reparer-manifests.py` reconstruit le manifeste — en ne
touchant qu'aux mods totalement inertes, pour ne jamais modifier une liste
d'origine vérifiée par l'auteur du mod.

### 2. UKMM ne fusionne pas tous les fichiers

Lu dans `crates/uk-mod/src/unpack.rs` (`build_file`) :

```rust
ResourceData::Mergeable(..) => versions.fold(base, |res, v| res.merge(v))  // additionne
ResourceData::Sarc(..)      => versions.fold(base, |res, v| res.merge(v))  // additionne
ResourceData::Binary(..)    => versions.pop_back()                          // LE DERNIER
```

Pour un `.sbyml`, un `.sbactorpack`, un `.smubin`… les ajouts de tous les mods
**s'additionnent**. Pour tout le reste, le **dernier mod de la liste écrase**
les autres. `conflits.py` classe chaque fichier avec cette règle exacte et
produit la liste des paires de mods qui s'écrasent.

### 3. Un mod peut ne rien faire sans erreur

`GameData/gamedata.sarc` est présent dans le zip de 7 mods, mais **aucun
manifeste ne le déclare** : UKMM ne le déploie jamais. C'est le genre de
détail qui donne l'impression que « les mods ne marchent pas ».

### 4. Le mod le plus dangereux, c'est Relics of the Past

`conflits.py` liste les paires de mods qui partagent un fichier qu'UKMM ne
sait pas fusionner. Le classement est sans appel :

| Paire | Fichiers en commun non fusionnables |
|---|---|
| Relics of the Past ↔ Second Wind | 134 |
| Ancient Weaponry ↔ Relics of the Past | 16 |
| Second Wind ↔ Linkle | 15 |
| Relics of the Past ↔ Linkle | 7 |

Relics of the Past écrase 157 fichiers que trois autres mods fournissent
aussi. C'est pour ça que le profil **sans échec** ne le contient pas, alors
que `combo` et `flo` le gardent.

---

## Méthode du banc d'essai

Rien n'est simulé. Pour chaque combinaison :

1. un profil UKMM jetable est créé avec les mods demandés ;
2. l'ordre de fusion est écrit ;
3. **le vrai script du lanceur** (`Set-ProfilUKMM.ps1`) est appelé : remerge,
   déploiement, liens durs, pack de textes français, `rules.txt` ;
4. chaque fichier déclaré par chaque mod est recherché tel quel dans
   `merged/` **et** dans le pack graphique lu par Cemu ;
5. le profil jetable est supprimé (le disque a une place comptée).

Les résultats sont dans [`docs/combinaisons-testees.md`](docs/combinaisons-testees.md).

### Résultat de la campagne

| Suite | Ce qu'elle teste | Essais | Échecs |
|---|---|---|---|
| `solo` | chaque mod seul | 14 | 0 |
| `paires` | tous les couples de mods | 78 | 0 |
| `sw` | Second Wind + chaque autre mod | 11 | 0 |
| `cumul` | Second Wind complet + chaque autre mod | 11 | 0 |
| `presets` | les 5 profils du lanceur | 5 | 0 |
| **Total** | | **123** | **0** |

Aucune combinaison ne casse la fusion. Cela ne veut pas dire que le jeu
*démarre* avec toutes : ça veut dire que **tout est bien installé et déployé**.
Ce qui reste à vérifier, c'est le seul test que personne ne peut faire à ta
place : **lancer Cemu et appuyer sur A → Nouvelle partie**.

---

## Installation

1. **Cemu 2.x** et un jeu BOTW déjà installé et fonctionnel dans Cemu.
2. **UKMM** dans `%USERPROFILE%\Tools\UKMM\ukmm.exe`, avec son
   `settings.yml` dans `%APPDATA%\ukmm\`. UKMM a besoin du *dump* du jeu.
3. Copier le dossier `lanceur/` sur le Bureau et lancer **`Lanceur-BOTW.bat`**.

> ⚠️ Ce projet ne contient aucun fichier de jeu. Ni le jeu, ni les ROM, ni les
> DLC. Le ray tracing est impossible sur Cemu : inutile de chercher.

---

## Arborescence

```
lanceur/     le lanceur et ses scripts (ASCII, sans BOM)
outils/      vérification de profil, analyse de conflits, banc d'essai
docs/        combinaisons testées, inventaire des mods, conflits détaillés
```

Tous les scripts `.ps1` et `.bat` sont en **ASCII pur sans BOM** : PowerShell
5.1 lit un `.ps1` en ANSI, et un BOM se retrouve dans le texte affiché.

---

## Dépannage rapide

| Symptôme | Cause la plus probable |
|---|---|
| Bloqué sur l'écran de chargement | partie créée avec un autre profil → nouvelle partie |
| Cemu démarre en jeu normal | `rules.txt` absent du pack UKMM |
| Noms d'objets vides | pack `Bootup_EUfr.pack` non déployé |
| « ECHEC : le profil n'a PAS été déployé » | Cemu ou UKMM encore ouvert |
| Le jeu ne démarre pas, le pack est vide | disque plein, UKMM n'a pas pu fusionner |

La touche `b` du lanceur (**Vérifier et réparer**) liste tout ça en direct.

---

## Credits et licences

* **The Legend of Zelda: Breath of the Wild** — © Nintendo. Aucun fichier du
  jeu n'est distribué ici.
* **Cemu** — LGPL-3.0. Projet non affilié à Nintendo.
* **UKMM** — MIT, © NiceneNerd.
* **Mods** — © de leurs auteurs respectifs, distribués via GameBanana. Voir
  [`Mods/`](Mods/) et les crédits dans le README d'origine.

Code de ce dépôt : MIT — voir [`LICENSE`](LICENSE).