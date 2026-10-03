"""Les outils externes : UKMM sur Windows, BCML dans WSL.

Pourquoi deux mecanismes si differents ?

UKMM est l'outil qu'on utilise vraiment : c'est un exe Windows, publie sur
GitHub avec un zip par version. On telecharge, on verifie le SHA-256 publie
a cote, on decompose dans %USERPROFILE%\\Tools\\UKMM. Rien de plus.

BCML est le predecessor de UKMM. Il n'existe plus de binaire Windows : il
tourne sous Linux. D'ou WSL. Et comme on ne peut pas touche au Python du
systeme WSL sans sudo, on installe un CPython autonome (python-build-standalone)
dans un prefixe utilisateur, puis bcml dans un venv isole. C'est exactement
la recette qui a ete verifiee sur cette machine, elle est donc reprise telle
quelle - elle est idempotente : relancer ne casse rien.
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

from . import config, i18n

_ = i18n._

UKMM_REPO = "NiceneNerd/UKMM"
UKMM_ASSET = "ukmm-x86_64-pc-windows-msvc.zip"
UKMM_SHA_ASSET = UKMM_ASSET + ".sha256"
CPYTHON_VERSION = "3.11"
CPYTHON_API = ("https://api.github.com/repos/astral-sh/python-build-standalone"
               "/releases/latest")
BCML_VENV = "$HOME/.local/bcml-venv"
BCML_BIN = BCML_VENV + "/bin/bcml"

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


# --- reseau ------------------------------------------------------------------

def _get_json(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _download(url, dest, timeout=900, progress=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    md5 = hashlib.md5()
    size = 0
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as out:
        total = int(r.headers.get("Content-Length") or 0)
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            md5.update(chunk)
            size += len(chunk)
            if progress and total:
                progress(size, total)
    return size, md5.hexdigest()


def _sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# --- UKMM -------------------------------------------------------------------

def ukmm_version(folder=None):
    """Version d'UKMM lue dans son CHANGELOG.md ('## [0.17.1] 2026-07-01')."""
    folder = folder or os.path.dirname(config.ukmm_exe())
    try:
        with io.open(os.path.join(folder, "CHANGELOG.md"), encoding="utf-8",
                     errors="replace") as f:
            head = f.read(4000)
    except OSError:
        return ""
    m = re.search(r"^## \[?v?([0-9][0-9.\-]*)", head, re.M)
    return m.group(1) if m else ""


def ukmm_state(cfg=None):
    exe = config.ukmm_exe(cfg)
    return {"name": "UKMM",
            "installed": os.path.isfile(exe),
            "path": exe,
            "version": ukmm_version(os.path.dirname(exe)) if os.path.isfile(exe) else "",
            "where": _("tool.where.native")}


def latest_ukmm():
    """{version, url, sha256, size} de la derniere version publiee."""
    rel = _get_json("https://api.github.com/repos/%s/releases/latest" % UKMM_REPO)
    assets = {a["name"]: a for a in rel.get("assets", [])}
    zip_asset = assets.get(UKMM_ASSET)
    if not zip_asset:
        raise RuntimeError(_("tool.ukmm.no_asset", name=UKMM_ASSET))
    sha = ""
    sha_asset = assets.get(UKMM_SHA_ASSET)
    if sha_asset:
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(sha_asset["browser_download_url"],
                                           headers={"User-Agent": USER_AGENT}),
                    timeout=60) as r:
                m = re.search(r"([0-9a-fA-F]{64})", r.read().decode("utf-8", "replace"))
            sha = m.group(1).lower() if m else ""
        except Exception:                                      # noqa: BLE001
            sha = ""
    return {"version": (rel.get("tag_name") or "").lstrip("v"),
            "url": zip_asset["browser_download_url"],
            "sha256": sha,
            "size": zip_asset.get("size", 0)}


