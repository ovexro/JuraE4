"""Build the .deb and check it: metadata, file layout, desktop/icon files,
and that the app actually runs from the installed-style /opt path.

Needs dpkg-deb + fakeroot (same as packaging/build-deb.sh); skips with a
clear message if they're missing, rather than failing.
"""
import os, shutil, subprocess, sys, tempfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name, extra, flush=True)


for tool in ("dpkg-deb", "fakeroot"):
    if shutil.which(tool) is None:
        print("SKIP all: '%s' not installed" % tool)
        sys.exit(0)

version = open(os.path.join(ROOT, "VERSION")).read().strip()
work = tempfile.mkdtemp(prefix="jura_deb_")
try:
    r = subprocess.run(["bash", os.path.join(ROOT, "packaging", "build-deb.sh")],
                        cwd=ROOT, capture_output=True, text=True, timeout=120)
    check("build-deb.sh exits 0", r.returncode == 0, r.stderr[-300:] if r.returncode else "")
    deb = os.path.join(ROOT, "dist", "jura-desktop_%s_all.deb" % version)
    check("expected .deb file was produced", os.path.isfile(deb), deb)
    if not os.path.isfile(deb):
        sys.exit(1)

    control = subprocess.run(["dpkg-deb", "-I", deb], capture_output=True, text=True).stdout
    check("declares the needed Depends", all(p in control for p in ("python3-pyqt5", "python3-bleak")), control)
    check("Architecture: all (pure Python)", "Architecture: all" in control)
    check("version matches VERSION file", ("Version: %s" % version) in control)

    listing = subprocess.run(["dpkg-deb", "-c", deb], capture_output=True, text=True).stdout
    for path in ("./opt/jura-desktop/jura_app.py", "./opt/jura-desktop/jura_wifi_v2.py",
                 "./opt/jura-desktop/jura_protocol.py", "./opt/jura-desktop/tools/extract_hash.py",
                 "./usr/bin/jura-desktop", "./usr/share/applications/jura-desktop.desktop",
                 "./usr/share/icons/hicolor/256x256/apps/jura-desktop.png",
                 "./usr/share/icons/hicolor/scalable/apps/jura-desktop.svg"):
        check("contains " + path, path in listing)
    check("legacy jura_wifi.py (ESP32 bridge) is NOT shipped", "jura_wifi.py" not in listing.replace("jura_wifi_v2.py", ""))
    check("launcher script is executable", "-rwxr-xr-x" in [l for l in listing.splitlines() if "usr/bin/jura-desktop" in l][0])

    extract = os.path.join(work, "extract")
    subprocess.run(["dpkg-deb", "-x", deb, extract], check=True)
    launcher = open(os.path.join(extract, "usr/bin/jura-desktop")).read()
    check("launcher runs the extracted jura_app.py", "/opt/jura-desktop/jura_app.py" in launcher and "run.sh" not in launcher, launcher)
    check("launcher script is valid sh", subprocess.run(["sh", "-n", os.path.join(extract, "usr/bin/jura-desktop")]).returncode == 0)

    if shutil.which("desktop-file-validate"):
        dv = subprocess.run(["desktop-file-validate", os.path.join(extract, "usr/share/applications/jura-desktop.desktop")],
                            capture_output=True, text=True)
        check("desktop-file-validate passes", dv.returncode == 0, dv.stdout + dv.stderr)
    else:
        print("SKIP desktop-file-validate: not installed")

    # Run the extracted app: isolated HOME for settings/lock, but PyQt5/bleak
    # resolved via this user's real site-packages -- the closest we can get,
    # without installing system packages, to what `Depends:` provides on a
    # clean machine (see packaging/README.md, "What hasn't been verified").
    fake_home = os.path.join(work, "home")
    os.makedirs(fake_home)
    env = dict(os.environ, HOME=fake_home, QT_QPA_PLATFORM="offscreen")
    import site
    env["PYTHONPATH"] = os.pathsep.join(site.getsitepackages() + [site.getusersitepackages()])
    try:
        subprocess.run([sys.executable, os.path.join(extract, "opt/jura-desktop/jura_app.py"), "--minimized"],
                       env=env, timeout=5, capture_output=True, text=True)
        check("app ran to completion unexpectedly fast", False)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
        check("app starts from the /opt layout and keeps running (timeout = alive)",
              "Traceback" not in err, err[-400:])
    check("settings dir was created under the isolated HOME", os.path.isdir(os.path.join(fake_home, ".config", "jura-desktop")))
finally:
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(os.path.join(ROOT, "dist"), ignore_errors=True)
