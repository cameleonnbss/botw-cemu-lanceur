param(
    [switch]$NonInteractif,
    [string]$Action = ''      # 'leger' | 'complet' | 'statut'
)

$ErrorActionPreference = 'Stop'

# Bascule entre deux reglages graphiques de Cemu.
#
# POURQUOI CE SCRIPT EXISTE
# -------------------------
# A la creation de ce script, tes reglages Cemu demandaient a la carte
# graphique de compiler des shaders enorme :
#     Enhanced Reflections + 32 echantillons de reflet
#     + Depth Of Field active
#     + anisotropie 16x
#     + distance de dessin au maximum sur les 5 categories
#     + ombres 200% et distance d'ombre "Very High"
#     + 120 FPS / 165 FPS
# Or Cemu ne compile PAS les shaders a l'avance : il les compile pendant le
# jeu, a la volee, des qu'il rencontre un materiau qu'il n'a jamais vu. Changer
# de pack graphique ou ajouter des milliers d'acteurs (Second Wind) oblige a
# compiler des milliers de shaders INEDITS. Avec des shaders aussi gros, la
# premiere fois peut durer tres longtemps (l'ecran reste noir ou fige) et on a
# l'impression que le jeu est plante. Ce n'est pas un plantage : c'est une
# compilation. Coupe avant la fin = tout est perdu, car le cache n'est ecrit
# qu'a la fermeture de Cemu.
#
# Le mode "Leger" met les shaders legers. Si le jeu demarre vite en mode
# Leger alors qu'il bloque en mode Complet, c'est la preuve que les
# mods sont bons et que c'etait la compilation.
#
# REGLES DU JEU
# -------------
# * ASCII pur, pas d'accent dans le fichier : PowerShell 5.1 lit un .ps1 sans
#   BOM comme de l'ANSI, donc un accent ecrit ici devient un caractere bizarre.
#   Les accents tapes par l'utilisateur (noms de parties) sont, eux, ecrits en
#   UTF-8 et s'affichent correctement.
# * Chemin du profil utilisateur jamais en dur : %APPDATA% etc.

$settingsPath = Join-Path $env:APPDATA 'Cemu\settings.xml'
$backupPath   = Join-Path $env:APPDATA 'Cemu\settings.xml.botw-beauty.bak'
$markerPath   = Join-Path $env:APPDATA 'Cemu\settings.xml.botw-mode.txt'

# Chaque entree = chemin relatif du pack + categorie + valeur du mode "Complet".
# On ne touche qu'a ces categories-la : tout le reste de tes reglages est
# laisse intact.
$presetsComplet = @(
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Depth Of Field';            val = 'Enabled' },
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Reflections';               val = 'Enhanced Reflections' },
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Reflection Range';          val = 'Extra High (32 samples)' },
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Anisotropic Filtering';     val = 'Extreme (16x)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'NPC, Enemies And Other Entities';            val = 'Extreme (2x, requires Extended Memory pack!)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Terrain, Buildings, Bushes And Other Objects'; val = 'Ultra (1.5x, requires Extended Memory pack!)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Trees (2D Billboards)';      val = 'Extreme' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Grass Blades Density';       val = 'Extreme (experimental)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Texture Distance Detail (LOD)'; val = 'Highest (-16, Not Recommended)' },
    @{ pack = 'BreathOfTheWild/Graphics';           cat = 'Shadows';                   val = 'High (200%)' },
    @{ pack = 'BreathOfTheWild/Graphics';           cat = 'Shadow Draw Distance';       val = 'Very High (Recommended)' },
    @{ pack = 'BreathOfTheWild/Mods/FPS++';         cat = 'FPS Limit';                 val = '120FPS Limit' },
    @{ pack = 'BreathOfTheWild/Mods/FPS++';         cat = 'Framerate Limit';           val = '165FPS (ideal for 165Hz displays)' }
)

# Valeurs du mode "Leger" : toutes existent bien dans les rules.txt de ces
# packs (verifie), donc Cemu ne remettra rien par defaut derriere.
$presetsLeger = @(
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Depth Of Field';        val = 'Disabled (no performance gain)' },
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Reflections';           val = 'Normal Reflections' },
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Reflection Range';      val = 'Disabled' },
    @{ pack = 'BreathOfTheWild/Enhancements';       cat = 'Anisotropic Filtering'; val = 'High (4x)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'NPC, Enemies And Other Entities';            val = 'Medium (1x)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Terrain, Buildings, Bushes And Other Objects'; val = 'Medium (1x)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Trees (2D Billboards)';  val = 'Medium (Default)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Grass Blades Density';   val = 'Medium (Default)' },
    @{ pack = 'BreathOfTheWild/Mods/DrawDistance';  cat = 'Texture Distance Detail (LOD)'; val = 'Normal (Default)' },
    @{ pack = 'BreathOfTheWild/Graphics';           cat = 'Shadows';               val = 'Medium (100%, Default)' },
    @{ pack = 'BreathOfTheWild/Graphics';           cat = 'Shadow Draw Distance';   val = 'High (Default)' },
    @{ pack = 'BreathOfTheWild/Mods/FPS++';         cat = 'FPS Limit';             val = '60FPS Limit (Default)' },
    @{ pack = 'BreathOfTheWild/Mods/FPS++';         cat = 'Framerate Limit';       val = '60FPS (ideal for 240/120/60Hz displays)' }
)

function Guard-Cemu {
    $running = Get-Process -Name Cemu -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host ''
        Write-Host "  Cemu est ouvert (PID $($running.Id -join ', '))." -ForegroundColor Yellow
        Write-Host "  Ferme-le : Cemu ecrase settings.xml a la fermeture et" -ForegroundColor Yellow
        Write-Host "  remettrait tes reglages par defaut." -ForegroundColor Yellow
        Write-Host ''
        exit 2
    }
}

