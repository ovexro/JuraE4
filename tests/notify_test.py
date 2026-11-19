"""Desktop notifications: alert transitions, brew finished/failed, connection lost/back, toggle."""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon
app = QApplication([]); import jura_app as J
def check(n, c, x=""): print(("PASS " if c else "FAIL ") + n, x)

# ---- pure helper ----
A = lambda *bits: [(b, J.NOTIFY_ALERTS.get(b, "x"), "warning") for b in bits]
m, cur = J.new_alert_notifications(A(13, 36, 39), set()); check("informational alerts never notify", m == [] and cur == set())
m, cur = J.new_alert_notifications(A(13, 1), set()); check("new notable alert announced", m == ["Fill the water tank"] and cur == {1})
m, cur = J.new_alert_notifications(A(13, 1), cur); check("same alert not repeated on the next poll", m == [])
m, cur = J.new_alert_notifications(A(13), cur); check("alert clears silently", m == [] and cur == set())
m, cur = J.new_alert_notifications(A(1), cur); check("alert that comes back is announced again", m == ["Fill the water tank"])
m, cur = J.new_alert_notifications(A(34, 10, 1), set()); check("batch is sorted by bit", m == ["Fill the water tank", "Refill the beans", "Cleaning needed"], m)

# ---- stubs for JuraApp ----
class Tray:
    def __init__(s): s.msgs = []
    def showMessage(s, t, x, icon, ms): s.msgs.append((t, x, icon))
class Set:
    def __init__(s): s.d = {}; s.saves = 0
    def get(s, k, d=None): return s.d.get(k, d)
    def set(s, k, v): s.d[k] = v
    def save(s): s.saves += 1
class Timer:
    def __init__(s): s.started = []; s.stopped = 0
    def start(s, ms): s.started.append(ms)
    def stop(s): s.stopped += 1
class Dash:
    _brewing_card_idx = None
    def __getattr__(s, n): return lambda *a, **k: None
class Wf:
    is_brewing = False; is_connected = False; _dongle_ip = "1.2.3.4"
    def disconnect_machine(s): pass
class Conn:
    _fallback_widgets = []; _ip_input = type("I", (), {"setText": lambda s, t: None})()
    def __getattr__(s, n): return lambda *a, **k: None
class Stk:
    def setCurrentWidget(s, w): pass
def mk(in_use=False):
    a = J.JuraApp.__new__(J.JuraApp)
    a._tray = Tray(); a._settings = Set(); a._dashboard = Dash(); a._wifi = Wf(); a._conn_screen = Conn(); a._stack = Stk()
    a._brew_timer = Timer(); a._brew_safety_timer = Timer(); a._reconnect_timer = Timer(); a._lost_timer = Timer()
    a._user_disconnect = False; a._reconnecting = False; a._reconnect_attempts = 0; a._tried_scan = False
    a._last_alerts = None; a._offline_by_user = False; a._notified_bits = set(); a._lost_notified = False
    a._brew_notified = False; a._brew_name = None
    a._update_tray_brew_actions = lambda c: None; a._try_reconnect = lambda: None
    a._window_in_use = lambda: in_use
    return a
titles = lambda a: [m[0] for m in a._tray.msgs]

# ---- alerts through _on_status ----
a = mk(); a._on_status(A(13, 1)); a._on_status(A(13, 1)); a._on_status(A(13, 1, 10))
check("status: announced once, then only the NEW alert", a._tray.msgs[0][1] == "Fill the water tank" and a._tray.msgs[1][1] == "Refill the beans" and len(a._tray.msgs) == 2, a._tray.msgs)
check("alert notification uses the Warning icon", a._tray.msgs[0][2] == QSystemTrayIcon.Warning)
a._on_status(A(13)); a._on_status(A(13, 1)); check("returns after clearing -> announced again", len(a._tray.msgs) == 3)

# ---- toggle ----
a = mk(); a._on_notify_toggled(False); check("toggle persists to settings", a._settings.d == {"notifications": False} and a._settings.saves == 1)
a._on_status(A(1)); check("disabled: nothing shown", a._tray.msgs == [] and a._notified_bits == {1})
a._on_notify_toggled(True); a._on_status(A(1)); check("re-enabled: alert already active does not flood", a._tray.msgs == [])
a._tray = None; a._on_status(A(10)); check("no tray available: silently skipped", True)

# ---- brew finished / failed ----
a = mk(in_use=False); a._brew_name = "Espresso"; a._on_brew_progress(40, 60); a._on_brew_progress(100, 60); a._on_brew_progress(100, 0)
check("brew finished while window not in use: ONE 'Espresso is ready'", titles(a) == ["Espresso is ready"], titles(a))
a = mk(in_use=True); a._brew_name = "Espresso"; a._on_brew_progress(100, 60); check("window in use: no balloon", a._tray.msgs == [])
a = mk(in_use=False); a._on_brew_error("Machine did not acknowledge brew command"); check("brew failure while hidden notifies", titles(a) == ["Brew failed"] and a._tray.msgs[0][1].startswith("Machine did not"))
a = mk(in_use=True); a._on_brew_error("x"); check("brew failure with window in use: no balloon", a._tray.msgs == [])

# ---- connection lost / back ----
a = mk(); a._on_disconnected()
check("unexpected drop: nothing shown at once, 15 s timer armed", a._tray.msgs == [] and a._lost_timer.started == [15000] and a._reconnecting)
a._on_lost_timeout(); check("still down after 15 s -> 'Lost connection' announced", titles(a) == ["Lost connection to the machine"])
a._on_connected("JURA E4"); check("reconnected -> 'Machine back online' once", titles(a) == ["Lost connection to the machine", "Machine back online"] and not a._lost_notified)
a._on_connected("JURA E4"); check("no second 'back online'", len(a._tray.msgs) == 2)
a = mk(); a._on_disconnected(); a._on_connected("JURA E4")
check("quick heal (post-brew @TS): timer cancelled, no notifications at all", a._tray.msgs == [] and a._lost_timer.stopped >= 1)
a = mk(); a._user_disconnect = True; a._offline_by_user = True; a._on_disconnected(); a._on_lost_timeout()
check("user Disconnect: no 'lost' notification", a._tray.msgs == [] and a._lost_timer.stopped >= 1)
