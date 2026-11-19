import os,sys
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt5.QtWidgets import QApplication
app=QApplication([]); import jura_app as J
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
class Wf:
    def __init__(s): s.connected=False; s.calls=[]; s._dongle_ip="192.168.1.105"
    @property
    def is_connected(s): return s.connected
    def connect_machine(s,ip,port=None): s.calls.append(("connect",ip))
    def disconnect_machine(s): s.calls.append(("disconnect",)); s.connected=False
    def scan(s): s.calls.append(("scan",))
class Dash:
    def __init__(s): s.log=[]
    def set_reconnecting(s,n=0): s.log.append(("reconnecting",n))
    def set_disconnected(s): s.log.append(("disconnected",))
    def set_connected(s): s.log.append(("connected",))
    def set_machine_info(s,i): pass
    def on_brew_status_clear(s): pass
class Timer:
    def __init__(s): s.started=[]; s.stopped=0
    def start(s,ms): s.started.append(ms)
    def stop(s): s.stopped+=1
    def isActive(s): return bool(s.started)
class Stack:
    cur=None
    def setCurrentWidget(s,w): Stack.cur=w
class Conn:
    def __init__(s): s.status=[]; s._fallback_widgets=[]; s._ip_input=type("I",(),{"setText":lambda self,t:None})()
    def show_status(s,t,c): s.status.append(t)
    def show_fallback(s,*a): s.status.append("fallback")
    def stop_animation(s): pass
    def start_animation(s,t): pass
class Set:
    def get(s,k,d=None): return d
    def set(s,*a): pass
    def save(s): pass
def mk():
    a=J.JuraApp.__new__(J.JuraApp); a._wifi=Wf(); a._dashboard=Dash(); a._conn_screen=Conn(); a._stack=Stack(); a._settings=Set()
    a._reconnect_timer=Timer(); a._brew_safety_timer=Timer(); a._tray=None; a._update_tray_brew_actions=lambda c: None
    a._user_disconnect=False; a._reconnecting=False; a._reconnect_attempts=0; a._tried_scan=False; a._last_alerts=None; a._offline_by_user=False
    return a
# a) unexpected drop -> reconnect forever with growing pauses, never the give-up screen
a=mk(); a._wifi.connected=True; a._on_disconnected()
check("drop: immediate reconnect attempt", a._reconnecting and a._wifi.calls==[("connect","192.168.1.105")], a._wifi.calls)
for i in range(9): a._on_connect_failed("No route to host")
check("9 failures: delays grow then hold at 30 s", a._reconnect_timer.started==[2000,5000,10000,20000,30000,30000,30000,30000,30000], a._reconnect_timer.started)
check("never shows the give-up fallback; still reconnecting", a._reconnecting and "fallback" not in a._conn_screen.status)
check("status text escalates (#<=2 plain, >=3 'unreachable')", a._dashboard.log[0]==("reconnecting",0) and a._dashboard.log[1]==("reconnecting",1) and a._dashboard.log[-1]==("reconnecting",9))
a._wifi.calls.clear(); a._try_reconnect(); check("timer fire -> connects again", a._wifi.calls==[("connect","192.168.1.105")])
a._on_connected("JURA E4"); check("success resets reconnect state", not a._reconnecting and a._reconnect_attempts==0 and a._dashboard.log[-1]==("connected",))
# b) Disconnect pressed while reconnecting
a=mk(); a._wifi.connected=True; a._wifi.connected=False; a._on_disconnected(); a._on_connect_failed("x")   # real backend: _connected is False after a drop
a._on_disconnect()
check("Disconnect while reconnecting: timer stopped, UI to Disconnected", a._reconnect_timer.stopped>=1 and not a._reconnecting and a._dashboard.log[-1]==("disconnected",) and Stack.cur is a._conn_screen and "Disconnected" in a._conn_screen.status, a._conn_screen.status)
a._wifi.calls.clear(); a._try_reconnect(); check("a stray timer after cancel does NOT reconnect", a._wifi.calls==[])
a._on_connected("late"); check("late connect_ok after Disconnect is undone (no dashboard)", a._wifi.calls==[("disconnect",)] and ("connected",) not in a._dashboard.log, a._wifi.calls)
a._on_scan_finished([type("D",(),{"ip":"1.2.3.4","port":51515})()]); check("late scan result ignored while user-offline", a._wifi.calls==[("disconnect",)])
a._on_retry(); check("user Retry clears the offline flag", not a._offline_by_user)
# c) normal Disconnect while connected still works once
a=mk(); a._wifi.connected=True
class Wc(Wf):
    def disconnect_machine(s): s.calls.append(("disconnect",)); s.connected=False; a._on_disconnected()   # backend emits `disconnected`
a._wifi=Wc(); a._wifi.connected=True; a._on_disconnect()
check("Disconnect while connected: one UI transition, no auto-reconnect", a._dashboard.log.count(("disconnected",))==1 and not a._reconnecting and a._wifi.calls==[("disconnect",)], (a._dashboard.log,a._wifi.calls))