function Get-CurrentMode {
    if (Test-Path -LiteralPath $markerPath) {
        return ([System.IO.File]::ReadAllText($markerPath)).Trim()
    }
    # Pas de marqueur : on deduit du contenu reel des reglages.
    if (-not (Test-Path -LiteralPath $settingsPath)) { return 'inconnu' }
    $raw = [System.IO.File]::ReadAllText($settingsPath)
    if ($raw -match 'Extra High \(32 samples\)') { return 'Complet' }
    if ($raw -match 'Normal Reflections') { return 'Leger' }
    return 'inconnu'
}

# Remplace la valeur d'une categorie de preset, dans l'entree de pack voulue,
# en traversant le bloc <Entry ...> qui contient le chemin du pack.
function Set-PackPreset([string]$xml, [string]$packPath, [string]$category, [string]$value) {
    $needle = 'graphicPacks/downloadedGraphicPacks/' + $packPath + '/rules.txt'
    $esc = [regex]::Escape($needle)
    # Les parentheses autour du cast sont obligatoires : sans elles,
    # PowerShell lit "[regex]'...'" seul puis concatene, et echoue.
    $entryRe = [regex]('(?s)<Entry\s+filename="' + $esc + '"\s*>(.*?)</Entry>')

    $m = $entryRe.Match($xml)
    if (-not $m.Success) {
        return @{ xml = $xml; changed = $false; why = "pack absent : $packPath" }
    }
    $block = $m.Groups[1].Value

    $catEsc = [regex]::Escape($category)
    $presetRe = [regex]('(?s)<Preset>\s*<category>' + $catEsc + '</category>\s*<preset>.*?</Preset>')
    $pm = $presetRe.Match($block)
    if (-not $pm.Success) {
        # La categorie n'est pas listee : on l'ajoute au bon endroit de l'entree.
        $newPreset = "`r`n            <Preset>`r`n                <category>$category</category>`r`n                <preset>$value</preset>`r`n            </Preset>"
        $blockNew = $block + $newPreset
        $xml = $xml.Substring(0, $m.Index) + '<Entry filename="' + $needle + '">' + $blockNew + '</Entry>' + $xml.Substring($m.Index + $m.Length)
        return @{ xml = $xml; changed = $true; why = "categorie ajoutee : $category" }
    }

    $oldPreset = $pm.Value
    if ($oldPreset -match ('<preset>' + [regex]::Escape($value) + '</preset>')) {
        return @{ xml = $xml; changed = $false; why = "deja en place : $category" }
    }
    $newPreset = [regex]::Replace($oldPreset, '(?s)<preset>.*?</preset>', "<preset>$value</preset>")
    $blockNew = $block.Substring(0, $pm.Index) + $newPreset + $block.Substring($pm.Index + $pm.Length)
    $xml = $xml.Substring(0, $m.Index) + '<Entry filename="' + $needle + '">' + $blockNew + '</Entry>' + $xml.Substring($m.Index + $m.Length)
    return @{ xml = $xml; changed = $true; why = "$category -> $value" }
}

function Show-Reglages {
    param([string]$Label, $Table)
    Write-Host "  $Label" -ForegroundColor Cyan
    foreach ($p in $Table) {
        Write-Host ("     {0,-46} {1}" -f $p.cat, $p.val) -ForegroundColor DarkGray
    }
}

