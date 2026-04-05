"""
JURA Smart Connect BLE Protocol
Reverse-engineered protocol for controlling JURA coffee machines
via the Smart Connect (BlueFrog) Bluetooth dongle.
"""

import asyncio
import struct
import threading
import time
import logging
from dataclasses import dataclass
from typing import Optional

from bleak import BleakScanner, BleakClient
from PyQt5.QtCore import QObject, pyqtSignal

logger = logging.getLogger(__name__)

BREW_COOLDOWN_SECONDS = 10

# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

_S1 = [14, 4, 3, 2, 1, 13, 8, 11, 6, 15, 12, 7, 10, 5, 0, 9]
_S2 = [10, 6, 13, 12, 14, 11, 1, 9, 15, 7, 0, 5, 3, 2, 4, 8]


def _shuffle(src: int, cnt: int, k1: int, k2: int) -> int:
    i1 = (cnt >> 4) % 256
    i2 = _S1[(src + cnt + k1) % 256 % 16]
    i3 = _S2[(i2 + k2 + i1 - cnt - k1) % 256 % 16]
    i4 = _S1[(i3 + k1 + cnt - k2 - i1) % 256 % 16]
    return (i4 - cnt - k1) % 256 % 16


def encdec(data: bytes, key: int) -> bytes:
    """Symmetric encrypt/decrypt using the JURA nibble-substitution cipher."""
    out = bytearray(len(data))
    k1, k2 = key >> 4, key & 0x0F
    cnt = 0
    for i, b in enumerate(data):
        hi = _shuffle(b >> 4, cnt, k1, k2)
        cnt += 1
        lo = _shuffle(b & 0x0F, cnt, k1, k2)
        cnt += 1
        out[i] = (hi << 4) | lo
    return bytes(out)


def encrypt(data, key: int, set_last: bool = False) -> bytes:
    buf = bytearray(data)
    buf[0] = key
    if set_last:
        buf[-1] = key
    return encdec(buf, key)


def decrypt(data: bytes, key: int) -> bytes:
    result = encdec(data, key)
    if result[0] != key:
        raise ValueError(f"Key mismatch: {key:#04x} vs {result[0]:#04x}")
    return result


def bruteforce_key(encrypted_status: bytes) -> Optional[int]:
    for k in range(256):
        result = encdec(encrypted_status, k)
        if result[0] == k:
            return k
    return None


# ---------------------------------------------------------------------------
# BLE UUIDs
# ---------------------------------------------------------------------------

class UUID:
    MACHINE_STATUS   = "5a401524-ab2e-2548-c435-08c300000710"
    START_PRODUCT    = "5a401525-ab2e-2548-c435-08c300000710"
    PRODUCT_PROGRESS = "5a401527-ab2e-2548-c435-08c300000710"
    P_MODE           = "5a401529-ab2e-2548-c435-08c300000710"
    BARISTA_MODE     = "5a401530-ab2e-2548-c435-08c300000710"
    ABOUT_MACHINE    = "5a401531-ab2e-2548-c435-08c300000710"
    STATISTICS_CMD   = "5a401533-ab2e-2548-c435-08c300000710"
    STATISTICS_DATA  = "5a401534-ab2e-2548-c435-08c300000710"


# Known JURA / TopTronic BLE company IDs (varies by dongle firmware)
MANUFACTURER_IDS = [172, 171]  # 0x00AC (this dongle), 0x00AB (some documentation)

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

