param(
    [switch]$NonInteractif,
    [string]$Action = '',     # save | list | restore | delete | rename | status
    [string]$Nom = '',
    [string]$Description = ''
)

$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.Encoding]::UTF8

# --- Constantes ---------------------------------------------------------------
# Le jeu n'a qu'UN seul emplacement de sauvegarde visible. Les dossiers 0..5 dans
# user\80000001 sont des tampons internes (autosaves / differents etats de monde) :
# on ne peut pas les choisir depuis le menu du jeu. Pour avoir plusieurs parties
# distinctes, il faut donc copier ce dossier ailleurs et le remettre quand on veut.
$saveRoot  = Join-Path $env:APPDATA 'Cemu\mlc01\usr\save\00050000\101c9500'
$shotsDir  = Join-Path $PSScriptRoot 'Sauvegardes'
$indexPath = Join-Path $shotsDir 'parties.json'
$mainFile  = 'user\80000001\0\game_data.sav'   # le fichier qui definit la partie

# Cemu, pour l'option "charger et jouer"
$cemu = Join-Path $env:USERPROFILE 'Downloads\cemu-2.6-windows-x64\Cemu_2.6\Cemu.exe'

# REGLES DU JEU
# -------------
# * ASCII pur, pas d'accent dans ce fichier : PowerShell 5.1 lit un .ps1 sans
#   BOM comme de l'ANSI et un accent ecrit ici devient un caractere bizarre.
#   Les accents que TU tapes au clavier sont ecrits en UTF-8 : ils s'affichent
#   correctement.
# * Chemin du profil utilisateur jamais en dur (%APPDATA%, $PSScriptRoot) :
#   le nom du compte contient un accent, un chemin en dur serait massacre.

# --- Garde-fous ---------------------------------------------------------------
function Guard-Cemu {
    $running = Get-Process -Name Cemu -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host ''
        Write-Host "  Cemu est ouvert (PID $($running.Id -join ', '))." -ForegroundColor Yellow
        Write-Host "  Ferme-le : une sauvegarde modifiee pendant que le jeu tourne" -ForegroundColor Yellow
        Write-Host "  peut etre ecrite a moitie." -ForegroundColor Yellow
        Write-Host ''
        exit 2
    }
}

function Guard-Save {
    if (-not (Test-Path -LiteralPath $saveRoot)) {
        throw "Sauvegarde introuvable : $saveRoot`nLance le jeu une fois pour qu'elle se cree."
    }
}

# --- Index nom / description --------------------------------------------------
# Le dossier de sauvegarde EST la sauvegarde du jeu : on n'y met surtout pas de
# fichier a nous, le jeu pourrait refuser de la lire. Les noms et descriptions
# vivent donc a cote, dans un seul fichier JSON.
function Read-Index {
    if (-not (Test-Path -LiteralPath $indexPath)) { return @() }
    $raw = [System.IO.File]::ReadAllText($indexPath, [System.Text.Encoding]::UTF8)
    if (-not $raw.Trim()) { return @() }
    try {
        $data = $raw | ConvertFrom-Json
    } catch {
        Write-Host "  (parties.json illisible, il sera recree)" -ForegroundColor Yellow
        return @()
    }
    # On jette les elements vides : sur un index "[]", ConvertFrom-Json peut
    # renvoyer $null, et @($null) est un tableau contenant un element vide
    # qui trainerait ensuite dans toutes les sauvegardes suivantes.
    return @(@($data) | Where-Object { $_ -and $_.id })
}

function Write-Index($entries) {
    if (-not (Test-Path -LiteralPath $shotsDir)) {
        New-Item -ItemType Directory -Path $shotsDir -Force | Out-Null
    }
    # -InputObject est indispensable : avec le pipeline, un tableau d'un seul
    # element est deroule et ConvertTo-Json ecrit un objet nu a la place du
    # tableau, ce qui fait disparaitre toutes les autres parties de l'index.
    $json = ConvertTo-Json -InputObject @($entries) -Depth 5
    [System.IO.File]::WriteAllText($indexPath, $json, (New-Object System.Text.UTF8Encoding($false)))
}

# --- Liste des parties --------------------------------------------------------
function Format-Taille([long]$o) {
    if     ($o -ge 1GB) { '{0:N2} Go' -f ($o / 1GB) }
    elseif ($o -ge 1MB) { '{0:N1} Mo' -f ($o / 1MB) }
    else                { '{0:N0} Ko' -f ($o / 1KB) }
}

# Coupe un texte trop long pour que les colonnes du tableau restent alignees.
function Short([string]$s, [int]$n) {
    if ($null -eq $s) { return '' }
    if ($s.Length -le $n) { return $s }
    return $s.Substring(0, $n - 1) + '.'
}

