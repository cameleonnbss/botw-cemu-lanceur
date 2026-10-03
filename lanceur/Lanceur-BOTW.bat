@echo off
rem =====================================================================
rem  LANCEUR Zelda BOTW sur Cemu
rem
rem  "choice" (natif Windows) renvoie un CODE DE SORTIE numerique : pas de
rem  comparaison de chaine fragile. Pas de "chcp 65001" ici : changer de page
rem  de code vide le tampon d'entree de la console. Fichier en ASCII pur.
rem
rem  Ordre du menu : "choice /c 123456789abcdefgh0" renvoie la POSITION
rem  de la touche. 1->1 ... 9->9, a->10, b->11, c->12, d->13, e->14,
rem  f->15, g->16, h->17, 0->18.
rem  On teste donc de la fin vers le debut : chaque "if errorlevel" doit
rem  correspondre au DERNIER cas encore possible.
rem =====================================================================
title Lanceur BOTW
setlocal

set "UKMM=%USERPROFILE%\Tools\UKMM\ukmm.exe"
set "SCRIPT=%~dp0Set-ProfilUKMM.ps1"
set "CHOIX=%~dp0Choix-Mods.ps1"
set "SAUVEGARDES=%~dp0Sauvegardes-BOTW.ps1"
set "GRAPHISMES=%~dp0Graphismes-BOTW.ps1"
set "COOP=%~dp0Coop-2Joueurs.ps1"
set "PANNEAU=%~dp0Panel-Profils.ps1"
set "VERIF=%~dp0Verifier-Tout.ps1"
set "OUTILS=%~dp0Outils"
set "BOTW=%~dp0botw\botw.py"
set "CEMU=%USERPROFILE%\Downloads\cemu-2.6-windows-x64\Cemu_2.6\Cemu.exe"
set "SETTINGS=%APPDATA%\ukmm\settings.yml"
set "PROFILDIR=%LOCALAPPDATA%\ukmm\wiiu\profiles"

:menu
rem Etat du profil actif, relu a chaque affichage.
set "PROFIL=?"
for /f "tokens=2 delims=:" %%a in ('findstr /R /C:"^  profile:" "%SETTINGS%" 2^>nul') do set "PROFIL=%%a"
set "PROFIL=%PROFIL: =%"
set "NBMODS=0"
if exist "%PROFILDIR%\%PROFIL%\profile.yml" (
  rem ATTENTION : pas de "|" ici. Un pipe a l'interieur d'un "for /f" mal
  rem echappe fait patienter cmd.exe en attente d'une entree : le menu se
  rem bloque. On compte donc en iterating sur les lignes de findstr.
  for /f %%n in ('findstr /R /C:"^      name:" "%PROFILDIR%\%PROFIL%\profile.yml" 2^>nul') do set /a NBMODS+=1
)
if "%PROFIL%"=="" set "PROFIL=?"
if "%PROFIL%"=="?" set "NBMODS=0"

echo.
echo ================================================================
echo     ZELDA  BREATH  OF  THE  WILD   -   lanceur
echo ================================================================
echo.
echo     Profil actif : %PROFIL%   (%NBMODS% mods)
echo.
echo   JOUER
echo     1. Second Wind +^ TES MODS    tout en meme temps ^(9 mods^)
echo     2. TES MODS seuls             Linkle, iles, armes anciennes
echo     3. Second Wind seul          extension complete
echo     4. BOOST ..................... Armes, teleport, vol rapide. Leger
echo     5. SANS ECHEC ................ le plus complet, tous testes
echo     6. CHOISIR TES MODS .......... tu coches ce que tu veux
echo.
echo   OUTILS
echo     7. Charger une partie        tes sauvegardes, nom + description
echo     8. Jeu a deux                2 manettes
echo     9. Panneau des profils       creer / dupliquer / supprimer
echo     a. Graphismes                rapide  ou  belle image
echo     b. Verifier et reparer       dit ce qui ne va pas
echo     c. Tester les profils        rejoue chaque profil et verifie
echo     d. Ouvrir UKMM
echo     e. Ouvrir Cemu

echo   botw  (the CLI, in English ; "botw lang fr" switches to French)
echo     f. botw menu ................ everything: mods, profiles, tools
echo     g. New game ................. keeps the old one, starts clean
echo     h. Documentation ............. this file, French or English
echo.
echo     0. Quitter
echo.
choice /c 123456789abcdefgh0 /n /m "Choix (0 pour quitter) : "
if errorlevel 18 exit /b 0
if errorlevel 17 goto doc
if errorlevel 16 goto nouvelle
if errorlevel 15 goto botw
if errorlevel 14 goto cemu
if errorlevel 13 goto ukmm
if errorlevel 12 goto tester
if errorlevel 11 goto verifier
if errorlevel 10 goto graphismes
if errorlevel 9 goto panneau
if errorlevel 8 goto coop
if errorlevel 7 goto sauvegardes
if errorlevel 6 goto choix
if errorlevel 5 goto sur
if errorlevel 4 goto boost
if errorlevel 3 goto sw
if errorlevel 2 goto flo
if errorlevel 1 goto combo
goto menu

