param(
    [switch]$NonInteractif,
    [string]$Action = '',
    [string]$Nom = '',
    [string]$Vers = ''
)

# ===========================================================================
#  PANNEAU DE GESTION DES PROFILS UKMM
#
#  Un "profil" = un ensemble de mods + leur ordre de fusion. UKMM n'en deploie
#  qu'un a la fois dans Cemu. Ce panneau permet d'en creer, dupliquer,
#  renommer, supprimer, basculer, et de gerer les mods de chacun.
#
#  Les mods eux-memes sont stockes a part (wiiu\mods) et partages par tous les
#  profils : dupliquer un profil ne duplique donc aucun Mo.
# ===========================================================================

$ErrorActionPreference = 'Stop'

$settings = Join-Path $env:APPDATA 'ukmm\settings.yml'
$ukmm     = Join-Path $env:USERPROFILE 'Tools\UKMM\ukmm.exe'
$root     = Join-Path $env:LOCALAPPDATA 'ukmm\wiiu'
$profiles = Join-Path $root 'profiles'
$modsDir  = Join-Path $root 'mods'
$gp       = Join-Path $env:APPDATA 'Cemu\graphicPacks\BreathOfTheWild_UKMM'
$modsLib  = Join-Path $PSScriptRoot 'Mods'

function Guard {
    $c = Get-Process -Name Cemu -ErrorAction SilentlyContinue
    if ($c) {
        Write-Host ''
        Write-Host "  Cemu est ouvert (PID $($c.Id -join ', '))." -ForegroundColor Yellow
        Write-Host '  Ferme-le : il verrouille les fichiers et ecrase settings.xml.' -ForegroundColor Yellow
        Write-Host ''
        exit 2
    }
    $u = Get-Process -Name ukmm -ErrorAction SilentlyContinue
    if ($u) {
        Write-Host ''
        Write-Host "  UKMM est ouvert (PID $($u.Id -join ', '))." -ForegroundColor Yellow
        Write-Host '  Ferme-le : il garde le profil en memoire et le reecraserait.' -ForegroundColor Yellow
        Write-Host ''
        exit 3
    }
}

function Get-ProfileActif {
    if (-not (Test-Path -LiteralPath $settings)) { return '' }
    $m = [regex]::Match([System.IO.File]::ReadAllText($settings), '(?m)^\s*profile:\s*(\S+)')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Set-ProfileActif([string]$nom) {
    $raw = [System.IO.File]::ReadAllText($settings)
    $new = [regex]::Replace($raw, '(?m)^(\s*profile:\s*).*$', ('$1' + $nom))
    # UKMM : serde_yaml refuse le BOM.
    [System.IO.File]::WriteAllText($settings, $new, (New-Object System.Text.UTF8Encoding($false)))
}

function Get-Profiles {
    if (-not (Test-Path -LiteralPath $profiles)) { return @() }
    Get-ChildItem -LiteralPath $profiles -Directory -ErrorAction SilentlyContinue |
        Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'profile.yml') } |
        Sort-Object Name
}

# --- Lecture / ecriture de profile.yml (edition textuelle, tout reste intact) --
function Read-Profile([string]$nom) {
    $f = Join-Path (Join-Path $profiles $nom) 'profile.yml'
    [System.IO.File]::ReadAllText($f)
}

function Write-Profile([string]$nom, [string]$txt) {
    $f = Join-Path (Join-Path $profiles $nom) 'profile.yml'
    $bak = "$f.bak"
    [System.IO.File]::Copy($f, $bak, $true)
    [System.IO.File]::WriteAllText($f, $txt, (New-Object System.Text.UTF8Encoding($false)))
}

