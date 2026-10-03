param(
    [switch]$Silence
)

$ErrorActionPreference = 'Continue'

# ===========================================================================
#  VERIFICATION COMPLETE
#
#  Un seul script qui regarde si tout est en place et dit clairement ce qui
#  ne va pas. A lancer quand le jeu ne demarre pas, ou avant de jouer pour
#  etre sur que tout est bon.
#
#  Fichier en ASCII pur, SANS BOM : PowerShell 5.1 lit un .ps1 en ANSI, et le
#  nom du dossier utilisateur contient un accent.
# ===========================================================================

$racine  = $PSScriptRoot
$settings = Join-Path $env:APPDATA 'ukmm\settings.yml'
$ukmm     = Join-Path $env:USERPROFILE 'Tools\UKMM\ukmm.exe'
$profiles = Join-Path $env:LOCALAPPDATA 'ukmm\wiiu\profiles'
$gp       = Join-Path $env:APPDATA 'Cemu\graphicPacks\BreathOfTheWild_UKMM'
$profil   = Join-Path $env:APPDATA 'Cemu\mlc01\usr\save\00050000\101c9500'
$outils   = Join-Path $racine 'Outils'

$ko = 0
$ok = 0

function Vert  { param($t) Write-Host "  [OK ] $t" -ForegroundColor Green
                $script:ok++ }
function Rouge { param($t) Write-Host "  [KO ] $t" -ForegroundColor Red
                $script:ko++ }
function Gris  { param($t) Write-Host "  [ -- ] $t" -ForegroundColor DarkGray }

Write-Host ''
Write-Host '================================================================'
Write-Host '  VERIFICATION COMPLETE'
Write-Host '================================================================'

# --- 1. UKMM --------------------------------------------------------------
Write-Host ''
Write-Host ' 1. Le gestionnaire de mods (UKMM)' -ForegroundColor Cyan
if (Test-Path -LiteralPath $ukmm) { Vert "UKMM installe : $ukmm" }
else { Rouge "UKMM introuvable : $ukmm" }
if (Test-Path -LiteralPath $settings) { Vert 'configuration UKMM presente' }
else { Rouge "configuration UKMM introuvable : $settings" }

$actif = '?'
if (Test-Path -LiteralPath $settings) {
    $m = [regex]::Match([System.IO.File]::ReadAllText($settings), '(?m)^\s*profile:\s*(\S+)\s*$')
    if ($m.Success) { $actif = $m.Groups[1].Value }
    if (Test-Path -LiteralPath (Join-Path $profiles $actif)) {
        Vert "profil actif : $actif"
    } else {
        Rouge "le profil actif '$actif' n'existe pas dans $profiles"
    }
    if ([regex]::IsMatch([System.IO.File]::ReadAllText($settings), '(?m)^\s*auto:\s*true')) {
        Gris 'deploy_config.auto = true (chaque remerge redeploie : c est voulu)'
    }
}

# --- 2. Les programmes qui doivent etre fermes ---------------------------
Write-Host ''
Write-Host ' 2. Ce qui doit etre ferme' -ForegroundColor Cyan
foreach ($p in @('Cemu', 'ukmm')) {
    $r = Get-Process -Name $p -ErrorAction SilentlyContinue
    if ($r) { Gris "$p est ouvert (PID $($r.Id -join ', ')) - ferme-le avant de changer de profil" }
    else    { Vert "$p est ferme" }
}

# --- 3. Le profil fusionne ----------------------------------------------
Write-Host ''
Write-Host ' 3. Le profil actif est-il completement fusionne ?' -ForegroundColor Cyan
$merged = Join-Path (Join-Path $profiles $actif) 'merged'
if (-not (Test-Path -LiteralPath $merged)) {
    Rouge "dossier de fusion absent : $merged"
} else {
    $fichiers = Get-ChildItem -LiteralPath $merged -Recurse -File -ErrorAction SilentlyContinue
    if ($fichiers.Count -gt 0) { Vert "$($fichiers.Count) fichiers fusionnes" }
    else { Rouge 'le profil est vide : aucun mod fusionne' }
}

