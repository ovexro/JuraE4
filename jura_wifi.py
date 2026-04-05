"""
JURA ESP32 WiFi-Serial Bridge Client
HTTP communication with the ESP32-WROOM-32 bridge that connects to the JURA E4
coffee machine via serial protocol over the service port.

The ESP32 runs a MicroPython HTTP server on port 80 with:
  POST /api          → send raw JURA command (body = command string)
  GET  /status       → machine type via TY:
  POST /brew/<name>  → trigger product (espresso, coffee, hotwater)

Replaces the old TCP-based WiFiManager that targeted the WiFi Connect V2 dongle
(which turned out to be cloud-only with no local API).
"""

import json
import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional, List
from urllib.request import Request, urlopen

from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_ESP32_IP = "192.168.1.108"
ESP32_PORT = 80
HTTP_TIMEOUT = 5  # seconds

BREW_COOLDOWN_SECONDS = 10
STATUS_POLL_INTERVAL = 4
HEARTBEAT_INTERVAL = 9

# E4 product code → ESP32 brew endpoint name
E4_PRODUCT_NAMES = {
    0x02: "espresso",
    0x03: "coffee",
    0x0D: "hotwater",
}

# E4 product code → FA: button hex (for raw commands)
E4_BUTTON_MAP = {
    0x02: "04",  # Espresso → button 1
    0x03: "05",  # Coffee   → button 2
    0x0D: "06",  # Hot Water → button 3
}


# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------

@dataclass
class WiFiDeviceInfo:
    ip: str
    port: int           # HTTP port (always 80 for ESP32)
    name: str           # Bridge name
    firmware: str       # MicroPython version
    machine_type: str   # e.g. "EF1031M V01.05"
    mac: str


# ---------------------------------------------------------------------------
# ESP32 Bridge Manager
# ---------------------------------------------------------------------------

