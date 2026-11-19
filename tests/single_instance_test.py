"""Single-instance guard (QLockFile + local socket) and the start-at-login entry."""
import os, sys, time, signal, tempfile, subprocess, textwrap
os.environ["QT_QPA_PLATFORM"] = "offscreen"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
app = QApplication([]); import jura_app as J
def check(n, c, x=""): print(("PASS " if c else "FAIL ") + n, x, flush=True)
tmp = tempfile.mkdtemp(prefix="jura_si_"); lock = os.path.join(tmp, "app.lock"); NAME = "jura-test-%d" % os.getpid()

# ---- in-process: lock, "show" message, release ----
a = J.SingleInstance(lock, NAME); b = J.SingleInstance(lock, NAME); shown = []
check("first launch becomes the instance", a.acquire())
a.on_show(lambda: shown.append(1))
check("second launch is refused", not b.acquire())
check("...and can reach the running instance", b.notify_running())
QTest.qWait(300); check("running instance was asked to show its window", shown == [1], shown)
b.notify_running(); QTest.qWait(300); check("repeat launches keep working", shown == [1, 1])
a.release(); c = J.SingleInstance(lock, NAME)
check("after the instance quits a new launch can take over", c.acquire()); c.release()
check("nobody listening -> notify_running reports False", not J.SingleInstance(lock, NAME + "-none").notify_running(300))

# ---- two REAL processes ----
holder_src = textwrap.dedent('''
    import os, sys, time
    os.environ["QT_QPA_PLATFORM"] = "offscreen"; sys.path.insert(0, sys.argv[1])
    from PyQt5.QtWidgets import QApplication; from PyQt5.QtTest import QTest
    app = QApplication([]); import jura_app as J
    g = J.SingleInstance(sys.argv[2], sys.argv[3]); ok = g.acquire(); n = []
    g.on_show(lambda: n.append(1)); print("holder acquired" if ok else "holder REFUSED", flush=True)
    t = time.time()
    while time.time() - t < float(sys.argv[4]): QTest.qWait(50)
    print("shows=%d" % len(n), flush=True)
''')
second_src = textwrap.dedent('''
    import os, sys
    os.environ["QT_QPA_PLATFORM"] = "offscreen"; sys.path.insert(0, sys.argv[1])
    from PyQt5.QtWidgets import QApplication
    app = QApplication([]); import jura_app as J
    g = J.SingleInstance(sys.argv[2], sys.argv[3])
    if g.acquire(): print("second GOT THE LOCK"); sys.exit(3)
    print("shown" if g.notify_running() else "unreachable"); sys.exit(0)
''')
lock2 = os.path.join(tmp, "app2.lock"); NAME2 = NAME + "-p"
h = subprocess.Popen([sys.executable, "-c", holder_src, ROOT, lock2, NAME2, "4"], stdout=subprocess.PIPE, text=True)
check("holder process started", h.stdout.readline().strip() == "holder acquired")
t = time.time(); r = subprocess.run([sys.executable, "-c", second_src, ROOT, lock2, NAME2], capture_output=True, text=True, timeout=20)
dt = time.time() - t
check("second process exits fast, asks the first to show", r.returncode == 0 and r.stdout.strip() == "shown" and dt < 6, "%.1f s %r" % (dt, r.stdout.strip()))
out = h.communicate(timeout=20)[0]; check("holder received exactly one show request", "shows=1" in out, out.strip())

# ---- stale lock from a process that died without cleanup ----
lock3 = os.path.join(tmp, "app3.lock"); NAME3 = NAME + "-s"
h = subprocess.Popen([sys.executable, "-c", holder_src, ROOT, lock3, NAME3, "30"], stdout=subprocess.PIPE, text=True); h.stdout.readline()
h.send_signal(signal.SIGKILL); h.wait(); check("crashed holder left its lock file behind", os.path.exists(lock3))
s3 = J.SingleInstance(lock3, NAME3); check("a launch after a crash is NOT blocked by the stale lock", s3.acquire()); s3.release()

# ---- autostart entry ----
os.environ["XDG_CONFIG_HOME"] = os.path.join(tmp, "xdg")
check("autostart off by default", not J.autostart_enabled())
J.set_autostart(True); txt = open(J.autostart_path()).read()
check("enabled -> entry written under XDG autostart", J.autostart_enabled() and J.autostart_path().startswith(os.path.join(tmp, "xdg", "autostart")))
check("entry launches run.sh --minimized, no terminal", "run.sh" in txt and "--minimized" in txt and "Terminal=false" in txt and "X-GNOME-Autostart-enabled=true" in txt, txt.splitlines()[4])
J.set_autostart(False); check("disabled -> entry removed", not J.autostart_enabled())
J.set_autostart(False); check("removing twice is harmless", True)
