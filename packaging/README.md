# Packaging (maintainers)

Builds `jura-desktop_<version>_all.deb` for Debian/Ubuntu/Mint, using the
system's `python3-pyqt5` and `python3-bleak` instead of a venv.

```bash
sudo apt install dpkg-dev fakeroot   # build-time only, if not already present
./packaging/build-deb.sh             # -> dist/jura-desktop_<version>_all.deb
```

Bump the version in `VERSION` at the repo root before building a new release.

## Install / remove the result

```bash
sudo apt install ./dist/jura-desktop_1.0.0_all.deb   # pulls python3-pyqt5, python3-bleak
sudo apt remove jura-desktop                         # settings in ~/.config/jura-desktop are kept
sudo apt purge jura-desktop                           # (dpkg has no equivalent of install.sh's --purge for this; remove that folder by hand if wanted)
```

## Layout this produces

```
/opt/jura-desktop/        jura_app.py, jura_wifi_v2.py, jura_protocol.py, icons, tools/extract_hash.py, README.md
/usr/bin/jura-desktop     launcher: exec python3 /opt/jura-desktop/jura_app.py "$@"
/usr/share/applications/jura-desktop.desktop
/usr/share/icons/hicolor/{48,64,128,256}x.../apps/jura-desktop.png + scalable/apps/jura-desktop.svg
/usr/share/doc/jura-desktop/copyright
```

`jura_wifi.py` and `esp32/` (legacy, unused) are not shipped. Settings (incl.
the saved dongle auth hash) always live in `~/.config/jura-desktop`, same as
the `install.sh` route -- untouched by install/remove either way.

This is a separate, independent route from `install.sh` (which builds its
own venv in `~/.local/share/jura-desktop`); use one or the other, not both,
to avoid two menu entries.

## Real install, verified 2026-11-19

`sudo apt install ./dist/jura-desktop_1.0.0_all.deb` was run for real on Linux Mint 22. First attempt: `Recommends: python3-scapy` pulled scapy's own Recommends chain (matplotlib -> scipy/sympy/ipython/tk...) -- **44 packages, 100+ MB**, for a one-time CLI step the setup guide already covers with `pip install scapy`. Fixed to `Suggests:` (apt never auto-installs that). Reinstalled: **5 packages** (python3-pyqt5, python3-pyqt5.sip, libqt5designer5, libqt5help5, python3-bleak) plus jura-desktop itself -- all directly needed, nothing incidental. The app ran correctly from the installed `/opt/jura-desktop` via `/usr/bin/jura-desktop`, using the `apt`-installed PyQt5/bleak (not this dev machine's pip packages). Everything was removed afterwards; the system was confirmed back to its pre-test package state.

## What hasn't been verified

Built and tested here (file layout, launcher, `desktop-file-validate`, the
app running from `/opt/jura-desktop` with PyQt5/bleak resolved the way the
`Depends:` would provide them) but **not yet installed for real with
`apt install`** on a clean machine, nor on Ubuntu or Debian specifically
(only Linux Mint 22). Do that before calling a release final.
