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

# L'outil Python range ses archives dans Sauvegardes\NouvellePartie et note
# leur profil dans nouvelle-partie.json. Ce gestionnaire ne lisait que
# parties.json : ses archives n'etaient donc jamais listees, et le dossier
# NouvellePartie lui-meme - qui n'est PAS une partie, seulement un
# conteneur - apparaitrait comme si elle l'etait.
function Get-ArchivesBotw {
    $dossier = Join-Path $shotsDir 'NouvellePartie'
    if (-not (Test-Path -LiteralPath $dossier)) { return @() }
    $index = Join-Path $dossier 'nouvelle-partie.json'
    $liste = @()
    foreach ($d in (Get-ChildItem -LiteralPath $dossier -Directory -ErrorAction SilentlyContinue |
                    Sort-Object Name -Descending)) {
        $entry = $null
        if (Test-Path -LiteralPath $index) {
            try {
                $brut = [System.IO.File]::ReadAllText($index) | ConvertFrom-Json
                $nom  = [System.IO.Path]::GetFileName($d.FullName)
                foreach ($r in @($brut)) {
                    if ($r -and ([System.IO.Path]::GetFileName([string]$r.path)) -eq $nom) {
                        $entry = $r
                        break
                    }
                }
            } catch { $entry = $null }
        }
        if (-not (Test-EstUnePartie $d.FullName)) { continue }
        $stats = Get-DossierStats $d.FullName
        $liste += [pscustomobject]@{
            Id          = $d.Name
            Nom         = $(if ($entry -and $entry.nom) { [string]$entry.nom } else { $d.Name })
            Description = $(if ($entry) { 'archive automatique (jeu de mods ' + [string]$entry.profil + ')' } else { 'archive automatique' })
            Date        = $d.CreationTime
            Octets      = $stats.Octets
            Fichiers    = $stats.Fichiers
            MD5         = $stats.MD5
            Profil      = $(if ($entry) { [string]$entry.profil } else { '' })
            Source      = 'archive'
            Chemin      = $d.FullName
        }
    }
    return $liste
}

# Une vraie partie contient les deux sous-dossiers 'user' et 'meta'. Un
# dossier qui n'en a pas est un conteneur ou une copie de travail : le
# lister parmi les parties fait choisir au hasard une ligne qui ne peut pas
# se charger.
function Test-EstUnePartie([string]$chemin) {
    return ((Test-Path -LiteralPath (Join-Path $chemin 'user') -PathType Container) -and
            (Test-Path -LiteralPath (Join-Path $chemin 'meta') -PathType Container))
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
        if (-not (Test-EstUnePartie $d.FullName)) { continue }
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
            Source      = $(if ($entry) { 'partie' } else { 'copie' })
            Chemin      = $d.FullName
        }
    }
    $liste += @(Get-ArchivesBotw)
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
# Commencer une nouvelle partie avec un autre jeu de mods, sans perdre celle
# d'ici. L'outil `botw jeu` fait les deux d'un coup, dans le bon ordre, et
# c'est lui qu'on appelle : un simple `botw newgame` ici viderait l'emplacement
# SANS changer les mods, et Cemu proposerait alors une partie qui ne pourra
# plus jamais se charger.
function Nouvelle-Partie([string]$shotsDirLocal) {
    Write-Host ''
    Write-Host '   Nouvelle partie' -ForegroundColor Cyan
    Write-Host '   ---------------'
    Write-Host '   Une partie ne se charge qu''avec le jeu de mods qui l''a creee.'
    Write-Host '   Cette commande met la partie d''ici de cote, puis bascule les mods.'
    Write-Host ''
    $actif = Get-ProfilActif
    if ($actif) {
        Write-Host ("   Jeu de mods actif maintenant : {0}" -f $actif) -ForegroundColor White
    }
    Write-Host ''
    $profils = @()
    # UKMM range les profils dans %LOCALAPPDATA%\ukmm\wiiu\profiles. Ses
    # reglages, eux, sont dans %APPDATA%\ukmm\settings.yml : deux endroits
    # differents, et chercher les profils dans le second donne 'aucun'.
    foreach ($racine in @($env:LOCALAPPDATA, $env:APPDATA)) {
        if (-not $racine) { continue }
        $liste = Join-Path $racine 'ukmm\wiiu\profiles'
        if (-not (Test-Path -LiteralPath $liste)) {
            $liste = Join-Path $racine 'ukmm\profiles'
        }
        if (Test-Path -LiteralPath $liste) {
            $profils = @(Get-ChildItem -LiteralPath $liste -Directory -ErrorAction SilentlyContinue |
                         Sort-Object Name | Select-Object -ExpandProperty Name)
        }
        if ($profils) { break }
    }
    if (-not $profils) {
        Write-Host '   Aucun jeu de mods trouve. Lance d''abord "botw catalog list".' -ForegroundColor Yellow
        return
    }
    Write-Host '   Jeux de mods disponibles :'
    for ($i = 0; $i -lt $profils.Count; $i++) {
        $marque = ''
        if ($profils[$i] -eq $actif) { $marque = '  (actif)' }
        Write-Host ("     {0,-3} {1}{2}" -f ($i + 1), $profils[$i], $marque)
    }
    Write-Host ''
    $n = (Read-Host '   Numero du jeu de mods (0 pour annuler)').Trim()
    $j = 0
    if (-not ([int]::TryParse($n, [ref]$j) -and $j -ge 1 -and $j -le $profils.Count)) {
        Write-Host '   Annule.' -ForegroundColor DarkGray
        return
    }
    $cible = $profils[$j - 1]
    if ($cible -eq $actif) {
        Write-Host ''
        Write-Host ("   Tu es deja sur '{0}'. Choisis un autre jeu de mods." -f $cible) -ForegroundColor Yellow
        return
    }
    Write-Host ''
    Write-Host ("   La partie actuelle sera mise de cote pour '{0}' et pourra" -f $actif) -ForegroundColor White
    Write-Host ("   toujours etre remise. Le jeu '{0}' partira d'une partie neuve." -f $cible) -ForegroundColor White
    $ok = (Read-Host '   On y va ? (oui/non)').Trim()
    if ($ok.ToLower() -ne 'oui') { Write-Host '   Annule.' -ForegroundColor DarkGray; return }
    $botw = Join-Path $PSScriptRoot 'botw\botw.py'
    if (-not (Test-Path -LiteralPath $botw)) {
        Write-Host '   botw.py est introuvable - bascule impossible depuis ici.' -ForegroundColor Red
        return
    }
    & python $botw jeu $cible -y
    Write-Host ''
    Write-Host '   Cemu va proposer une partie neuve. Ta partie d''ici reste de cote.' -ForegroundColor Green
}