def install_ukmm(force=False, cfg=None):
    """Telecharge et installe UKMM dans %USERPROFILE%\\Tools\\UKMM.

    Un zip corrompu s'arretait a moitie et laissait un UKMM inutilisable.
    On verifie donc le SHA-256 publie par l'auteur avant de decompresser, et on
    extrait dans un dossier temporaire avant de remplacer l'ancien.
    """
    exe = config.ukmm_exe(cfg)
    folder = os.path.dirname(exe)
    if os.path.isfile(exe) and not force:
        i18n.ok(_("tool.ukmm.present", v=ukmm_version(folder) or "?", p=exe))
        return False
    try:
        info = latest_ukmm()
    except Exception as e:                                     # noqa: BLE001
        i18n.ko(_("tool.ukmm.net_error", e=e))
        return False
    i18n.info(_("tool.ukmm.download", v=info["version"],
                size=mods_human(info["size"])))
    tmp = tempfile.mkdtemp(prefix="botw-ukmm-")
    try:
        zip_path = os.path.join(tmp, UKMM_ASSET)
        _download(info["url"], zip_path)
        if info["sha256"]:
            got = _sha256(zip_path)
            if got != info["sha256"]:
                i18n.ko(_("tool.ukmm.sha_bad", a=got[:16], b=info["sha256"][:16]))
                return False
            i18n.ok(_("tool.ukmm.sha_ok"))
        else:
            i18n.warn(_("tool.ukmm.no_sha"))
        extract = os.path.join(tmp, "x")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract)
        root = extract
        for base, _d, files in os.walk(extract):
            if "ukmm.exe" in files:
                root = base
                break
        backup = None
        if os.path.isdir(folder):
            backup = folder + ".old-%d" % int(os.getpid())
            os.replace(folder, backup)
        try:
            shutil.move(root, folder)
        except OSError:
            if backup and os.path.isdir(backup):
                os.replace(backup, folder)
            raise
        if backup and os.path.isdir(backup):
            shutil.rmtree(backup, ignore_errors=True)
        if cfg is not None:
            cfg["ukmm_exe"] = os.path.join(folder, "ukmm.exe")
            config.save(cfg)
        i18n.ok(_("tool.ukmm.installed", v=ukmm_version(folder) or info["version"],
                  p=folder))
        return True
    except Exception as e:                                     # noqa: BLE001
        i18n.ko(_("tool.ukmm.failed", e=e))
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def open_ukmm():
    exe = config.ukmm_exe()
    if not os.path.isfile(exe):
        i18n.ko(_("doctor.ukmm.missing", path=exe))
        return False
    subprocess.Popen([exe], cwd=os.path.dirname(exe))
    i18n.ok(_("tool.ukmm.open", p=exe))
    return True


# --- BCML (sous WSL) --------------------------------------------------------

def wsl_distros(timeout=30):
    """Distributions WSL installees."""
    try:
        r = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return []
    raw = (r.stdout or b"")
    text = raw.decode("utf-16-le", "replace") if b"\x00" in raw else raw.decode("utf-8", "replace")
    out = []
    for line in text.replace("\x00", "\n").splitlines():
        s = line.strip()
        if s and s not in out:
            out.append(s)
    return out


def _wsl(cmd, distro=None, timeout=180):
    args = ["wsl.exe"]
    if distro:
        args += ["-d", distro]
    args += ["--", "bash", "-lc", cmd]
    return subprocess.run(args, capture_output=True, text=True, errors="replace",
                          timeout=timeout)


