param(
    [switch]$NonInteractif,
    [string]$Action = ''
)

$ErrorActionPreference = 'Stop'

# Jeu a deux sur BOTW (Wii U) : c'est natif, aucun mod necessaire.
# Ce qu'il faut, c'est que Cemu reconnaisse DEUX manettes. Le nombre de
# canaux de manette est stocke dans settings.xml :
#     <PadChannels>1</PadChannels>     -> une seule manette (ton cas actuel)
#     <PadChannels>2</PadChannels>     -> deux manettes
# Cemu ecris ce fichier en sortie : il faut donc le modifier Cemu ferme.

$settings = Join-Path $env:APPDATA 'Cemu\settings.xml'

function Guard-Cemu {
    $r = Get-Process -Name Cemu -ErrorAction SilentlyContinue
    if ($r) {
        Write-Host ''
        Write-Host "  Cemu est ouvert (PID $($r.Id -join ', '))." -ForegroundColor Yellow
        Write-Host "  Ferme Cemu puis relance : il ecrase settings.xml a la sortie." -ForegroundColor Yellow
        Write-Host ''
        exit 2
    }
}

function Get-Canaux {
    if (-not (Test-Path -LiteralPath $settings)) { return -1 }
    $raw = [System.IO.File]::ReadAllText($settings)
    $m = [regex]::Match($raw, '<PadChannels>(\d+)</PadChannels>')
    if ($m.Success) { return [int]$m.Groups[1].Value }
    return -1
}

function Set-Canaux([int]$n) {
    $raw = [System.IO.File]::ReadAllText($settings)
    if ($raw -notmatch '<PadChannels>\d+</PadChannels>') {
        throw "Balise <PadChannels> introuvable dans settings.xml (version de Cemu inattendue ?)"
    }
    $new = [regex]::Replace($raw, '<PadChannels>\d+</PadChannels>', "<PadChannels>$n</PadChannels>")
    # UTF-8 SANS BOM : Cemu refuse de demarrer avec un BOM dans settings.xml.
    [System.IO.File]::WriteAllText($settings, $new, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "  Canaux de manette passes a $n." -ForegroundColor Green
}

function Show-Aide {
    Write-Host ''
    Write-Host '  --- Comment jouer a deux ---' -ForegroundColor Cyan
    Write-Host ''
    Write-Host '  1. Branche 2 manettes sur le PC (XInput : Xbox, ou un pad'
    Write-Host '     PlayStation/Xbox generique cable).'
    Write-Host '  2. Lance Cemu avec ce menu ouvert au choix "7. Jeu a deux".'
    Write-Host '  3. Dans le jeu, au titre, appuie simultanement sur le bouton'
    Write-Host '     "+" (ou "Start") des DEUX manettes.'
    Write-Host '  4. Joueur 2 apparait en bleu ; il peut rejoindre ou quitter'
    Write-Host '     quand il veut avec + / -.'
    Write-Host ''
    Write-Host '  Compatibilite des mods :' -ForegroundColor Yellow
    Write-Host '  - Profil MES MODS (Linkle) : le joueur 2 aura Link par defaut.'
    Write-Host '    Linkle n a pas de version "Link joueur 2" : prevoyez de'
    Write-Host '    jouer le joueur 1 avec Link et le joueur 2 avec Link.'
    Write-Host '  - Second Wind : Tres modifie le monde, mais le mode 2 joueurs'
    Write-Host '    reste fonctionnel. Sauvegardez avant (option 6).'
    Write-Host ''
    Write-Host '  Si une manette n est pas reconnue : Cemu -> Options ->'
    Write-Host '  "Configurer le controleur" et assigne-la a un canal libre.'
    Write-Host ''
}

if ($NonInteractif) {
    switch ($Action.ToLower()) {
        # Seules les ecritures exigent Cemu ferme ; lire l'etat ou l'aide
        # doit rester possible pendant que le jeu tourne.
        'enable'  { Guard-Cemu; Set-Canaux 2 }
        'disable' { Guard-Cemu; Set-Canaux 1 }
        'status' {
            $c = Get-Canaux
            Write-Host "PadChannels = $c"
            if ($c -ge 2) { Write-Host 'jeu a deux : ACTIF' -ForegroundColor Green }
            else { Write-Host 'jeu a deux : inactif (1 manette)' -ForegroundColor Yellow }
        }
        'help' { Show-Aide }
        default { throw "Action inconnue : $Action" }
    }
    exit 0
}

Guard-Cemu
while ($true) {
    $c = Get-Canaux
    Write-Host ''
    Write-Host '------------------------------------------------------------'
    Write-Host '   JEU A DEUX  -  Cemu / Zelda Breath of the Wild'
    Write-Host '------------------------------------------------------------'
    if ($c -ge 2) {
        Write-Host "  Etat : 2 manettes reconnues (jeu a deux actif)." -ForegroundColor Green
    } else {
        Write-Host "  Etat : 1 seule manette reconnue -> jeu a deux impossible." -ForegroundColor Yellow
    }
    Write-Host ''
    Write-Host '   1. Activer le jeu a deux (2 manettes)'
    Write-Host '   2. Desactiver (retour a 1 manette)'
    Write-Host '   3. Comment ca marche (aide)'
    Write-Host '   0. Quitter'
    Write-Host ''
    $choix = Read-Host '   Choix'
    switch ($choix.Trim()) {
        '1' { Set-Canaux 2 }
        '2' { Set-Canaux 1 }
        '3' { Show-Aide }
        '0' { exit 0 }
        default { Write-Host '   Choix invalide.' -ForegroundColor Red }
    }
}