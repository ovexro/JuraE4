"""First-launch setup guide: key validation, copy buttons, help links."""
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt5.QtWidgets import QApplication, QPushButton, QLabel
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt
app = QApplication([]); import jura_app as J
def check(n, c, x=""): print(("PASS " if c else "FAIL ") + n, x, flush=True)

s = J.SetupScreen(); got = []; s.hash_submitted.connect(got.append)
GOOD = "0123456789abcdef" * 4
s._hash_input.setText(GOOD); s._on_submit()
check("valid key is emitted upper-case", got == [GOOD.upper()] and s._error_label.text() == "", got)
s._hash_input.setText(" : ".join(GOOD[i:i+8] for i in range(0, 64, 8)).replace(" : ", ":")); s._on_submit()
check("colons are accepted (as printed by some tools)", got[-1] == GOOD.upper())
s._hash_input.setText(" ".join(GOOD[i:i+16] for i in range(0, 64, 16))); s._on_submit()
check("spaces are accepted", got[-1] == GOOD.upper())
n = len(got); s._hash_input.setText("ABC123"); s._on_submit()
check("too short: error says how many characters, nothing emitted", len(got) == n and "64" in s._error_label.text() and "got 6" in s._error_label.text(), s._error_label.text())
s._hash_input.setText("Z" * 64); s._on_submit()
check("64 characters but not hex: clear error, nothing emitted", len(got) == n and "hexadecimal" in s._error_label.text(), s._error_label.text())
s._hash_input.setText(GOOD); QTest.keyClick(s._hash_input, Qt.Key_Return)
check("pressing Enter in the field submits", len(got) == n + 1)

texts = " ".join(l.text() for l in s.findChildren(QLabel))
check("guide names the phone-side tool and the steps", "PCAPdroid" in texts and "J.O.E." in texts and ".pcap" in texts)
check("commands point at the real extractor in this install", os.path.join(J.APP_DIR, "tools", "extract_hash.py") in s._cmd_extract and "pip install scapy" in s._cmd_install)
copy_btns = [b for b in s.findChildren(QPushButton) if b.text() == "Copy"]
check("two Copy buttons (install + extract)", len(copy_btns) == 2)
copy_btns[1].click(); check("Copy puts the extract command on the clipboard", QApplication.clipboard().text() == s._cmd_extract)
check("button confirms with 'Copied'", copy_btns[1].text() == "Copied")

opened = []
J.QDesktopServices.openUrl = staticmethod(lambda u: opened.append(u.toString()) or True)
for b in s.findChildren(QPushButton):
    if b.text() in ("Open the PCAPdroid page", "Open the full step-by-step guide"): b.click()
check("help buttons open the PCAPdroid page and the GitHub guide", opened == [J.PCAPDROID_URL, J.GUIDE_URL], opened)
check("guide anchor exists in the README", "#first-time-setup-auth-hash" in J.GUIDE_URL and "## First-time setup (auth hash)" in open(os.path.join(J.APP_DIR, "README.md")).read())
