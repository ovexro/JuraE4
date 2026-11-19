import os,sys,socket,threading,time
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
from PyQt5.QtCore import QCoreApplication
PORT=51993; W.CONNECT_RETRY_DELAY=0.5
def respond(c,cmd):
    try:
        if cmd.startswith("@HP"): c.sendall(W.encrypt("@hp4"))
        elif cmd=="@TS:01": c.sendall(W.encrypt("@ts"))
        elif cmd=="@TG:C0": c.sendall(W.encrypt("@TF:00040000890000")); c.sendall(W.encrypt("@tg:C000FF00"))
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
def serve_later(delay):
    time.sleep(delay); s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",PORT)); s.listen(2)
    while True:
        c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()
app=QCoreApplication([])
def mk():
    m=W.WiFiV2Manager(); st={"ok":threading.Event(),"fail":[]}
    m.connect_ok.connect(lambda s: st["ok"].set()); m.connect_fail.connect(lambda s: (st["fail"].append(s), st["ok"].set())); return m,st
A=mk(); B=mk()
def check(n,c,x=""): print(("PASS " if c else "FAIL ")+n,x,flush=True)
def sc():
    # nothing listening for the first 0.8 s -> attempts 1-2 refused, a later one succeeds
    threading.Thread(target=serve_later,args=(0.8,),daemon=True).start()
    m,st=A; t=time.monotonic(); m.connect_machine("127.0.0.1",PORT); st["ok"].wait(10)
    check("refused at first, accepted on a retry", m.is_connected and not st["fail"], "%.1f s"%(time.monotonic()-t)); m.disconnect_and_wait()
    # permanently refused port -> gives up after all attempts with the J.O.E. hint
    m,st=B; t=time.monotonic(); m.connect_machine("127.0.0.1",51992); st["ok"].wait(15); dt=time.monotonic()-t
    check("always refused: fails after %d attempts with the 'Close J.O.E.' hint"%W.CONNECT_ATTEMPTS, st["fail"] and "J.O.E." in st["fail"][0] and abs(dt-(W.CONNECT_ATTEMPTS-1)*0.5)<0.6, "%.1f s"%dt)
    app.quit()
threading.Thread(target=sc,daemon=True).start(); app.exec_()
