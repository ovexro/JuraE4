#!/usr/bin/env python3
"""Decrypt ALL JURA TCP 51515 sessions from pcap captures."""

from collections import defaultdict
from scapy.all import rdpcap, TCP, IP, Raw
from wifi_crypto import decrypt_message

JURA_IP = "192.168.1.105"
PORT = 51515


def decrypt_pcap(pcap_file, label=""):
    packets = rdpcap(pcap_file)

    # Group TCP data packets by stream
    streams = defaultdict(list)
    for pkt in packets:
        if TCP in pkt and (pkt[TCP].dport == PORT or pkt[TCP].sport == PORT):
            if Raw in pkt:
                src = pkt[IP].src
                dst = pkt[IP].dst
                sp = pkt[TCP].sport
                dp = pkt[TCP].dport
                if dp == PORT:
                    key = (src, sp, dst, dp)
                else:
                    key = (dst, dp, src, sp)
                streams[key].append(pkt)

    print(f"\n{'=' * 80}")
    print(f"  {label or pcap_file} — {len(streams)} TCP sessions")
    print(f"{'=' * 80}")

    for i, (key, pkts) in enumerate(streams.items()):
        client_ip = key[0]
        print(f"\n{'─' * 80}")
        print(f"SESSION {i+1} ({key[0]}:{key[1]} <-> {key[2]}:{key[3]})")
        print(f"{'─' * 80}")

        # Split into individual messages (handle TCP reassembly)
        buf = {client_ip: b'', key[2]: b''}
        messages = []

        for pkt in pkts:
            src = pkt[IP].src
            data = bytes(pkt[Raw].load)
            buf[src] += data

            # Extract complete messages (ending with 0d0a)
            while b'\r\n' in buf[src]:
                idx = buf[src].index(b'\r\n')
                msg = buf[src][:idx + 2]
                buf[src] = buf[src][idx + 2:]
                direction = ">>>" if src == client_ip else "<<<"
                label_dir = "CLIENT" if src == client_ip else "SERVER"
                messages.append((label_dir, direction, msg))

        for j, (label_dir, direction, msg) in enumerate(messages):
            try:
                plaintext = decrypt_message(msg)
                # Truncate very long lines for readability
                display = plaintext.rstrip('\r\n')
                if len(display) > 120:
                    display = display[:120] + "..."
                print(f"  [{j+1:2d}] {label_dir} {direction} {display}")
            except Exception as e:
                print(f"  [{j+1:2d}] {label_dir} {direction} DECRYPT ERROR: {e} | raw: {msg[:30].hex()}...")


if __name__ == "__main__":
    import sys

    files = sys.argv[1:] or ["session1.pcap"]
    for f in files:
        decrypt_pcap(f, f)
