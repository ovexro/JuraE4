#!/usr/bin/env python3
"""Render the README screenshots straight from the app's own widgets.

Offscreen, with fixed sample data: no coffee machine, no network, no desktop
clutter and no real IP address in the pictures. Re-run after any design change:

    python3 tools/make_screenshots.py            # writes docs/screenshots/*.png
"""
import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_SCALE_FACTOR", "2")          # crisp on high-DPI screens
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtTest import QTest

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
app = QApplication([]); app.setStyle("Fusion")
import jura_app as J
from jura_wifi_v2 import MachineStatistics

pal = QPalette()
for role, col in ((QPalette.Window, J.BG), (QPalette.WindowText, J.TEXT), (QPalette.Base, J.BG_ELEVATED),
                  (QPalette.AlternateBase, J.BG_CARD), (QPalette.Text, J.TEXT), (QPalette.Button, J.BG_CARD),
                  (QPalette.ButtonText, J.TEXT), (QPalette.Highlight, J.GOLD), (QPalette.HighlightedText, J.TEXT_DARK)):
    pal.setColor(role, QColor(col))
app.setPalette(pal)

OUT = os.path.join(ROOT, "docs", "screenshots"); os.makedirs(OUT, exist_ok=True)
W, H = 1060, 740


class Settings:                      # defaults only -- never reads the user's real settings
    def get_product(self, name): return {}
    def get(self, key, default=None): return default


def save(widget, name, size=(W, H), wait=300):
    host = QMainWindow(); host.setStyleSheet(J.STYLESHEET); host.setCentralWidget(widget)
    host.resize(*size); host.show(); QTest.qWait(wait)
    path = os.path.join(OUT, name); host.grab().save(path); print("wrote", os.path.relpath(path, ROOT))
    host.takeCentralWidget(); widget.setParent(None)


def dashboard():
    d = J.DashboardScreen(Settings())
    d.set_connected(); d.set_machine_info("JURA E4 — WiFi V2")
    d.update_alerts([(13, "Coffee ready", "success"), (36, "Energy save", "info"), (39, "Keys locked", "info")])
    return d


save(dashboard(), "dashboard.png")

d = dashboard()                      # mid-brew: Espresso animating, the other cards locked
d.begin_brew_request(0x02); d.on_brew_started(); d.on_brew_progress(60, 60)
QTest.qWait(1800)                    # let the fill animation ease toward 60 %
save(d, "brewing.png", wait=200)

d = dashboard()                      # blocking alerts shown as pills
d.update_alerts([(1, "Fill water", "warning"), (10, "No beans", "warning"), (34, "Cleaning alert", "warning")])
save(d, "attention.png")

st = J.StatisticsScreen()
st.update_statistics(MachineStatistics(778, 13, 710, 52, 35, 82, -1, 1, 1, 0))
save(st, "statistics.png", size=(W, 800))

J.APP_DIR = "/home/user/.local/share/jura-desktop"      # generic path in the setup guide's commands
save(J.SetupScreen(), "setup.png", size=(W, 1290), wait=400)

dlg = J.BrewConfirmDialog("Espresso", 2, 45, 1); dlg.show(); QTest.qWait(250)
path = os.path.join(OUT, "confirm.png"); dlg.grab().save(path); print("wrote", os.path.relpath(path, ROOT))
