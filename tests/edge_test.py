import os, sys, socket, threading, time
os.environ["QT_QPA_PLATFORM"]="offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
def mk():
    a,b=socket.socketpair(); m=W.WiFiV2Manager(); m._sock=a; return m,b
def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ")+name, extra)
# 1. pushes first, expected reply later -> waits for expected, returns both
m,b=mk()
def s1(): b.sendall(W.encrypt("@TF:0004")); time.sleep(0.2); b.sendall(W.encrypt("@tg:C000FF00"))
threading.Thread(target=s1).start(); t=time.monotonic(); r=m._recv_all(2, expect="@tg:C0"); dt=time.monotonic()-t
check("expect waits past a non-matching push", len(r)==2 and r[-1].startswith("@tg:C0"), "%d msgs %.0f ms"%(len(r),dt*1000)); check("  returns ~200ms+grace, not +300ms", 0.2<=dt<0.32, "%.0f ms"%(dt*1000))
# 2. expected never arrives -> returns pushes after `timeout`, no exception
m,b=mk(); b.sendall(W.encrypt("@TF:0004")); t=time.monotonic(); r=m._recv_all(0.6, expect="@tg:C0"); dt=time.monotonic()-t
check("expected missing -> full timeout, returns what arrived", len(r)==1 and 0.58<dt<0.75, "%d msgs %.0f ms"%(len(r),dt*1000))
# 3. nothing at all -> [] after timeout
m,b=mk(); t=time.monotonic(); r=m._recv_all(0.4); dt=time.monotonic()-t
check("silence -> [] after timeout", r==[] and 0.38<dt<0.55, "%.0f ms"%(dt*1000))
# 4. message split across two chunks (mid-message) is reassembled
m,b=mk(); raw=W.encrypt("@tp")
def s4(): b.sendall(raw[:3]); time.sleep(0.15); b.sendall(raw[3:])
threading.Thread(target=s4).start(); r=m._recv_all(2, expect="@tp"); check("split message reassembled", r==["@tp"], repr(r))
# 5. bundled messages (<=16ms apart) all collected
m,b=mk()
def s5(): b.sendall(W.encrypt("@tp")); time.sleep(0.016); b.sendall(W.encrypt("@TB")); time.sleep(0.016); b.sendall(W.encrypt("@TV:3E02"))
threading.Thread(target=s5).start(); r=m._recv_all(2, expect="@tp"); check("bundle within grace collected", r==["@tp","@TB","@TV:3E02"], repr(r))
# 6. peer closes right after sending -> messages returned first, next call raises
m,b=mk(); b.sendall(W.encrypt("@tp")); b.close(); r=m._recv_all(2, expect="@tp")
check("close after data: data returned", r==["@tp"], repr(r))
try: m._recv_all(1); check("  next call raises ConnectionError", False)
except ConnectionError: check("  next call raises ConnectionError", True)
# 7. peer closes with nothing -> raises
m,b=mk(); b.close()
try: m._recv_all(1); check("close w/o data raises", False)
except ConnectionError: check("close w/o data raises", True)
# 8. garbage line is skipped, valid one after it still parsed
m,b=mk(); b.sendall(b"junk\r\n"); b.sendall(W.encrypt("@ts")); r=m._recv_all(2, expect="@ts"); check("garbage skipped", r==["@ts"], repr(r))
