"""UDP discovery: reply parsing, broadcast targets, multi-device collection, scan fallback text."""
import os, sys, socket, threading, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jura_wifi_v2 as W
def check(n, c, x=""): print(("PASS " if c else "FAIL ") + n, x, flush=True)
M = W.WiFiV2Manager

def reply(fw=b"TT237W", ssid=b"Kitchen-JURA", machine=b"JURA E4", mac=bytes.fromhex("c05d89c86968")):
    d = bytearray(120); d[2:4] = b"\xa5\xf3"
    d[4:4 + len(fw)] = fw; d[20:20 + len(ssid)] = ssid; d[52:52 + len(machine)] = machine; d[103:109] = mac
    return bytes(d)

# ---- parsing ----
dev = M._parse_discovery_reply(reply(), ("192.168.1.50", 51515))
check("valid reply parsed", dev and (dev.ip, dev.firmware, dev.name, dev.machine_type, dev.mac) == ("192.168.1.50", "TT237W", "Kitchen-JURA", "JURA E4", "c0:5d:89:c8:69:68"), dev)
check("too short rejected", M._parse_discovery_reply(reply()[:100], ("1.1.1.1", 1)) is None)
check("wrong magic rejected", M._parse_discovery_reply(b"\x00\x10\x00\x00" + reply()[4:], ("1.1.1.1", 1)) is None)
check("empty SSID gets a default name", M._parse_discovery_reply(reply(ssid=b""), ("1.1.1.1", 1)).name == "WiFi Connect V2")

# ---- broadcast addresses ----
sample = ("1: lo    inet 127.0.0.1/8 scope host lo\\       valid_lft forever\n"
          "2: enp1s0    inet 192.168.2.134/24 brd 192.168.2.255 scope global dynamic noprefixroute enp1s0\n"
          "3: wlan0    inet 10.0.0.7/16 brd 10.0.255.255 scope global wlan0\n")
check("broadcast addresses read from `ip addr`", M._parse_broadcast_addresses(sample) == ["192.168.2.255", "10.0.255.255"], M._parse_broadcast_addresses(sample))
t = M._broadcast_targets(); check("targets always include the limited broadcast, all IPv4", t[0] == "255.255.255.255" and all(x.count(".") == 3 for x in t), t)

# ---- loopback responders ----
PORT = 51991
def responder(host, payloads, stop):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((host, PORT)); s.settimeout(0.2)
    while not stop.is_set():
        try: _, addr = s.recvfrom(64)
        except socket.timeout: continue
        for p in payloads: s.sendto(p, addr)
    s.close()
stop = threading.Event()
def start(host, payloads):
    th = threading.Thread(target=responder, args=(host, payloads, stop), daemon=True); th.start(); time.sleep(0.1)

start("127.0.0.1", [b"junk", reply(), reply()])            # garbage first, then the same device twice
t0 = time.monotonic(); r = W.WiFiV2Manager._udp_discover(3, targets=["127.0.0.1"], port=PORT); dt = time.monotonic() - t0
check("one device found despite garbage + duplicate replies", len(r) == 1 and r[0].machine_type == "JURA E4", [(d.ip, d.mac) for d in r])
check("returns shortly after the replies stop (not the full 3 s)", dt < 1.5, "%.2f s" % dt)
start("127.0.0.2", [reply(ssid=b"Office-JURA", mac=bytes.fromhex("aabbccddeeff"))])
r = W.WiFiV2Manager._udp_discover(3, targets=["127.0.0.1", "127.0.0.2"], port=PORT)
check("two dongles on the network are both found", sorted(d.ip for d in r) == ["127.0.0.1", "127.0.0.2"] and {d.name for d in r} == {"Kitchen-JURA", "Office-JURA"}, [(d.ip, d.name) for d in r])
stop.set(); time.sleep(0.4)
t0 = time.monotonic(); r = W.WiFiV2Manager._udp_discover(0.7, targets=["127.0.0.1"], port=PORT); dt = time.monotonic() - t0
check("nobody answers -> empty list after the timeout", r == [] and 0.6 < dt < 1.3, "%.2f s" % dt)
check("an unreachable target doesn't break the scan", W.WiFiV2Manager._udp_discover(0.3, targets=["203.0.113.1", "999.1.1.1"], port=PORT) == [])

# ---- app: what the user sees when the scan finds nothing ----
from PyQt5.QtWidgets import QApplication
app = QApplication([]); import jura_app as J
class Conn:
    shown = []
    def show_fallback(s, text, ip): Conn.shown.append((text, ip))
    def __getattr__(s, n): return lambda *a, **k: None
class Set:
    def get(s, k, d=None): return {"dongle_ip": "192.168.1.77"}.get(k, d)
class Wf:
    def scan(s): Wf.scans = getattr(Wf, "scans", 0) + 1
a = J.JuraApp.__new__(J.JuraApp); a._conn_screen = Conn(); a._settings = Set(); a._wifi = Wf(); a._offline_by_user = False
a._reconnecting = False; a._tried_scan = False
a._on_connect_failed("Connection refused by the dongle.\nIf J.O.E. is open on your phone, close it first")
check("first failure triggers a scan and remembers the reason", Wf.scans == 1 and a._tried_scan and "J.O.E." in a._last_connect_error)
a._on_scan_finished([])
text, ip = Conn.shown[-1]
check("empty scan: says nothing found AND repeats the real error", "No JURA machine found" in text and "close it first" in text, text.replace("\n", " | "))
check("manual field is pre-filled with the saved IP, not a hard-coded one", ip == "192.168.1.77", ip)
b = J.JuraApp.__new__(J.JuraApp); b._conn_screen = Conn(); b._settings = Set(); b._offline_by_user = False; b._last_connect_error = None
b._on_scan_finished([]); check("empty scan with no earlier error: plain message", "Last connection attempt" not in Conn.shown[-1][0])
