import os,sys
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt5.QtWidgets import QApplication
app=QApplication([]); import jura_app as J
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
class Wf:
    is_brewing=False; brewed=[]
    def brew(self,*a): Wf.brewed.append(a)
class Dash:
    errs=[]
    def on_brew_error(self,m): Dash.errs.append(m)
    def show_error(self,m): Dash.errs.append(m)
class Tm:
    def stop(self): pass
class St:
    def set(self,*a): pass
    def save(self): pass
    def set_product(self,*a): pass
a=J.JuraApp.__new__(J.JuraApp); a._wifi=Wf(); a._dashboard=Dash(); a._brew_timer=Tm(); a._settings=St(); a._last_alerts=None
check("no status yet -> not blocked", a._brew_blockers(0x02)==[])
a._last_alerts=[(13,"Coffee ready","success"),(36,"Energy save","info"),(39,"Keys locked","info")]
check("idle status -> not blocked", a._brew_blockers(0x02)==[] and a._brew_blockers(0x0D)==[])
a._last_alerts=[(1,"Fill water","warning"),(10,"No beans","warning"),(36,"Energy save","info")]
check("coffee blocked by water+beans", a._brew_blockers(0x03)==["Fill water","No beans"], a._brew_blockers(0x03))
check("hot water blocked by water only", a._brew_blockers(0x0D)==["Fill water"], a._brew_blockers(0x0D))
a._last_alerts=[(10,"No beans","warning"),(2,"Empty grounds","warning")]
check("hot water NOT blocked by beans/grounds", a._brew_blockers(0x0D)==[] and a._brew_blockers(0x02)==["Empty grounds","No beans"] or a._brew_blockers(0x02)==["No beans","Empty grounds"], a._brew_blockers(0x02))
a._on_brew(0x02,1,45,5,1); check("_on_brew blocked: backend NOT called, reason shown", Wf.brewed==[] and Dash.errs and Dash.errs[-1].startswith("Fix first:"), Dash.errs)
a._last_alerts=[(13,"Coffee ready","success")]; a._on_brew(0x02,1,45,5,1); check("_on_brew clear: backend called", len(Wf.brewed)==1)
