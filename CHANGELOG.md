# Journal des modifications

Toutes les versions published_will follow [SemVer](https://semver.org/lang/fr/).

## [0.4.0] — en cours

### Ajouté
- **Banc d'essai des combinaisons** (`outils/matrice.py`) : 5 suites —
  `solo` (chaque mod seul), `paires` (tous les couples), `sw` (Second Wind ×
  chaque mod), `cumul` (Second Wind + un mod), `presets` (les profils réels).
  Chaque essai fait la chaîne complète : fusion UKMM, déploiement vers Cemu,
  vérification fichier par fichier.
- **Analyse de conflits** (`outils/conflits.py`) : classe chaque fichier selon
  la règle réelle du moteur UKMM (`ResourceData::Binary` → dernier gagne ;
  `Mergeable`/`Sarc` → addition) et liste les paires de mods qui s'écrasent.
- **Réparation des manifestes** (`outils/reparer-manifests.py`) : reconstruit
  le `manifest.yml` des mods totalement inertes, et ne touche qu'à eux.
- **Vérification complète** (`lanceur/Verifier-Tout.ps1`, touche `b`) :
  UKMM, profil actif, pack déployé, `rules.txt`, pack de textes français,
  sauvegardes, place disque.
- **Test des profils** dans le lanceur (touche `c`).
- **Profil « sans échec »** (touche `5`) : le set le plus complet, vérifié.

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