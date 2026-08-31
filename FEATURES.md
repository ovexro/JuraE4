# JURA E4 Desktop App — Feature Inventory

Single source of truth for what's implemented and what's not. Check items as they ship. When a feature is fully polished and no further enhancement would meaningfully improve it, mark it COMPLETE.

## WiFi Connect V2 Protocol (jura_wifi_v2.py) — COMPLETE
- [x] TCP 51515 encrypted protocol (nibble-substitution, discOne/discTwo S-boxes)
- [x] @HP authentication with configurable hash (now correctly distinguishes @hp4 accept from @hp5:XX reject)
- [x] @TS session control
- [x] @TG:C0 maintenance status (Cleaning %, Filter %, Descaling %)
- [x] @TG:43 maintenance counters (6 uint16 counters)
- [x] @TR:32,XX product counters (WiFi format: 2 bytes/product)
- [x] @TP brew command with @TB/@TV live progress
- [x] @TF full status bitmask parsing (40+ alerts)
- [x] UDP discovery + direct IP connect
- [x] Thread-safe socket operations (_sock_lock actually covers every send/recv/close now — brew, status poll, connect, disconnect, statistics all serialized on one shared TCP socket, fixed 2026-08-31)
- [x] Persistent receive buffer across recv() calls — a message split mid-read is no longer silently dropped (fixed 2026-08-31)
- [x] MachineStatistics dataclass + read_statistics() background thread (now crash-proof against a mid-read disconnect)
- [x] Brew cooldown (10s, now race-free), status polling (4s), safety timeout (120s, now explicitly signals brew_error instead of failing silently)
- [x] Connection refused -> "Close J.O.E. first" hint
- [x] File-based rotating debug log (~/.config/jura-desktop/jura.log) for diagnosing brew/connection issues after the fact (added 2026-08-31)

## GUI — First-Launch Setup
- [x] Shows when no auth hash is configured
- [x] 64-char hex input with validation
- [x] Saves hash to settings, never asked again
- [x] Instructions point to tools/extract_hash.py

## GUI — Connection Screen
- [x] Auto-connect on launch (saved IP -> UDP discovery -> connect)
- [x] Animated splash with manual IP fallback
- [x] WiFi V2 only

## GUI — Dashboard
- [x] Header: JURA brand, machine info, StatusLED, Statistics button, Disconnect button
- [x] 3 product cards (Espresso, Coffee, Hot Water)
- [x] Brew confirmation dialog
- [x] Alert status bar with @TF bitmask alerts + maintenance warnings at <15%
- [x] Reconnecting state (amber LED, 5 attempts x 5s)
- [x] Brew animation — tracks full brew cycle (preparing -> heating -> pouring -> done)
- [x] Brew animation timing matches real machine phases (waits for live data before filling cup)
- [x] Brew overlay no longer closes early on a stale "Enjoy your coffee" status alert from a previous brew (gated on actual backend brewing state, fixed 2026-08-31, hardware-verified)

## GUI — Statistics & Maintenance
- [x] 3 StatCounterCard widgets + total beverages
- [x] 3 MaintenanceBar widgets (green >50%, amber 20-50%, red <20%, gray N/A)
- [x] Cycle counts, loading state, refresh button, timestamp

## System Tray
- [x] QSystemTrayIcon with context menu
- [x] Show/hide window, quick-brew shortcuts
- [x] Connection status in menu
- [x] Minimize to tray on window close
- [x] Quit from tray menu
- [x] Graceful fallback when tray unavailable

## Auto-connect, Reconnect, Settings — COMPLETE
- [x] Saved IP fast path -> UDP fallback -> manual entry
- [x] Auto-reconnect on unexpected drop (5 x 5s)
- [x] Settings: ~/.config/jura-desktop/settings.json
- [x] Atomic save (tmp + os.replace)

## Tools — COMPLETE
- [x] tools/extract_hash.py — PCAP auth hash extraction
- [x] captures/wifi_crypto.py — standalone encryption test
- [x] captures/decrypt_all.py — full session decryptor

## Desktop Integration — COMPLETE
- [x] .desktop launcher, menu entry, SVG/PNG icons, run.sh, requirements.txt

## Git & GitHub — COMPLETE
- [x] Repository: github.com/ovexro/JuraE4 (public)
- [x] Secrets sanitized (empty placeholders in repo)
- [x] Local secrets protected via git update-index --assume-unchanged
- [x] Legal disclaimer in README (EU Directive 2009/24/EC)
- [x] README with full setup guide

## Not Feasible
- Plug-and-play pairing (dongle rejects empty/random hashes — not feasible without factory reset)
- Multiple machine support (only one E4 — build if needed)
