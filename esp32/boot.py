"""boot.py — Connect ESP32 to WiFi on startup."""

import network
import time

SSID = ""       # Your WiFi SSID
PASSWORD = ""   # Your WiFi password

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

if not wlan.isconnected():
    print(f"Connecting to {SSID}...")
    wlan.connect(SSID, PASSWORD)
    for _ in range(30):
        if wlan.isconnected():
            break
        time.sleep(1)

if wlan.isconnected():
    ip = wlan.ifconfig()[0]
    print(f"WiFi connected: {ip}")
else:
    print("WiFi connection FAILED — starting anyway")