function Get-DossierStats([string]$chemin) {
    $m = Get-ChildItem -LiteralPath $chemin -Recurse -File -ErrorAction SilentlyContinue |
         Measure-Object -Property Length -Sum
    return [pscustomobject]@{
        Fichiers = $m.Count
        Octets   = [long]$m.Sum
        MD5      = (Get-FileMD5 (Join-Path $chemin $mainFile))
    }
}

function Get-FileMD5([string]$chemin) {
    if (-not (Test-Path -LiteralPath $chemin)) { return '' }
    try { return (Get-FileHash -LiteralPath $chemin -Algorithm MD5).Hash } catch { return '' }
}

# --- Profil UKMM actif -------------------------------------------------------
# Pourquoi cette complication : une partie enregistree avec un jeu de mods A
# ne peut PAS etre lue avec un jeu de mods B. Le jeu relit la partie a travers
# les fichiers des mods installes ; si un fichier attendu a disparu ou a
# change, la lecture boucle sur l'ecran de chargement, SANS AUCUN MESSAGE.
# C'est le probleme numero un de ce lanceur. On note donc, pour chaque partie,
# le profil UKMM qui etait actif au moment de l'enregistrement, et on previent
# avant de charger une partie qui ne correspond pas au profil du moment.
function Get-ProfilActif {
    $s = Join-Path $env:APPDATA 'ukmm\settings.yml'
    if (-not (Test-Path -LiteralPath $s)) { return '' }
    $m = [regex]::Match([System.IO.File]::ReadAllText($s), '(?m)^\s*profile:\s*(\S+)\s*$')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Clear-Libelle([string]$s) {
    # Rend un libelle sure pour un nom de dossier Windows, sans accents.
    $s = $s -replace '[\\/:*?"<>|]', '-'
    $s = $s -replace '\s+', '_'
    $s = $s -replace '^_+|_+$', ''
    if ($s.Length -gt 40) { $s = $s.Substring(0, 40) }
    return $s
}

# Fusionne ce qui est sur le disque et ce qui est dans l'index : une partie
# creee avant l'existence de l'index (ou copiee a la main) reste listee, avec le
# nom du dossier comme nom lisible.
function Get-Parties {
    if (-not (Test-Path -LiteralPath $shotsDir)) { return @() }
    $index = Read-Index
    $liste = @()
    foreach ($d in (Get-ChildItem -LiteralPath $shotsDir -Directory -ErrorAction SilentlyContinue |
                    Sort-Object Name -Descending)) {
        $entry = $index | Where-Object { $_.id -eq $d.Name } | Select-Object -First 1
        $stats = Get-DossierStats $d.FullName
        $liste += [pscustomobject]@{
            Id          = $d.Name
            Nom         = $(if ($entry -and $entry.nom) { $entry.nom } else { $d.Name })
            Description = $(if ($entry) { [string]$entry.description } else { '' })
            # Date construite a partir des nombres, sans ParseExact : sur une
            # machine FR, ParseExact depend du calendrier systeme (gregorien,
            # bouddhiste, perse...) et peut echouer sur un "03/10/2026".
            Date        = $(if ($d.Name -match '^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})') {
                               New-Object DateTime -ArgumentList @(
                                   [int]$matches[1], [int]$matches[2], [int]$matches[3],
                                   [int]$matches[4], [int]$matches[5], 0)
                           } else { $d.CreationTime })
            Octets      = $stats.Octets
            Fichiers    = $stats.Fichiers
            MD5         = $stats.MD5
            Profil      = $(if ($entry -and $entry.profil) { [string]$entry.profil } else { '' })
            Chemin      = $d.FullName
        }
    }
    # On renvoie le tableau tel quel, SANS la virgule protectrice. C'est
    # l'appelant qui fait @(Get-Parties) : les deux mecanismes ne marchent pas
    # ensemble, sinon une seule partie devient un tableau contenant un tableau
    # et $parties[0].Date n'est plus une date (le menu plante sur ToString).
    return $liste
}

function Set-Info([string]$id, [string]$nom, [string]$desc, [string]$profil) {
    $avant  = @(Read-Index | Where-Object { $_.id -eq $id } | Select-Object -First 1)
    $index = @(Read-Index | Where-Object { $_.id -ne $id })
    # Un renommage ne doit jamais perdre le profil : si on ne le passe pas,
    # on reprend celui deja connu, sinon celui qui est actif maintenant.
    $profilFinal = $profil
    if (-not $profilFinal -and $avant) { $profilFinal = [string]$avant.profil }
    if (-not $profilFinal) { $profilFinal = Get-ProfilActif }
    $index += [pscustomobject]@{ id = $id; nom = $nom; description = $desc; profil = $profilFinal }
    Write-Index $index
}

# --- Affichage ----------------------------------------------------------------
function Show-Parties {
    $parties = @(Get-Parties)
    Write-Host ''
    Write-Host '   #  NOM                         QUAND                 TAILLE' -ForegroundColor Cyan
    Write-Host ('   ' + ('-' * 62)) -ForegroundColor DarkGray
    if (-not $parties) {
        Write-Host '   Aucune partie enregistree pour l''instant.' -ForegroundColor DarkGray
        return $parties
    }
    $md5Vif = Get-FileMD5 (Join-Path $saveRoot $mainFile)
    $actif  = Get-ProfilActif
    for ($i = 0; $i -lt $parties.Count; $i++) {
        $p = $parties[$i]
        $ligne = "   {0,-3} {1,-28} {2,-20} {3,8}" -f ($i + 1), (Short $p.Nom 28), $p.Date.ToString('dd/MM/yyyy HH:mm'), (Format-Taille $p.Octets)
        if ($md5Vif -and $p.MD5 -eq $md5Vif) {
            Write-Host ($ligne + '   <-- en cours') -ForegroundColor Green
        } else {
            Write-Host $ligne
        }
        if ($p.Description) {
            Write-Host ('        ' + (Short $p.Description 66)) -ForegroundColor DarkGray
        }
        if ($p.Profil) {
            if ($actif -and $p.Profil -ne $actif) {
                Write-Host ("        profil : {0}   (actif : {1})   - NE PAS charger avec l autre" -f $p.Profil, $actif) -ForegroundColor Yellow
            } else {
                Write-Host ("        profil : {0}" -f $p.Profil) -ForegroundColor DarkGray
            }
        }
    }
    return $parties
}

function Demander-Numero([int]$max) {
    $n = Read-Host "   Numero (1 a $max, 0 pour annuler)"
    $i = 0
    if ([int]::TryParse($n.Trim(), [ref]$i) -and $i -ge 1 -and $i -le $max) { return $i }
    return 0
}

# --- Actions ------------------------------------------------------------------
function Save-Partie([string]$nom, [string]$desc) {
    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $label = Clear-Libelle $nom
    $id = $stamp
    if ($label) { $id = "$stamp`_$label" }
    $dest = Join-Path $shotsDir $id
    if (Test-Path -LiteralPath $dest) { throw "Une partie porte deja ce nom : $id" }

    New-Item -ItemType Directory -Path $shotsDir -Force | Out-Null
    Copy-Item -LiteralPath $saveRoot -Destination $dest -Recurse -Force
    Set-Info $id $nom $desc (Get-ProfilActif)

    $stats = Get-DossierStats $dest
    Write-Host ''
    Write-Host "  Partie enregistree : $nom  ($(Format-Taille $stats.Octets))" -ForegroundColor Green
    return $id
}

function Restore-Partie($p, [switch]$DemanderConfirmation) {
    if (-not (Test-Path -LiteralPath $p.Chemin)) { throw "Partie introuvable : $($p.Id)" }

    if ($DemanderConfirmation) {
        Write-Host ''
        Write-Host "  Tu vas remplacer ta partie actuelle par :" -ForegroundColor Yellow
        Write-Host "     $($p.Nom)  -  $($p.Date.ToString('dd/MM/yyyy HH:mm'))  -  $(Format-Taille $p.Octets)"
        if ($p.Description) { Write-Host "     $($p.Description)" -ForegroundColor DarkGray }

        # Avertissement principal : le profil ne correspond pas.
        $actif = Get-ProfilActif
        $risque = $false
        if ($p.Profil -and $actif -and $p.Profil -ne $actif) {
            $risque = $true
            Write-Host ''
            Write-Host '  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!' -ForegroundColor Red
            Write-Host '  !  DANGER : PROFIL DIFFERENT                       !' -ForegroundColor Red
            Write-Host '  !                                                  !' -ForegroundColor Red
            Write-Host ("  !  Cette partie a ete creee avec le profil       !") -ForegroundColor Red
            Write-Host ("  !  {0}" -f $p.Profil.PadRight(46)) -ForegroundColor Red
            Write-Host ("  !  alors que le profil actif est {0}{1}!" -f $actif, (' ' * [Math]::Max(0, 30 - $actif.Length))) -ForegroundColor Red
            Write-Host '  !                                                  !' -ForegroundColor Red
            Write-Host '  !  Le jeu va BLOQUER A L ECRAN DE CHARGEMENT,     !' -ForegroundColor Red
            Write-Host '  !  sans aucun message.                              !' -ForegroundColor Red
            Write-Host '  !                                                  !' -ForegroundColor Red
            Write-Host '  !  Bascule d abord sur le bon profil avec le        !' -ForegroundColor Red
            Write-Host '  !  lanceur (touches 1 a 5), puis reviens ici.      !' -ForegroundColor Red
            Write-Host '  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!' -ForegroundColor Red
        } elseif ($p.Profil -and -not $actif) {
            Write-Host ''
            Write-Host "  (profil de la partie : $($p.Profil) - UKMM n'est pas installe)" -ForegroundColor Yellow
        }

        Write-Host ''
        $question = $(if ($risque) { '   Tu es SUR de charger quand meme ? tape OUI' }
                      else { '   Tu confirmes ? tape OUI' })
        $ok = (Read-Host $question).Trim()
        if ($ok.ToUpper() -ne 'OUI') { Write-Host '   Annule, rien n''a change.' -ForegroundColor DarkGray; return $false }
    }

    # On ne detruit jamais la partie en cours sans copie de securite.
    $backup = Save-Partie 'Securite avant chargement' ("Sauvegarde automatique de la partie qui etait chargee avant '$(($p.Nom))'.")

    $parent = Split-Path -Parent $saveRoot
    Remove-Item -LiteralPath $saveRoot -Recurse -Force
    Copy-Item -LiteralPath $p.Chemin -Destination $saveRoot -Recurse -Force

    # Verification : on compare l'empreinte du fichier principal. Si elle ne
    # correspond pas, la partie chargee n'est pas celle demandee.
    $md5Apres = Get-FileMD5 (Join-Path $saveRoot $mainFile)
    Write-Host ''
    Write-Host "  Partie chargee : $($p.Nom)" -ForegroundColor Green
    if ($md5Apres -eq $p.MD5 -and $md5Apres) {
        Write-Host "  Verifie : identique a la sauvegarde d'origine." -ForegroundColor Green
    } else {
        Write-Host "  ATTENTION : l'empreinte ne correspond pas." -ForegroundColor Red
        Write-Host "  Partie d'origine : $($p.MD5)" -ForegroundColor Red
        Write-Host "  Partie chargee  : $md5Apres" -ForegroundColor Red
    }
    Write-Host "  (ta partie d'avant est restee en : $backup)" -ForegroundColor DarkGray
    return $true
}

function Delete-Partie($p) {
    Remove-Item -LiteralPath $p.Chemin -Recurse -Force
    $index = @(Read-Index | Where-Object { $_.id -ne $p.Id })
    Write-Index $index
    Write-Host "  Partie supprimee : $($p.Nom)" -ForegroundColor Yellow
}

# --- Mode non interactif (pour les tests et les scripts) ---------------------
if ($NonInteractif) {
    Guard-Cemu
    Guard-Save
    switch ($Action.ToLower()) {
        'save' {
            if (-not $Nom) { $Nom = 'partie' }
            Save-Partie $Nom $Description | Out-Null
        }
        'restore' {
            if (-not $Nom) { throw "restore exige -Nom <id>" }
            $p = Get-Parties | Where-Object { $_.Id -eq $Nom } | Select-Object -First 1
            if (-not $p) { throw "Partie inconnue : $Nom" }
            Restore-Partie $p | Out-Null
        }
        'delete' {
            if (-not $Nom) { throw "delete exige -Nom <id>" }
            $p = Get-Parties | Where-Object { $_.Id -eq $Nom } | Select-Object -First 1
            if (-not $p) { throw "Partie inconnue : $Nom" }
            Delete-Partie $p
        }
        'rename' {
            if (-not $Nom) { throw "rename exige -Nom <id>" }
            $p = Get-Parties | Where-Object { $_.Id -eq $Nom } | Select-Object -First 1
            if (-not $p) { throw "Partie inconnue : $Nom" }
            Set-Info $p.Id $(if ($Description) { $Description } else { $p.Nom }) '' $p.Profil
        }
        'list' { @(Get-Parties) | ForEach-Object { Write-Host ("{0}|{1}|{2}|{3}|{4}|{5}" -f $_.Id, $_.Nom, $_.Description, $_.Octets, $_.MD5, $_.Profil) } }
        'status' {
            $md5 = Get-FileMD5 (Join-Path $saveRoot $mainFile)
            $actif = Get-ProfilActif
            Write-Host "VIF=$md5"
            Write-Host "PROFIL=$actif"
            @(Get-Parties) | ForEach-Object { Write-Host ("{0} {1} {2}" -f $_.Id, $(if ($_.MD5 -eq $md5) { 'EN_COURS' } else { '-' }), $_.Profil) }
        }
        default { throw "Action inconnue : $Action" }
    }
    exit 0
}

# --- Menu --------------------------------------------------------------------
Guard-Cemu
Guard-Save
if (-not (Test-Path -LiteralPath $shotsDir)) { New-Item -ItemType Directory -Path $shotsDir -Force | Out-Null }

while ($true) {
    Write-Host ''
    Write-Host '------------------------------------------------------------'
    Write-Host '   MES  PARTIES  -  Zelda Breath of the Wild'
    Write-Host '------------------------------------------------------------'
    $null = Show-Parties
    Write-Host ''
    Write-Host '   1. Enregistrer ma partie      (avec un nom + une description)'
    Write-Host '   2. CHARGER une partie'
    Write-Host '   3. Charger une partie ET jouer'
    Write-Host '   4. Changer le nom / la description'
    Write-Host '   5. Supprimer une partie'
    Write-Host '   0. Quitter'
    Write-Host ''
    $choix = (Read-Host '   Choix').Trim()

    switch ($choix) {
        '1' {
            Write-Host ''
            $nom = Read-Host '   Nom de la partie'
            if (-not $nom.Trim()) { Write-Host '   Annule.' -ForegroundColor DarkGray; break }
            Write-Host '   Description (facultatif, decris ta partie, ex: "avant le donjon"' -ForegroundColor DarkGray
            $desc = Read-Host '   Description'
            Save-Partie $nom.Trim() $desc.Trim() | Out-Null
        }
        '2' {
            $parties = @(Show-Parties)
            if (-not $parties) { break }
            $i = Demander-Numero $parties.Count
            if ($i -eq 0) { Write-Host '   Annule.' -ForegroundColor DarkGray; break }
            Restore-Partie $parties[$i - 1] -DemanderConfirmation | Out-Null
        }
        '3' {
            $parties = @(Show-Parties)
            if (-not $parties) { break }
            $i = Demander-Numero $parties.Count
            if ($i -eq 0) { Write-Host '   Annule.' -ForegroundColor DarkGray; break }
            if (Restore-Partie $parties[$i - 1] -DemanderConfirmation) {
                if (Test-Path -LiteralPath $cemu) {
                    Write-Host ''
                    Write-Host '  Cemu demarre...' -ForegroundColor Green
                    Start-Process -FilePath $cemu | Out-Null
                    Write-Host '  Laisse Cemu se charger, puis ouvre ta partie.' -ForegroundColor DarkGray
                    exit 0
                } else {
                    Write-Host "  Cemu est introuvable ($cemu) : ouvre-le a la main." -ForegroundColor Yellow
                    exit 0
                }
            }
        }
        '4' {
            $parties = @(Show-Parties)
            if (-not $parties) { break }
            $i = Demander-Numero $parties.Count
            if ($i -eq 0) { Write-Host '   Annule.' -ForegroundColor DarkGray; break }
            $p = $parties[$i - 1]
            Write-Host ''
            Write-Host "   Nom actuel : $($p.Nom)"
            $n2 = Read-Host '   Nouveau nom (laisse vide pour garder)'
            $d2 = Read-Host '   Nouvelle description (laisse vide pour garder)'
            # Un champ laisse vide = on garde la valeur actuelle. Pour effacer
            # volontairement une description, taper "VIDE".
            $nomFinal  = $(if ($n2.Trim()) { $n2.Trim() } else { $p.Nom })
            $descFinal = $(if ($d2.Trim() -eq 'VIDE') { '' }
                           elseif ($d2.Trim()) { $d2.Trim() }
                           else { $p.Description })
            Set-Info $p.Id $nomFinal $descFinal $p.Profil
            Write-Host ''
            Write-Host "  Enregistre : $nomFinal" -ForegroundColor Green
        }
        '5' {
            $parties = @(Show-Parties)
            if (-not $parties) { break }
            $i = Demander-Numero $parties.Count
            if ($i -eq 0) { Write-Host '   Annule.' -ForegroundColor DarkGray; break }
            $p = $parties[$i - 1]
            $ok = (Read-Host "   Supprimer definitivement '$($p.Nom)' ? (oui/non)").Trim()
            if ($ok.ToLower() -eq 'oui') { Delete-Partie $p }
            else { Write-Host '   Annule.' -ForegroundColor DarkGray }
        }
        '0' { exit 0 }
        default { Write-Host '   Choix invalide.' -ForegroundColor Red }
    }
}
