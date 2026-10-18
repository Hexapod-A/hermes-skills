#!/usr/bin/env python3
"""THE REPLICA of the kcode binary, rebuilt from input/output traces only.

REA_BUG=crc_init   deliberate mismatch for the demo: CRC init 0x0000 instead of 0xFFFF.
REA_BUG=v1         the first rebuild, kept to show the loop: it buffered decode output and wrote
                   nothing on an error. Triage of the v1 run showed the binary writes the runs it
                   already decoded BEFORE it fails (it streams with putchar). v2 (default) streams too."""
import os
import sys


def crc16(data, init):
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("-e", "-d", "-c"):
        sys.stderr.write("usage: kcode -e|-d|-c < input\n")
        return 2
    data = sys.stdin.buffer.read()[: 1 << 20]
    out = sys.stdout.buffer
    mode = sys.argv[1]
    if mode == "-c":
        init = 0x0000 if os.environ.get("REA_BUG") == "crc_init" else 0xFFFF
        out.write(b"%04X\n" % crc16(data, init))
        return 0
    if mode == "-e":
        parts, i = [], 0
        while i < len(data):
            j = i
            while j < len(data) and data[j] == data[i] and j - i < 255:
                j += 1
            parts.append("%02x%02x" % (j - i, data[i]))
            i = j
        out.write(("".join(parts) + "\n").encode())
        return 0
    text = data.rstrip(b"\r\n")
    if len(text) % 4:
        sys.stderr.write(f"error: length {len(text)} is not a multiple of 4\n")
        return 3
    hexd = b"0123456789abcdefABCDEF"
    v1 = os.environ.get("REA_BUG") == "v1"
    res = bytearray()

    def fail(msg):
        if not v1:
            out.write(bytes(res))   # v2: what was decoded before the error still goes out
        out.flush()
        sys.stderr.write(msg)
        return 3

    for i in range(0, len(text), 4):
        for k in range(4):
            if text[i + k] not in hexd:
                return fail(f"error: bad hex at {i + k}\n")
        run, b = int(text[i:i + 2], 16), int(text[i + 2:i + 4], 16)
        if run == 0:
            return fail(f"error: zero run at {i}\n")
        res += bytes([b]) * run
    out.write(bytes(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
