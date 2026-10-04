# Journal des modifications

Toutes les versions publiées suivent [SemVer](https://semver.org/lang/fr/).

## [1.2.0] — 4 octobre 2026

### Ajouté
- **`installer.py`**, l'installateur complet. Il vérifie Python, copie le
  lanceur et l'outil, **contrôle chaque fichier copié par MD5** (une copie à
  moitié faite donne un lanceur qui semble marcher et qui exécute du code vieux
  de trois semaines), vérifie que les `.bat`/`.cmd`/`.ps1` sont ASCII, sans
  BOM et en CRLF, puis dit où sont UKMM et Cemu. Options `--dest`, `--check`
  (n'écrit rien) et `--shortcut`. Re-lancer ne détruit aucun profil, aucune
  partie, aucun mod.
- **`botw installmods <fichier|lien>`** installe un mod depuis un `.zip` du
  disque ou une URL. Le fichier est copié dans la bibliothèque, le lien est
  téléchargé. Un zip sans `meta.yml`, un zip corrompu ou une page web sont
  refusés — et le refus **retire** la copie, sinon `botw mods list` le
  reproposerait à chaque fois. Un mod déjà présent n'est jamais écrasé.
- **Les deux parties en haut du menu `botw ui`**, en raccourcis directs : les
  questions « je veux rejouer ma partie » et « je veux tous les mods » sont ce
  qu'on presse 95 % du temps, et elles n'étaient qu'un sous-menu plus loin.
  Les deux jeux de mods sont configurables (`botw config set raccourcis`) :
  ce dépôt est universel, Second Wind n'est le bon choix que chez ceux qui
  l'ont installé.
- **`outils/verifier-doc-cli.py`** fait passer chaque commande `botw` citée
  dans les deux README par le vrai analyseur d'arguments. Une documentation
  qui cite une commande inexistante est pire que pas de documentation.
- **Art ASCII** en tête des deux README.
- **Les touches 1 et 2 du lanceur : passer d'une partie à l'autre en une
  touche.** C'est le geste de tous les jours — « je veux rejouer ma partie
  principale », puis « je veux les 13 mods » — et il demandait jusqu'ici de
  changer le jeu de mods *puis* d'aller chercher la bonne partie dans un
  sous-menu, en espérant ne pas se tromper. Une touche qui change les mods
  sans changer la partie produit exactement le chargement infini : c'est le
  bug le plus fréquent du projet. Les touches 1 et 2 font donc les trois
  mouvements dans l'ordre sûr — mettre la partie de côté, déployer, remettre
  celle qui va avec. L'autre partie n'est jamais perdue.
- **`verifier-lanceur-menu.py`** : chaque touche du menu `.bat` est vérifiée
  contre l'étiquette qu'elle atteint, et les touches 1 et 2 contre le profil
  et la ligne d'appel qu'elles emploient. Un `goto` vers une étiquette
  inexistante ne lève aucune erreur : la fenêtre se ferme et l'utilisateur
  ne voit rien. Le script l'a attrapé sur la version précédente, où la
  touche 1 pointait encore vers le profil `combo`, supprimé.

### Corrigé
- **`botw jeu` refaisait une re-fusion à chaque fois, pour rien.** Le test de
  « le déploiement correspond-il à la fusion » comparait deux comptes. Sur le
  profil `sur`, UKMM livre 5614 fichiers quand sa propre fusion en compte
  5477 : le compte différait, donc chaque appel estimait le déploiement
  incomplet et redéployait. Il compare désormais le **contenu** — le
  déploiement est complet dès que tout ce qui est fusionné est déployé, quel
  que soit le surplus. Mesuré sur la vraie machine : **0,4 s au lieu de 34 s**.
- **Un faux blocage : « le jeu ne démarrera pas » sur un profil qui démarre.**
  UKMM livre 5614 fichiers alors que sa propre fusion n'en compte que 5477 —
  138 fichiers d'une fusion antérieure restent chez Cemu. Le compte comparait
  les deux nombres dans les deux sens et criait à l'échec. Or un **sur-ensemble**
  n'a jamais bloqué Cemu : le jeu lit le pack et y trouve tout ce qu'il attend.
  Le message conseillait surtout « relancez le lanceur », et la re-fusion
  reproduisait exactement le même écart — donc la cons loopingait. Le
  diagnostic est désormais directionnel : des fichiers **manquants** bloquent
  (le jeu tournerait avec un jeu de mods incomplet), des fichiers **en trop**
  sont signalés sans être comptés comme une erreur.
- **`botw jeu X --lancer` déployait deux fois.** `newgame.basculer` finit par
  un déploiement, et `ui.launch` en refaisait un : deux minutes de re-fusion
  pour démarrer un jeu déjà en place. Le second reçoit maintenant le
  déploiement par un drapeau ; aucune vérification n'est sautée.
- **Rejouer sa partie du jour coûtait une re-fusion.** Redemander le profil
  déjà actif, dont la partie lui appartient et dont le déploiement est
  complet, ne peut rien changer — mais le profileur repartait quand même.
  L'outil compte les fichiers, compare le pack à la fusion, et lance
  directement. Mesuré sur la machine de développement : **34,4 s → 0,33 s**.
  Le court-circuit ne dispense d'aucune vérification : un déploiement
  incomplet, ou une partie venue d'un autre profil, repasse par la voie
  normale.
- **La touche 1 du menu ne fonctionnait plus.** Elle pointait vers le profil
  `combo`, supprimé pour libérer 1,6 Go. L'utilisateur tapait 1 et obtenait
  « profil inconnu ».
- **Armes invisibles en jeu.** Le pack `Draw Distance` propose des options qui
  ne fonctionnent qu'avec le pack `Extended Memory`, lequel ne peut pas tourner
  avec les mods. L'arme que Link tient n'est pas un objet : c'est un **acteur
  attaché**, géré comme les PNJ. Elle disparaissait donc avec eux — en silence,
  sans erreur, sans crash. `botw check` repère maintenant ces réglages et
  `botw fix` les remet à la valeur la plus haute qui n'exige rien, en gardant
  les 2560×1440, les ombres à 200 % et les 120 images/seconde du joueur.
  La liste des valeurs sûres est lue dans le `rules.txt` du pack, pas recopiée
  en dur : une version ultérieure du pack reste donc couverte.
- **Toutes les icônes d'inventaire invisibles.** `HD Map and Icons` remplace
  **1 558 icônes** et son `rules.txt` porte `default = true` : Cemu l'active à
  chaque lancement **même après l'avoir retiré de `settings.xml`**. Le retirer
  de la liste ne servait donc à rien — le pack revenait, et les 49 entrées du
  fichier paraissaient parfaitement propres. `botw check` regarde désormais ce
  qu'il y a **sur le disque** et signale ces packs ; `botw fix` passe
  `default = true` à `false`, ce qui est réversible et ne supprime rien.
- **Le gestionnaire de sauvegardes confondait tout.** Il listait *tous* les
  dossiers de `Sauvegardes/`, donc quatre copies de sécurité et le dossier
  conteneur `NouvellePartie` apparaissaient comme des parties à charger, toutes
  de la même taille — et la vraie partie du joueur, celle que l'outil archive,
  n'apparaissait **nulle part**. Les deux gestionnaires se lisaient des index
  différents (`parties.json` et `nouvelle-partie.json`) sans se connaître.
  La liste est désormais en trois groupes — **vos parties**, **archives
  automatiques**, **copies de sécurité** — chaque ligne annonce les mods
  qui peuvent la charger, et un dossier sans `user`+`meta` n'est plus proposé.
- **Deux parties dans la même seconde se marchaient dessus.** L'horodatage des
  archives était figé à l'import du module ; une bascule rapide était refusée.
- **Une archive à moitié copiée était traitée comme valide.** Un dossier
  interrompu existe bel et bien : le remettre en place faisait perdre la partie
  sans un seul message. La présence du *fichier* de partie est maintenant
  vérifiée, pas celle du dossier.
- **`maj-bureau.py` pointait un niveau trop haut** et laissait la copie livrée
  au joueur en retard, sans le dire. Il demande désormais au disque où se
  trouve le programme plutôt que de supposer sa propre position.

### Ajouté
- **`installer.py`**, l'installateur complet. Il vérifie Python, copie le
  lanceur et l'outil, **contrôle chaque fichier copié par MD5** (une copie à
  moitié faite donne un lanceur qui semble marcher et qui exécute du code vieux
  de trois semaines), vérifie que les `.bat`/`.cmd`/`.ps1` sont ASCII, sans
  BOM et en CRLF, puis dit où sont UKMM et Cemu. Options `--dest`, `--check`
  (n'écrit rien) et `--shortcut`. Re-lancer ne détruit aucun profil, aucune
  partie, aucun mod.
- **`botw installmods <fichier|lien>`** installe un mod depuis un `.zip` du
  disque ou une URL. Le fichier est copié dans la bibliothèque, le lien est
  téléchargé. Un zip sans `meta.yml`, un zip corrompu ou une page web sont
  refusés — et le refus **retire** la copie, sinon `botw mods list` le
  reproposerait à chaque fois. Un mod déjà présent n'est jamais écrasé.
- **Les deux parties en haut du menu `botw ui`**, en raccourcis directs : les
  questions « je veux rejouer ma partie » et « je veux tous les mods » sont ce
  qu'on presse 95 % du temps, et elles n'étaient qu'un sous-menu plus loin.
  Les deux jeux de mods sont configurables (`botw config set raccourcis`) :
  ce dépôt est universel, Second Wind n'est le bon choix que chez ceux qui
  l'ont installé.
- **`outils/verifier-doc-cli.py`** fait passer chaque commande `botw` citée
  dans les deux README par le vrai analyseur d'arguments. Une documentation
  qui cite une commande inexistante est pire que pas de documentation.
- **Art ASCII** en tête des deux README.
- **La langue du poste, sans réglage.** L'outil démarre désormais dans la
  langue de l'interface de Windows, lue via `GetUserDefaultUILanguage` : Windows
  ne définit ni `LANG` ni `LC_ALL`, donc une détection par variables échouait
  partout sauf sous Git Bash et WSL. La locale du shell est lue aussi en
  repli, et `fr-CA` donne le français comme `fr-FR`. Un choix fait à la main
  reste prioritaire, et `botw lang auto` rend la décision au système.
  La cause du problème : la configuration portait `lang: "en"` par défaut, donc
  `load()` renvoyait toujours une langue et la détection ne se déclenchait
  jamais sur une installation neuve.
- **Une partie par jeu de mods** (`botw jeu <profil>`). Changer de profil ne
  touchait pas à l'emplacement de sauvegarde : le profil changeait, la partie
  restant, et plus rien ne pouvait la charger. `botw jeu` fait les deux
  ensemble, dans cet ordre — **l'ordre est la sécurité** : la partie part en
  archive *avant* le déploiement, donc un déploiement qui échoue la laisse
  déjà de côté. L'écran **Jouer** affiche `partie` ou `nouvelle` pour chaque
  profil, et bascule les deux d'un coup au choix.
- **Nouvelle partie avec d'autres mods** depuis le gestionnaire de sauvegardes
  (option 6) : il liste les jeux de mods installés, annonce où part la partie
  actuelle, et appelle `botw jeu`. Un `botw newgame` appelait directement
  viderait l'emplacement **sans** changer les mods — Cemu proposerait alors
  une partie qui ne pourrait plus jamais se charger.
- **Réglages de packs signalés par `botw check`** (gravité 1 : le jeu démarre,
  il manque seulement des choses à l'écran).
- **`Outils\verif-sauvegardes.ps1`** : vérifie que le script livré compile et
  que chaque dossier est bien classé partie / archive / copie. Il vérifie
  désormais que **le numéro affiché sélectionne bien la ligne affichée à côté**
  — l'invariant qui manquait et qui laissait passer le bug de chargement de la
  mauvaise partie. Trois obstacles ont dû être contournés pour y arriver : le
  script **ne démarrait pas** (`$PSScriptRoot` est vide hors exécution d'un
  fichier, et le menu interactif bloquait sur un `Read-Host` sans personne
  derrière), et `Write-Host` n'écrit dans aucun flux capturable en PowerShell
  5.1 — seule une transcription voit ce que l'utilisateur a lu. La preuve
  que le contrôle mord : remis sur le code d'avant, il signale les 7 numéros
  qui pointent vers la mauvaise partie. `-Cible <fichier>` permet de le
  pointer ailleurs.

### Ajouté
- **`installer.py`**, l'installateur complet. Il vérifie Python, copie le
  lanceur et l'outil, **contrôle chaque fichier copié par MD5** (une copie à
  moitié faite donne un lanceur qui semble marcher et qui exécute du code vieux
  de trois semaines), vérifie que les `.bat`/`.cmd`/`.ps1` sont ASCII, sans
  BOM et en CRLF, puis dit où sont UKMM et Cemu. Options `--dest`, `--check`
  (n'écrit rien) et `--shortcut`. Re-lancer ne détruit aucun profil, aucune
  partie, aucun mod.
- **`botw installmods <fichier|lien>`** installe un mod depuis un `.zip` du
  disque ou une URL. Le fichier est copié dans la bibliothèque, le lien est
  téléchargé. Un zip sans `meta.yml`, un zip corrompu ou une page web sont
  refusés — et le refus **retire** la copie, sinon `botw mods list` le
  reproposerait à chaque fois. Un mod déjà présent n'est jamais écrasé.
- **Les deux parties en haut du menu `botw ui`**, en raccourcis directs : les
  questions « je veux rejouer ma partie » et « je veux tous les mods » sont ce
  qu'on presse 95 % du temps, et elles n'étaient qu'un sous-menu plus loin.
  Les deux jeux de mods sont configurables (`botw config set raccourcis`) :
  ce dépôt est universel, Second Wind n'est le bon choix que chez ceux qui
  l'ont installé.
- **`outils/verifier-doc-cli.py`** fait passer chaque commande `botw` citée
  dans les deux README par le vrai analyseur d'arguments. Une documentation
  qui cite une commande inexistante est pire que pas de documentation.
- **Art ASCII** en tête des deux README.
- **Cemu démarre tout seul à l'allumage du PC**
  (`outils/demarrage-auto.py` et `outils/Cemu-BOTW-au-demarrage.cmd`, à copier
  dans le dossier *Démarrage* de Windows). Trois règles, dans cet ordre :
  **rien n'est déployé au boot** — un déploiement refusionne 1,7 Go et prend
  deux minutes, ce qui viderait un disque déjà serré ; si la partie chargée
  n'appartient pas au profil actif, **Cemu n'est pas lancé**, parce que le jeu
  planterait ; et le motif est écrit en clair dans `demarrage-auto.log`.
  Supprimer le fichier du dossier *Démarrage* suffit à tout annuler.

### Corrigé
- **`botw fix` annonçait « corrigé » sur un cas qu'il ne corrige pas.** Quand la
  partie vient d'un autre jeu de mods, aucun pack graphique n'y est pour rien :
  `fix` refaisait un déploiement de deux minutes sans toucher à la cause, et le
  message renvoyait vers `botw fix` lui-même. Le cas est détecté, aucun
  déploiement n'est déclenché, et la sortie donne les deux seules commandes
  qui le règlent : `botw jeu <profil>`, ou le lanceur touche 7.
- **Quatre clés de traduction utilisées mais jamais définies** s'affichaient
  telles quelles dans l'interface (`catalog.available`, `deploy.nothing`).
  Elles sont ajoutées dans les deux langues, et un test relit désormais le code
  pour vérifier que toute clé utilisée existe — une clé manquante ne se voit
  qu'à l'affichage, donc trop tard.
- **Le gestionnaire de sauvegardes chargeait la mauvaise partie.** La liste
  s'affichait par groupe (vos parties / archives / copies) mais le numéro tapé
  était utilisé pour indexer le tableau **non regroupé** : taper 3 chargeait la
  6ᵉ. Pire, l'option 5 « supprimer » supprimait la même ligne décalée — une
  faute de frappe pouvait effacer une autre sauvegarde. Les numéros sont
  désormais distribués dans l'ordre de défilement, et c'est ce tableau qui est
  renvoyé.
- **Choisir la partie ET son jeu de mods.** Charger une partie créée avec un
  autre jeu de mods affichait un avertissement, puis laissait sortir du menu,
  changer de profil, revenir et rejouer toute la liste — le profil actif
  restait le mauvais. Le gestionnaire propose maintenant de basculer sur le bon
  jeu de mods et de charger la partie dans la foulée, dans l'ordre sûr : copie
  de sécurité, déploiement, puis copie de la partie.
- **Les copies de sécurité étaient étiquetées avec le mauvais profil.**
  `Save-Partie` nota le profil **actif**, pas celui de la partie **copiée** : une
  sauvegarde `secondwind` archivée pendant que `sur` était actif était annoncée
  comme `sur`. C'est l'erreur inverse de la vérité, et elle faisait basculer le
  jeu vers le mauvais profil au chargement suivant. L'étiquette vient
  maintenant de la date du fichier de partie confrontée à l'historique des
  déploiements.
- **L'avertissement annonçait un blocage, le jeu plantait.** Le message disait
  « le jeu va bloquer sur l'écran de chargement » ; ce qui arrive réellement
  est un crash (`0xc0000005`) peu après le lancement. Le texte dit les deux, et
  propose la sortie avant de reprocher le problème.
- **Trois lignes marquées « en cours » à la fois** quand plusieurs archives
  sont identiques au contenu de la partie chargée. Une seule est marquée.
- **Une copie « Sécurité » vide (0 Ko)** occupait une ligne sans rien
  sauvegarder, et laissait croire qu'une partie avait été préservée. Rien n'est
  copié si l'emplacement est vide.
- **`doctor` signalait « noms de sauvegarde : présents » en rouge** sur un poste
  qui n'en a pas encore. Le message d'échec n'existait pas : le même texte
  s'affichait donc dans les deux cas, en [KO]. L'index n'est désormais
  contrôlé que s'il y a une partie à nommer — sans partie, il s'affiche en
  information, et `doctor` ne raterait plus son verdict sur un poste neuf.
- **Les `.bat` et `.ps1` arrivaient en LF après un `git clone`.** Dans un
  `.gitattributes`, c'est la **dernière** règle qui gagne : le `* text eol=lf`
  général, écrit avant les exceptions, écrasait les règles CRLF. La suite de
  tests passait dans le dossier de travail et échouait juste après
  l'installation documentée. Les règles sont remises dans l'ordre.
- **Les tests dépendaient de la langue du poste.** Sur une machine
  francophone, cinq tests échouaient uniquement parce que l'interface passait
  en français. La fausse machine est maintenant un poste **anglais** : la suite
  se comporte pareil partout, et la détection de langue est exercée par des
  tests qui la pilotent explicitement.
- **`--dest D:/BOTW` affichait `D:/BOTW\Lanceur-BOTW.bat`.** Windows accepte de
  mélanger les deux séparateurs, l'installation était donc correcte — mais
  l'écran final de l'installateur ressemblait à une panne. Le dossier est
  normalisé une fois pour toutes, et le test le vérifie de bout en bout, sur
  une vraie installation.

### Tests
- **`outils/tests_installeur.py`, 18 tests de l'installateur** : le dossier de
  destination est normalisé, `--check` n'écrit rien (même quand le dossier
  n'existe pas), la copie est exacte jusqu'au contrôle MD5 après écriture —
  une copie à moitié faite est refusée —, une installation réelle produit un
  lanceur jouable, et la relancer ne réécrit rien.
- **361 tests** (274 auparavant). Les garanties de sécurité sont vérifiées par
  mutation : casser l'ordre archivage-puis-déploiement fait échouer 5 tests,
  mal étiqueter l'archive en fait échouer 4, retirer la normalisation du
  dossier d'installation en fait échouer 4, retirer le contrôle MD5 après copie
  en fait échouer 1.

## [1.1.0] — 4 octobre 2026

### Ajouté
- **`installer.py`**, l'installateur complet. Il vérifie Python, copie le
  lanceur et l'outil, **contrôle chaque fichier copié par MD5** (une copie à
  moitié faite donne un lanceur qui semble marcher et qui exécute du code vieux
  de trois semaines), vérifie que les `.bat`/`.cmd`/`.ps1` sont ASCII, sans
  BOM et en CRLF, puis dit où sont UKMM et Cemu. Options `--dest`, `--check`
  (n'écrit rien) et `--shortcut`. Re-lancer ne détruit aucun profil, aucune
  partie, aucun mod.
- **`botw installmods <fichier|lien>`** installe un mod depuis un `.zip` du
  disque ou une URL. Le fichier est copié dans la bibliothèque, le lien est
  téléchargé. Un zip sans `meta.yml`, un zip corrompu ou une page web sont
  refusés — et le refus **retire** la copie, sinon `botw mods list` le
  reproposerait à chaque fois. Un mod déjà présent n'est jamais écrasé.
- **Les deux parties en haut du menu `botw ui`**, en raccourcis directs : les
  questions « je veux rejouer ma partie » et « je veux tous les mods » sont ce
  qu'on presse 95 % du temps, et elles n'étaient qu'un sous-menu plus loin.
  Les deux jeux de mods sont configurables (`botw config set raccourcis`) :
  ce dépôt est universel, Second Wind n'est le bon choix que chez ceux qui
  l'ont installé.
- **`outils/verifier-doc-cli.py`** fait passer chaque commande `botw` citée
  dans les deux README par le vrai analyseur d'arguments. Une documentation
  qui cite une commande inexistante est pire que pas de documentation.
- **Art ASCII** en tête des deux README.
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
- **`installer.py`**, l'installateur complet. Il vérifie Python, copie le
  lanceur et l'outil, **contrôle chaque fichier copié par MD5** (une copie à
  moitié faite donne un lanceur qui semble marcher et qui exécute du code vieux
  de trois semaines), vérifie que les `.bat`/`.cmd`/`.ps1` sont ASCII, sans
  BOM et en CRLF, puis dit où sont UKMM et Cemu. Options `--dest`, `--check`
  (n'écrit rien) et `--shortcut`. Re-lancer ne détruit aucun profil, aucune
  partie, aucun mod.
- **`botw installmods <fichier|lien>`** installe un mod depuis un `.zip` du
  disque ou une URL. Le fichier est copié dans la bibliothèque, le lien est
  téléchargé. Un zip sans `meta.yml`, un zip corrompu ou une page web sont
  refusés — et le refus **retire** la copie, sinon `botw mods list` le
  reproposerait à chaque fois. Un mod déjà présent n'est jamais écrasé.
- **Les deux parties en haut du menu `botw ui`**, en raccourcis directs : les
  questions « je veux rejouer ma partie » et « je veux tous les mods » sont ce
  qu'on presse 95 % du temps, et elles n'étaient qu'un sous-menu plus loin.
  Les deux jeux de mods sont configurables (`botw config set raccourcis`) :
  ce dépôt est universel, Second Wind n'est le bon choix que chez ceux qui
  l'ont installé.
- **`outils/verifier-doc-cli.py`** fait passer chaque commande `botw` citée
  dans les deux README par le vrai analyseur d'arguments. Une documentation
  qui cite une commande inexistante est pire que pas de documentation.
- **Art ASCII** en tête des deux README.
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
- **`installer.py`**, l'installateur complet. Il vérifie Python, copie le
  lanceur et l'outil, **contrôle chaque fichier copié par MD5** (une copie à
  moitié faite donne un lanceur qui semble marcher et qui exécute du code vieux
  de trois semaines), vérifie que les `.bat`/`.cmd`/`.ps1` sont ASCII, sans
  BOM et en CRLF, puis dit où sont UKMM et Cemu. Options `--dest`, `--check`
  (n'écrit rien) et `--shortcut`. Re-lancer ne détruit aucun profil, aucune
  partie, aucun mod.
- **`botw installmods <fichier|lien>`** installe un mod depuis un `.zip` du
  disque ou une URL. Le fichier est copié dans la bibliothèque, le lien est
  téléchargé. Un zip sans `meta.yml`, un zip corrompu ou une page web sont
  refusés — et le refus **retire** la copie, sinon `botw mods list` le
  reproposerait à chaque fois. Un mod déjà présent n'est jamais écrasé.
- **Les deux parties en haut du menu `botw ui`**, en raccourcis directs : les
  questions « je veux rejouer ma partie » et « je veux tous les mods » sont ce
  qu'on presse 95 % du temps, et elles n'étaient qu'un sous-menu plus loin.
  Les deux jeux de mods sont configurables (`botw config set raccourcis`) :
  ce dépôt est universel, Second Wind n'est le bon choix que chez ceux qui
  l'ont installé.
- **`outils/verifier-doc-cli.py`** fait passer chaque commande `botw` citée
  dans les deux README par le vrai analyseur d'arguments. Une documentation
  qui cite une commande inexistante est pire que pas de documentation.
- **Art ASCII** en tête des deux README.
- **Banc d'essai des combinaisons** (`outils/matrice.py`) : 5 suites —
  `solo` (chaque mod seul), `paires` (tous les couples), `sw` (Second Wind ×
  chaque mod), `cumul` (Second Wind + un mod), `presets` (les profils réels).
  Chaque essai fait la chaîne complète : fusion UKMM, déploiement vers Cemu,
  vérification fichier par fichier.
  **Campagne complète : 123 essais, 0 échec, 63 minutes de calcul réel.**
- **Analyse de conflits** (`outils/conflits.py`) : classe chaque fichier selon
  la règle réelle du moteur UKMM (`ResourceData::Binary` → dernier gagne ;
  `Mergeable`/`Sarc` → addition) et liste les paires de mods qui s'écrasent.
  Classement : Relics of the Past écrase 156 fichiers fournis par trois
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
