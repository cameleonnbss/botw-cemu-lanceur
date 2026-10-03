# botw — Breath of the Wild on Cemu

Everything around *The Legend of Zelda: Breath of the Wild* running under
Cemu on Windows: mods, profiles, saves, two-player, and a health check that
tells you what is actually wrong instead of leaving you guessing.

**English is the default language.** French is one command away:
`botw lang fr`. The same command with `en` switches back.

```bat
botw                 :: opens the menu
botw doctor          :: full health check
botw deploy sur      :: switch the game to the "sans echec" profile
botw catalog         :: the mod combinations proven to work
botw readme fr       :: this document, in French
```

---

## 1. Install

You need three things. `botw tools` installs the first two for you.

| Tool | What it does | Installed by |
|---|---|---|
| Python 3.9+ | runs this tool | you |
| [UKMM](https://github.com/NiceneNerd/UKMM) | merges the mods | `botw tools install-ukmm` |
| Cemu 2.x | runs the game | you (and your own game dump) |
| BCML | *optional*, the old mod manager, under WSL | `botw tools install-bcml` |

Drop the folder anywhere. There is nothing to compile, no installer, no
registry. Open a terminal in the folder and run:

```bat
botw.bat doctor
```

If the menu opens and the health check is green, everything is in place.

---

## 2. The menu

Run `botw` with no arguments. Every command below is one button.

```
  1) Play a game with a profile
  2) Mods
  3) Profiles
  4) Two players
  5) External tools
  6) Health check
  7) Read this documentation
  8) Change the language
  N) start a NEW GAME (keeps the current one)
  F) Read the documentation in FRENCH
  Q) Quit
```

---

## 3. Mods

### The library

Mods live in `Desktop\BOTW\Mods`. UKMM keeps its own copy in
`%LOCALAPPDATA%\ukmm\wiiu\mods`; both are listed, and a mod found only in
one is marked.

```bat
botw mods list                  :: everything you own, and where it is used
botw mods install -p sur "Relics of the Past.zip"
botw mods uninstall -p sur "Relics of the Past.zip"
```

You can name a mod by its file name, by its display name, or by any part of
either — `relics`, `Relics_of_the_Past.zip` and `Relics of the Past` all find
the same file.

### Downloading

```bat
botw mods search wind           :: search the library, then GameBanana
botw mods download 12345        :: download mod #12345 and check its MD5
botw mods download 12345 -i -p sur   :: download it, then install it
```

Every download is checked against the MD5 GameBanana publishes. A corrupted
file is refused before it ever reaches the merge — otherwise it is discovered
hours later, as a crash with no explanation.

### Why `uninstall` edits a file instead of calling UKMM

`ukmm uninstall` writes into the **active** profile and deletes the zip from
the mod store. That is friendlier than doing nothing, but it quietly breaks
your other profiles. `botw mods uninstall` removes the mod from
`profile.yml` instead: local, reversible, and it cannot touch another profile.

---

## 4. Profiles

A profile is a set of mods plus the order they are merged in. That order is
not cosmetic — see §6.

```bat
botw profile list
botw profile show sur
botw profile use sur
botw profile verify sur         :: every file each mod declares is really there
botw profile create speedrun "mod1.zip" "mod2.zip"
botw profile delete speedrun
```

### Verified combinations

The test bench merged, deployed and checked **123 mod combinations, file by
file, with zero failures**: each mod alone, every pair, Second Wind with
each other mod, then the five launcher profiles. Those results are a
catalog, not a wish list:

```bat
botw catalog                    :: the list, with what each one contains
botw catalog sur --as hardcore --deploy
```

| Profile | Mods | Files | What it is |
|---|---|---|---|
| `boost` | 10 | 1371 | the default: weapons, koroks, islands, portals, champion gear |
| `sur` | 13 | 5614 | everything that shortens the game; no *Relics of the Past* |
| `combo` | 9 | 4780 | Second Wind + weapons, koroks, islands, gear |
| `flo` | 6 | 524 | the shortest: no map expansion, no Second Wind |
| `secondwind` | 3 | 4283 | Second Wind only |

---

## 5. Deploying

`botw deploy <profile>` runs the whole chain:

```
active profile -> remerge -> deploy -> hardlinks -> French text pack -> rules.txt
```

Four things about that chain are worth knowing, because each one cost hours:

1. **`deploy_config.auto: true` is set in `%APPDATA%\ukmm\settings.yml`.**
   Every `remerge` therefore deploys the **active** profile. So `botw` sets
   the active profile *before* merging, and puts your default profile back
   afterwards.
2. **UKMM only adds the new profile's files.** Files from the previous
   profile stay behind and the two mix. `botw` clears the folder first. They
   are hardlinks, so the UKMM storage is untouched and the disk cost is zero.
3. **`ukmm.exe` is a GUI-subsystem binary.** `& $ukmm` in PowerShell does not
   wait for it and returns an empty exit code — a false failure. `subprocess`
   waits for the real process and returns the real code.
4. **UKMM never deploys the French text pack.** Mods that add text declare
   `Pack/Bootup_XXxx.pack`; on a French game UKMM merges it into
   `Bootup_EUfr.pack` but copies nothing, because its manifest still names
   the English file. Result: added item and island names are blank. `botw`
   places the file itself.

`botw deploy` refuses to run while Cemu or UKMM are open: Cemu locks the
deployed files, and UKMM redeploys on exit, which would overwrite what you
just installed.

---

## 6. Load order

UKMM stacks mods in `load_order`, and **the last one wins** for any file it
cannot merge. Get it wrong and the weakest mod silently overwrites the
strongest one.

The order `botw` enforces, weakest first:

```
Second Wind (core)          -> its modules -> Ancient Weaponry -> Relics of the Past
-> Hyrule Warriors weapons  -> Islands -> Seamless Warping -> koroks
-> 10x Paraglider           -> Farore's Wind -> Champion's Leathers -> Linkle
```

`Relics of the Past` sits above Ancient Weaponry but below Linkle, and
`botw profile verify` will tell you if a mod ended up nowhere near its files.

---

## 7. Saves

The game sees exactly one save slot. Its `game_data.sav` is **encrypted**,
so no tool — including this one — can read a character name or a description.
Those are whatever you type.

```bat
botw newgame status
botw newgame                :: archive the current game, prepare a fresh one
botw newgame revert         :: put the most recent one back
botw newgame revert 2       :: put back the second most recent
```

### The loading-screen hang

This is the single most confusing failure in the whole setup, and its cause
is known: **a save only opens with the mods it was created with.** The file
is encrypted against the profile. Load a `boost` game under `sur` and the game
sits on the loading screen forever, with no error anywhere.

That is why `botw newgame` exists: it moves the current slot aside instead of
deleting it, so you can start fresh without losing anything. The older
`Sauvegardes-BOTW.ps1` save manager records which profile each save belongs
to and warns in a red box before you load a mismatched one.

---

## 8. Two players

**Same sofa, two pads.** Cemu opens one controller by default. One tag in
`%APPDATA%\Cemu\settings.xml` fixes it:

```bat
botw coop enable             :: PadChannels 1 -> 2
botw coop disable            ;; back to one controller
botw coop status
```

Cemu rewrites `settings.xml` when it exits, so close the game first — `botw`
refuses to change it while Cemu is running.

**Over the network with Radmin VPN.** `botw coop radmin` prints the adapter
and address it found, then the five steps. In short: install Radmin VPN on
both machines, create a network with the same name on both, connect both,
and allow Cemu on private networks in the Windows firewall.

Both machines must run the **same game version, the same mods and the same
profile**. `botw profile show` prints it.

---

## 9. External tools

```bat
botw tools list
botw tools install-ukmm      ;; from the official GitHub releases
botw tools install-bcml      ;; into WSL, isolated, no sudo
botw tools ukmm              ;; open the mod manager
```

UKMM is downloaded from its GitHub release, and the SHA-256 published next to
the file is verified before anything is extracted — a half-written UKMM is
worse than none.

BCML has no Windows build any more, so it goes into WSL. To avoid `sudo` and
any change to the system Python, a standalone CPython is installed under
`~/.local/python311` and BCML into a venv at `~/.local/bcml-venv`. The recipe
is idempotent: running it again installs nothing and breaks nothing.

---

## 10. When something is wrong

```bat
botw doctor
```

Fifteen checks in seven groups: UKMM and its configuration, programs that
must be closed, whether the active profile is fully merged, what Cemu will
actually read, saves, external tools, and free disk space. It exits non-zero
if anything failed, so it works in a script.

The single most common cause of a failure after installing mods is **a save
that does not match the profile**. Check §7.

---

## Commands

| Command | Effect |
|---|---|
| `botw` | open the menu |
| `botw doctor` | full health check |
| `botw deploy <profile> [--activate]` | merge and deploy |
| `botw profile list\|show\|use\|create\|delete\|verify` | profiles |
| `botw mods list\|search\|download\|install\|uninstall` | mods |
| `botw tools list\|install-ukmm\|install-bcml\|ukmm` | external tools |
| `botw catalog [<name>] [--as <profile>] [--deploy]` | verified combinations |
| `botw coop status\|enable\|disable\|radmin` | two players |
| `botw newgame [revert <n>\|status]` | fresh game, keep the old one |
| `botw readme [en\|fr] [-o]` | this document |
| `botw matrix [suite]` | the combination test bench |
| `botw lang [en\|fr]` | language |
| `botw --lang fr <command>` | one run in French |

---

## Known limits

* Text added by mods is **English only**. There is no French source upstream;
  this is a limitation of the mods themselves, not of the tool.
* Ray tracing is impossible in Cemu on this machine's disk budget.
* GameBanana's search endpoint currently returns 404. `botw mods search`
  still searches your local library and reports any failure instead of
  pretending it found nothing.
* `botw newgame` moves the *slot*, not the archive: your other saves managed
  by `Sauvegardes-BOTW.ps1` are untouched.

## Licence

MIT. This tool contains no game assets.
