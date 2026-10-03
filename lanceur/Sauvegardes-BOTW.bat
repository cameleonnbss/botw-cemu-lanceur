@echo off
rem Gestionnaire de sauvegardes BOTW.
rem Le menu est entierement en PowerShell : on evite ainsi les problemes de
rem "set /p" / accents / page de code rencontres avec un menu en batch.
rem Ce fichier est en ASCII pur.
title Sauvegardes BOTW
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Sauvegardes-BOTW.ps1"
if errorlevel 2 (
  echo.
  pause
)