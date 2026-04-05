"""main.py — JURA Coffee Machine WiFi-Serial Bridge.

Speaks the JURA 4-byte serial protocol over UART to the machine,
and exposes an HTTP API on port 80 for the desktop app.

API:
  POST /api         body = raw command (e.g. "TY:")  → returns response
  GET  /status      → machine type via TY:
  POST /brew/<code> → trigger product by FA: button code
"""

import socket
import time
import json
import network
from machine import UART, Pin

# ---------------------------------------------------------------------------
# JURA 4-byte serial encoding
# ---------------------------------------------------------------------------
# Each byte is encoded as 4 UART bytes. Bits 2 and 5 carry data.
# Base byte: 0xDB (1101_1011). 9600 baud, 8ms between 4-byte groups.

def jura_encode_byte(b):
    out = bytearray(4)
    for i in range(4):
        out[i] = 0xDB
        out[i] |= ((b >> (i * 2)) & 1) << 2
        out[i] |= ((b >> (i * 2 + 1)) & 1) << 5
    return out


def jura_decode_byte(data):
    b = 0
    for i in range(4):
        b |= ((data[i] >> 2) & 1) << (i * 2)
        b |= ((data[i] >> 5) & 1) << (i * 2 + 1)
    return b


# ---------------------------------------------------------------------------
# UART communication with the machine
# ---------------------------------------------------------------------------

uart = UART(2, baudrate=9600, tx=16, rx=17, timeout=100)


