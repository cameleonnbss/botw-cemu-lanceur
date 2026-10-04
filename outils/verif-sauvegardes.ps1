# Verifie que Sauvegardes-BOTW.ps1 compile, affiche la liste reelle des
# parties, et surtout que le NUMERO AFFICHE designe bien la partie qu'on
# renvoie quand l'utilisateur tape ce numero.
#
# Fichier en ASCII pur, SANS BOM, et aucun chemin en dur : ce script est lu
# par PowerShell 5.1, qui interprete un .ps1 sans BOM en ANSI. Un accent dans
# le chemin - y compris le nom d'utilisateur - devient illisible.
param([string]$Cible)
$ErrorActionPreference = 'Stop'
$fichier = if ($Cible) { $Cible } else { Join-Path $env:USERPROFILE 'Desktop\BOTW\Sauvegardes-BOTW.ps1' }
if (-not (Test-Path -LiteralPath $fichier)) {
    Write-Host ('INTROUVABLE : ' + $fichier) -ForegroundColor Red
    exit 1
}

$erreurs = $null
[void][System.Management.Automation.Language.Parser]::ParseFile(
    $fichier, [ref]$null, [ref]$erreurs)
if ($erreurs) {
    Write-Host 'SYNTAXE : ERREURS' -ForegroundColor Red
    $erreurs | ForEach-Object { Write-Host ('  ' + $_.Message) }
    exit 1
}
Write-Host 'SYNTAXE : OK' -ForegroundColor Green
Write-Host ''

# On charge le script sans lancer le menu interactif : Read-Host sur une
# entree fermee rend la main, ce qui suffit a definir toutes les fonctions.
#
# $PSScriptRoot n'existe que dans un fichier .ps1 execute : dans un
# scriptblock cree a la main il est vide, et $shotsDir = Join-Path
# $PSScriptRoot ... echoue aussitot avec "chaine vide". C'est pour cela que ce
# fichier de verification ne demarrait meme pas. On remplace donc la variable
# par le vrai chemin avant de charger le code.
$racine = Split-Path -Parent $fichier
$texte = [System.IO.File]::ReadAllText($fichier)
$texte = $texte.Replace('$PSScriptRoot', "'" + $racine + "'")

# On ne charge que les FONCTIONS. Tout ce qui suit le mode non interactif est
# coupe : le menu attend indefiniment derriere un Read-Host sans personne, et le
# fichier de verification se mettait a boucler la-dessus au lieu de rendre la
# main. Pas de 'exit' ajoute non plus : dans un script charge par
# [scriptblock]::Create, un exit tuerait aussi ce verificateur-la.
$marqueur = '# --- Mode non interactif'
$pos = $texte.IndexOf($marqueur)
if ($pos -lt 0) {
    Write-Host ('MARQUEUR INTROUVABLE : ' + $marqueur) -ForegroundColor Red
    exit 1
}
$texte = $texte.Substring(0, $pos)
. ([scriptblock]::Create($texte)) 2>$null

# ---------------------------------------------------------------------------
# 1. ORDRE : le numero affiche doit selectionner la partie affichee
# ---------------------------------------------------------------------------
# C'est l'invariant qui manquait. La liste s'affiche par groupe (vos parties,
# archives, copies) mais le tableau renvoye pouvait garder l'ordre brut : taper
# 3 chargeait alors la 6e, et l'option "supprimer" effacait la meme ligne
# decalee. On capture ce que Show-Parties ECRIT et ce qu'il RENVOIE, puis on
# compare numero par numero.
#
# Write-Host n'ecrit PAS dans un flux capturable en PowerShell 5.1 : le
# famous "6>&1" ne renvoie rien, il est ne vide. Start-Transcript, lui, voit
# tout ce qui va a l'ecran. C'est la seule facon de savoir reellement ce que
# l'utilisateur a lu.
$trace = Join-Path $env:TEMP 'verif-sauvegardes-trace.txt'
Start-Transcript -Path $trace -Force | Out-Null
$objets = @(Show-Parties)
Stop-Transcript | Out-Null
$lignes = @()
if (Test-Path -LiteralPath $trace) {
    $lignes = @(Get-Content -LiteralPath $trace -Encoding UTF8)
    Remove-Item -LiteralPath $trace -Force -ErrorAction SilentlyContinue
}
if ($lignes.Count -eq 0) {
    Write-Host 'AFFICHAGE : rien n a pu etre capture (transcription vide)' -ForegroundColor Red
    exit 1
}

$affiches = @()
foreach ($l in $lignes) {
    # On s'appuie sur la colonne date pour borner le nom : un nom de 28
    # caracteres n'a pas de remplissage, et une coupe au premier espace
    # multiple avalerait la date dans le nom.
    $m = [regex]::Match($l, '^\s+(\d+)\s+(.{1,28}?)\s+\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}')
    if ($m.Success) {
        $affiches += [pscustomobject]@{
            Numero = [int]$m.Groups[1].Value
            Nom    = $m.Groups[2].Value.Trim()
        }
    }
}