# Bloc d'un mod dans le map "mods:" -> (debut, fin, hash, nom, zip, enabled)
function Get-ModBlocks([string]$txt) {
    $lines = $txt -split "`r?`n"
    $res = @()
    $i = 0
    while ($i -lt $lines.Count) {
        if ($lines[$i] -match '^  (\d+):\s*$') {
            $hash = $Matches[1]
            $start = $i
            $j = $i + 1
            $name = ''; $zip = ''; $enabled = $true
            while ($j -lt $lines.Count -and $lines[$j] -notmatch '^  \d+:\s*$' -and $lines[$j] -notmatch '^\S') {
                if ($lines[$j] -match '^      name: (.+?)\s*$') { $name = $Matches[1] }
                if ($lines[$j] -match '^\s+path: (.+?)\s*$') { $zip = $Matches[1] }
                if ($lines[$j] -match '^\s+enabled: (true|false)\s*$') { $enabled = ($Matches[1] -eq 'true') }
                $j++
            }
            $res += [pscustomobject]@{
                Hash = $hash; Name = $name; Zip = $zip; Enabled = $enabled
                Start = $start; End = $j
            }
            $i = $j
        } else { $i++ }
    }
    return $res
}

function Set-ModEnabled([string]$nom, [string]$hash, [bool]$on) {
    $txt = Read-Profile $nom
    $lines = $txt -split "`r?`n"
    $blk = Get-ModBlocks $txt | Where-Object { $_.Hash -eq $hash }
    if (-not $blk) { throw "Mod introuvable : $hash" }
    for ($i = $blk.Start; $i -lt $blk.End; $i++) {
        if ($lines[$i] -match '^(\s+enabled: )(true|false)\s*$') {
            $lines[$i] = $Matches[1] + ($(if ($on) { 'true' } else { 'false' }))
        }
    }
    Write-Profile $nom ($lines -join "`r`n")
}

function Remove-ModFromProfile([string]$nom, [string]$hash) {
    $txt = Read-Profile $nom
    $lines = [System.Collections.ArrayList]@($txt -split "`r?`n")
    $blk = Get-ModBlocks $txt | Where-Object { $_.Hash -eq $hash }
    if (-not $blk) { throw "Mod introuvable : $hash" }

    # 1. retirer l'entree de load_order (une seule, en gardant tout le reste).
    #    Attention : $lines[0..($i-1)] TRONQUERait le tableau et supprimerait
    #    aussi les lignes suivantes -> il faut reconstruire les deux morceaux.
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i].Trim() -eq "- $hash") { [void]$lines.RemoveAt($i); break }
    }

    # 2. retirer le bloc du mod (du dernier indice vers le premier, pour que les
    #    numeros de ligne du bloc restent valides pendant la suppression).
    [void]$lines.RemoveRange($blk.Start, $blk.End - $blk.Start)

    Write-Profile $nom (@($lines) -join "`r`n")
}

# --- Actions ----------------------------------------------------------------
function New-ProfileVide([string]$nom) {
    if (-not $nom) { throw 'Nom obligatoire.' }
    if ($nom -notmatch '^[A-Za-z0-9_-]+$') {
        throw 'Nom invalide : lettres, chiffres, - et _ uniquement (le chemin du profil est utilise tel quel).'
    }
    $dir = Join-Path $profiles $nom
    if (Test-Path -LiteralPath $dir) { throw "Le profil '$nom' existe deja." }
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $dir 'merged') -Force | Out-Null
    # UKMM echoue si le dossier merged/ n'existe pas.
    $yml = "mods: {}`r`nload_order: []`r`n"
    [System.IO.File]::WriteAllText((Join-Path $dir 'profile.yml'), $yml,
        (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "  Profil '$nom' cree (vide)." -ForegroundColor Green
}

function Copy-Profile([string]$src, [string]$dst) {
    $srcDir = Join-Path $profiles $src
    if (-not (Test-Path -LiteralPath $srcDir)) { throw "Profil source introuvable : $src" }
    if ($dst -notmatch '^[A-Za-z0-9_-]+$') { throw 'Nom invalide.' }
    $dir = Join-Path $profiles $dst
    if (Test-Path -LiteralPath $dir) { throw "Le profil '$dst' existe deja." }
    # On copie UNIQUEMENT profile.yml : le dossier merged/ sera regenere par le
    # remerge. Les .zip des mods sont deja partages (wiiu\mods), donc 0 Mo.
    # Attention : Join-Path de PowerShell 5.1 n'accepte que 2 arguments
    # positionnels -> il faut l'imbriquer.
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $dir 'merged') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $srcDir 'profile.yml') -Destination $dir -Force
    $n = (Get-ModBlocks (Read-Profile $dst)).Count
    Write-Host "  Profil '$dst' cree depuis '$src' ($n mods, 0 Mo copies)." -ForegroundColor Green
}

