# JURA Desktop Control

A premium Linux desktop app for controlling the **JURA E4** coffee machine through the **WiFi Connect V2** dongle. Reverse-engineered from the official J.O.E. Android app.

## Features

### Brew Control
- **Three products**: Espresso, Coffee, Hot Water
- Adjustable **strength** (1-3), **volume** (slider), and **temperature** (Low/Normal/High)
- Confirmation dialog before every brew (safety)
- **Live brewing animation** with real-time progress and temperature from the machine
- Heating phase detection with pulsing "Heating up..." display
- "Enjoy your coffee!" completion feedback

### Statistics & Maintenance
- **Lifetime product counters** — how many espressos, coffees, and hot waters have been made
- **Maintenance progress bars** — Cleaning, Descaling, and Filter status (color-coded: green/amber/red)
- **Cycle counters** — number of maintenance cycles performed
- Maintenance warnings surface in the dashboard status bar when due

### Connection
- **Auto-connect on launch** — tries saved IP, falls back to UDP discovery
- **Auto-reconnect** on unexpected connection drops (5 attempts, 5 seconds apart)
- **Settings persistence** — dongle IP and brew preferences saved across sessions
- Clear error messages (e.g. "Close J.O.E. on your phone first" when the dongle is busy)

### Desktop Integration
- **System tray** — minimize to tray on close, quick-brew from the tray menu
- Dark theme with gold accents
- Custom-painted SVG/PNG icons
- `.desktop` launcher

## Screenshots

The app has three screens:

1. **Connection splash** — auto-connects on launch, manual IP fallback if needed
2. **Dashboard** — product cards with brew controls, status bar with machine alerts
3. **Statistics** — beverage counters, maintenance health bars, refresh button

## Requirements

- **Python** 3.10+
- **PyQt5** 5.15+
- **bleak** 3.0+ (BLE library — installed but only used by the reference protocol module)
- **Linux** with a desktop environment (tested on Linux Mint / Cinnamon)
- **JURA WiFi Connect V2 dongle** plugged into the coffee machine
- Machine and computer on the **same local network**

## Installation

```bash
# Clone
git clone https://github.com/ovexro/JuraE4.git
cd JuraE4

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
./run.sh
```

## First-time setup (auth hash)

The WiFi Connect V2 dongle requires a per-dongle authentication hash. This is a one-time setup — you extract the hash once and the app remembers it forever.

### Step 1: Capture network traffic

You need a packet capture of the J.O.E. app connecting to your machine. Pick whichever method works for your setup:

**Option A — Wireshark (easiest if your PC is on the same WiFi)**
1. Install [Wireshark](https://www.wireshark.org/)
2. Start capturing on your WiFi interface
3. Open J.O.E. on your phone and let it connect to the coffee machine
4. Stop the capture, save as `capture.pcap`

**Option B — tcpdump on an OpenWrt router**
```bash
# SSH into your router
ssh root@192.168.1.1

# Capture traffic to/from the dongle (replace IP if different)
tcpdump -i br-lan -w /tmp/capture.pcap host 192.168.1.105 &

# Open J.O.E. on your phone, let it connect, then:
kill %1
scp root@192.168.1.1:/tmp/capture.pcap .
```

**Option C — tcpdump on Linux (if your network allows promiscuous mode)**
```bash
sudo tcpdump -i wlan0 -w capture.pcap port 51515
# Open J.O.E. on phone, let it connect, then Ctrl+C
```

### Step 2: Extract the hash

```bash
pip install scapy  # one-time dependency
python3 tools/extract_hash.py capture.pcap
```

Output:
```
============================================================
  AUTH HASH FOUND
============================================================

  Device name:  Your Phone
  Auth hash:    CCC3B0FDD2EE35B9...

  Paste this hash into the JURA Desktop Control app
  when prompted on first launch.
============================================================
```

### Step 3: Paste into the app

On first launch, the app shows a setup screen. Paste the 64-character hash and click **SAVE & CONNECT**. Done — you'll never be asked again.

## Usage

### Daily use
1. Launch the app — it auto-connects to the dongle (saved IP from last session)
2. If discovery fails, enter the dongle's IP manually (check your router's DHCP leases)
3. Once connected, the IP is saved for next time

### Making coffee
1. Choose a product card (Espresso, Coffee, or Hot Water)
2. Adjust strength, volume, and temperature
3. Click **BREW** and confirm
4. Watch the live brewing animation with real progress from the machine

### System tray
- Closing the window minimizes to the system tray (stays connected)
- Right-click the tray icon for quick-brew shortcuts
- Select **Quit** from the tray menu to fully exit

### Statistics
- Click **Statistics** in the dashboard header
- View lifetime beverage counts and maintenance status
- Click **Refresh** to re-read data from the machine

## Architecture

```
jura_app.py          PyQt5 GUI — all screens, widgets, animations
jura_wifi_v2.py      WiFi V2 protocol client — encryption, auth, commands
jura_protocol.py     BLE protocol module (reference — used for alert definitions)
jura_wifi.py         ESP32 bridge client (legacy, not used)
esp32/               ESP32 MicroPython firmware (legacy, not used)
captures/            Network capture analysis tools
```

### Protocol

The WiFi Connect V2 dongle communicates over **TCP port 51515** with a per-message nibble-substitution cipher. The encryption was reverse-engineered from the decompiled J.O.E. Android APK (`WifiCryptoUtil.java`).

Key commands:
| Command | Purpose |
|---------|---------|
| `@HP:` | Authentication (static hash per dongle) |
| `@TS:01/00` | Start/stop session |
| `@TG:C0` | Maintenance status (cleaning/descaling/filter %) |
| `@TG:43` | Maintenance counters |
| `@TR:32,XX` | Product counters (lifetime totals) |
| `@TP:` | Brew command (product, strength, volume, temperature) |
| `@TV:` | Brew progress push (real-time % and temperature) |
| `@TF:` | Machine status bitmask (40+ alerts) |

The dongle handles all machine-level serial encryption internally — the desktop app only needs the WiFi-layer cipher.

### Threading Model

- **Main thread**: Qt event loop (GUI rendering, signal dispatch)
- **WiFiV2Manager**: daemon threads for status polling, brew progress, statistics reading
- **Communication**: Qt signals with automatic cross-thread queuing
- **Safety**: `threading.Lock` for connection state, `_sock_lock` for socket send/recv atomicity

## Configuration

Settings are stored in `~/.config/jura-desktop/settings.json`:

```json
{
  "dongle_ip": "192.168.1.105",
  "product_espresso": {"strength": 2, "volume": 45, "temperature": 1},
  "product_coffee": {"strength": 2, "volume": 100, "temperature": 1},
  "product_hot water": {"volume": 220, "temperature": 1}
}
```

## Limitations

- **Single connection**: The WiFi V2 dongle accepts only one TCP connection at a time. Close the J.O.E. phone app before using the desktop app.
- **E4 only**: Tested exclusively on the JURA E4. Other JURA models may work if they use the same WiFi Connect V2 dongle, but product codes and register layouts will differ.
- **No BLE brewing**: The BLE Smart Connect dongle works for status reading but rejects brew commands from Linux (BlueZ ATT limitation). WiFi V2 is the only working brew path.

## License

Private — not for redistribution.

## Credits

- Protocol reverse-engineering: decompiled from the [J.O.E.](https://play.google.com/store/apps/details?id=ch.toptronic.joe) Android app
- Built with [Claude Code](https://claude.ai/code) (Claude Opus 4.6)
