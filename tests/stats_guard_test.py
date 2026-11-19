import os,sys
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt5.QtWidgets import QApplication
app=QApplication([]); import jura_app as J
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
class W:  # stand-in for the manager: only what the guard + handlers touch
    is_brewing=False; is_connected=True; calls=0
    def read_statistics(self): W.calls+=1
class Dash:
    msgs=[]
    def show_error(self,m): Dash.msgs.append(m)
class Stack:
    cur=None
    def setCurrentWidget(self,w): Stack.cur=w
app_obj=J.JuraApp.__new__(J.JuraApp)           # no __init__: avoids auto-connect to the real dongle
app_obj._wifi=W(); app_obj._dashboard=Dash(); app_obj._stack=Stack(); app_obj._stats_screen=J.StatisticsScreen()
for brewing,conn,want in [(False,True,None),(True,True,"Cannot read statistics while brewing"),(False,False,"Not connected to the machine")]:
    W.is_brewing, W.is_connected = brewing, conn
    check("reason brewing=%s connected=%s"%(brewing,conn), app_obj._stats_unavailable_reason()==want, app_obj._stats_unavailable_reason())
W.is_brewing=True; W.calls=0; Dash.msgs.clear(); Stack.cur=None
app_obj._on_show_stats(); check("open during brew: toast, no navigation, no read", Dash.msgs==["Cannot read statistics while brewing"] and Stack.cur is None and W.calls==0, Dash.msgs)
sc=app_obj._stats_screen; sc.show_loading(); app_obj._on_stats_refresh()
check("refresh during brew: spinner replaced by message, Refresh re-enabled", not sc._load_timer.isActive() and sc._refresh_btn.isEnabled() and "while brewing" in sc._status_label.text(), sc._status_label.text())
W.is_brewing=False; W.is_connected=True; W.calls=0; app_obj._on_show_stats(); check("normal open still loads", W.calls==1 and Stack.cur is sc and sc._load_timer.isActive())