function Apply-Mode([string]$mode) {
    if (-not (Test-Path -LiteralPath $settingsPath)) {
        throw "Fichier de reglages Cemu introuvable : $settingsPath"
    }
    Guard-Cemu

    $raw = [System.IO.File]::ReadAllText($settingsPath)
    if ($raw -match '<\?xml') {
        try { [xml]$null = $raw } catch { throw "settings.xml est abime, on ne touche a rien." }
    }

    $table = if ($mode -eq 'Leger') { $presetsLeger } else { $presetsComplet }
    $nom   = if ($mode -eq 'Leger') { 'Leger' } else { 'Complet' }
    $xml = $raw
    $n = 0
    foreach ($p in $table) {
        $r = Set-PackPreset $xml $p.pack $p.cat $p.val
        $xml = $r.xml
        if ($r.changed) { $n++ }
    }

    if ($n -eq 0) {
        Write-Host "Deja en mode $nom, rien a changer." -ForegroundColor Gray
    } else {
        # Sauvegarde de la version "beaute" au tout premier passage, pour
        # pouvoir toujours revenir en arriere.
        if (-not (Test-Path -LiteralPath $backupPath)) {
            [System.IO.File]::WriteAllText($backupPath, $raw, (New-Object System.Text.UTF8Encoding($false)))
            Write-Host "Sauvegarde creee : settings.xml.botw-beauty.bak" -ForegroundColor DarkGray
        }
        [System.IO.File]::WriteAllText($settingsPath, $xml, (New-Object System.Text.UTF8Encoding($false)))
        [System.IO.File]::WriteAllText($markerPath, $nom, (New-Object System.Text.UTF8Encoding($false)))
        Write-Host "Mode graphique -> $nom  ($n reglages modifies)" -ForegroundColor Green
    }

    # --- Verification apres ecriture ---------------------------------------
    # Cemu peut reecrire settings.xml a sa fermeture. Si l'utilisateur croit
    # avoir mis le mode Leger mais que le jeu tourne encore en Complet, il ne
    # le voit pas. On relit donc le fichier et on controle une valeur temoin
    # pour chaque pack, et on previent clairement si ca n'a pas pris.
    $lu = [System.IO.File]::ReadAllText($settingsPath)
    Write-Host ''
    Write-Host '  Verification (relue depuis le fichier) :' -ForegroundColor Cyan
    $temoin = @(
        @{ label = 'Reflections';        attendu = $(if ($mode -eq 'Leger') { 'Normal Reflections' } else { 'Enhanced Reflections' }) },
        @{ label = 'Reflection Range';   attendu = $(if ($mode -eq 'Leger') { 'Disabled' } else { 'Extra High \(32 samples\)' }) },
        @{ label = 'Anisotropie';        attendu = $(if ($mode -eq 'Leger') { 'High \(4x\)' } else { 'Extreme \(16x\)' }) },
        @{ label = 'Distance de dessin'; attendu = $(if ($mode -eq 'Leger') { 'Normal \(Default\)' } else { 'Highest \(-16, Not Recommended\)' }) },
        @{ label = 'Ombres';             attendu = $(if ($mode -eq 'Leger') { 'Medium \(100%, Default\)' } else { 'High \(200%\)' }) }
    )
    $ko = 0
    foreach ($t in $temoin) {
        if ($lu -match ('<preset>' + $t.attendu + '</preset>')) {
            Write-Host "     OK  $($t.label)" -ForegroundColor Green
        } else {
            Write-Host "     !!  $($t.label) : valeur absente du fichier !" -ForegroundColor Red
            $ko++
        }
    }
    if ($ko -gt 0) {
        Write-Host ''
        Write-Host "  ECHEC : le mode n'a pas ete ecrit. Cause possible : Cemu" -ForegroundColor Red
        Write-Host "  etait ouvert, ou Cemu a reecrit settings.xml apres coup." -ForegroundColor Red
        Write-Host "  Ferme Cemu, relance ce menu, puis verifie la ligne 'Verification'." -ForegroundColor Red
        exit 4
    }
    Show-Reglages $nom $table
    Write-Host ''
    Write-Host "  Au PROCHAIN lancement, Cemu va recompiler ses shaders : laisse-le" -ForegroundColor Yellow
    Write-Host "  tourner 5 a 15 minutes au premier demarrage, ne le ferme pas." -ForegroundColor Yellow
}

# --- Mode non interactif -----------------------------------------------------
if ($NonInteractif) {
    switch ($Action.ToLower()) {
        'leger'   { Apply-Mode 'Leger';   exit 0 }
        'complet' { Apply-Mode 'Complet'; exit 0 }
        'statut'  { Write-Host (Get-CurrentMode); exit 0 }
        default   { throw "Action inconnue : $Action" }
    }
}

# --- Menu --------------------------------------------------------------------
Write-Host ''
Write-Host '------------------------------------------------------------'
Write-Host '   GRAPHISMES  -  Zelda Breath of the Wild'
Write-Host '------------------------------------------------------------'
Write-Host "  Mode actuel : $(Get-CurrentMode)" -ForegroundColor Cyan
Write-Host ''
Write-Host '   1. Mode LEGER    shaders simples, demarrage rapide'
Write-Host '   2. Mode COMPLET  belle image, mais 1re fois tres longue'
Write-Host '   0. Quitter'
Write-Host ''

$choix = (Read-Host '   Choix').Trim()
switch ($choix) {
    '1' { Apply-Mode 'Leger' }
    '2' { Apply-Mode 'Complet' }
    '0' { exit 0 }
    default { Write-Host '   Choix invalide.' -ForegroundColor Red }
}
