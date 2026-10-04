@echo off
REM ---------------------------------------------------------------------
REM Cemu BOTW - demarrage automatique.
REM
REM Allumer le PC, attendre, et Cemu demarre tout seul sur le profil
REM full mods. Le script NE redeploie rien : il verifie seulement que le
REM jeu peut charger, et refuse de demarrer si la partie chargee vient
REM d'un autre jeu de mods, parce que le jeu planterait.
REM
REM Pour ne plus lancer Cemu au demarrage : supprime ce fichier.
REM Pour voir ce qui s'est passe :
REM     %USERPROFILE%\botw-bcml-work\demarrage-auto.log
REM
REM Fichier en ASCII pur, SANS BOM : cmd.exe ne lit pas l'UTF-8. Aucun
REM chemin en dur, aucun accent : le nom du compte en contient un, et un
REM fichier .cmd lu en ANSI deviendrait illisible.
REM ---------------------------------------------------------------------

REM On laisse le poste demarrer. 'ping' et non 'timeout' : ce dernier echoue
REM quand il n'y a pas de console derriere, et interrompt tout le script.
ping -n 21 127.0.0.1 >nul

set "PYW="
if exist "%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe" set "PYW=%LOCALAPPDATA%\Programs\Python\Launcher\pyw.exe"
for /d %%d in ("%LOCALAPPDATA%\Python\pythoncore-*") do set "PYW=%%d\pythonw.exe"
if not defined PYW for /d %%d in ("%LOCALAPPDATA%\Programs\Python\Python*") do set "PYW=%%d\pythonw.exe"
if not defined PYW goto :fin

set "BOTW=%USERPROFILE%\botw-bcml-work"
if not exist "%BOTW%\demarrage-auto.py" goto :fin

start "" "%PYW%" "%BOTW%\demarrage-auto.py"

:fin
exit /b 0