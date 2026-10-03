@echo off
REM ---------------------------------------------------------------
REM botw - CLI (English by default, French with: botw lang fr)
REM
REM ASCII only, CRLF, no accented characters: Windows PowerShell 5.1
REM reads .bat as ANSI and the username of this machine has an accent.
REM ---------------------------------------------------------------
setlocal
if not defined BOTW_HOME set "BOTW_HOME=%~dp0"
pushd "%BOTW_HOME%"
set "PYTHONIOENCODING=utf-8"
where py >nul 2>nul && ( py -3 "%BOTW_HOME%botw.py" %* ) || ( python "%BOTW_HOME%botw.py" %* )
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
