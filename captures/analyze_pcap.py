#!/usr/bin/env python3
"""Analyze JURA WiFi V2 TCP 51515 captures — extract sessions and payloads."""

import sys
from collections import defaultdict
from scapy.all import rdpcap, TCP, UDP, IP, Raw

JURA_IP = "192.168.1.105"
PORT = 51515

def analyze(pcap_file):
    packets = rdpcap(pcap_file)

    # ========== UDP Analysis ==========
    print("=" * 70)
    print("UDP 51515 PACKETS")
    print("=" * 70)
    udp_count = 0
    for pkt in packets:
        if UDP in pkt and pkt[UDP].dport == PORT or (UDP in pkt and pkt[UDP].sport == PORT):
            udp_count += 1
            if Raw in pkt:
                data = bytes(pkt[Raw].load)
                src = pkt[IP].src
                dst = pkt[IP].dst
                print(f"\n  [{udp_count}] {src}:{pkt[UDP].sport} -> {dst}:{pkt[UDP].dport} ({len(data)} bytes)")
                print(f"      HEX: {data.hex()}")
                # Try to decode ASCII portions
                ascii_parts = []
                for b in data:
                    if 0x20 <= b < 0x7f:
                        ascii_parts.append(chr(b))
                    else:
                        ascii_parts.append('.')
                print(f"      ASCII: {''.join(ascii_parts)}")
    print(f"\n  Total UDP packets: {udp_count}")

    # ========== TCP Session Extraction ==========
    print("\n" + "=" * 70)
    print("TCP 51515 SESSIONS")
    print("=" * 70)

    # Group TCP packets by stream (src_ip:src_port <-> dst_ip:dst_port)
    streams = defaultdict(list)
    for pkt in packets:
        if TCP in pkt and (pkt[TCP].dport == PORT or pkt[TCP].sport == PORT):
            if Raw in pkt:
                src = pkt[IP].src
                dst = pkt[IP].dst
                sp = pkt[TCP].sport
                dp = pkt[TCP].dport
                # Normalize stream key
                if dp == PORT:
                    key = (src, sp, dst, dp)
                else:
                    key = (dst, dp, src, sp)
                streams[key].append(pkt)

    for i, (key, pkts) in enumerate(streams.items()):
        client_ip, client_port, server_ip, server_port = key
        print(f"\n{'─' * 70}")
        print(f"SESSION {i+1}: {client_ip}:{client_port} <-> {server_ip}:{server_port}")
        print(f"  Packets with data: {len(pkts)}")
        print(f"{'─' * 70}")

        for j, pkt in enumerate(pkts):
            data = bytes(pkt[Raw].load)
            src = pkt[IP].src
            direction = ">>>" if pkt[IP].src == client_ip else "<<<"
            label = "CLIENT" if direction == ">>>" else "SERVER"

            print(f"\n  [{j+1}] {label} {direction} ({len(data)} bytes)")
            print(f"      HEX: {data.hex()}")

            # Check framing
            if data[-2:] == b'\r\n' or data[-2:] == b'\x0d\x0a':
                print(f"      FRAMING: ends with \\r\\n (JURA serial framing)")
            if data[0] == 0x2a:
                print(f"      PREFIX: 0x2a ('*') — encrypted JURA protocol")

            # Show ASCII-safe representation
            ascii_parts = []
            for b in data:
                if 0x20 <= b < 0x7f:
                    ascii_parts.append(chr(b))
                else:
                    ascii_parts.append('.')
            print(f"      ASCII: {''.join(ascii_parts)}")

            # Analyze byte patterns
            if len(data) >= 4:
                print(f"      BYTE[0:4]: {data[0]:02x} {data[1]:02x} {data[2]:02x} {data[3]:02x}")
                if data[0] == 0x2a:
                    # Strip 2a prefix and 0d0a suffix for payload analysis
                    payload = data[1:-2] if data[-2:] == b'\x0d\x0a' else data[1:]
                    print(f"      PAYLOAD (strip 2a..0d0a): {payload.hex()} ({len(payload)} bytes)")

    # ========== Cross-Session Comparison ==========
    print("\n" + "=" * 70)
    print("CROSS-SESSION COMPARISON")
    print("=" * 70)

    all_first_msgs = []
    for i, (key, pkts) in enumerate(streams.items()):
        client_ip = key[0]
        client_msgs = [bytes(p[Raw].load) for p in pkts if p[IP].src == client_ip]
        server_msgs = [bytes(p[Raw].load) for p in pkts if p[IP].src != client_ip]

        all_first_msgs.append({
            'session': i+1,
            'client_msgs': client_msgs,
            'server_msgs': server_msgs,
        })

        print(f"\n  Session {i+1}: {len(client_msgs)} client msgs, {len(server_msgs)} server msgs")
        for k, msg in enumerate(client_msgs):
            print(f"    C[{k}] {len(msg):3d}B: {msg[:20].hex()}{'...' if len(msg)>20 else ''}")
        for k, msg in enumerate(server_msgs):
            print(f"    S[{k}] {len(msg):3d}B: {msg[:20].hex()}{'...' if len(msg)>20 else ''}")

    # Compare first messages across sessions (looking for static bytes)
    if len(all_first_msgs) >= 2:
        print(f"\n  --- First Client Message Comparison ---")
        first_clients = [s['client_msgs'][0] for s in all_first_msgs if s['client_msgs']]
        if len(first_clients) >= 2:
            min_len = min(len(m) for m in first_clients)
            static_bytes = []
            dynamic_bytes = []
            for pos in range(min_len):
                vals = set(m[pos] for m in first_clients)
                if len(vals) == 1:
                    static_bytes.append(pos)
                else:
                    dynamic_bytes.append(pos)
            print(f"    Min length: {min_len}, Static positions: {len(static_bytes)}, Dynamic: {len(dynamic_bytes)}")
            if static_bytes:
                print(f"    Static byte positions: {static_bytes[:30]}{'...' if len(static_bytes)>30 else ''}")
                static_hex = ' '.join(f"{first_clients[0][p]:02x}" for p in static_bytes[:30])
                print(f"    Static byte values: {static_hex}")
            if dynamic_bytes:
                print(f"    Dynamic byte positions: {dynamic_bytes[:30]}{'...' if len(dynamic_bytes)>30 else ''}")

if __name__ == "__main__":
    pcap_file = sys.argv[1] if len(sys.argv) > 1 else "session1.pcap"
    analyze(pcap_file)
