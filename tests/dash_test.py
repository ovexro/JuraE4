import os,sys
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt5.QtWidgets import QApplication
from PyQt5.QtTest import QTest
app=QApplication([]); import jura_app as J
class FakeSettings:
    def get_product(self,n): return {}
    def get(self,k,d=None): return d
d=J.DashboardScreen(FakeSettings()); d.resize(1060,740); d.show()
cards=d._cards; esp=next(c for c in cards if c._product.code==0x02)
def st(): return [("anim" if c._stack.currentIndex()==1 else ("locked" if not c._brew_btn.isEnabled() else "idle")) for c in cards]
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
check("initial: all idle", set(st())=={"idle"}, st())
# 1. confirmed brew: all locked, NO animation yet
d.begin_brew_request(0x02); check("request: all locked, none animating", set(st())=={"locked"}, st())
# 2. machine acks: only requested card animates, others stay locked
d.on_brew_started(); s=st(); check("ack: requested card animates, others locked", s.count("anim")==1 and s.count("locked")==len(cards)-1 and st()[cards.index(esp)]=="anim", s)
# 3. progress reaches the animating card only
d.on_brew_progress(40,60); check("progress goes to active card", abs(esp._brew_anim._target_progress-0.4)<1e-9)
d.on_brew_progress(100,60)
QTest.qWait(2900); check("after 100% + 2.5s the card returns, all unlock", set(st())=={"idle"}, st())
# 4. rejected brew: rejection fires SYNCHRONOUSLY inside the emit (cooldown etc.)
d.brew_requested.connect(lambda *a: d.on_brew_error("Please wait 3s between brews"))
d.begin_brew_request(0x02); d.brew_requested.emit(0x02,1,45,5,1)
check("rejected brew: no animation, nothing left locked", set(st())=={"idle"} and d._brewing_card_idx is None and d._pending_brew_code is None, st())
# 5. 'already in progress' toast must NOT reset a running brew
d.brew_requested.disconnect(); d.begin_brew_request(0x02); d.on_brew_started(); before=st()
d.show_error("A brew is already in progress"); check("show_error leaves running brew untouched", st()==before, st())
# 6. ack never comes -> error unlocks
d.on_brew_error("Machine did not acknowledge brew command"); check("no-ack error unlocks all", set(st())=={"idle"}, st())
# 7. stray ack with nothing pending animates nothing
d.on_brew_started(); check("ack with nothing pending: no animation", "anim" not in st(), st())
