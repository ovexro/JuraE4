#!/usr/bin/env python3
"""
JURA WiFi Connect V2 — TCP 51515 encryption/decryption.
Reverse-engineered from J.O.E. APK: joe_android_connector.src.connection.wifi.WifiCryptoUtil
"""

import random
import time

# S-box tables from WifiCryptoUtil.java (DIFFERENT from BLE and serial!)
DISC_ONE = [1, 0, 3, 2, 15, 14, 8, 10, 6, 13, 7, 12, 11, 9, 5, 4]
DISC_TWO = [9, 12, 6, 11, 10, 15, 2, 14, 13, 0, 4, 3, 1, 8, 7, 5]

# Characters that need ESC escaping
ESCAPED_CHARS = {0, 10, 13, 38, 27}  # NUL, LF, CR, '&', ESC


def _norm(value: int) -> int:
    """Normalize to 0-255 range (Java's normalizeTo255Range)."""
    return value % 256


def _encode_decode_half_byte(uc_data: int, uc_turn: int, uc_base_one: int, uc_base_two: int) -> int:
    """Core nibble substitution cipher — symmetric encode/decode."""
    idx1 = _norm(uc_data + uc_turn + uc_base_one) % 16
    t = uc_turn >> 4
    val1 = DISC_ONE[idx1]
    idx2 = _norm(val1 + uc_base_two + _norm(t) - uc_turn - uc_base_one) % 16
    val2 = DISC_TWO[idx2]
    idx3 = _norm(val2 + uc_base_one + uc_turn - uc_base_two - _norm(t)) % 16
    val3 = DISC_ONE[idx3]
    return _norm(_norm(val3 - uc_turn - uc_base_one) % 16)


def decrypt_message(raw_bytes: bytes) -> str:
    """Decrypt a complete TCP 51515 message (including 0x2a prefix and 0d0a suffix).

    Returns the plaintext string.
    """
    assert raw_bytes[0] == 0x2a, f"Expected * prefix, got {raw_bytes[0]:#04x}"

    # Strip prefix and suffix
    data = raw_bytes[1:]  # remove 0x2a
    if data[-2:] == b'\r\n':
        data = data[:-2]  # remove 0d0a

    # Extract key (handle ESC escaping)
    pos = 0
    if data[pos] == 0x1b:  # ESC
        key = data[pos + 1] ^ 0x80
        pos = 2
    else:
        key = data[pos]
        pos = 1

    k1 = (key >> 4) & 0x0F  # high nibble
    k2 = key & 0x0F          # low nibble

    # Decrypt payload
    plaintext = bytearray()
    turn = 0
    while pos < len(data):
        b = data[pos]
        if b == 0x1b:  # ESC
            pos += 1
            b = data[pos] ^ 0x80

        hi = _encode_decode_half_byte((b >> 4) & 0x0F, turn, k1, k2)
        turn += 1
        lo = _encode_decode_half_byte(b & 0x0F, turn, k1, k2)
        turn += 1

        plaintext.append((hi << 4) | lo)
        pos += 1

    return plaintext.decode('utf-8', errors='replace')


def encrypt_message(plaintext: str, key: int = None) -> bytes:
    """Encrypt a plaintext string into a complete TCP 51515 message.

    Returns bytes including 0x2a prefix, key, encrypted payload, and 0d0a suffix.
    """
    if key is None:
        key = _generate_key()

    k1 = (key >> 4) & 0x0F
    k2 = key & 0x0F

    plaintext_bytes = plaintext.encode('utf-8')

    # Build output: start with key byte (ESC-escaped if needed)
    output = bytearray()
    if key in ESCAPED_CHARS:
        output.append(0x1b)
        output.append(key ^ 0x80)
    else:
        output.append(key)

    # Encrypt each byte
    turn = 0
    for b in plaintext_bytes:
        hi = _encode_decode_half_byte((b >> 4) & 0x0F, turn, k1, k2)
        turn += 1
        lo = _encode_decode_half_byte(b & 0x0F, turn, k1, k2)
        turn += 1

        encrypted_byte = _norm((hi << 4) | _norm(lo))

        if encrypted_byte in ESCAPED_CHARS:
            output.append(0x1b)
            encrypted_byte ^= 0x80
        output.append(_norm(encrypted_byte))

    # Wrap: * prefix + payload + CR LF
    return bytes([0x2a]) + bytes(output) + b'\r\n'


def _generate_key() -> int:
    """Generate a random key byte (low nibble not 14 or 15)."""
    rng = random.Random(int(time.time() * 1000))
    while True:
        k = rng.randint(0, 255)
        if (k & 0x0F) not in (14, 15):
            return k


# === Test / Demo ===
if __name__ == "__main__":
    # Test round-trip
    for test in ["TY:\r\n", "AN:01\r\n", "FA:05\r\n", "IC:\r\n"]:
        encrypted = encrypt_message(test)
        decrypted = decrypt_message(encrypted)
        assert decrypted == test, f"Round-trip failed: {test!r} -> {decrypted!r}"
        print(f"  OK: {test!r} -> {encrypted.hex()} -> {decrypted!r}")

    print("\nRound-trip tests passed!")

    # Decrypt captured session 1 messages
    print("\n=== Decrypting Session 1 from capture ===")
    session1_msgs = [
        # Client messages
        ("CLIENT", bytes.fromhex("2a826472f6a9918e039b20f2f99623d7cd4c8d6a19d85586b886a7ac0eccd7b151da1b8080d180dd7e840b6f45cd8cce60505b857cfa9c84d8eecb28be8edbf640dda7647eae0c8652ef08b981f9ef96c2c9a8616ab079ce08098877b520a5f9f570bc9b111ffbacb10d0a")),
        # Server response
        ("SERVER", bytes.fromhex("2a3ec43b046186550d0a")),
        # Client cmd 2
        ("CLIENT", bytes.fromhex("2a826430fca96b8336ff0d0a")),
        # Server resp 2
        ("SERVER", bytes.fromhex("2a293761fe10870d0a")),
        # Client cmd 3
        ("CLIENT", bytes.fromhex("2a8765aecbcbcc62e4e60d0a")),
        # Server resp 3
        ("SERVER", bytes.fromhex("2a8fc5d28ae76669b17ca2fc1d1dbb3b0d0a")),
        # Client cmd 4
        ("CLIENT", bytes.fromhex("2a8765aea0cbda62e4e60d0a")),
        # Server resp 4
        ("SERVER", bytes.fromhex("2a32d3ceee4b440d0a")),
    ]

    for direction, msg in session1_msgs:
        try:
            plaintext = decrypt_message(msg)
            print(f"  {direction:6s} ({len(msg):3d}B): {plaintext!r}")
        except Exception as e:
            print(f"  {direction:6s} ({len(msg):3d}B): ERROR: {e}")