function Rename-Profile([string]$src, [string]$dst) {
    if ($dst -notmatch '^[A-Za-z0-9_-]+$') { throw 'Nom invalide.' }
    $s = Join-Path $profiles $src
    if (-not (Test-Path -LiteralPath $s)) { throw "Profil introuvable : $src" }
    if (Test-Path -LiteralPath (Join-Path $profiles $dst)) { throw "Le profil '$dst' existe deja." }
    Rename-Item -LiteralPath $s -NewName $dst
    if ((Get-ProfileActif) -eq $src) { Set-ProfileActif $dst }
    Write-Host "  Profil '$src' renomme en '$dst'." -ForegroundColor Green
}

function Delete-Profile([string]$nom) {
    $dir = Join-Path $profiles $nom
    if (-not (Test-Path -LiteralPath $dir)) { throw "Profil introuvable : $nom" }
    if ((Get-Profiles).Count -le 1) { throw 'Impossible : il doit rester au moins un profil.' }
    Remove-Item -LiteralPath $dir -Recurse -Force
    Write-Host "  Profil '$nom' supprime." -ForegroundColor Yellow
    if ((Get-ProfileActif) -eq $nom) {
        # Repli sur le profil le plus fourni en mods : UKMM cree aussi un
        # profil "Default" vide, on ne veut pas se retrouver la-dessus.
        $reste = Get-Profiles | Sort-Object -Property @{E = {
            try { (Get-ModBlocks (Read-Profile $_.Name)).Count } catch { 0 }
        }} -Descending | Select-Object -First 1
        Set-ProfileActif $reste.Name
        Write-Host "  Profil actif bascule sur '$($reste.Name)'." -ForegroundColor Gray
    }
}

function Invoke-Ukmm([string[]]$Arguments) {
    $p = Start-Process -FilePath $ukmm -ArgumentList $Arguments `
                       -WorkingDirectory (Split-Path -Parent $ukmm) `
                       -Wait -PassThru -NoNewWindow
    return $p.ExitCode
}

function Apply-Profile([string]$nom) {
    $script = Join-Path $PSScriptRoot 'Set-ProfilUKMM.ps1'
    if (-not (Test-Path -LiteralPath $script)) { throw "Set-ProfilUKMM.ps1 introuvable a cote du panneau." }
    & $script -Profile $nom
}

function Show-Info {
    $actif = Get-ProfileActif
    Write-Host ''
    Write-Host '  Profil              Mods  Merges      Taille' -ForegroundColor Cyan
    foreach ($p in Get-Profiles) {
        $n = 0
        try { $n = (Get-ModBlocks (Read-Profile $p.Name)).Count } catch {}
        $md = Join-Path $p.FullName 'merged'
        $nf = 0; $oct = 0
        if (Test-Path -LiteralPath $md) {
            $s = Get-ChildItem -LiteralPath $md -Recurse -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum
            $nf = $s.Count; $oct = [long]$s.Sum
        }
        $marq = if ($p.Name -eq $actif) { ' *' } else { '  ' }
        $ko = if ($oct -ge 1GB) { '{0:N1} Go' -f ($oct/1GB) } else { '{0:N0} Mo' -f ($oct/1MB) }
        Write-Host ("  {0}{1,-18} {2,4}  {3,5}      {4,7}{5}" -f $marq, $p.Name, $n, $nf, $ko,
            $(if ($p.Name -eq $actif) { '   <- actif' } else { '' })) -ForegroundColor $(if ($p.Name -eq $actif) { 'Green' } else { 'Gray' })
    }
    Write-Host ''
    Write-Host "  (* = profil charge en jeu ; merged = fichiers produits par la fusion)" -ForegroundColor DarkGray
}