class WiFiManager(QObject):
    """Manages HTTP communication with the JURA ESP32 WiFi-serial bridge.

    Exposes the same signal interface as BLEManager so the GUI can use
    either connection type transparently.
    """

    scan_finished  = pyqtSignal(list)    # [WiFiDeviceInfo, ...]
    connect_ok     = pyqtSignal(str)     # machine info
    connect_fail   = pyqtSignal(str)     # error message
    disconnected   = pyqtSignal()
    status_update  = pyqtSignal(list)    # alerts [(bit, name, severity), ...]
    brew_started   = pyqtSignal()
    brew_error     = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._lock = threading.Lock()
        self._connected = False
        self._brewing = False
        self._last_brew_time = 0.0
        self._base_url: Optional[str] = None
        self._stop_event = threading.Event()
        self._hb_thread: Optional[threading.Thread] = None
        self._st_thread: Optional[threading.Thread] = None

    # -- Thread-safe properties --

    @property
    def is_connected(self):
        with self._lock:
            return self._connected

    @property
    def is_brewing(self):
        with self._lock:
            return self._brewing

    def _set_connected(self, value: bool):
        with self._lock:
            self._connected = value
            if not value:
                self._brewing = False

    def _set_brewing(self, value: bool):
        with self._lock:
            self._brewing = value

    # -- HTTP helpers --

    def _http_get(self, path: str, timeout: float = HTTP_TIMEOUT) -> Optional[dict]:
        """GET request to the ESP32, return parsed JSON or None."""
        if not self._base_url:
            return None
        try:
            url = f"{self._base_url}{path}"
            with urlopen(Request(url), timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            logger.debug("HTTP GET %s failed: %s", path, exc)
            return None

    def _http_post(self, path: str, body: str = "", timeout: float = HTTP_TIMEOUT) -> Optional[dict]:
        """POST request to the ESP32, return parsed JSON or None."""
        if not self._base_url:
            return None
        try:
            url = f"{self._base_url}{path}"
            data = body.encode("ascii") if body else b""
            req = Request(url, data=data, method="POST")
            req.add_header("Content-Type", "text/plain")
            with urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            logger.debug("HTTP POST %s body=%r failed: %s", path, body, exc)
            return None

    @staticmethod
    def _probe_esp32(ip: str, port: int = ESP32_PORT, timeout: float = 3) -> Optional[dict]:
        """Check if an ESP32 bridge is reachable at the given IP."""
        try:
            url = f"http://{ip}:{port}/status"
            with urlopen(Request(url), timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    # -- Public API (called from Qt main thread) --

    def scan(self):
        threading.Thread(target=self._do_scan, daemon=True).start()

    def connect_machine(self, ip: str, port: int):
        threading.Thread(target=self._do_connect, args=(ip, port), daemon=True).start()

    def disconnect_machine(self):
        self._do_disconnect()

    def brew(self, product_code, strength, volume_ml, volume_step, temperature):
        with self._lock:
            if self._brewing:
                self.brew_error.emit("A brew is already in progress")
                return
            now = time.monotonic()
            if now - self._last_brew_time < BREW_COOLDOWN_SECONDS:
                remaining = int(BREW_COOLDOWN_SECONDS - (now - self._last_brew_time))
                self.brew_error.emit(f"Please wait {remaining}s between brews")
                return
        threading.Thread(
            target=self._do_brew,
            args=(product_code, strength, volume_ml, volume_step, temperature),
            daemon=True,
        ).start()

    def disconnect_and_wait(self, timeout=3):
        self._do_disconnect()

    def shutdown(self):
        self._do_disconnect()

    # -- Raw command API (for testing / custom commands) --

    def send_command(self, cmd: str) -> Optional[str]:
        """Send a raw JURA command via the ESP32 bridge. Returns the response string."""
        if not self._connected or not self._base_url:
            return None
        result = self._http_post("/api", cmd)
        if result and "response" in result:
            return result["response"]
        return None

    # ======================================================================
    # Discovery
    # ======================================================================

    def _do_scan(self):
        """Check if the ESP32 bridge is reachable at the default IP."""
        try:
            results: List[WiFiDeviceInfo] = []

            logger.info("WiFi scan: checking ESP32 bridge at %s...", DEFAULT_ESP32_IP)
            data = self._probe_esp32(DEFAULT_ESP32_IP)
            if data:
                machine_type = data.get("type", "Unknown")
                results.append(WiFiDeviceInfo(
                    ip=DEFAULT_ESP32_IP,
                    port=ESP32_PORT,
                    name="JURA ESP32 Bridge",
                    firmware="MicroPython",
                    machine_type=machine_type,
                    mac="",
                ))
                logger.info("WiFi scan: ESP32 found — %s", machine_type)

            self.scan_finished.emit(results)
        except Exception as exc:
            logger.exception("WiFi scan failed")
            self.error.emit(f"Scan failed: {exc}")
            self.scan_finished.emit([])

    # ======================================================================
    # Connection
    # ======================================================================

    def _do_connect(self, ip: str, port: int):
        try:
            if port <= 0:
                port = ESP32_PORT

            self._base_url = f"http://{ip}:{port}"
            logger.info("WiFi connect: %s", self._base_url)

            data = self._http_get("/status", timeout=5)
            if not data:
                self.connect_fail.emit(
                    f"ESP32 bridge not responding at {ip}:{port}\n"
                    "Check that the ESP32 is powered on and connected to WiFi."
                )
                self._base_url = None
                return

            machine_type = data.get("type", "")
            logger.info("WiFi connected: %s — %s", self._base_url, machine_type)

            self._set_connected(True)
            self._stop_event.clear()

            # Start background threads
            self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
            self._hb_thread.start()
            self._st_thread = threading.Thread(target=self._status_loop, daemon=True)
            self._st_thread.start()

            display = machine_type
            if display.lower().startswith("ty:"):
                display = display[3:]
            self.connect_ok.emit(display.strip() or f"ESP32 {ip}")

        except Exception as exc:
            logger.exception("WiFi connect failed")
            self.connect_fail.emit(str(exc))

    def _do_disconnect(self):
        with self._lock:
            was_connected = self._connected
            self._connected = False
            self._brewing = False
        self._stop_event.set()
        self._base_url = None
        if was_connected:
            self.disconnected.emit()

    # ======================================================================
    # Background loops
    # ======================================================================

    def _heartbeat_loop(self):
        fail_count = 0
        while not self._stop_event.is_set():
            with self._lock:
                if not self._connected:
                    return
            try:
                data = self._http_get("/status", timeout=3)
                if data:
                    fail_count = 0
                else:
                    fail_count += 1
                    if fail_count >= 3:
                        logger.warning("WiFi heartbeat: 3 failures, disconnecting")
                        self._do_disconnect()
                        return
            except Exception:
                fail_count += 1
            self._stop_event.wait(HEARTBEAT_INTERVAL)

    def _status_loop(self):
        fail_count = 0
        while not self._stop_event.is_set():
            with self._lock:
                if not self._connected:
                    return
            try:
                result = self._http_post("/api", "IC:")
                if result and "response" in result:
                    alerts = self._parse_status(result["response"])
                    self.status_update.emit(alerts)
                    fail_count = 0
                else:
                    fail_count += 1
                    if fail_count >= 5:
                        logger.warning("WiFi status: 5 failures, disconnecting")
                        self._do_disconnect()
                        return
            except Exception:
                fail_count += 1
            self._stop_event.wait(STATUS_POLL_INTERVAL)

    @staticmethod
    def _parse_status(response: str) -> list:
        """Parse IC: response into alert tuples compatible with BLE format."""
        alerts = []
        lower = response.lower().strip()
        if lower.startswith("ic:") or "ok" in lower:
            alerts.append((13, "Coffee ready", "success"))
        return alerts

    # ======================================================================
    # Brewing
    # ======================================================================

    def _do_brew(self, product_code, strength, volume_ml, volume_step, temperature):
        if not self._connected or not self._base_url:
            self.brew_error.emit("Not connected")
            return

        product_name = E4_PRODUCT_NAMES.get(product_code)
        button = E4_BUTTON_MAP.get(product_code)
        if not product_name or not button:
            self.brew_error.emit(f"Unknown product code: {product_code:#04x}")
            return

        try:
            self._set_brewing(True)
            with self._lock:
                self._last_brew_time = time.monotonic()

            logger.info("WiFi brew: %s (FA:%s, strength=%d, vol=%dml, temp=%d)",
                        product_name, button, strength, volume_ml, temperature)

            result = self._http_post(f"/brew/{product_name}")
            if result is None:
                self.brew_error.emit("No response from ESP32 bridge")
                self._set_brewing(False)
                return

            response = result.get("response", "")
            logger.info("WiFi brew response: %s", response)
            self.brew_started.emit()

            # Auto-clear brewing flag after estimated brew time
            estimated_s = max(volume_ml * 0.25, 5)
            self._stop_event.wait(estimated_s)
            self._set_brewing(False)

        except Exception as exc:
            self._set_brewing(False)
            self.brew_error.emit(str(exc))
