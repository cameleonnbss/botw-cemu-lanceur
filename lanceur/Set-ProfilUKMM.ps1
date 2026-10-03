param(
    [Parameter(Mandatory = $true)]
    [string]$Profile
)

$ErrorActionPreference = 'Stop'

$settings = Join-Path $env:APPDATA 'ukmm\settings.yml'
$ukmm     = Join-Path $env:USERPROFILE 'Tools\UKMM\ukmm.exe'

if (-not (Test-Path -LiteralPath $settings)) {
    throw "Config UKMM introuvable : $settings"
}
if (-not (Test-Path -LiteralPath $ukmm)) {
    throw "UKMM introuvable : $ukmm"
}

# Cemu verrouille les fichiers deployes : il faut le fermer avant de re-merger.
$running = Get-Process -Name Cemu -ErrorAction SilentlyContinue
if ($running) {
    Write-Host ""
    Write-Host "  Cemu est encore ouvert (PID $($running.Id -join ', '))." -ForegroundColor Yellow
    Write-Host "  Ferme Cemu puis relance ce script, sinon le deploiement peut echouer." -ForegroundColor Yellow
    Write-Host ""
    exit 2
}

# UKMM ouvert = il garde le profil en memoire et, avec auto: true, il redeploie
# a sa fermeture : il ecraserait le profil qu'on vient d'ecrire. Ferme-le d'abord.
$ukmmRunning = Get-Process -Name ukmm -ErrorAction SilentlyContinue
if ($ukmmRunning) {
    Write-Host ""
    Write-Host "  UKMM est encore ouvert (PID $($ukmmRunning.Id -join ', '))." -ForegroundColor Yellow
    Write-Host "  Ferme UKMM puis relance : sinon il remettra son profil a la" -ForegroundColor Yellow
    Write-Host "  fermeture et redeployera par-dessus le tien." -ForegroundColor Yellow
    Write-Host ""
    exit 3
}

$profiles = Join-Path $env:LOCALAPPDATA 'ukmm\wiiu\profiles'
if (-not (Test-Path -LiteralPath (Join-Path $profiles $Profile))) {
    Write-Host "Profils disponibles :" -ForegroundColor Cyan
    Get-ChildItem -LiteralPath $profiles -Directory | ForEach-Object { Write-Host "  - $($_.Name)" }
    throw "Profil inconnu : $Profile"
}

# Lecture / ecriture en UTF-8 SANS BOM : serde_yaml de UKMM refuse le BOM.
$raw = [System.IO.File]::ReadAllText($settings)
$new = [regex]::Replace($raw, '(?m)^(\s*profile:\s*).*$', ('$1' + $Profile))
$changed = ($new -ne $raw)

$gp = Join-Path $env:APPDATA 'Cemu\graphicPacks\BreathOfTheWild_UKMM'

