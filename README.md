# BOTW on Cemu — launcher, mod profiles, saves

[![Français](README.fr.md) ![English](README.md)

```
                                 .:.
                               __   ___    __    ___    __    ___
                              / /  / __ \  / /__  / __ \  / /  / __ \
                             / /  / /_/ /  / / _ \/ / / / / /  / /_/ /
                            / /__/ /  __/  / /_/ / /_/ / / /__/ /  __/
                            \____/_/   \_\/ ____/ \___/ \___/_____/  \_\

                       _   _         __     ___                 __
                      | | | |       / /    / __ \   __  __ ___  / /
                      | |_| |      / /    / / / /  / / / //_/  / /
                      |  _  |     / /___ / /_/ /  / /_/ / ,<   / /
                      |_| |_|    /_____/\____/  /_/\__,_/_/|_| /_/

                        B R E A T H   O F   T H E   W I L D
                        - - - - - - - - - - - - - - -
                        mods, profiles, saves, Cemu
```

A tool for running *The Legend of Zelda: Breath of the Wild* on **Cemu** with
mods. It installs mod combinations that **actually work**, deploys them, keeps
one save per mod set, and fixes the famous infinite loading screen.

No hand-tuning. No save ever moved without telling you.

---

## Contents

- [Installation](#installation)
- [Playing](#playing)
- [The command line tool](#the-command-line-tool)
- [Shipped profiles](#shipped-profiles)
- [One save per mod set](#-one-save-per-mod-set)
- [The four causes of the infinite loading screen](#the-four-causes-of-the-infinite-loading-screen)
- [The save manager](#the-save-manager)
- [Building your own profile](#building-your-own-profile)
- [Two players](#two-players)
- [Graphics](#graphics)
- [What the test bench found](#what-the-test-bench-found)
- [Tests](#tests)
- [Layout](#layout)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits-and-licenses)

---

## Installation

You need [Python 3.8+](https://www.python.org/downloads/). That is all: UKMM
and Cemu are **verified**, not silently installed.

```bash
git clone https://github.com/cameleonnbss/botw-cemu-lanceur.git
cd botw-cemu-lanceur
python installer.py
```

The installer, step by step:

1. **checks Python**;
2. **copies** the launcher and the tool to `%USERPROFILE%\Desktop\BOTW`;
3. **verifies every copied file by MD5** — a half-finished copy produces a
   launcher that looks like it works while running three-week-old code. That is
   the most invisible failure in the project;
4. **checks the files Windows executes**: `.bat`, `.cmd` and `.ps1` must be
   ASCII, BOM-less, with CRLF line endings. PowerShell 5.1 reads a BOM-less
   `.ps1` as ANSI, and a `.bat` in LF can stop on a random line;
5. **looks for UKMM and Cemu**, and says exactly what to install if missing.

Options:

| Option | Effect |
|---|---|
| `--dest D:\BOTW` | install somewhere other than the desktop |
| `--check` | verify without writing a single byte |
| `--shortcut` | add the launcher to Windows startup |

**Re-running `installer.py` destroys nothing.** No profile, no save, no mod is
touched: it is a reinstall on top of an install.

### What you also need

| Program | Where to put it |
|---|---|
| **[UKMM](https://github.com/SuperKEDITachi/ukmm)** | `ukmm.exe` in `%USERPROFILE%\Tools\UKMM\` |
| **[Cemu 2.x](https://cemu.info/)** | leave it in your `Downloads` folder |

The installer looks for both and tells you what is missing. It does not
download them for you: they are third-party software with their own licences.

---

## Playing

Double-click `Lanceur-BOTW.bat`.

| Key | Action |
|---|---|
| **`1`** | **My main save** — Second Wind + your cheats, *with its save* |
| **`2`** | **My FULL MODS save** — the 13 mods, *with its save* |
| `3` | Second Wind alone (profile `secondwind`) |
| `4` | **BOOST** — weapons, teleport, fast glide (the lightest) |
| `5` | Your mods alone — Linkle, islands, ancient weapons (profile `flo`) |
| `6` | **Pick your mods** — tick what you want |
| `7` | Load a save — with name and description |
| `8` | Two players |
| `9` | Profile panel |
| `a` | Graphics — *Light* or *Full* mode |
| `b` | **Check and repair** — says exactly what is wrong |
| `c` | **Test the profiles** — replays and verifies each one |
| `d` | Open UKMM |
| `e` | Open Cemu |
| `0` | Quit |

### The two everyday keys

One key is enough because it does all three things, in order:

1. it puts the current save **aside**;
2. it deploys the right mod set;
3. it puts **the matching save** back.

**The other save is never lost** — it is archived, and the other key picks it
back up.

> ⚠️ A save created with one mod set does not open with another. The game
> hangs on the loading screen **with no error message at all**. Changing mods
> without changing the save is exactly the bug that breaks your game — which is
> why these two keys do both, together.

If the requested profile is already active and the save belongs to it, nothing
is re-deployed: the tool counts the files and checks the deployment matches the
merge. Measured on the development machine, the same switch goes from
**34.4 s to 0.33 s**.

The two mod sets are **configurable** — this repository is universal, and
Second Wind is only the right choice if you installed it:

```bash
botw config set raccourcis '{"jeu_1":"boost","jeu_2":"sur"}'
```

---

## The command line tool

`botw` does everything the launcher does. The language is **your system's**:
French on a French machine, English anywhere else.

```bash
botw lang fr      # force French
botw lang en      # force English
botw lang auto    # back to automatic detection
```

| Command | What it does |
|---|---|
| `botw jeu <profile> --lancer` | switch mod set **and** save, then launch Cemu |
| `botw check` | will the game start? three lines, nothing changes |
| `botw fix -y` | remove the packs that block loading, redeploy |
| `botw doctor` | full health report |
| **`botw installmods <file\|url>`** | **install a mod from a `.zip` or a URL** |
| `botw mods list` | the local library |
| `botw mods search <word>` | search online |
| `botw mods download <id>` | download a mod without installing it |
| `botw catalog <name> --deploy` | rebuild a tested combination |
| `botw catalog` | list the combinations |
| `botw profile list` | profiles and their file counts |
| `botw profile verify <name>` | check a profile is complete |
| `botw newgame [revert]` | start clean without losing the save |
| `botw graphics` | fast mode or full graphics |
| `botw coop` | two controllers |
| `botw tools install-ukmm` | install UKMM |
| `botw ui` | the menu, with buttons |
| `botw readme en` | this documentation |

### `installmods` — the mod you already have

The local library only knows mods it has already seen, and the online search
no longer answers. So:

```bash
botw installmods "C:\Users\you\Downloads\MyMod.zip"   # a file on disk
botw installmods "https://example.org/mymod.zip"      # a link
botw installmods "MyMod.zip" -p sur                   # which profile
botw installmods --list                               # the library
```

The file is **copied** into the library, or **downloaded** if it is a link. Two
guard rails:

- a zip without `meta.yml` is refused, **and removed again** — otherwise
  `botw mods list` would offer it again every time;
- a link to a web page (HTML) is refused the same way.

The mod goes into `profile.yml`, so removing it later is trivial and fully
reversible.

---

## Shipped profiles

These are not lists of mods: they are combinations **really merged, deployed
and played**.

| Profile | Mods | Files | What it is |
|---|---|---|---|
| `sur` | 13 | 5 614 | Second Wind + everything else verified — **fail-safe** |
| `boost` | 10 | 1 371 | Hyrule Warriors weapons, lots of koroks, islands, instant portals |
| `flo` | 6 | 524 | the shortest one: koroks, weapons, islands, outfits |
| `secondwind` | 3 | 4 283 | Second Wind only: shrines redesigned, no fail |

`botw catalog` lists more, with their file counts.

### What is deliberately left out

Exactly one mod in the library is excluded: `Relics_of_the_Past`. It replaces
**249 files** UKMM cannot merge, so it simply erases what another mod
provided — and it breaks quests in progress. A mod that wins by erasing the
others is not a combination, it is a gamble.

The tool refuses it and explains why, rather than handing you a profile that
crashes three hours later.

---

## ⚠️ One save per mod set

**Loading a save created with a different mod set hangs the loading screen,
forever, with no error message.**

The game replays the save through the installed mod files. If the mod that
created it is gone — or if the set has changed — the read crashes silently.

So `botw jeu` does both, in this order:

1. the current save is **archived first**, labelled with the profile that can
   load it;
2. the new profile is deployed;
3. the save belonging to *that* profile is put back, if there is one.

If step 2 fails, the save is already out of the way. **The archive is a copy**:
the original is never moved.

`botw newgame revert <n>` puts any archived save back in place.

---

## The four causes of the infinite loading screen

All reported by `botw check`, all fixed by `botw fix`.

| Cause | Symptom | Fix |
|---|---|---|
| `Extended Memory` | game never finishes loading | the pack is removed |
| `HD Map and Icons` | **every** inventory icon invisible | `default = true` → `false` |
| `Draw Distance` | the weapon Link holds is invisible | settings dropped to safe values |
| a lone mod that overwrites nothing | the mod "works" but does nothing | reported by `botw profile verify` |

`HD Map and Icons` is the nastiest: its `rules.txt` says `default = true`, so
**Cemu re-enables it on every launch, even after you removed it from
`settings.xml`**. Removing the entry did nothing — the pack came back, and the
file looked perfectly clean. The tool now looks at what is **on disk**.

---

## The save manager

`Sauvegardes-BOTW.bat` — your saves with a **name** and a **description**,
because the game encrypts them: there is no way to read the date yourself.

- it shows, for each save, **which mods can load it**;
- if you load a save that was not created with the active profile, it
  **offers to switch mod sets by itself**, in the safe order;
- it archives before deploying, so a failure never costs you a save;
- it refuses a half-copied archive: an interrupted folder does exist, and
  putting it back would lose the save without a single message.

---

## Building your own profile

Two ways, and both ask you questions:

```bash
botw build                 # a few questions, then it builds and deploys
botw catalog combo --deploy
```

Launcher key **6** ("Pick your mods") goes further: a list of tick boxes with
**all** your mods, read from the `Mods\` folder. Type the numbers to tick or
untick, and UKMM merges, redeploys, and you play.

```bash
botw profile verify <profile>   # reports mods that overwrite nothing
```

---

## Two players

```bash
botw coop status     # how many controllers are configured
botw coop enable     # switch to two controllers
botw coop disable
```

Over a local connection, a VPN such as Radmin VPN keeps the session off the
public network. `botw coop radmin` prints the walkthrough.

---

## Graphics

```bash
botw graphics         # fast mode or full graphics
```

Two modes, because not everything can run at once: Cemu cannot execute shaders
at the same time as everything else. Fast mode keeps the game smooth; full mode
keeps shadows and draw distance.

---

## What the test bench found

`outils/matrice.py` replays each combination through the real chain — merge,
deploy, file-by-file verification. The reports are in [`docs/`](docs/).

In plain terms, it found that:

- two mods did **absolutely nothing**;
- UKMM did not merge **every** file;
- a mod could do nothing, **without raising a single error**;
- the most dangerous mod was one we would have kept.

---

## Tests

```bash
cd cli && python -m pytest tests -q               # 334 tests: the botw tool
python -m pytest outils/tests_installeur.py -q   # 18 tests: the installer
```

The installer is tested by installing it, in a temporary folder: a destination
typed with `/`, a `--check` that must not write, a copy tampered with after the
fact, and a second run that must rewrite nothing. `outils/verifier-doc-cli.py`
runs every command quoted in both READMEs through the real argument parser —
documentation that quotes a command which does not exist is worse than no
documentation.

The project takes Windows files very seriously: `.bat`, `.cmd` and `.ps1` must
be ASCII, BOM-less, CRLF. `outils/verifier-lanceur-menu.py` additionally checks
that **every menu key reaches a label that exists** — a `goto` to a missing
label raises no error: the window closes and the user sees nothing.

---

## Layout

```
installer.py         the installer, run it first
lanceur/             the .bat and .ps1 files
cli/                 the botw tool, its tests and its languages
outils/              verification and test-bench scripts
docs/                test campaign reports
```

---

## Troubleshooting

| Symptom | Cause | Solution |
|---|---|---|
| infinite loading | profile ≠ the save's profile | key `1` or `2`, or `botw jeu <profile>` |
| infinite loading | blocking pack | `botw check` then `botw fix` |
| invisible icons | `HD Map and Icons` | `botw fix` (reversible) |
| "unknown profile" | the profile was deleted | `botw catalog <name> --deploy` |
| empty names in game | language pack not deployed | `botw fix` |
| nothing opens on double-click | PowerShell 5.1 and encoding | `python installer.py` repairs everything |

---

## Credits and licenses

- *The Legend of Zelda: Breath of the Wild* — Nintendo. This repository
  **ships no game files**.
- [Cemu](https://cemu.info/) — Wii U emulator, GPLv3.
- [UKMM](https://github.com/SuperKEDITachi/ukmm) — mod manager.
- [BCML](https://github.com/RoadKill64/Bcml) — mod loader.
- Mods are distributed on GameBanana and belong to their authors.

See [LICENSE](LICENSE).