ALERTS = {
    0: ("Insert tray", "warning"),
    1: ("Fill water", "warning"),
    2: ("Empty grounds", "warning"),
    3: ("Empty tray", "warning"),
    4: ("Insert coffee bin", "error"),
    5: ("Outlet missing", "error"),
    6: ("Rear cover missing", "error"),
    7: ("Milk alert", "warning"),
    8: ("Fill system", "info"),
    9: ("System filling", "info"),
    10: ("No beans", "warning"),
    11: ("Welcome", "info"),
    12: ("Heating up", "info"),
    13: ("Coffee ready", "success"),
    17: ("Please wait", "info"),
    18: ("Coffee rinsing", "info"),
    25: ("Press rinse", "warning"),
    26: ("Goodbye", "info"),
    31: ("Enjoy your coffee", "success"),
    32: ("Filter alert", "warning"),
    33: ("Descaling alert", "warning"),
    34: ("Cleaning alert", "warning"),
    36: ("Energy save", "info"),
    39: ("Keys locked", "info"),
}


def parse_alerts(decrypted: bytes) -> list:
    active = []
    for i in range((len(decrypted) - 1) * 8):
        byte_off = (i >> 3) + 1
        bit_off = 7 - (i & 0b111)
        if byte_off < len(decrypted) and (decrypted[byte_off] >> bit_off) & 1:
            name, severity = ALERTS.get(i, (f"Alert #{i}", "info"))
            active.append((i, name, severity))
    return active


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@dataclass
class Product:
    code: int
    name: str
    strength_min: int = 1
    strength_max: int = 8
    strength_default: int = 4
    volume_min: int = 25
    volume_max: int = 120
    volume_step: int = 5
    volume_default: int = 60
    temp_default: int = 1
    icon_style: str = "coffee"


# Verified from EF1031 XML (article 15435, JURA E4)
# Strength: 1=Mild, 2=Normal, 3=Strong (NOT 1-8!)
# Temperature: 0=Low, 1=Normal, 2=High
E4_PRODUCTS = [
    Product(code=0x02, name="Espresso", icon_style="espresso",
            strength_min=1, strength_max=3, strength_default=2,
            volume_min=15, volume_max=240, volume_step=5, volume_default=45,
            temp_default=1),
    Product(code=0x03, name="Coffee", icon_style="coffee",
            strength_min=1, strength_max=3, strength_default=2,
            volume_min=15, volume_max=240, volume_step=5, volume_default=100,
            temp_default=1),
    Product(code=0x0D, name="Hot Water", icon_style="coffee",
            strength_min=0, strength_max=0, strength_default=0,
            volume_min=25, volume_max=300, volume_step=5, volume_default=220,
            temp_default=1),
]


# ---------------------------------------------------------------------------
# Device Info
# ---------------------------------------------------------------------------

@dataclass
class DeviceInfo:
    address: str
    name: str
    key: int
    article_number: int
    rssi: int


# ---------------------------------------------------------------------------
# BLE Manager
# ---------------------------------------------------------------------------

