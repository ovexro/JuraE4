#!/usr/bin/env python3
"""
Extract the JURA WiFi Connect V2 authentication hash from a network capture.

Usage:
    python3 extract_hash.py <capture.pcap>

How to capture:
    1. Start a packet capture on your network (Wireshark, tcpdump, etc.)
    2. Open the J.O.E. app on your phone and let it connect to the machine
    3. Stop the capture and save as .pcap
    4. Run this tool on the saved capture

The tool finds the @HP authentication message in TCP port 51515 traffic,
decrypts it, and prints the auth hash ready to paste into the app.

Requirements:
    pip install scapy
"""

import sys
import os

# --------------------------------------------------------------------------
# Inline decryption (self-contained — no imports from the main app)
# --------------------------------------------------------------------------

_D1 = [1, 0, 3, 2, 15, 14, 8, 10, 6, 13, 7, 12, 11, 9, 5, 4]
_D2 = [9, 12, 6, 11, 10, 15, 2, 14, 13, 0, 4, 3, 1, 8, 7, 5]


def _hb(data, turn, k1, k2):
    i1 = (data + turn + k1) % 256 % 16
    t = turn >> 4
    v1 = _D1[i1]
    i2 = (v1 + k2 + (t % 256) - turn - k1) % 256 % 16
    v2 = _D2[i2]
    i3 = (v2 + k1 + turn - k2 - (t % 256)) % 256 % 16
    v3 = _D1[i3]
    return (v3 - turn - k1) % 256 % 16


def decrypt(raw):
    """Decrypt a JURA TCP 51515 wire message to plaintext."""
    if not raw or raw[0] != 0x2A:
        return None
    data = raw[1:]
    if data[-2:] == b"\r\n":
        data = data[:-2]
    pos = 0
    if data[pos] == 0x1B:
        key = data[pos + 1] ^ 0x80
        pos = 2
    else:
        key = data[pos]
        pos = 1
    k1 = (key >> 4) & 0x0F
    k2 = key & 0x0F
    out = bytearray()
    turn = 0
    while pos < len(data):
        b = data[pos]
        if b == 0x1B:
            pos += 1
            b = data[pos] ^ 0x80
        hi = _hb((b >> 4) & 0x0F, turn, k1, k2)
        turn += 1
        lo = _hb(b & 0x0F, turn, k1, k2)
        turn += 1
        out.append((hi << 4) | lo)
        pos += 1
    return out.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# PCAP parsing
# --------------------------------------------------------------------------

PORT = 51515


def extract_from_pcap(pcap_file):
    """Extract auth hash from a PCAP file."""
    try:
        from scapy.all import rdpcap, TCP, Raw
    except ImportError:
        print("Error: scapy is required.  Install it with:")
        print("    pip install scapy")
        sys.exit(1)

    if not os.path.exists(pcap_file):
        print(f"Error: file not found: {pcap_file}")
        sys.exit(1)

    packets = rdpcap(pcap_file)

    # Reassemble TCP data streams to port 51515
    streams = {}
    for pkt in packets:
        if TCP in pkt and Raw in pkt:
            sp, dp = pkt[TCP].sport, pkt[TCP].dport
            if dp == PORT:
                key = (sp, dp)
                streams.setdefault(key, b"")
                streams[key] += bytes(pkt[Raw].load)

    if not streams:
        print("No TCP traffic to port 51515 found in this capture.")
        print("Make sure you captured while J.O.E. was connecting to the machine.")
        sys.exit(1)

    # Search all streams for @HP messages
    found = []
    for key, data in streams.items():
        # Split into individual messages (delimited by 0x2a prefix)
        i = 0
        while i < len(data):
            if data[i] == 0x2A:
                # Find end (0d 0a)
                end = data.find(b"\r\n", i)
                if end == -1:
                    break
                msg = data[i : end + 2]
                try:
                    plain = decrypt(msg)
                    if plain and "@HP:" in plain:
                        found.append(plain.strip())
                except Exception:
                    pass
                i = end + 2
            else:
                i += 1

    if not found:
        print("Found TCP 51515 traffic but no @HP authentication message.")
        print("The capture may not include the moment J.O.E. connected.")
        print("Try capturing again from BEFORE opening J.O.E.")
        sys.exit(1)

    # Parse the @HP message(s)
    for hp_msg in found:
        # Format: @HP:<PIN>,<DEVICE_NAME_HEX>,<AUTH_HASH>
        # or:     @HP:,<DEVICE_NAME_HEX>,<AUTH_HASH>  (empty PIN)
        parts = hp_msg.split(",")
        if len(parts) >= 3:
            auth_hash = parts[-1].strip().rstrip("\r\n")
            name_hex = parts[-2].strip()
            try:
                device_name = bytes.fromhex(name_hex).decode("ascii", errors="replace")
            except ValueError:
                device_name = name_hex

            print()
            print("=" * 60)
            print("  AUTH HASH FOUND")
            print("=" * 60)
            print()
            print(f"  Device name:  {device_name}")
            print(f"  Auth hash:    {auth_hash}")
            print()
            print("  Paste this hash into the JURA Desktop Control app")
            print("  when prompted on first launch.")
            print()
            print("=" * 60)
            return auth_hash

    print("Could not parse the @HP message.")
    sys.exit(1)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 extract_hash.py <capture.pcap>")
        print()
        print("Extracts the JURA WiFi Connect V2 auth hash from a network capture.")
        print("Capture traffic on your network while J.O.E. connects to the machine.")
        sys.exit(0)

    extract_from_pcap(sys.argv[1])
