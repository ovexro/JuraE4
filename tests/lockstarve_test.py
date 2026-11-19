import os,sys,socket,threading,time
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
from PyQt5.QtCore import QCoreApplication
PORT=51994; W.DONGLE_PORT=PORT; W.BREW_COOLDOWN_SECONDS=0
def respond(c,cmd):
    try:
        if cmd.startswith("@HP"): c.sendall(W.encrypt("@hp4"))
        elif cmd=="@TS:01": c.sendall(W.encrypt("@ts"))
        elif cmd=="@TG:C0": c.sendall(W.encrypt("@TF:00040000890000")); c.sendall(W.encrypt("@tg:C000FF00"))
        elif cmd.startswith("@TP:"):
            c.sendall(W.encrypt("@tp")); c.sendall(W.encrypt("@TB"))
            for pct in range(0,101,10):
                time.sleep(0.6); c.sendall(W.encrypt("@TV:3C0201010009FFFFFFFF11FFFF11%02XFF"%pct))
            c.sendall(W.encrypt("@TV:3E02"))
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
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",PORT)); s.listen(2); r.set()
    while True:
        c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()
app=QCoreApplication([]); r=threading.Event(); threading.Thread(target=serve,args=(r,),daemon=True).start(); r.wait()
m=W.WiFiV2Manager(); ok=threading.Event(); m.connect_ok.connect(lambda s: ok.set())
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x)
def sc():
    m.connect_machine("127.0.0.1", PORT); ok.wait(5); time.sleep(0.5)
    m.brew(2,1,45,5,1); time.sleep(0.3)
    worst=0.0; n=0; t_end=time.monotonic()+5.0
    while time.monotonic()<t_end:
        t=time.monotonic(); b=m.is_brewing; d=time.monotonic()-t; worst=max(worst,d); n+=1; time.sleep(0.05)
    check("is_brewing never blocks during a brew (GUI thread calls it)", worst<0.05, "worst wait %.0f ms over %d calls"%(worst*1000,n))
    t=time.monotonic()
    while m.is_brewing and time.monotonic()-t<15: time.sleep(0.05)
    check("brew finishes and flag clears promptly", not m.is_brewing and time.monotonic()-t<3, "%.1f s"%(time.monotonic()-t))
    m.shutdown(); app.quit()
threading.Thread(target=sc,daemon=True).start(); app.exec_()
