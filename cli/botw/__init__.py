"""botw - everything around Breath of the Wild on Cemu.

The package is deliberately split so each piece can be tested on its own:

    config    where things live on this machine (no hard-coded path)
    i18n      English by default, French optional
    deploy    merge a UKMM profile and deploy it to Cemu
    profiles  read / create / delete UKMM profiles
    mods      the mod library: list, install, download from GameBanana
    tools     install the external tools (UKMM, BCML)
    catalog   the mod combinations the test bench proved to work
    coop      two players, same world (local pads + Radmin VPN)
    newgame   start a fresh game on top of the current one
    readme    print the documentation, in the chosen language
    doctor    the health check
    ui        a menu for people who would rather click
    cli       the dispatcher
"""
__version__ = "1.2.0"