class BLEManager(QObject):
    scan_finished  = pyqtSignal(list)
    connect_ok     = pyqtSignal(str)
    connect_fail   = pyqtSignal(str)
    disconnected   = pyqtSignal()
    status_update  = pyqtSignal(list)
    brew_started   = pyqtSignal()
    brew_error     = pyqtSignal(str)
    error          = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._loop = None
        self._client = None
        self._key = 0
        self._lock = threading.Lock()
        self._connected = False
        self._brewing = False
        self._last_brew_time = 0.0
        self._hb_task = None
        self._st_task = None
        self._last_address = None
        self._last_key = 0
        self._write_types = {}  # per-UUID cache: "request" or "command"
        ready = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(ready,), daemon=True)
        self._thread.start()
        ready.wait(timeout=5)

    def _run(self, ready):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        ready.set()
        self._loop.run_forever()

    def _submit(self, coro):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)

    @property
    def is_connected(self):
        with self._lock:
            return self._connected

    @property
    def is_brewing(self):
        with self._lock:
            return self._brewing

    def _set_connected(self, value):
        with self._lock:
            self._connected = value
            if not value:
                self._brewing = False

    def _set_brewing(self, value):
        with self._lock:
            self._brewing = value

    def scan(self):
        self._submit(self._do_scan())

    def connect_machine(self, address, key):
        self._submit(self._do_connect(address, key))

    def disconnect_machine(self):
        self._submit(self._do_disconnect())

    def brew(self, product_code, strength, volume_ml, volume_step, temperature):
        # Validate parameters
        if not (1 <= strength <= 8):
            self.brew_error.emit(f"Invalid strength: {strength}")
            return
        if not (1 <= temperature <= 2):
            self.brew_error.emit(f"Invalid temperature: {temperature}")
            return
        units = volume_ml // volume_step
        if not (1 <= units <= 60):
            self.brew_error.emit(f"Invalid volume: {volume_ml}ml")
            return
        with self._lock:
            if self._brewing:
                self.brew_error.emit("A brew is already in progress")
                return
            now = time.monotonic()
            if now - self._last_brew_time < BREW_COOLDOWN_SECONDS:
                remaining = int(BREW_COOLDOWN_SECONDS - (now - self._last_brew_time))
                self.brew_error.emit(f"Please wait {remaining}s between brews")
                return
        self._submit(self._do_brew(product_code, strength, units, temperature))

    def disconnect_and_wait(self, timeout=3):
        """Synchronous disconnect — blocks until done or timeout. For use during app shutdown."""
        if self._loop and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._do_disconnect(), self._loop)
            try:
                future.result(timeout=timeout)
            except Exception:
                pass

    def shutdown(self):
        self._set_connected(False)
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

    # -- async internals --

    async def _do_scan(self):
        try:
            devices = await BleakScanner.discover(timeout=10, return_adv=True)
            results = []
            for addr, (dev, adv) in devices.items():
                if adv.local_name == "TT214H BlueFrog":
                    # Try known JURA manufacturer IDs
                    man = b""
                    for mid in MANUFACTURER_IDS:
                        man = adv.manufacturer_data.get(mid, b"")
                        if man:
                            break
                    # Fallback: use any manufacturer data available
                    if not man and adv.manufacturer_data:
                        first_id = next(iter(adv.manufacturer_data))
                        man = adv.manufacturer_data[first_id]
                        logger.info("Using manufacturer data from company %d", first_id)
                    key = man[0] if len(man) >= 1 else 0
                    art = struct.unpack_from('<H', man, 4)[0] if len(man) >= 6 else 0
                    results.append(DeviceInfo(addr, adv.local_name, key, art, adv.rssi))
            self.scan_finished.emit(results)
        except Exception as e:
            logger.exception("Scan failed")
            self.error.emit(f"Scan failed: {e}")
            self.scan_finished.emit([])

    async def _write_char(self, uuid, data):
        """Write to a GATT characteristic with automatic write-type handling.

        Tries write-without-response first (works on this dongle), falls back
        to write-with-response. Caches the working write type per-UUID.
        """
        # Fast path: reuse a previously successful write type
        wtype = self._write_types.get(uuid)
        if wtype == "command":
            await self._client.write_gatt_char(uuid, data, response=False)
            return
        if wtype == "request":
            await self._client.write_gatt_char(uuid, data, response=True)
            return

        # First attempt — try write-without-response (works on BlueFrog)
        try:
            await self._client.write_gatt_char(uuid, data, response=False)
            self._write_types[uuid] = "command"
            return
        except Exception as e:
            logger.debug("Write Command to %s failed (%s), trying Write Request", uuid, e)

        # Fallback — write-with-response (ATT Write Request)
        await self._client.write_gatt_char(uuid, data, response=True)
        self._write_types[uuid] = "request"

    async def _do_connect(self, address, key):
        try:
            self._client = BleakClient(address, timeout=15)
            await self._client.connect()

            if key == 0:
                raw = await self._client.read_gatt_char(UUID.MACHINE_STATUS)
                key = bruteforce_key(raw)
                if key is None:
                    await self._client.disconnect()
                    self.connect_fail.emit("Could not determine encryption key")
                    return
                logger.info("Encryption key recovered via brute-force")
            self._key = key
            self._last_address = address
            self._last_key = key

            # Send initial heartbeat ("stay in BLE mode")
            hb = encrypt(bytes([0x00, 0x7F, 0x80]), self._key)
            await self._write_char(UUID.P_MODE, hb)

            # Unlock Barista Mode so the dongle accepts brew commands.
            # Ref: Jutta-Proto CoffeeMaker::unlock() writes {0x00, 0x00}
            # to the BARISTA_MODE characteristic.
            try:
                unlock_cmd = encrypt(bytes([0x00, 0x00]), self._key)
                await self._write_char(UUID.BARISTA_MODE, unlock_cmd)
                logger.info("Barista mode unlocked")
            except Exception as e:
                logger.debug("Barista mode unlock skipped (%s)", e)

            about = await self._client.read_gatt_char(UUID.ABOUT_MACHINE)
            info = about.decode('ascii', errors='replace').strip('\x00').strip()

            self._set_connected(True)
            self._hb_task = asyncio.ensure_future(self._heartbeat_loop())
            self._st_task = asyncio.ensure_future(self._status_loop())
            self.connect_ok.emit(info if info else "JURA E4")
        except Exception as e:
            logger.exception("Connect failed")
            self.connect_fail.emit(str(e))

    async def _do_disconnect(self):
        self._set_connected(False)
        self._write_types.clear()
        for task in (self._hb_task, self._st_task):
            if task:
                task.cancel()
        if self._client and self._client.is_connected:
            try:
                dc = encrypt(bytes([0x00, 0x7F, 0x81]), self._key)
                await self._write_char(UUID.P_MODE, dc)
            except Exception:
                pass
            try:
                await self._client.disconnect()
            except Exception:
                pass
        self.disconnected.emit()

    async def _heartbeat_loop(self):
        while self._connected:
            if not self._client or not self._client.is_connected:
                self._set_connected(False)
                self.disconnected.emit()
                return
            try:
                hb = encrypt(bytes([0x00, 0x7F, 0x80]), self._key)
                await self._write_char(UUID.P_MODE, hb)
            except Exception:
                logger.warning("Heartbeat failed, disconnecting")
                self._set_connected(False)
                self.disconnected.emit()
                return
            await asyncio.sleep(9)

    async def _status_loop(self):
        fail_count = 0
        while self._connected:
            if not self._client or not self._client.is_connected:
                self._set_connected(False)
                self.disconnected.emit()
                return
            try:
                raw = await self._client.read_gatt_char(UUID.MACHINE_STATUS)
                data = decrypt(raw, self._key)
                alerts = parse_alerts(data)
                self.status_update.emit(list(alerts))
                fail_count = 0
                # Check if brew completed (bit 31 = "Enjoy your coffee")
                if self._brewing and any(bit == 31 for bit, _, _ in alerts):
                    self._set_brewing(False)
            except ValueError:
                logger.warning("Status decryption failed (key mismatch)")
            except Exception:
                fail_count += 1
                if fail_count >= 3:
                    logger.warning("Status loop: 3 consecutive failures, disconnecting")
                    self._set_connected(False)
                    self.disconnected.emit()
                    return
            await asyncio.sleep(4)

    async def _do_brew(self, code, strength, volume_units, temperature):
        if not self._connected or not self._client or not self._client.is_connected:
            self.brew_error.emit("Not connected")
            return
        try:
            self._set_brewing(True)
            with self._lock:
                self._last_brew_time = time.monotonic()
            data = bytearray(18)
            data[1] = code
            data[3] = strength
            data[4] = volume_units
            data[7] = temperature
            cmd = encrypt(data, self._key, set_last=True)
            await self._write_char(UUID.START_PRODUCT, cmd)
            self.brew_started.emit()
        except Exception as e:
            self._set_brewing(False)
            self.brew_error.emit(str(e))