function Show-Parties {
    $parties = @(Get-Parties)
    Write-Host ''
    if (-not $parties) {
        Write-Host '   Aucune partie enregistree pour l''instant.' -ForegroundColor DarkGray
        return $parties
    }
    $md5Vif = Get-FileMD5 (Join-Path $saveRoot $mainFile)
    $actif  = Get-ProfilActif

    # Trois groupes, parce que trois statuts. Melanger une partie named avec
    # une copie de securite etait la source de la confusion : six lignes
    # pareilles a 6,3 Mo, dont deux seulement etaient des parties.
    $groupes = @(
        [pscustomobject]@{ Titre = 'VOS PARTIES';                Source = 'partie';  Couleur = 'Cyan' },
        [pscustomobject]@{ Titre = 'ARCHIVES AUTOMATIQUES';      Source = 'archive'; Couleur = 'Green' },
        [pscustomobject]@{ Titre = 'COPIES DE SECURITE';         Source = 'copie';   Couleur = 'DarkGray' }
    )
    $numero = 0
    # L'ordre AFFICHE et l'ordre du tableau renvoye doivent etre le meme. Avant,
    # on affichait par groupe mais on renvoyait le tableau brut : taper 3
    # chargeait la 6e, et supprimer une partie en supprimait une autre. Les
    # numeros sont donc distribues ici, dans l'ordre deffilement, et c'est ce
    # tableau qui est renvoye.
    $affiches = @()
    $marqueDejaPosee = $false
    foreach ($g in $groupes) {
        $dans = @($parties | Where-Object { $_.Source -eq $g.Source })
        if (-not $dans) { continue }
        Write-Host ''
        Write-Host ('   ' + $g.Titre) -ForegroundColor $g.Couleur
        Write-Host '   #  NOM                         QUAND                 TAILLE      MODS' -ForegroundColor DarkGray
        Write-Host ('   ' + ('-' * 74)) -ForegroundColor DarkGray
        foreach ($p in $dans) {
            $numero++
            $affiches += $p
            $mods = $(if ($p.Profil) { $p.Profil } else { '?' })
            $ligne = "   {0,-3} {1,-28} {2,-20} {3,8}  {4}" -f $numero, (Short $p.Nom 28), $p.Date.ToString('dd/MM/yyyy HH:mm'), (Format-Taille $p.Octets), $mods
            # Plusieurs archives peuvent etre identiques au contenu de la
            # partie en cours : elles sont interchangeables, mais en marquer
            # trois "en cours" donne l'illusion qu'il y a trois parties.
            if ($md5Vif -and -not $marqueDejaPosee -and $p.MD5 -eq $md5Vif) {
                $marqueDejaPosee = $true
                Write-Host ($ligne + '   <-- en cours') -ForegroundColor Green
            } else {
                Write-Host $ligne
            }
            if ($p.Description) {
                Write-Host ('        ' + (Short $p.Description 66)) -ForegroundColor DarkGray
            }
            if ($p.Profil) {
                if ($actif -and $p.Profil -ne $actif) {
                    Write-Host ("        cette partie a ete creee avec '{0}' ; le jeu de mods actif est '{1}'." -f $p.Profil, $actif) -ForegroundColor Yellow
                    Write-Host '        utilise "botw jeu <profil>" pour basculer les deux d un coup.' -ForegroundColor DarkYellow
                }
            }
        }
    }
    Write-Host ''
    Write-Host ('   ' + $numero + ' ligne(s). Le numero est celui affiche ci-dessus.') -ForegroundColor DarkGray
    return $affiches
}

