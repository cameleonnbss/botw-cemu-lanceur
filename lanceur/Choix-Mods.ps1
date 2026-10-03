param(
    [Parameter(Mandatory = $true)][string]$Profile
)

$ErrorActionPreference = 'Stop'

# ===========================================================================
#  CHOIX DES MODS
#
#  Tu coches les mods que tu veux, le profil est modifie puis redeploye.
#  Regle importante d'UKMM decouverte a l'usage : "ukmm install <zip> <profil>"
#  ecrit en realite dans le profil ACTIF, pas dans celui passe en argument.
#  On positionne donc le profil actif sur la cible avant d'appeler UKMM,
#  sinon les mods installes disparaisent en silence.
# ===========================================================================

$settings = Join-Path $env:APPDATA 'ukmm\settings.yml'
$ukmm     = Join-Path $env:USERPROFILE 'Tools\UKMM\ukmm.exe'
$profiles = Join-Path $env:LOCALAPPDATA 'ukmm\wiiu\profiles'
$modsDir  = Join-Path $env:LOCALAPPDATA 'ukmm\wiiu\mods'
$lib      = Join-Path $PSScriptRoot 'Mods'
$appliquer = Join-Path $PSScriptRoot 'Set-ProfilUKMM.ps1'

function Guard {
    if (Get-Process -Name Cemu -ErrorAction SilentlyContinue) {
        Write-Host "`n  Cemu est ouvert. Ferme-le puis relance.`n" -ForegroundColor Yellow
        exit 2
    }
    if (Get-Process -Name ukmm -ErrorAction SilentlyContinue) {
        Write-Host "`n  UKMM est ouvert. Ferme-le puis relance.`n" -ForegroundColor Yellow
        exit 3
    }
}

# Mods incompatibles connus : meme emplacement d'arme dans le jeu.
$CONFLITS = @(
    @{ A = 'Ancient_Weaponry_Mark_II'; B = 'Relics_of_the_Past'
       Raison = 'les deux remplacent la meme epee / lance / bouclier / arc' }
)

function Get-ProfileText { [System.IO.File]::ReadAllText((Join-Path (Join-Path $profiles $Profile) 'profile.yml')) }

function Get-ProfileMods {
    $txt = Get-ProfileText
    $res = @()
    $lines = $txt -split "`r?`n"
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^  (\d+):\s*$') {
            $hash = $Matches[1]; $start = $i; $j = $i + 1
            $zip = ''; $name = ''
            while ($j -lt $lines.Count -and $lines[$j] -notmatch '^  \d+:\s*$' -and $lines[$j] -notmatch '^\S') {
                if ($lines[$j] -match '^\s+path: .*\\([^\\\r\n]+)\s*$') { $zip = $Matches[1] }
                if ($lines[$j] -match '^      name: (.+?)\s*$') { $name = $Matches[1] }
                $j++
            }
            $res += [pscustomobject]@{ Hash = $hash; Zip = $zip; Name = $name; Start = $start; End = $j }
            $i = $j - 1
        }
    }
    return $res
}

function Get-LibMods {
    Add-Type -AssemblyName System.IO.Compression.FileSystem -ErrorAction SilentlyContinue
    $out = @()
    foreach ($f in (Get-ChildItem -LiteralPath $lib -Filter *.zip -File -ErrorAction SilentlyContinue | Sort-Object Name)) {
        $nom = $f.BaseName
        try {
            $zip = [System.IO.Compression.ZipFile]::OpenRead($f.FullName)
            $e = $zip.Entries | Where-Object { $_.FullName -eq 'meta.yml' } | Select-Object -First 1
            if ($e) {
                $sr = New-Object System.IO.StreamReader($e.Open())
                $meta = $sr.ReadToEnd(); $sr.Close()
                if ($meta -match '(?m)^name:\s*(.+?)\s*$') { $nom = $Matches[1] }
            }
            $zip.Dispose()
        } catch {}
        $out += [pscustomobject]@{ Fichier = $f; Nom = $nom }
    }
    return $out
}

function Remove-Mod([string]$zip) {
    $pfile = Join-Path (Join-Path $profiles $Profile) 'profile.yml'
    [System.IO.File]::Copy($pfile, "$pfile.bak", $true)
    $lines = [System.Collections.ArrayList]@((Get-ProfileText) -split "`r?`n")
    $blk = Get-ProfileMods | Where-Object { $_.Zip -eq $zip }
    if (-not $blk) { return $false }
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i].Trim() -eq "- $($blk.Hash)") { [void]$lines.RemoveAt($i); break }
    }
    [void]$lines.RemoveRange($blk.Start, $blk.End - $blk.Start)
    [System.IO.File]::WriteAllText($pfile, (@($lines) -join "`r`n"), (New-Object System.Text.UTF8Encoding($false)))
    return $true
}

function Set-Actif([string]$nom) {
    $raw = [System.IO.File]::ReadAllText($settings)
    [System.IO.File]::WriteAllText($settings,
        ([regex]::Replace($raw, '(?m)^(\s*profile:\s*).*$', ('$1' + $nom))),
        (New-Object System.Text.UTF8Encoding($false)))
}

