import os,sys,socket,threading,time
os.environ["QT_QPA_PLATFORM"]="offscreen"; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
from PyQt5.QtCore import QCoreApplication
W.DONGLE_PORT=51997; tg={"v":"@tg:C000FF00"}
def respond(c,cmd):
    try:
        if cmd.startswith("@HP"): c.sendall(W.encrypt("@hp4"))
        elif cmd=="@TS:01": c.sendall(W.encrypt("@ts"))
        elif cmd=="@TG:C0": c.sendall(W.encrypt("@TF:00040000890000")); time.sleep(0.1); c.sendall(W.encrypt(tg["v"]))
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
    s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); s.bind(("127.0.0.1",51997)); s.listen(2); r.set()
    while True:
        c,_=s.accept(); threading.Thread(target=handle,args=(c,),daemon=True).start()
app=QCoreApplication([]); r=threading.Event(); threading.Thread(target=serve,args=(r,),daemon=True).start(); r.wait()
m=W.WiFiV2Manager(); got=[]; m.status_update.connect(lambda a: got.append([x[0] for x in a])); ok=threading.Event(); m.connect_ok.connect(lambda s: ok.set())
def sc():
    m.connect_machine("127.0.0.1", W.DONGLE_PORT); ok.wait(5); t=time.monotonic()
    while not got and time.monotonic()-t<6: time.sleep(0.05)
    print(("PASS" if got and 32 not in got[0] and 13 in got[0] else "FAIL"),"filter N/A (0xFF): bit 32 hidden, others kept:",got[:1])
    got.clear(); tg["v"]="@tg:C0002000"; time.sleep(4.8)
    print(("PASS" if got and 32 in got[-1] else "FAIL"),"filter present (0x20): bit 32 kept:",got[-1:] )
    print("unit:",W.WiFiV2Manager._filter_not_applicable(["@TF:00","@tg:C000FF00"]),W.WiFiV2Manager._filter_not_applicable(["@tg:C0"]),W.WiFiV2Manager._filter_not_applicable([]))
    m.shutdown(); app.quit()
threading.Thread(target=sc,daemon=True).start(); app.exec_()