Write-Host 'LISTE REELLE TELLE QUE L''UTILISATEUR LA VOIT' -ForegroundColor Cyan
foreach ($a in $affiches) {
    Write-Host ("  {0,-3} {1}" -f $a.Numero, $a.Nom)
}
Write-Host ''

$problemes = 0

if ($affiches.Count -ne $objets.Count) {
    Write-Host ("ORDRE : {0} ligne(s) affichee(s), {1} objet(s) renvoye(s)" -f `
        $affiches.Count, $objets.Count) -ForegroundColor Red
    $problemes++
} else {
    Write-Host ("ORDRE : {0} ligne(s), meme nombre renvoye" -f $affiches.Count) -ForegroundColor Green
}

for ($i = 0; $i -lt $affiches.Count; $i++) {
    $n = $affiches[$i].Numero
    if ($n -ne ($i + 1)) {
        Write-Host ("  ORDRE : ligne {0} numerotee {1}" -f ($i + 1), $n) -ForegroundColor Red
        $problemes++
        continue
    }
    # L'ecran tronque volontairement les noms longs a 28 caracteres : on
    # compare donc avec la meme troncature, sinon un nom affiche serait pris
    # pour une faute alors que c'est le retour qui compte.
    $rendu = Short ([string]$objets[$i].Nom) 28
    $vu = [string]$affiches[$i].Nom
    if ($vu -ne $rendu) {
        Write-Host ("  ORDRE : numero {0} affiche '{1}' mais renvoie '{2}'" -f $n, $vu, $rendu) -ForegroundColor Red
        $problemes++
    }
}

if ($problemes -eq 0) {
    Write-Host '  chaque numero renvoie bien la ligne affichee a cote' -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# 2. MARQUAGE : une seule ligne "en cours" a la fois
# ---------------------------------------------------------------------------
$enCours = @($lignes | Where-Object { $_ -like '*<-- en cours*' })
if ($enCours.Count -gt 1) {
    Write-Host ("MARQUAGE : {0} ligne(s) 'en cours' en meme temps" -f $enCours.Count) -ForegroundColor Red
    $problemes++
} else {
    Write-Host ("MARQUAGE : {0} ligne(s) 'en cours'" -f $enCours.Count) -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# 3. ETIQUETTE : le profil doit decrire la partie, pas le profil actif
# ---------------------------------------------------------------------------
# Une copie de securite nota le profil ACTIF au moment de la copie. Une
# sauvegarde secondwind archivee pendant que 'sur' etait actif etait donc
# annoncee 'sur' : l'erreur inverse de la verite, et de quoi faire basculer le
# jeu vers le mauvais profil au chargement suivant. On recoupe la date du
# fichier de partie avec l'historique des deploiements.
$actif = Get-ProfilActif
$notes = @()
$slot = Join-Path (Join-Path $shotsDir 'NouvellePartie') 'slot.json'
if (Test-Path -LiteralPath $slot) {
    try { $notes = @(Get-Content -LiteralPath $slot -Raw -Encoding UTF8 | ConvertFrom-Json) }
    catch { $notes = @() }
}
$archives = @(Get-Parties | Where-Object { $_.Source -eq 'archive' })
$examinees = 0
$verifiees = 0
if ($notes.Count -gt 0) {
    foreach ($p in $archives) {
        $fich = Join-Path $p.Chemin 'user\80000001\0\game_data.sav'
        if (-not (Test-Path -LiteralPath $fich)) { continue }
        $examinees++
        try { $ecrit = (Get-Item -LiteralPath $fich).LastWriteTimeUtc }
        catch { continue }
        $candidat = ''
        $quandMax = -1.0
        foreach ($n in @($notes)) {
            if (-not $n.profil) { continue }
            $q = 0.0
            if (-not [double]::TryParse([string]$n.quand, [ref]$q)) { continue }
            if ($q -le ($ecrit.AddSeconds(2).Ticks / 10000000) -and $q -gt $quandMax) {
                $quandMax = $q
                $candidat = [string]$n.profil
            }
        }
        if ($candidat -and $p.Profil) {
            $verifiees++
            if ($p.Profil -ne $candidat) {
                Write-Host ("  ETIQUETTE : '{0}' dit {1} mais la partie vient de {2}" -f `
                    $p.Nom, $p.Profil, $candidat) -ForegroundColor Red
                $problemes++
            }
        }
    }
}
Write-Host ("ETIQUETTES : {0} archive(s) examinee(s), {1} recoupable(s) avec l'historique" -f `
    $examinees, $verifiees) -ForegroundColor Green
if ($notes.Count -eq 0) {
    Write-Host '  pas d historique de deploiements (slot.json absent) : rien a recouper' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host ('PROFIL ACTIF : ' + $actif) -ForegroundColor Yellow
Write-Host ''
if ($problemes -gt 0) {
    Write-Host ("{0} probleme(s)." -f $problemes) -ForegroundColor Red
    exit 1
}
Write-Host 'TOUT EST CONFORME.' -ForegroundColor Green
exit 0