function Demander-Numero([int]$max) {
    $n = Read-Host "   Numero (1 a $max, 0 pour annuler)"
    $i = 0
    if ([int]::TryParse($n.Trim(), [ref]$i) -and $i -ge 1 -and $i -le $max) { return $i }
    return 0
}

# --- Actions ------------------------------------------------------------------
function Get-ProfilPartieCourante {
    # Le profil avec lequel la partie de l'emplacement a ete ecrite, et non le
    # profil actif maintenant. Les deux differentent des que tu as change de jeu
    # de mods sans rejouer : etiquette une copie de securite avec le profil
    # ACTIF affirmait qu'elle se chargeait avec des mods qui ne peuvent pas la
    # lire. C'est l'erreur inverse de la verite, et elle fait basculer le jeu
    # vers le mauvais profil.
    #
    # Methode : la date du fichier de partie dit quand elle a ete ecrite ;
    # l'historique des deploiements dit quel etait le profil a ce moment-la.
    $slot = Join-Path (Join-Path $shotsDir 'NouvellePartie') 'slot.json'
    if (-not (Test-Path -LiteralPath $slot)) { return '' }
    $fichier = Join-Path $saveRoot $mainFile
    if (-not (Test-Path -LiteralPath $fichier)) { return '' }
    try {
        $notes = Get-Content -LiteralPath $slot -Raw -Encoding UTF8 | ConvertFrom-Json
        $ecrit = (Get-Item -LiteralPath $fichier).LastWriteTimeUtc
    } catch { return '' }
    $meilleur = ''
    $quandMeilleur = -1.0
    foreach ($n in @($notes)) {
        if (-not $n.profil) { continue }
        $q = 0.0
        if (-not [double]::TryParse([string]$n.quand, [ref]$q)) { continue }
        if ($q -le ($ecrit.AddSeconds(2).Ticks / 10000000) -and $q -gt $quandMeilleur) {
            $quandMeilleur = $q
            $meilleur = [string]$n.profil
        }
    }
    return $meilleur
}

function Save-Partie([string]$nom, [string]$desc) {
    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $label = Clear-Libelle $nom
    $id = $stamp
    if ($label) { $id = "$stamp`_$label" }
    $dest = Join-Path $shotsDir $id
    if (Test-Path -LiteralPath $dest) { throw "Une partie porte deja ce nom : $id" }

    # Rien a copier : pas de dossier vide. Une copie "Securite" a 0 Ko
    # occupe une ligne dans le gestionnaire sans rien sauvegarder, et donne
    # l'illusion qu'une partie a ete preservee.
    $avant = Test-EstUnePartie $saveRoot
    if (-not $avant) {
        Write-Host '  Rien a copier : l''emplacement de sauvegarde est vide.' -ForegroundColor DarkGray
        return ''
    }

    New-Item -ItemType Directory -Path $shotsDir -Force | Out-Null
    Copy-Item -LiteralPath $saveRoot -Destination $dest -Recurse -Force
    # Le profil de la partie COPIEE, pas le profil actif : c'est lui qui
    # indique ce qu'il faut deplier pour la recharger.
    $profilCopie = Get-ProfilPartieCourante
    if (-not $profilCopie) { $profilCopie = Get-ProfilActif }
    Set-Info $id $nom $desc $profilCopie

    $stats = Get-DossierStats $dest
    Write-Host ''
    Write-Host "  Partie enregistree : $nom  ($(Format-Taille $stats.Octets))" -ForegroundColor Green
    return $id
}

function Basculer-Jeu([string]$profil) {
    # Deploie le profil demande par l'outil `botw`. Le depot se fait AVANT la
    # copie de la partie visee : si le deploiement echoue, la partie d'origine
    # n'a pas encore ete touchee, et l'archive de securite existe deja.
    $botw = Join-Path $PSScriptRoot 'botw\botw.py'
    if (-not (Test-Path -LiteralPath $botw)) {
        Write-Host "  botw.py est introuvable : le jeu de mods n'a pas pu etre change." -ForegroundColor Red
        return $false
    }
    Write-Host ''
    Write-Host ("  Deploiement du jeu de mods '{0}'..." -f $profil) -ForegroundColor Cyan
    & python $botw deploy $profil --activate
    return ($LASTEXITCODE -eq 0)
}