def bcml_state(distro=None):
    """Detecte BCML. Ne lance pas le binaire : le demarrer est lent (Qt)."""
    exe = config.ukmm_exe()
    distros = wsl_distros()
    if distro:
        distros = [d for d in distros if d == distro] or [distro]
    for d in distros:
        try:
            r = _wsl("test -x %s && echo yes || echo no" % BCML_BIN, d, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if "yes" in (r.stdout or ""):
            return {"name": "BCML", "installed": True, "path": BCML_BIN,
                    "version": "", "where": _("tool.where.wsl", distro=d),
                    "distro": d, "exe": exe}
    return {"name": "BCML", "installed": False, "path": BCML_BIN, "version": "",
            "where": _("tool.where.none"), "distro": distros[0] if distros else "",
            "exe": exe}


_BCML_SCRIPT = r"""
set -e
PREFIX="$HOME/.local/python311"
VENV="$HOME/.local/bcml-venv"
API="https://api.github.com/repos/astral-sh/python-build-standalone/releases/latest"

if [ ! -x "$VENV/bin/bcml" ]; then
  echo "== CPython 3.11 autonome (sans sudo) =="
  if [ ! -x "$PREFIX/bin/python3.11" ]; then
    URL=$(curl -sSL --max-time 120 "$API" \
      | grep -oE 'https://[^"]*cpython-3\.11\.[0-9]+\+[0-9]+-x86_64-unknown-linux-gnu-install_only\.tar\.gz' \
      | head -1)
    if [ -z "$URL" ]; then echo "ECHEC: CPython introuvable"; exit 1; fi
    echo "telechargement $URL"
    mkdir -p "$HOME/.cache/cpython"
    curl -sSL --max-time 900 -o "$HOME/.cache/cpython/cpython311.tar.gz" "$URL"
    mkdir -p "$PREFIX"
    tar -xzf "$HOME/.cache/cpython/cpython311.tar.gz" -C "$PREFIX" --strip-components=1
  fi
  echo "== environnement virtuel =="
  [ -x "$VENV/bin/python" ] || "$PREFIX/bin/python3.11" -m venv "$VENV"
  "$VENV/bin/python" -m pip install --quiet --upgrade pip
  echo "== installation de bcml =="
  "$VENV/bin/python" -m pip install --quiet bcml
fi

if [ -x "$VENV/bin/bcml" ]; then
  echo "BCML_OK $VENV/bin/bcml"
  QT_QPA_PLATFORM=offscreen "$VENV/bin/bcml" version 2>&1 | head -3 || true
else
  echo "ECHEC: bcml absent"
  exit 1
fi
"""


def install_bcml(distro=None):
    """Installe BCML dans WSL (meme recette que celle verifiee a la main)."""
    if not wsl_distros():
        i18n.ko(_("tool.bcml.no_wsl"))
        return False
    state = bcml_state(distro)
    if state["installed"]:
        i18n.ok(_("tool.bcml.ok", d=BCML_BIN))
        return False
    target = distro or state.get("distro") or ""
    i18n.info(_("tool.bcml.start", d=target))
    try:
        r = _wsl(_BCML_SCRIPT, target, timeout=900)
    except subprocess.TimeoutExpired:
        i18n.ko(_("tool.bcml.timeout"))
        return False
    except OSError as e:
        i18n.ko(_("tool.bcml.failed", e=e))
        return False
    out = (r.stdout or "") + (r.stderr or "")
    if "BCML_OK" in out:
        for line in out.splitlines():
            if line.strip():
                i18n.info(line.strip())
        i18n.ok(_("tool.bcml.installed", d=BCML_BIN))
        return True
    i18n.ko(_("tool.bcml.failed", e=out.strip()[-500:] or _("tool.bcml.unknown")))
    return False


# --- rapport -----------------------------------------------------------------

def mods_human(n):
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f TB" % n


def report(cfg=None):
    i18n.title(_("tool.list"))
    st = [ukmm_state(cfg)]
    try:
        st.append(bcml_state())
    except Exception:                                          # noqa: BLE001
        st.append({"name": "BCML", "installed": False, "version": "", "path": "",
                   "where": _("tool.where.unknown")})
    rows = []
    for s in st:
        if s["installed"]:
            msg = _("tool.state.ok", v=s["version"] or "?", p=s["path"])
            i18n.ok("%-6s %s" % (s["name"], msg))
        else:
            i18n.ko("%-6s %s" % (s["name"], _("tool.state.ko", p=s["path"])))
        rows.append((s["name"], s["installed"], s["where"]))
    cemu = config.cemu_exe(cfg)
    if cemu:
        i18n.ok("%-6s %s" % ("Cemu", cemu))
    else:
        i18n.ko("%-6s %s" % ("Cemu", _("tool.cemu.missing")))
        rows.append(("Cemu", False, ""))
    return rows
