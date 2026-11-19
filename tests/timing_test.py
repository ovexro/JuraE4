"""Fake WiFi-V2 dongle on localhost + timing harness for WiFiV2Manager.

Mimics timings measured from jura.log: @TG:C0 -> @TF x2 immediately then @tg:C0
~200 ms later; @TS/@TG:43/@TR ~200 ms; @TP -> @tp after 100 ms, @TB, then @TV
pushes (duplicated) and a final short @TV. Reports client-side latency.
"""
import os, sys, socket, threading, time, statistics
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W

PORT = 51999
W.DONGLE_PORT = PORT
sent_at = {}          # label -> server monotonic send time
lock = threading.Lock()


def srv_send(conn, text, label=None):
    msg = W.encrypt(text)
    if label:
        sent_at[label] = time.monotonic()
    conn.sendall(msg)


def handle(conn):
    buf = b""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                return
            buf += chunk
            while b"\r\n" in buf:
                i = buf.index(b"\r\n")
                raw, buf = buf[:i + 2], buf[i + 2:]
                cmd = W.decrypt(raw).strip()
                threading.Thread(target=respond, args=(conn, cmd), daemon=True).start()
    except OSError:
        pass


def respond(conn, cmd):
    try:
        if cmd.startswith("@HP"):
            time.sleep(0.015); srv_send(conn, "@hp4")
        elif cmd == "@TS:01":
            time.sleep(0.2); srv_send(conn, "@ts")
        elif cmd == "@TG:C0":
            srv_send(conn, "@TF:00040000890000"); srv_send(conn, "@TF:00040000890000")
            time.sleep(0.2); srv_send(conn, "@tg:C000FF00", "tg_c0")
        elif cmd == "@TG:43":
            time.sleep(0.2); srv_send(conn, "@tg:43000000000000000004780000")
        elif cmd.startswith("@TR:32,"):
            time.sleep(0.2); srv_send(conn, "@tr:32,%s,02E7FFFF000D02B2" % cmd[-2:])
        elif cmd.startswith("@TP:"):
            time.sleep(0.1); srv_send(conn, "@tp")
            time.sleep(0.3); srv_send(conn, "@TB")
            for pct in (0, 25, 50, 75, 100):
                time.sleep(0.5)
                tv = "3C0201010009FFFFFFFF11FFFF11%02XFF" % pct
                srv_send(conn, "@TV:" + tv, "tv%d" % pct)
                srv_send(conn, "@TV:" + tv)  # dongle duplicates, like the real log
            time.sleep(0.016); srv_send(conn, "@TV:3E02", "tv_done")
    except OSError:
        pass


def serve(ready):
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PORT)); s.listen(2); ready.set()
    while True:
        c, _ = s.accept()
        threading.Thread(target=handle, args=(c,), daemon=True).start()


def main():
    from PyQt5.QtCore import QCoreApplication
    app = QCoreApplication([])
    ready = threading.Event(); threading.Thread(target=serve, args=(ready,), daemon=True).start(); ready.wait()
    m = W.WiFiV2Manager()
    ev = {"ok": threading.Event(), "status": [], "prog": [], "started": threading.Event(), "err": []}
    m.connect_ok.connect(lambda s: ev["ok"].set())
    m.connect_fail.connect(lambda s: (ev["err"].append(s), ev["ok"].set()))
    m.status_update.connect(lambda a: ev["status"].append((time.monotonic(), a)))
    m.brew_progress.connect(lambda p, t: ev["prog"].append((time.monotonic(), p)))
    m.brew_started.connect(lambda: ev["started"].set())
    m.brew_error.connect(lambda s: ev["err"].append("brew_error: " + s))
    stats_box = []
    m.statistics_ready.connect(lambda s: stats_box.append((time.monotonic(), s)))

    def scenario():
        run(m, ev, stats_box)
        app.quit()
    threading.Thread(target=scenario, daemon=True).start()
    app.exec_()


def run(m, ev, stats_box):
    t0 = time.monotonic(); m.connect_machine("127.0.0.1", W.DONGLE_PORT); ev["ok"].wait(10)
    conn_ms = (time.monotonic() - t0) * 1000
    print("%s connect: %.0f ms (limit 900)%s" % ("PASS" if conn_ms < 900 and not ev["err"] else "FAIL", conn_ms, "  ERR %s" % ev["err"] if ev["err"] else ""))

    # single poll round-trip (call the same path the status loop uses)
    t = time.monotonic(); r = m._send_recv("@TG:C0", **({"expect": "@tg:C0"} if "expect" in m._send_recv.__code__.co_varnames else {}))
    print("@TG:C0 round trip: %.0f ms, messages=%d (%s)" % ((time.monotonic() - t) * 1000, len(r), ",".join(x[:6] for x in r)))

    # status loop effective cadence
    time.sleep(0.2); n0 = len(ev["status"]); time.sleep(9.0)
    ts = [x[0] for x in ev["status"][n0:]]
    gaps = [b - a for a, b in zip(ts, ts[1:])]
    print("%s status poll: %d updates in 9 s (one per poll), mean interval %.2f s" % ("PASS" if len(ts) == 2 and gaps and 3.9 < statistics.mean(gaps) < 4.8 else "FAIL", len(ts), statistics.mean(gaps) if gaps else float("nan")))

    t = time.monotonic(); m.read_statistics()
    while not stats_box and time.monotonic() - t < 10: time.sleep(0.01)
    st_ms = (time.monotonic() - t) * 1000
    print("%s read_statistics: %.0f ms (limit 1300)" % ("PASS" if st_ms < 1300 else "FAIL", st_ms))

    time.sleep(0.5)
    m._last_brew_time = 0.0
    m.brew(0x02, 1, 45, 5, 1)
    ev["started"].wait(5)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline and not any(p == 100 for _, p in ev["prog"]): time.sleep(0.01)
    time.sleep(0.4)
    lats = []
    for lbl, pct in [("tv0", 0), ("tv25", 25), ("tv50", 50), ("tv75", 75), ("tv100", 100)]:
        c = [t for t, p in ev["prog"] if p == pct]
        if lbl in sent_at and c:
            lats.append((c[0] - sent_at[lbl]) * 1000)
    print("%s brew progress latency (push sent -> brew_progress emitted), ms: %s (limit mean 150)" % (
        "PASS" if lats and statistics.mean(lats) < 150 else "FAIL", ["%.0f" % x for x in lats]))
    print("%s no brew errors: %s" % ("PASS" if not [e for e in ev["err"] if e.startswith("brew_error")] else "FAIL", [e for e in ev["err"] if e.startswith("brew_error")]))
    m.shutdown()


main()
