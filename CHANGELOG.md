# Journal des modifications

Toutes les versions publiées suivent [SemVer](https://semver.org/lang/fr/).

## [1.1.0] — 4 octobre 2026

### Ajouté
- **Diagnostic et réparation du chargement infini** (`botw check`, `botw fix`).
  La cause du blocage n'est presque jamais le profil de mods : ce sont les
  packs graphiques de Cemu, gardés dans `%APPDATA%\Cemu\settings.xml`.
  `ExtendedMemory` remappe +2 Go et exige le jeu recompilé ;
  `HD_Map_and_Icons` remplace des fichiers du jeu, ce que les `rules.txt`
  d'UKMM interdisent avec un autre chargeur. Les packs cosmétiques sont
  désactivés aussi, les triches conservées.
  `botw check` ne change rien et renvoie 0 si rien ne peut bloquer ; `botw fix`
  retire les packs fautifs puis redéploie, sans toucher à la sauvegarde.
- **Constructeur de profil** (`botw build`) : dix questions oui/non — dont
  **Linkle** et **Second Wind**, les deux plus demandées. Les mods sont
  assemblés du plus léger au plus lourd, le profil est vérifié avant d'être
  déployé, et le nom est proposé d'après les réponses.
- **Art ASCII** (`botw art`) : la Triforce et Linkle.
- **Lanceur : deux touches de plus.** `i` diagnostique, `j` répare, `f` ouvre
  le menu `botw`, `g` prépare une nouvelle partie, `h` la documentation.
  Vingt touches, chacune testée par `outils/tester-lanceur.py`.
- **Historique des déploiements** dans `Sauvegardes\NouvellePartie\slot.json` :
  c'est lui qui permet de dire avec quels mods une sauvegarde a été créée.
- **Graphismes et correction des couleurs** (`botw graphics`) : remet la
  résolution, l’anticrénelage et les préréglages *Clarity* du pack
  `Enhancements` — c’est-à-dire la **correction des couleurs** — plus les
  huit correctifs de compatibilité de Cemu (`Workarounds`). C’est la commande
  inverse de ce que `botw fix` fait sur ces packs : jusqu’ici, le correctif du
  chargement était **irréversible**. Deux garanties, couvertes par les tests :
  les packs bloquants (`ExtendedMemory`, `HD_Map_and_Icons`) sont retirés dans
  la même opération, et le pack UKMM reste en premier dans la liste. Les packs
  tiers (`DrawDistance`, `FPS++`, `DivineLaserBeam`) restent désactivés par
  défaut et reviennent avec `--mods`. Touche `G` du menu.
- **`outils/maj-bureau.py`** : recopie le programme vers le bureau et **prouve**
  que la copie est identique (MD5 fichier par fichier), supprime les fichiers
  devenus obsolètes, et revérifie qu'aucun `.bat` ou `.ps1` n'a perdu son
  ASCII, son absence de BOM ou ses CRLF.

### Corrigé
- **`botw build` déployait un profil par accident quand stdin était fermé.**
  Le garde-fou reposait sur `sys.stdin.isatty()`, qui renvoie *vrai* sous Git
  Bash même avec `< /dev/null` : MSYS résout la redirection, Windows ne voit
  qu'un flux. Les réponses par défaut suffisaient alors à créer un profil, le
  déployer, le rendre actif — donc à rendre la sauvegarde existante
  illisible, le pire résultat possible, et invisible. Le contrôle repose
  désormais sur le fait qu'aucune question n'a pu être posée, avec un test
  qui reproduit exactement le mensonge de `isatty`.
- **`botw build` renvoyait un tuple en code de sortie.** `construire()` rend
  `(nom, code)` et `cmd_build` le comparait à `0` : la condition n'était jamais
  vraie, le profil n'était jamais activé, et `sys.exit()` recevait un tuple.
- **`botw check` annonçait « tout va bien » à une sauvegarde incompatible.**
  Le profil était lu comme « celui du dernier déploiement » : après
  `deploy boost`, une partie enregistrée, puis `deploy autre`, la partie
  était attribuée à `autre`. C'est précisément le cas que la commande doit
  attraper. Le profil retenu est maintenant celui qui était actif quand la
  sauvegarde a été écrite.
- **Un compte de fichiers déployés négatif.** Le dossier du pack graphique
  pouvait ne pas exister ; retrancher `rules.txt` donnait `-1`, et le
  diagnostic signalait un décalage de déploiement qui n'existait pas.
- **`botw build` sans terminal** explique désormais ce qu'il faut écrire
  (`botw build --yes --name <nom>`) au lieu de faire son travail par défaut.

### Divers
- Deux caractères CJK qui s'étaient glissés dans `builder.py`, et un test qui
  refuse désormais toute écriture étrangère dans les sources.
- Les locales sont vérifiées dans les deux sens : 352 clés, et aucun test ne
  fige plus un numéro d'option du menu.

## [1.0.0] — 4 octobre 2026

### Ajouté
- **Le CLI `botw`** (`cli/`) : un vrai programme en ligne de commande, en
  Python, sans dépendance externe. English by default, French with
  `botw lang fr`. Menu interactif et commandes complètes : `doctor`, `deploy`,
  `profile`, `mods`, `tools`, `catalog`, `coop`, `newgame`, `readme`, `config`,
  `matrix`. Code de sortie 0 ou 1 pour chaque commande, donc utilisable dans
  un script.
- **Installation des outils externes depuis l'outil** :
  `botw tools install-ukmm` télécharge la dernière version publiée sur GitHub
  et vérifie son SHA-256 avant d'extraire ; `botw tools install-bcml` installe
  BCML dans WSL avec un CPython autonome et un environnement virtuel isolé,
  sans privilèges administrateur et sans toucher au Python du système.
- **Téléchargement de mods** : `botw mods search` interroge la bibliothèque
  locale puis GameBanana ; `botw mods download <id>` vérifie le MD5 publié
  avant d'écrire le fichier, et `-i` enchaîne sur l'installation.
- **Catalogue des combinaisons vérifiées** (`botw catalog`) : les cinq profils
  du lanceur et leurs listes de mods, tels que mesurés par le banc d'essai.
  `botw catalog sur --as hardcore --deploy` recrée la combinaison dans un
  profil neuf et la déploie.
- **Nouvelle partie** (`botw newgame`) : met l'emplacement de sauvegarde
  courant de côté sans le supprimer, et `botw newgame revert` le remet en
  place. C'est la parade documentée au blocage sur l'écran de chargement.
  Index et archives dans un dossier à part, pour ne pas toucher au
  `parties.json` du gestionnaire de sauvegardes.
- **Jeu à deux** (`botw coop`) : réglage de `PadChannels` dans
  `settings.xml`, et un guide Radmin VPN en cinq étapes qui affiche
  l'adaptateur et l'adresse détectés.
- **140 tests hors ligne** (`cli/tests`) : ils repointent `%APPDATA%`,
  `%LOCALAPPDATA%` et `%USERPROFILE%` vers un dossier temporaire et ne
  touchent jamais une vraie sauvegarde ni un vrai profil.
- **Trois touches dans le lanceur** : `f` menu botw, `g` nouvelle partie,
  `h` documentation en français ou anglais. Le test de routage passe de 16 à
  19 touches, sans échec.
- **`README.md` et `README.fr.md`** du CLI, accessibles par `botw readme`
  et par les boutons `7` et `F` du menu.

### Corrigé
- `botw mods uninstall` supprimait les mauvais blocs de `profile.yml` dès
  qu'il y en avait plus d'un : ils sont désormais retirés de la fin vers le
  début.
- Un zip de mod corrompu interrompait `profile verify` au lieu d'être
  signalé : il est maintenant listé comme un mod en défaut, et les autres
  mods sont vérifiés normalement.
- `profile verify` annonçait des fichiers manquants pour un profil qui n'était
  pas déployé. Le pack graphique ne contient que le profil actif : l'outil le
  dit et ne compte plus que la fusion.
- Le menu bouclait indéfiniment quand stdin était fermé (Ctrl+D, tâche
  planifiée) : la réponse par défaut ne changeait jamais.
- `botw catalog` et `botw profile delete` attendaient indéfiniment une
  confirmation sans terminal ; ils refusent par défaut et acceptent `--yes`.
- `mods install` et `mods uninstall` renvoyaient toujours « argument
  manquant » : le test portait sur un mauvais nom d'argument.
- Sortie console forcée en UTF-8 : les accents français ne provoquent plus
  d'erreur d'encodage sur la console Windows.

## [0.4.0] — 3 octobre 2026

### Ajouté
- **Banc d'essai des combinaisons** (`outils/matrice.py`) : 5 suites —
  `solo` (chaque mod seul), `paires` (tous les couples), `sw` (Second Wind ×
  chaque mod), `cumul` (Second Wind + un mod), `presets` (les profils réels).
  Chaque essai fait la chaîne complète : fusion UKMM, déploiement vers Cemu,
  vérification fichier par fichier.
  **Campagne complète : 123 essais, 0 échec, 63 minutes de calcul réel.**
- **Analyse de conflits** (`outils/conflits.py`) : classe chaque fichier selon
  la règle réelle du moteur UKMM (`ResourceData::Binary` → dernier gagne ;
  `Mergeable`/`Sarc` → addition) et liste les paires de mods qui s'écrasent.
  Classement : Relics of the Past écrase 157 fichiers fournis par trois
  autres mods ; le profil « sans échec » l'exclut pour cette raison.
- **Réparation des manifestes** (`outils/reparer-manifests.py`) : reconstruit
  le `manifest.yml` des mods totalement inertes, et ne touche qu'à eux.
- **Vérification complète** (`lanceur/Verifier-Tout.ps1`, touche `b`) :
  UKMM, profil actif, pack déployé, `rules.txt`, pack de textes français,
  cohérence du déploiement, sauvegardes, place disque. 12 contrôles.
- **Test des profils** dans le lanceur (touche `c`).
- **Profil « sans échec »** (touche `5`, profil `sur`) : Second Wind complet
  + 10 autres mods, 5 614 fichiers fusionnés, Relics of the Past exclu.
- **Chaque sauvegarde retient son profil** : le gestionnaire de sauvegardes
  note le profil UKMM actif à l'enregistrement et refuse de charger une partie
  d'un autre profil sans avertissement encadré. C'est la cause numéro un du
  blocage de l'écran de chargement.

### Corrigé
- **`10x Speed Paraglider v2` ne faisait rien.** Son manifeste déclarait
  `Pack/TitleBG.pack`, absent du zip ; son unique fichier
  (`Actor/AIProgram/Player_Link.baiprog`) n'était jamais appliqué.
- **`Second Wind - Eventide Fix` ne faisait rien.** Même cause : 21 fichiers
  ignorés, donc le correctif Eventide n'était jamais actif.
- **Ordre de fusion de `combo` et `flo`** : Linkle était sous les mods
  d'armures dans `combo`, et en toute dernier dans `flo`. Les deux profils
  ont été réordonnés et revérifiés.
- **Échec du déploiement non propagé** : le lanceur affichait « profil
  déployé » même quand la fusion avait échoué.
- **Pack de textes français** : UKMM ne déploie jamais `Bootup_EUfr.pack` sur
  un jeu français (le manifeste reprend le nom anglais). Le script le pose en
  lien dur.

### Documenté
- **Le blocage de l'écran de chargement vient des sauvegardes, pas des mods.**
  Preuves : date de la sauvegarde vivante (17:28) antérieure à toutes les
  fusions (17:38–17:58) ; snapshot de 14:11 antérieur à tous les mods.
  Charger une partie dont le set de mods n'existe plus = boucle infinie.
- **`GameData/gamedata.sarc`** est embarqué par 7 mods mais déclaré par aucun
  manifeste : UKMM ne le déploie jamais.
- Les textes ajoutés par les mods n'existent qu'en anglais : aucune
  traduction officielle n'est disponible.

## [0.3.0]
- Gestionnaire de sauvegardes complet : noms, descriptions, restauration
  vérifiée par MD5, marque de la partie en cours.
- Bascule graphique *Léger* / *Complet* avec vérification après écriture.
- Correctif du pack de textes français.

## [0.2.0]
- Choix des mods à la souris/au clavier, avec détection des conflits connus.
- Panneau des profils : créer, dupliquer, supprimer.

## [0.1.0]
- Premier lanceur fonctionnel : UKMM + BCML, profil `combo`, déployé vers
  Cemu en liens durs.
