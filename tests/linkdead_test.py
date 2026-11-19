import os,sys,socket,threading,time
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
from PyQt5.QtCore import QCoreApplication
PORT=51996; W.DONGLE_PORT=PORT; mode={"m":"close"}; conns=[]
def handle(c):
    conns.append(c); buf=b""
    while True:
        try: d=c.recv(4096)
        except OSError: return
        if not d: return
        buf+=d
        while b"\r\n" in buf:
            i=buf.index(b"\r\n"); raw,buf=buf[:i+2],buf[i+2:]; cmd=W.decrypt(raw).strip()
            if cmd.startswith("@HP"): c.sendall(W.encrypt("@hp4"))
            elif cmd=="@TS:01": c.sendall(W.encrypt("@ts"))
            elif cmd=="@TG:C0":
                if mode["m"]=="silent": continue      # keep socket open, never answer
                c.sendall(W.encrypt("@TF:00040000890000")); c.sendall(W.encrypt("@tg:C000FF00"))
def serve(r):
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",PORT)); s.listen(2); r.set()
    while True:
        c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()
app=QCoreApplication([]); r=threading.Event(); threading.Thread(target=serve,args=(r,),daemon=True).start(); r.wait()
def mkmgr():
    m=W.WiFiV2Manager(); st={"ok":threading.Event(),"dis":threading.Event(),"d":None}
    m.connect_ok.connect(lambda s: st["ok"].set())
    def d(): st["d"]=time.monotonic(); st["dis"].set()
    m.disconnected.connect(d); return m,st
M1=mkmgr(); M2=mkmgr()          # connections made in the main (event-loop) thread
def trial(kind,mgr):
    m,st=mgr; mode["m"]=kind; conns.clear()
    m.connect_machine("127.0.0.1", W.DONGLE_PORT); st["ok"].wait(5)
    s=m._sock; opts=(s.getsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY), s.getsockopt(socket.SOL_SOCKET,socket.SO_KEEPALIVE), s.getsockopt(socket.IPPROTO_TCP,socket.TCP_KEEPIDLE))
    time.sleep(0.6); t0=time.monotonic()
    if kind=="close":
        for c in conns:
            try: c.shutdown(socket.SHUT_RDWR); c.close()
            except OSError: pass
    st["dis"].wait(40); return opts, (st["d"]-t0 if st["d"] else None)
def sc():
    o,dt=trial("close",M1); print("sockopts NODELAY/KEEPALIVE/KEEPIDLE =",o); print(("PASS" if dt is not None and dt<=5 else "FAIL"),"closed link detected in", None if dt is None else "%.1f s (<= one 4 s poll; was 5 polls)"%dt)
    o,dt=trial("silent",M2); print(("PASS" if dt is not None and 11<dt<20 else "FAIL"),"silent dongle declared dead in", None if dt is None else "%.1f s (3 x ~6 s; was ~30 s)"%dt)
    app.quit()
threading.Thread(target=sc,daemon=True).start(); app.exec_()