function Restore-Partie($p, [switch]$DemanderConfirmation) {
    if (-not (Test-Path -LiteralPath $p.Chemin)) { throw "Partie introuvable : $($p.Id)" }

    $actif = Get-ProfilActif
    $basculer = $false

    if ($DemanderConfirmation) {
        Write-Host ''
        Write-Host "  Tu vas remplacer ta partie actuelle par :" -ForegroundColor Yellow
        Write-Host "     $($p.Nom)  -  $($p.Date.ToString('dd/MM/yyyy HH:mm'))  -  $(Format-Taille $p.Octets)"
        if ($p.Description) { Write-Host "     $($p.Description)" -ForegroundColor DarkGray }

        if ($p.Profil -and $actif -and $p.Profil -ne $actif) {
            # Le cas le plus courant : on propose la solution avant de
            # reprocher le probleme. Avertir sans proposer la sortie obligeait
            # a sortir du menu, changer de profil, revenir, rejouer la liste -
            # et le profil actif, lui, restait often le mauvais.
            Write-Host ''
            Write-Host '  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!' -ForegroundColor Red
            Write-Host '  !  ATTENTION : JEU DE MODS DIFFERENT                 !' -ForegroundColor Red
            Write-Host '  !                                                  !' -ForegroundColor Red
            Write-Host '  !  Cette partie a ete creee avec le jeu de mods     !' -ForegroundColor Red
            Write-Host ("  !  {0}" -f $p.Profil.PadRight(46)) -ForegroundColor Red
            Write-Host ("  !  alors que le jeu de mods actif est {0}{1}!" -f $actif, (' ' * [Math]::Max(0, 30 - $actif.Length))) -ForegroundColor Red
            Write-Host '  !                                                  !' -ForegroundColor Red
            Write-Host '  !  Le jeu plante ou bloque sur l''ecran de            !' -ForegroundColor Red
            Write-Host '  !  chargement, sans aucun message.                   !' -ForegroundColor Red
            Write-Host '  !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!' -ForegroundColor Red
            Write-Host ''
            Write-Host ("  On peut changer le jeu de mods sur '{0}'" -f $p.Profil) -ForegroundColor White
            Write-Host '  et charger ta partie aussitot (ton jeu de mods' -ForegroundColor DarkGray
            Write-Host '  actif est memorise pour y revenir).' -ForegroundColor DarkGray
            Write-Host ''
            $rep = (Read-Host ("   Basculer sur '{0}' et charger ? (oui/non)" -f $p.Profil)).Trim().ToLower()
            if ($rep -eq 'oui') {
                $basculer = $true
            } else {
                Write-Host '   D accord. On charge sans changer le jeu de mods.' -ForegroundColor Yellow
                $ok = (Read-Host '   Tu es SUR de charger quand meme ? tape OUI').Trim()
                if ($ok.ToUpper() -ne 'OUI') { Write-Host '   Annule, rien n''a change.' -ForegroundColor DarkGray; return $false }
            }
        } elseif ($p.Profil -and -not $actif) {
            Write-Host ''
            Write-Host "  (profil de la partie : $($p.Profil) - UKMM n'est pas installe)" -ForegroundColor Yellow
            Write-Host ''
            $ok = (Read-Host '   Tu confirmes ? tape OUI').Trim()
            if ($ok.ToUpper() -ne 'OUI') { Write-Host '   Annule, rien n''a change.' -ForegroundColor DarkGray; return $false }
        } else {
            Write-Host ''
            $ok = (Read-Host '   Tu confirmes ? tape OUI').Trim()
            if ($ok.ToUpper() -ne 'OUI') { Write-Host '   Annule, rien n''a change.' -ForegroundColor DarkGray; return $false }
        }
    }

    # On ne detruit jamais la partie en cours sans copie de securite.
    $backup = Save-Partie 'Securite avant chargement' ("Sauvegarde automatique de la partie qui etait chargee avant '$($p.Nom)'.")

    # Le jeu de mods d'abord, la partie ensuite. L'ordre inverse deployerait la
    # partie dans un profil qui n'est pas encore en place.
    if ($basculer -and -not (Basculer-Jeu $p.Profil)) {
        Write-Host ''
        Write-Host '  Le jeu de mods n''a pas pu etre change. Ta partie n''a pas ete remplacee.' -ForegroundColor Red
        return $false
    }

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
    Write-Host '   6. Nouvelle partie avec d''autres mods'
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
        '6' { Nouvelle-Partie $shotsDir }
        '0' { exit 0 }
        default { Write-Host '   Choix invalide.' -ForegroundColor Red }
    }
}
