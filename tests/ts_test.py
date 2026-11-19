import os,sys,socket,threading,time
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
from PyQt5.QtCore import QCoreApplication
PORT=51995; W.DONGLE_PORT=PORT; mode={"m":"poll_ts"}; W.BREW_COOLDOWN_SECONDS=0
def respond(c,cmd):
    try:
        if cmd.startswith("@HP"): c.sendall(W.encrypt("@hp4"))
        elif cmd=="@TS:01": c.sendall(W.encrypt("@ts"))
        elif cmd=="@TG:C0":
            if mode["m"]=="poll_ts": c.sendall(W.encrypt("@TS")); c.sendall(W.encrypt("@tg:C000FF00"))
            else: c.sendall(W.encrypt("@TF:00040000890000")); c.sendall(W.encrypt("@tg:C000FF00"))
        elif cmd.startswith("@TP:"):
            c.sendall(W.encrypt("@tp")); time.sleep(0.2); c.sendall(W.encrypt("@TB"))
            time.sleep(0.3); c.sendall(W.encrypt("@TV:3C0201010009FFFFFFFF11FFFF110AFF")); time.sleep(0.4); c.sendall(W.encrypt("@TS"))
    except OSError: pass
def handle(c):
    buf=b""
    while True:
        try: d=c.recv(4096)
        except OSError: return
        if not d: return
        buf+=d
        while b"\r\n" in buf:
            i=buf.index(b"\r\n"); raw,buf=buf[:i+2],buf[i+2:]; threading.Thread(target=respond,args=(c,W.decrypt(raw).strip()),daemon=True).start()
def serve(r):
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",PORT)); s.listen(4); r.set()
    while True:
        c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()
app=QCoreApplication([]); r=threading.Event(); threading.Thread(target=serve,args=(r,),daemon=True).start(); r.wait()
def mk():
    m=W.WiFiV2Manager(); st={"ok":threading.Event(),"dis":threading.Event(),"t":None,"errs":[],"prog":[],"started":threading.Event()}
    m.connect_ok.connect(lambda s: st["ok"].set()); m.brew_error.connect(lambda e: st["errs"].append(e)); m.brew_progress.connect(lambda p,t: st["prog"].append(p)); m.brew_started.connect(lambda: st["started"].set())
    def d(): st["t"]=time.monotonic(); st["dis"].set()
    m.disconnected.connect(d); return m,st
A=mk(); B=mk()
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
def sc():
    m,st=A; mode["m"]="poll_ts"; t0=time.monotonic(); m.connect_machine("127.0.0.1", W.DONGLE_PORT); st["ok"].wait(5); st["dis"].wait(10)
    dt=(st["t"]-t0) if st["t"] else None
    check("@TS in poll reply -> disconnected immediately", dt is not None and dt<1.5 and not m.is_connected, None if dt is None else "%.2f s"%dt)
    m,st=B; mode["m"]="brew_ts"; m.connect_machine("127.0.0.1", W.DONGLE_PORT); st["ok"].wait(5); time.sleep(0.3)
    t0=time.monotonic(); m.brew(2,1,45,5,1); st["dis"].wait(8); dt=(st["t"]-t0) if st["t"] else None
    check("@TS mid-brew -> error + disconnect fast (not 120 s)", dt is not None and dt<3 and any("session ended" in e for e in st["errs"]) and not m.is_brewing, "%s errs=%s prog=%s"%("%.2f s"%dt if dt else None, st["errs"], st["prog"]))
    app.quit()
threading.Thread(target=sc,daemon=True).start(); app.exec_()