if (-not $changed) {
    Write-Host "Le profil est deja '$Profile'." -ForegroundColor Gray
} else {
    [System.IO.File]::WriteAllText($settings, $new, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Profil -> $Profile" -ForegroundColor Green
    # UKMM n'ajoute que les fichiers du nouveau profil : sans nettoyage, les
    # fichiers de l'ancien profil restent deployes (les deux se melangent).
    # On vide donc son dossier de sortie ; ce sont des hardlinks, les fichiers
    # sources dans le stockage UKMM ne sont pas affectes.
    if (Test-Path -LiteralPath $gp) {
        Remove-Item -LiteralPath $gp -Recurse -Force
        Write-Host "Ancien deploiement efface (fichiers de l'ancien profil)." -ForegroundColor Gray
    }
}

function Invoke-Ukmm {
    param([string[]]$Arguments)
    # ukmm.exe est une application "GUI subsystem" : "& $ukmm" ne l'attend pas et
    # laisse $LASTEXITCODE vide (d'ou un faux "Echec"). Start-Process -Wait
    # attend vraiment et renvoie un vrai code de sortie.
    $p = Start-Process -FilePath $ukmm -ArgumentList $Arguments `
                       -WorkingDirectory (Split-Path -Parent $ukmm) `
                       -Wait -PassThru -NoNewWindow
    return $p.ExitCode
}

Write-Host "Fusion des mods..." -ForegroundColor Cyan
$code = Invoke-Ukmm @('remerge')
if ($code -ne 0) { throw "Echec du merge (code $code)" }

# UKMM n'ajoute que les fichiers du nouveau profil : sans nettoyage, ceux de
# l'ancien profil restent deployes (les deux se melangent). On vide donc son
# dossier de sortie a chaque passage ; ce sont des hardlinks, les fichiers
# sources du stockage UKMM ne sont pas affectes.
if (Test-Path -LiteralPath $gp) {
    Remove-Item -LiteralPath $gp -Recurse -Force
    Write-Host "Dossier de deploiement vide." -ForegroundColor Gray
}

Write-Host "Deploiement vers Cemu..." -ForegroundColor Cyan
$code = Invoke-Ukmm @('deploy')
if ($code -ne 0) { throw "Echec du deploiement (code $code)" }

# --- Deploiement dur, independant de l'etat interne de UKMM -----------------
# UKMM ne deploie que les fichiers listes dans wiiu\pending.yml. Or ce journal
# peut devenir incoherent (processus UKMM tue, changement de profil, mod
# ajoute a la main) : dans ce cas "deploy" repond "No changes pending
# deployment" et ne copie RIEN, sans lever la moindre erreur. Le seul moyen de
# reconstruire ce journal dans UKMM (reset_pending) n'existe que dans
# l'interface graphique, pas en ligne de commande.
# On pose donc nous-memes les hardlinks depuis merged/ vers le pack graphique.
# C'est exactement ce que fait la methode "HardLink" de UKMM : un hardlink ne
# coute pas d'espace disque et les deux noms pointent sur le meme inode.
$mergedRoot = Join-Path $env:LOCALAPPDATA ('ukmm\wiiu\profiles\' + $Profile + '\merged')
function Deploy-Hardlinks([string]$srcRoot, [string]$dstRoot) {
    if (-not (Test-Path -LiteralPath $srcRoot)) { return 0 }
    $n = 0
    Get-ChildItem -LiteralPath $srcRoot -Recurse -File -Force | ForEach-Object {
        $rel = $_.FullName.Substring($srcRoot.Length).TrimStart('\')
        $dst = Join-Path $dstRoot $rel
        $parent = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        }
        if (-not (Test-Path -LiteralPath $dst)) {
            New-Item -ItemType HardLink -Path $dst -Target $_.FullName -Force | Out-Null
            $n++
        }
    }
    return $n
}
$linked = (Deploy-Hardlinks (Join-Path $mergedRoot 'content') (Join-Path $gp 'content')) +
          (Deploy-Hardlinks (Join-Path $mergedRoot 'aoc')     (Join-Path $gp 'aoc'))
Write-Host "Hardlinks poses : $linked" -ForegroundColor Cyan

# --- Patch UKMM : pack de textes FR non deploye ------------------------------
# Les mods qui ajoutent du texte (Islands Expansion, Relics of the Past, Second
# Wind...) declarent "Pack/Bootup_EUen.pack" dans leur manifest.yml. Sur un jeu
# FR, UKMM genere bien le pack fusionne dans merged/content/Pack/Bootup_EUfr.pack
# (un SARC contenant Message/Msg_EUfr.product.ssarc), mais son manifeste de
# deploiement reprend le nom anglais tel quel : ce fichier n'est donc JAMAIS
# copie vers Cemu. Resultat : noms d'objets / koroks / iles vides en jeu.
# On le deploye nous-memes en hardlink (zero espace disque).
$mergedDir = Join-Path $env:LOCALAPPDATA ('ukmm\wiiu\profiles\' + $Profile + '\merged')
$srcPackDir = Join-Path $mergedDir 'content\Pack'
$langPacks = Get-ChildItem -LiteralPath $srcPackDir -Filter 'Bootup_*.pack' -File -ErrorAction SilentlyContinue
foreach ($lp in $langPacks) {
    $dest = Join-Path $gp ('content\Pack\' + $lp.Name)
    if (Test-Path -LiteralPath $dest) { continue }
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    New-Item -ItemType HardLink -Path $dest -Target $lp.FullName -Force | Out-Null
    Write-Host "Pack de textes deploye en plus : $($lp.Name)" -ForegroundColor Green
}

# Cemu ne detecte le pack que grace a rules.txt. Comme on a vide le dossier,
# UKMM ne le recree pas s'il n'a rien a redployer : on le reecrit au besoin.
$rules = Join-Path $gp 'rules.txt'
if (-not (Test-Path -LiteralPath $rules)) {
    $rulesBody = @(
        '[Definition]'
        'titleIds = 00050000101C9300,00050000101C9400,00050000101C9500'
        'name = UKMM'
        'path = The Legend of Zelda: Breath of the Wild/Mods/UKMM'
        'description = Provides U-King Mod Manager integration. Disable to turn off all UKMM mods. Do not use alongside BCML or file replacement graphic packs.'
        'version = 7'
        'default = true'
        'fsPriority = 9999'
    ) -join "`r`n"
    [System.IO.File]::WriteAllText($rules, $rulesBody, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "rules.txt recree (indispensable pour que Cemu charge le pack)." -ForegroundColor Yellow
}

$count = (Get-ChildItem -LiteralPath $gp -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
$merged = Join-Path $env:LOCALAPPDATA ('ukmm\wiiu\profiles\' + $Profile + '\merged')
$expected = (Get-ChildItem -LiteralPath $merged -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Host ""
Write-Host "Profil '$Profile' deploye : $count fichiers (merge : $expected + rules.txt)." -ForegroundColor Green
if ($count -ne ($expected + 1)) {
    Write-Host "  ATTENTION : $count fichiers deployes pour $expected attendus (+ rules.txt)." -ForegroundColor Red
    Write-Host "  Des fichiers d'un autre profil sont peut-etre restes." -ForegroundColor Red
}