:combo
call :jouer combo
if errorlevel 1 goto menu
goto fin

:sur
call :jouer sur
if errorlevel 1 goto menu
goto fin

:boost
call :jouer boost
if errorlevel 1 goto menu
goto fin

:sw
call :jouer secondwind
if errorlevel 1 goto menu
goto fin

:flo
call :jouer flo
if errorlevel 1 goto menu
goto fin

rem ---------------------------------------------------------------------
rem :jouer <profil>
rem "call :jouer" sans second argument : le parametre est passe a
rem Set-ProfilUKMM.ps1. Si le deploiement echoue (Cemu ouvert, UKMM ouvert,
rem profil inconnu...), on NE doit surtout pas afficher "Profil deploye" :
rem ce serait un mensonge, l'utilisateur lancerait le jeu avec l'ancien jeu
rem de mods, et c'est exactement ce qui bloque a l'ecran de chargement.
rem ---------------------------------------------------------------------
:jouer
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" -Profile %1
if errorlevel 1 goto :echec
goto :eof

:echec
echo.
echo   ECHEC : le profil n'a PAS ete deploye.
echo   Lis le message ci-dessus, corrige le probleme, puis reessaie.
echo   Le menu ci-dessous montre le profil actif REEL, pas celui demande.
pause
exit /b 1

:choix
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%CHOIX%" -Profile %PROFIL%
if errorlevel 2 pause
goto menu

:sauvegardes
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%SAUVEGARDES%"
if errorlevel 2 pause
goto menu

:graphismes
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%GRAPHISMES%"
if errorlevel 2 pause
goto menu

:coop
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%COOP%"
if errorlevel 2 pause
goto menu

:panneau
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%PANNEAU%"
if errorlevel 2 pause
goto menu

rem ---------------------------------------------------------------------
rem Verification complete : lit tout l etat et dit ce qui ne va pas.
rem ---------------------------------------------------------------------
:verifier
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%VERIF%"
pause
goto menu

rem ---------------------------------------------------------------------
rem Banc d'essai : rejoue chaque profil du lanceur avec la vraie chaine
rem (fusion + deploiement + verification fichier par fichier).
rem ---------------------------------------------------------------------
:tester
echo.
echo   Test des profils. Cela prend 2 a 5 minutes.
echo   Cemu et UKMM doivent etre fermes : ils le sont d'apres la touche b.
echo.
if exist "%OUTILS%\matrice.py" (
  python "%OUTILS%\matrice.py" presets
) else (
  echo   Outils\matrice.py introuvable : copie incomplete du dossier.
)
echo.
pause
goto menu

:botw
if not exist "%BOTW%" (
  echo   botw\botw.py introuvable : copie incomplete du dossier.
  pause
  goto menu
)
python "%BOTW%" ui
goto menu

rem ---------------------------------------------------------------------
rem New game : moves the current save slot aside instead of deleting it.
rem That is THE answer to a game stuck on the loading screen.
rem ---------------------------------------------------------------------
:nouvelle
if not exist "%BOTW%" goto :nouvelle_sans_botw
python "%BOTW%" newgame
echo.
pause
goto menu
:nouvelle_sans_botw
echo.
echo   Pour une nouvelle partie : A -^> Nouvelle partie dans Cemu.
echo   Le dossier botw est introuvable, l ancienne ne peut pas etre
echo   archivee automatiquement.
pause
goto menu

rem ---------------------------------------------------------------------
rem Documentation : le README du dossier botw, dans la langue demandee.
rem ---------------------------------------------------------------------
:doc
if not exist "%BOTW%" (
  echo   Le dossier botw est introuvable : copie incomplete.
  pause
  goto menu
)
echo.
set "LANGUE=fr"
set /p "LANGUE=Langue de la documentation (fr / en) [fr] : "
if /i not "%LANGUE%"=="en" set "LANGUE=fr"
python "%BOTW%" readme "%LANGUE%"
echo.
pause
goto menu

:ukmm
start "" "%UKMM%"
goto menu

:cemu
start "" "%CEMU%"
goto menu

rem ---------------------------------------------------------------------
rem Bannie affichee apres un deploiement reussi. C'est l'ecran de
rem chargement qui bloque, pas le jeu : une partie enregistree avec un
rem autre jeu de mods ne peut pas ete lue par celui-la.
rem ---------------------------------------------------------------------
:fin
echo.
echo   Profil deploye. Tu peux lancer Cemu.
echo.
echo   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo   !  PARTIE NOUVELLE pour ce profil                      !
echo   !                                                      !
echo   !  Dans Cemu : bouton A  -^>  Nouvelle partie  -^>  OK !
echo   !                                                      !
echo   !  Une partie deja enregistree a ete creee avec un    !
echo   !  autre jeu de mods. La charger bloque a l'ecran de  !
echo   !  chargement, sans message. C'est le probleme le plus  !
echo   !  courant : une partie par profil.                    !
echo   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
pause
goto menu