function Pick-Profile([string]$question) {
    $ps = Get-Profiles
    if (-not $ps) { throw 'Aucun profil.' }
    Write-Host ''
    for ($i = 0; $i -lt $ps.Count; $i++) {
        $actif = if ($ps[$i].Name -eq (Get-ProfileActif)) { '  <- actif' } else { '' }
        Write-Host ("   {0}. {1}{2}" -f ($i+1), $ps[$i].Name, $actif)
    }
    Write-Host ''
    $n = Read-Host $question
    $i = 0
    if ([int]::TryParse($n, [ref]$i) -and $i -ge 1 -and $i -le $ps.Count) { return $ps[$i-1].Name }
    Write-Host '   Choix invalide.' -ForegroundColor Red
    return $null
}

function Menu-Profile {
    Guard
    while ($true) {
        Write-Host ''
        Write-Host '------------------------------------------------------------'
        Write-Host '   PANNEAU DES PROFILS  -  Zelda BOTW'
        Write-Host '------------------------------------------------------------'
        Show-Info
        Write-Host '   1. Basculer sur un profil (fusion + deploiement)'
        Write-Host '   2. Creer un profil VIDE'
        Write-Host '   3. Dupliquer un profil (copier ses mods)'
        Write-Host '   4. Renommer un profil'
        Write-Host '   5. Supprimer un profil'
        Write-Host '   6. Gerer les mods d''un profil'
        Write-Host '   0. Quitter'
        Write-Host ''
        $c = Read-Host '   Choix'
        try {
            switch ($c.Trim()) {
                '1' {
                    $n = Pick-Profile 'Numero du profil a charger'
                    if ($n) { Apply-Profile $n }
                }
                '2' {
                    $n = (Read-Host '   Nom du nouveau profil (ex: solo, coop, test)').Trim()
                    if ($n) { New-ProfileVide $n }
                }
                '3' {
                    $src = Pick-Profile 'Numero du profil a dupliquer'
                    if ($src) {
                        $dst = (Read-Host "   Nom de la copie (ex: $src-bis)").Trim()
                        if ($dst) { Copy-Profile $src $dst }
                    }
                }
                '4' {
                    $src = Pick-Profile 'Numero du profil a renommer'
                    if ($src) {
                        $dst = (Read-Host '   Nouveau nom').Trim()
                        if ($dst) { Rename-Profile $src $dst }
                    }
                }
                '5' {
                    $src = Pick-Profile 'Numero du profil a supprimer'
                    if ($src) {
                        $ok = Read-Host "   Supprimer DEFINITIVEMENT '$src' ? ses mods seront retires de ce profil uniquement (oui/non)"
                        if ($ok.Trim().ToLower() -eq 'oui') { Delete-Profile $src }
                        else { Write-Host '   Annule.' -ForegroundColor DarkGray }
                    }
                }
                '6' { Menu-Mods }
                '0' { exit 0 }
                default { Write-Host '   Choix invalide.' -ForegroundColor Red }
            }
        } catch {
            Write-Host ''
            Write-Host "   ERREUR : $($_.Exception.Message)" -ForegroundColor Red
            Write-Host ''
        }
    }
}