# --- 4. Le pack deploye dans Cemu ---------------------------------------
Write-Host ''
Write-Host ' 4. Ce que Cemu va reellement lire' -ForegroundColor Cyan
if (-not (Test-Path -LiteralPath $gp)) {
    Rouge "pack UKMM absent de Cemu : $gp"
} else {
    $deployed = Get-ChildItem -LiteralPath $gp -Recurse -File -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath (Join-Path $gp 'rules.txt')) {
        Vert 'rules.txt present (Cemu voit bien le pack)'
    } else {
        Rouge 'rules.txt ABSENT : Cemu ignore tout le pack, le jeu demarre en vanilla'
    }
    $packs = Get-ChildItem -LiteralPath (Join-Path $gp 'content\Pack') -Filter 'Bootup_*.pack' `
                          -File -ErrorAction SilentlyContinue
    if ($packs) {
        foreach ($p in $packs) { Vert "pack de textes : $($p.Name)" }
    } else {
        Rouge 'aucun pack de textes (Bootup_*.pack) : les noms ajoutes par les mods seront vides'
    }
    if ($merged -and (Test-Path -LiteralPath $merged)) {
        $attendu = (Get-ChildItem -LiteralPath $merged -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        $reel = ($deployed | Where-Object { $_.Name -ne 'rules.txt' } | Measure-Object).Count
        if ($attendu -eq 0) {
            Gris 'rien a comparer'
        } elseif ($reel -eq $attendu) {
            Vert "tout ce qui est fusionne est deploye ($reel fichiers)"
        } else {
            Rouge "deploiement incoherent : $reel fichiers deployes pour $attendu fusionnes"
            Rouge 'relance le profil depuis le lanceur (touche 1 a 5)'
        }
    }
}

# --- 5. Les sauvegardes ---------------------------------------------------
Write-Host ''
Write-Host ' 5. Les sauvegardes' -ForegroundColor Cyan
if (Test-Path -LiteralPath $profil) {
    # Le dossier racine ne contient que des sous-dossiers (user\80000001\...) :
    # il faut descendre, sinon on conclut a tort qu'il n'y a aucune sauvegarde.
    $saves = Get-ChildItem -LiteralPath $profil -Recurse -File -ErrorAction SilentlyContinue
    if ($saves.Count -gt 0) { Vert "$($saves.Count) fichier(s) de sauvegarde dans la partie en cours" }
    else { Gris 'aucune sauvegarde : c est normal si tu n as jamais joue' }
} else {
    Gris "pas encore de dossier de sauvegarde ($profil)"
}
$json = Join-Path $racine 'Sauvegardes\parties.json'
if (Test-Path -LiteralPath $json) { Vert 'noms et descriptions des parties : presents' }
else { Gris 'Sauvegardes\parties.json absent (les parties n ont pas encore ete nommees)' }

# --- 6. L analyse des conflits -------------------------------------------
Write-Host ''
Write-Host ' 6. Analyse des conflits entre mods' -ForegroundColor Cyan
$py = (Get-Command python -ErrorAction SilentlyContinue)
$conflits = Join-Path $racine 'Outils\conflits.py'
if ($py -and (Test-Path -LiteralPath $conflits)) {
    Gris 'lancer  python conflits.py  pour la liste detaillee des chevauchements'
} elseif (-not (Test-Path -LiteralPath $conflits)) {
    Gris 'Outils\conflits.py absent (copie incomplete du dossier)'
} else {
    Gris 'python introuvable : analyse automatique impossible'
}

# --- 7. Disque ------------------------------------------------------------
Write-Host ''
Write-Host ' 7. Place disponible' -ForegroundColor Cyan
$libre = (Get-PSDrive -Name 'C').Free / 1GB
if ($libre -lt 2) { Rouge ("il ne reste que {0:N1} Go sur C: - UKMM ne pourra plus fusionner" -f $libre) }
else { Vert ("{0:N1} Go libres sur C:" -f $libre) }

# --- Verdict --------------------------------------------------------------
Write-Host ''
Write-Host '================================================================'
if ($ko -eq 0) {
    Write-Host "  TOUT VA BIEN  ($ok controles passes)" -ForegroundColor Green
    Write-Host '================================================================'
    exit 0
} else {
    Write-Host "  $ko PROBLEME(S) A REPARER  ($ok controles passes)" -ForegroundColor Red
    Write-Host '================================================================'
    Write-Host ''
    Write-Host '  Repartition des problemes :'
    Write-Host '   - pack UKMM absent ou rules.txt manquant'
    Write-Host '       -> ferme Cemu, puis relance une touche de jeu du lanceur'
    Write-Host '   - deploiement incoherent'
    Write-Host '       -> le lanceur recree tout : touche 1 a 5'
    Write-Host '   - pas de pack de textes'
    Write-Host '       -> idem, le lanceur le rajoute tout seul'
    Write-Host '   - disque plein'
    Write-Host '       -> supprime des profils inutiles (touche 9 du lanceur)'
    exit 1
}