function Invoke-Ukmm([string[]]$A) {
    (Start-Process -FilePath $ukmm -ArgumentList $A -WorkingDirectory (Split-Path -Parent $ukmm) `
                    -Wait -PassThru -NoNewWindow).ExitCode
}

Guard
if (-not (Test-Path -LiteralPath (Join-Path $profiles $Profile))) {
    Write-Host "  Profil inconnu : $Profile" -ForegroundColor Red
    Write-Host '  Profils : ' -NoNewline
    (Get-ChildItem -LiteralPath $profiles -Directory).Name -join ', '
    exit 1
}

# Etat initial : ce que contient reellement le profil. Calcule UNE SEULE FOIS
# avant la boucle : si on le recalculait a chaque affichage, les coches que
# l'utilisateur vient de poser seraient ecrasees au tour suivant.
$dansProfil = @{}
foreach ($m in Get-ProfileMods) { $dansProfil[$m.Zip] = $m }
$libMods = Get-LibMods
$etat = @{}
for ($i = 0; $i -lt $libMods.Count; $i++) {
    $etat[$i] = $dansProfil.ContainsKey($libMods[$i].Fichier.Name)
}

while ($true) {
    Write-Host ''
    Write-Host '------------------------------------------------------------'
    Write-Host "   CHOIX DES MODS   profil : $Profile"
    Write-Host '------------------------------------------------------------'

    for ($i = 0; $i -lt $libMods.Count; $i++) {
        $zip = $libMods[$i].Fichier.Name
        $on = $etat[$i]
        $marque = if ($on) { '[X]' } else { '[ ]' }
        $col    = if ($on) { 'Green' } else { 'Gray' }
        Write-Host ("   {0}. {1} {2}" -f ($i + 1), $marque, $libMods[$i].Nom) -ForegroundColor $col

        foreach ($c in $CONFLITS) {
            if ($on -and (($c.A -eq $zip -and $etat[$libMods.IndexOf(($libMods | Where-Object { $_.Fichier.Name -eq $c.B })[0])]) -or
                          ($c.B -eq $zip -and $etat[$libMods.IndexOf(($libMods | Where-Object { $_.Fichier.Name -eq $c.A })[0])]))) {
                Write-Host ("        ! CONFLIT avec l'autre mod d'armes : {0}" -f $c.Raison) -ForegroundColor Red
            }
        }
    }
    # mods presents dans le profil mais absents du dossier Mods
    foreach ($k in $dansProfil.Keys) {
        if (-not ($libMods | Where-Object { $_.Fichier.Name -eq $k })) {
            Write-Host "   .  [X] $($dansProfil[$k].Name)   (absent du dossier Mods\)" -ForegroundColor Yellow
        }
    }

    Write-Host ''
    Write-Host '   Tape les numeros a cocher/decocher, separes par des espaces.'
    Write-Host '   V = valider et jouer      0 = annuler'
    Write-Host ''
    $saisie = Read-Host '   Choix'
    $saisie = $saisie.Trim().ToLower()
    if ($saisie -eq '0') { exit 0 }
    if ($saisie -eq 'v' -or $saisie -eq '') { break }

    foreach ($tok in ($saisie -split '[\s,]+')) {
        $n = 0
        if ([int]::TryParse($tok, [ref]$n) -and $n -ge 1 -and $n -le $libMods.Count) {
            $etat[$n-1] = -not $etat[$n-1]
        } else {
            Write-Host "   '$tok' ignore (numero hors liste)" -ForegroundColor DarkYellow
        }
    }
}

# --- Application ------------------------------------------------------------
# UKMM ecrit dans le profil actif : on le positionne sur la cible.
Write-Host ''
Write-Host "  Profil actif positionne sur '$Profile'." -ForegroundColor Gray
Set-Actif $Profile

$ajoutes = 0; $retires = 0
for ($i = 0; $i -lt $libMods.Count; $i++) {
    $zip = $libMods[$i].Fichier.Name
    $present = $dansProfil.ContainsKey($zip)
    if (-not $etat[$i] -and $present) {
        if (Remove-Mod $zip) { $retires++; Write-Host "  - Retire : $($libMods[$i].Nom)" -ForegroundColor Yellow }
    } elseif ($etat[$i] -and -not $present) {
        $code = Invoke-Ukmm @('install', $libMods[$i].Fichier.FullName, $Profile)
        if ($code -eq 0) {
            $ajoutes++
            Write-Host "  + Ajoute : $($libMods[$i].Nom)" -ForegroundColor Green
        } else {
            Write-Host "  ! Refuse : $($libMods[$i].Nom) (code $code)" -ForegroundColor Red
            Write-Host '    Certains mods ont des options a cocher : installe-les via' -ForegroundColor DarkYellow
            Write-Host '    l''interface graphique d''UKMM (option 8 du lanceur).' -ForegroundColor DarkYellow
        }
    }
}

Write-Host ''
Write-Host "  Bilan : $ajoutes ajoute(s), $retires retire(s)." -ForegroundColor Cyan
Write-Host '  Fusion + deploiement...' -ForegroundColor Cyan
& $appliquer -Profile $Profile