function Menu-Mods {
    while ($true) {
        $nom = Pick-Profile 'Dans quel profil veux-tu gerer les mods ?'
        if (-not $nom) { return }
        Write-Host ''
        Write-Host "   MODS DU PROFIL '$nom'" -ForegroundColor Cyan
        $blocks = Get-ModBlocks (Read-Profile $nom)
        if (-not $blocks) { Write-Host '   (aucun mod)' -ForegroundColor DarkGray }
        for ($i = 0; $i -lt $blocks.Count; $i++) {
            $etat = if ($blocks[$i].Enabled) { 'actif   ' } else { 'DESACTIF' }
            $col  = if ($blocks[$i].Enabled) { 'Green' } else { 'DarkYellow' }
            Write-Host ("   {0}. [{1}] {2}" -f ($i+1), $etat, $blocks[$i].Name) -ForegroundColor $col
        }
        Write-Host ''
        Write-Host '   A. Activer / desactiver un mod'
        Write-Host '   R. Retirer un mod de ce profil (le .zip reste disponible)'
        Write-Host '   I. Installer un mod depuis le dossier Mods\'
        Write-Host '   M. Menu principal'
        Write-Host ''
        $c = Read-Host '   Choix'
        try {
            switch ($c.Trim().ToUpper()) {
                'A' {
                    $n = Read-Host '   Numero du mod a basculer'
                    $i = 0
                    if ([int]::TryParse($n, [ref]$i) -and $i -ge 1 -and $i -le $blocks.Count) {
                        Set-ModEnabled $nom $blocks[$i-1].Hash (-not $blocks[$i-1].Enabled)
                        Write-Host "   Mod bascule." -ForegroundColor Green
                        Write-Host "   Fait : applique 'Basculer sur un profil' pour que ca s'applique en jeu." -ForegroundColor DarkGray
                    } else { Write-Host '   Numero invalide.' -ForegroundColor Red }
                }
                'R' {
                    $n = Read-Host '   Numero du mod a retirer'
                    $i = 0
                    if ([int]::TryParse($n, [ref]$i) -and $i -ge 1 -and $i -le $blocks.Count) {
                        Remove-ModFromProfile $nom $blocks[$i-1].Hash
                        Write-Host "   '$($blocks[$i-1].Name)' retire de '$nom'." -ForegroundColor Yellow
                        Write-Host "   Fait : applique 'Basculer sur un profil' pour que ca s'applique en jeu." -ForegroundColor DarkGray
                    } else { Write-Host '   Numero invalide.' -ForegroundColor Red }
                }
                'I' {
                    $zips = @(Get-ChildItem -LiteralPath $modsLib -Filter *.zip -File -ErrorAction SilentlyContinue |
                              Sort-Object Name)
                    if (-not $zips) { Write-Host '   Aucun .zip dans le dossier Mods\.' -ForegroundColor Red; break }
                    Write-Host ''
                    for ($i = 0; $i -lt $zips.Count; $i++) {
                        Write-Host ("   {0}. {1}" -f ($i+1), $zips[$i].Name)
                    }
                    Write-Host ''
                    $n = Read-Host '   Numero du .zip a installer'
                    $i = 0
                    if ([int]::TryParse($n, [ref]$i) -and $i -ge 1 -and $i -le $zips.Count) {
                        $code = Invoke-Ukmm @('install', $zips[$i-1].FullName, $nom)
                        if ($code -ne 0) { throw "UKMM a refuse le mod (code $code). S'il a des options a cocher, installe-le via l'interface graphique d'UKMM." }
                        Write-Host '   Mod installe.' -ForegroundColor Green
                    } else { Write-Host '   Numero invalide.' -ForegroundColor Red }
                }
                'M' { return }
                default { Write-Host '   Choix invalide.' -ForegroundColor Red }
            }
        } catch {
            Write-Host ''
            Write-Host "   ERREUR : $($_.Exception.Message)" -ForegroundColor Red
            Write-Host ''
        }
    }
}

# --- Mode non interactif (tests / scripts) ----------------------------------
if ($NonInteractif) {
    Guard
    switch ($Action.ToLower()) {
        'list'   { Get-Profiles | ForEach-Object { Write-Host $_.Name } }
        'create' { New-ProfileVide $Nom }
        'copy'   { Copy-Profile $Nom $Vers }
        'delete' { Delete-Profile $Nom }
        'rename' { Rename-Profile $Nom $Vers }
        'switch' { Apply-Profile $Nom }
        default  { throw "Action inconnue : $Action" }
    }
    exit 0
}

Menu-Profile
