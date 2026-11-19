import os, sys, socket, threading, time
os.environ["QT_QPA_PLATFORM"]="offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
from PyQt5.QtCore import QCoreApplication
PORT=51998; W.DONGLE_PORT=PORT; W.BREW_COOLDOWN_SECONDS=1.5
mode={"ack":True}
def respond(c,cmd):
    try:
        if cmd.startswith("@HP"): c.sendall(W.encrypt("@hp4"))
        elif cmd=="@TS:01": c.sendall(W.encrypt("@ts"))
        elif cmd=="@TG:C0": c.sendall(W.encrypt("@TF:00040000890000")); time.sleep(0.05); c.sendall(W.encrypt("@tg:C000FF00"))
        elif cmd.startswith("@TP:") and mode["ack"]:
            c.sendall(W.encrypt("@tp")); time.sleep(0.4); c.sendall(W.encrypt("@TV:3E02"))
    except OSError: pass
def handle(c):
    buf=b""
    try:
        while True:
            d=c.recv(4096)
            if not d: return
            buf+=d
            while b"\r\n" in buf:
                i=buf.index(b"\r\n"); raw,buf=buf[:i+2],buf[i+2:]
                threading.Thread(target=respond,args=(c,W.decrypt(raw).strip()),daemon=True).start()
    except OSError: pass
def serve(r):
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",PORT)); s.listen(2); r.set()
    while True:
        c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()
app=QCoreApplication([]); r=threading.Event(); threading.Thread(target=serve,args=(r,),daemon=True).start(); r.wait()
m=W.WiFiV2Manager(); errs=[]; started=[]; done=threading.Event()
m.brew_error.connect(lambda e: errs.append(e)); m.brew_started.connect(lambda: started.append(time.monotonic()))
m.connect_ok.connect(lambda s: done.set())
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
def wait_idle(): 
    t=time.monotonic()
    while m.is_brewing and time.monotonic()-t<8: time.sleep(0.02)
def scenario():
    m.connect_machine("127.0.0.1", W.DONGLE_PORT); done.wait(5)
    m.brew(2,1,45,5,1); time.sleep(0.2); wait_idle(); time.sleep(0.1)
    check("1st brew acknowledged+finished", len(started)==1 and not m.is_brewing and not errs, errs)
    n=len(errs); m.brew(2,1,45,5,1); time.sleep(0.15)
    check("2nd brew right after completion is rejected (cooldown from END)", len(errs)==n+1 and "Please wait" in errs[-1] and len(started)==1, errs[-1:] )
    time.sleep(1.6); n=len(errs); m.brew(2,1,45,5,1); time.sleep(0.2); wait_idle()
    check("brew accepted once cooldown elapsed", len(started)==2 and len(errs)==n, errs[n:])
    # failed start (no ack) must NOT arm the cooldown
    time.sleep(1.7); mode["ack"]=False; n=len(errs); m.brew(2,1,45,5,1)
    t=time.monotonic(); wait_idle(); dt=time.monotonic()-t
    check("no-ack start errors out (~5s)", len(errs)==n+1 and "not acknowledge" in errs[-1], "%.1fs %s"%(dt,errs[-1:]))
    n=len(errs); m.brew(2,1,45,5,1); time.sleep(0.2)
    check("retry after failed start is NOT blocked by cooldown", not any("Please wait" in e for e in errs[n:]), errs[n:])
    mode["ack"]=True; wait_idle(); m.shutdown(); app.quit()
threading.Thread(target=scenario,daemon=True).start(); app.exec_()