def send_command(cmd):
    """Send a JURA command string, return the decoded response."""
    if not cmd.endswith("\r\n"):
        cmd += "\r\n"

    # Flush any stale data in RX buffer
    while uart.any():
        uart.read()

    # Encode and send each byte with 8ms inter-group delay
    for ch in cmd.encode("ascii"):
        uart.write(jura_encode_byte(ch))
        time.sleep_ms(8)

    # Wait for response (machine takes ~50-500ms)
    time.sleep_ms(500)

    # Read and decode response
    raw = bytearray()
    deadline = time.ticks_add(time.ticks_ms(), 1000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if uart.any():
            chunk = uart.read()
            if chunk:
                raw.extend(chunk)
                deadline = time.ticks_add(time.ticks_ms(), 200)
        else:
            time.sleep_ms(10)

    if len(raw) < 4:
        return ""

    # Decode 4-byte groups
    decoded = bytearray()
    for i in range(0, len(raw) - 3, 4):
        decoded.append(jura_decode_byte(raw[i:i + 4]))

    return safe_decode(decoded).strip()


def send_and_listen(cmd, listen_ms=5000):
    """Send a JURA command, then listen for an extended period collecting all responses.
    Returns a list of decoded response strings (one per line/message)."""
    if not cmd.endswith("\r\n"):
        cmd += "\r\n"

    while uart.any():
        uart.read()

    for ch in cmd.encode("ascii"):
        uart.write(jura_encode_byte(ch))
        time.sleep_ms(8)

    time.sleep_ms(300)

    responses = []
    raw = bytearray()
    deadline = time.ticks_add(time.ticks_ms(), listen_ms)
    gap_deadline = time.ticks_add(time.ticks_ms(), 2000)

    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if uart.any():
            chunk = uart.read()
            if chunk:
                raw.extend(chunk)
                gap_deadline = time.ticks_add(time.ticks_ms(), 1000)
        else:
            # If we have data and hit a gap, decode what we have so far
            if len(raw) >= 4 and time.ticks_diff(gap_deadline, time.ticks_ms()) <= 0:
                decoded = bytearray()
                for i in range(0, len(raw) - 3, 4):
                    decoded.append(jura_decode_byte(raw[i:i + 4]))
                text = decoded.decode("ascii", "replace").strip()
                if text:
                    responses.append(text)
                raw = bytearray()
                gap_deadline = time.ticks_add(time.ticks_ms(), 1000)
            time.sleep_ms(10)

    # Decode any remaining data
    if len(raw) >= 4:
        decoded = bytearray()
        for i in range(0, len(raw) - 3, 4):
            decoded.append(jura_decode_byte(raw[i:i + 4]))
        text = decoded.decode("ascii", "replace").strip()
        if text:
            responses.append(text)

    return responses


def send_raw(text):
    """Encode and send a string over UART (no flush, no read)."""
    if not text.endswith("\r\n"):
        text += "\r\n"
    for ch in text.encode("ascii"):
        uart.write(jura_encode_byte(ch))
        time.sleep_ms(8)


def safe_decode(ba):
    """Decode bytearray to string, replacing non-ASCII with '?'."""
    chars = []
    for b in ba:
        chars.append(chr(b) if 32 <= b < 127 or b in (10, 13) else '?')
    return "".join(chars)


def read_until(marker, timeout_ms=3000):
    """Read and decode UART data until a marker string is found or timeout."""
    raw = bytearray()
    decoded_so_far = ""
    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        if uart.any():
            chunk = uart.read()
            if chunk:
                raw.extend(chunk)
                # Try to decode what we have
                if len(raw) >= 4:
                    decoded = bytearray()
                    for i in range(0, len(raw) - 3, 4):
                        decoded.append(jura_decode_byte(raw[i:i + 4]))
                    decoded_so_far = safe_decode(decoded)
                    if marker in decoded_so_far:
                        return decoded_so_far.strip()
        else:
            time.sleep_ms(5)
    return decoded_so_far.strip()


def do_handshake(t2_response):
    """Perform the full @T1/@T2/@T3 handshake atomically.
    t2_response: the hex string to send as @t2:<value> (e.g. '8120000000')
    Returns a log of all steps."""
    log = []

    # Flush
    while uart.any():
        uart.read()

    # Step 1: Send @T1
    send_raw("@T1")
    log.append("TX: @T1")

    # Step 2: Wait for @T2 (which includes @t1 ack in same buffer)
    # From testing: machine sends "@t1\r\n@T2:81C001B628" together
    resp = read_until("@T2", timeout_ms=5000)
    log.append("RX: " + resp)

    if "@T2" not in resp:
        log.append("FAIL: No @T2 challenge received")
        return log

    # Step 3: Send @t2:<response> immediately
    t2_cmd = "@t2:" + t2_response
    send_raw(t2_cmd)
    log.append("TX: " + t2_cmd)

    # Step 4: Wait for @T3 or rejection
    resp = read_until("@T3", timeout_ms=5000)
    if not resp:
        # Maybe machine sent something else (rejection)
        resp = read_until("@t0", timeout_ms=3000)
    log.append("RX: " + resp)

    if "@T3" in resp:
        # Step 5: Acknowledge with @t3
        send_raw("@t3")
        log.append("TX: @t3")

        # Listen for post-auth data
        time.sleep_ms(500)
        extra = read_until("\n", timeout_ms=3000)
        if extra:
            log.append("RX post-auth: " + extra)

        log.append("STATUS: HANDSHAKE COMPLETE")

        # Test: try FA:05 now
        send_raw("FA:05")
        log.append("TX: FA:05 (test brew)")
        brew_resp = read_until("\n", timeout_ms=3000)
        log.append("RX: " + brew_resp)
    else:
        log.append("STATUS: HANDSHAKE FAILED")

    return log


# ---------------------------------------------------------------------------
# E4 product button mapping (FA: codes)
# ---------------------------------------------------------------------------

PRODUCTS = {
    "espresso": "04",
    "coffee":   "05",
    "hotwater": "06",
    "water":    "06",
}

# ---------------------------------------------------------------------------
# HTTP server
# ---------------------------------------------------------------------------

def parse_request(data):
    """Parse HTTP request, return (method, path, body)."""
    text = data.decode("ascii", "replace")
    lines = text.split("\r\n")
    first = lines[0].split(" ") if lines else []
    method = first[0] if len(first) >= 2 else "GET"
    path = first[1] if len(first) >= 2 else "/"
    body = text.split("\r\n\r\n", 1)[-1] if "\r\n\r\n" in text else ""
    return method, path, body.strip()


def send_response(cl, status, body, content_type="application/json"):
    status_text = {200: "OK", 400: "Bad Request", 404: "Not Found", 500: "Error"}
    cl.send(f"HTTP/1.1 {status} {status_text.get(status, 'OK')}\r\n")
    cl.send(f"Content-Type: {content_type}\r\n")
    cl.send("Access-Control-Allow-Origin: *\r\n")
    cl.send(f"Content-Length: {len(body)}\r\n")
    cl.send("Connection: close\r\n\r\n")
    cl.send(body)


def json_response(cl, status, data):
    body = json.dumps(data)
    send_response(cl, status, body)


def handle_request(cl, method, path, body):
    """Route and handle an HTTP request."""
    path_lower = path.lower().rstrip("/")

    # POST /api — send raw JURA command
    if path_lower == "/api" and method == "POST":
        if not body:
            json_response(cl, 400, {"error": "Empty command"})
            return
        response = send_command(body)
        json_response(cl, 200, {"command": body, "response": response})
        return

    # GET /status — machine type
    if path_lower == "/status":
        ty = send_command("TY:")
        json_response(cl, 200, {"type": ty})
        return

    # POST /brew/<product>
    if path_lower.startswith("/brew") and method == "POST":
        parts = path_lower.split("/")
        product = parts[2] if len(parts) > 2 else ""
        button = PRODUCTS.get(product)
        if not button:
            json_response(cl, 400, {
                "error": f"Unknown product: {product}",
                "available": list(PRODUCTS.keys()),
            })
            return
        response = send_command(f"FA:{button}")
        json_response(cl, 200, {
            "product": product,
            "command": f"FA:{button}",
            "response": response,
        })
        return

    # /handshake — capture @T1/@T2/@T3 exchange with extended listen
    if path_lower == "/handshake":
        cmd = body if (method == "POST" and body) else "@T1"
        responses = send_and_listen(cmd, listen_ms=8000)
        json_response(cl, 200, {
            "command": cmd,
            "responses": responses,
            "count": len(responses),
        })
        return

    # POST /auth — perform full handshake with a given @t2 response
    # body = hex string for @t2 response (e.g. "8120000000")
    if path_lower == "/auth" and method == "POST":
        t2_resp = body.strip() if body else "8120000000"
        try:
            log = do_handshake(t2_resp)
        except Exception as e:
            import sys
            sys.print_exception(e)
            log = [str(type(e).__name__) + ": " + str(e)]
        json_response(cl, 200, {"t2_response": t2_resp, "log": log})
        return

    # POST /auth-brew — full handshake, capture hex of encrypted responses
    if path_lower == "/auth-brew" and method == "POST":
        product = body.strip() if body else "05"
        log = []
        try:
            while uart.any():
                uart.read()

            # Full handshake
            send_raw("@T1")
            log.append("TX: @T1")
            resp = read_until("@T2", timeout_ms=5000)
            log.append("RX: " + resp)
            send_raw("@t2:8120000000")
            log.append("TX: @t2:8120000000")
            resp = read_until("@T3", timeout_ms=5000)
            log.append("RX: " + resp)
            send_raw("@t3")
            log.append("TX: @t3")

            # Capture post-auth encrypted data as HEX
            time.sleep_ms(1000)
            raw = bytearray()
            deadline = time.ticks_add(time.ticks_ms(), 3000)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if uart.any():
                    chunk = uart.read()
                    if chunk:
                        raw.extend(chunk)
                        deadline = time.ticks_add(time.ticks_ms(), 500)
                else:
                    time.sleep_ms(10)
            if raw:
                # Decode 4-byte groups to get actual bytes
                decoded = bytearray()
                for i in range(0, len(raw) - 3, 4):
                    decoded.append(jura_decode_byte(raw[i:i + 4]))
                log.append("RX post-auth hex: " + decoded.hex())
                log.append("RX post-auth txt: " + safe_decode(decoded))

            # Send FA:05 and capture response as hex
            while uart.any():
                uart.read()
            fa_cmd = "FA:" + product
            send_raw(fa_cmd)
            log.append("TX: " + fa_cmd)

            time.sleep_ms(500)
            raw = bytearray()
            deadline = time.ticks_add(time.ticks_ms(), 3000)
            while time.ticks_diff(deadline, time.ticks_ms()) > 0:
                if uart.any():
                    chunk = uart.read()
                    if chunk:
                        raw.extend(chunk)
                        deadline = time.ticks_add(time.ticks_ms(), 500)
                else:
                    time.sleep_ms(10)
            if raw:
                decoded = bytearray()
                for i in range(0, len(raw) - 3, 4):
                    decoded.append(jura_decode_byte(raw[i:i + 4]))
                log.append("RX FA hex: " + decoded.hex())
                log.append("RX FA txt: " + safe_decode(decoded))

        except Exception as e:
            import sys
            sys.print_exception(e)
            log.append(str(type(e).__name__) + ": " + str(e))
        json_response(cl, 200, {"product": product, "log": log})
        return

    # GET / — info page
    if path_lower == "" or path_lower == "/":
        wlan = network.WLAN(network.STA_IF)
        ip = wlan.ifconfig()[0] if wlan.isconnected() else "not connected"
        json_response(cl, 200, {
            "name": "JURA ESP32 Bridge",
            "ip": ip,
            "endpoints": {
                "POST /api": "Send raw command (body = command string)",
                "GET /status": "Get machine type",
                "POST /brew/espresso": "Brew espresso",
                "POST /brew/coffee": "Brew coffee",
                "POST /brew/hotwater": "Brew hot water",
            },
        })
        return

    json_response(cl, 404, {"error": "Not found"})


def main():
    wlan = network.WLAN(network.STA_IF)
    ip = wlan.ifconfig()[0] if wlan.isconnected() else "0.0.0.0"

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", 80))
    s.listen(5)
    print(f"HTTP server listening on {ip}:80")

    while True:
        cl = None
        try:
            cl, addr = s.accept()
            cl.settimeout(30)
            data = cl.recv(2048)
            if data:
                method, path, body = parse_request(data)
                print(f"{method} {path}")
                handle_request(cl, method, path, body)
        except OSError as e:
            print(f"Connection error: {e}")
        except Exception as e:
            print(f"Error: {e}")
            if cl:
                try:
                    json_response(cl, 500, {"error": str(e)})
                except Exception:
                    pass
        finally:
            if cl:
                try:
                    cl.close()
                except Exception:
                    pass


main()
