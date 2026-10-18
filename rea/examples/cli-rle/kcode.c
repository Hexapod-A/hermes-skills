/* THE ORIGINAL (treat as a black box binary). kcode: a tiny byte codec + checksum tool.
 * Build: cc -O2 -o kcode kcode.c      (run_demo.py builds it into a temp folder)
 *   kcode -e   run-length encode stdin -> hex text "RRBB..." (RR = run 1..255, BB = byte) + "\n"
 *   kcode -d   decode that text back to bytes
 *   kcode -c   CRC-16/CCITT-FALSE of stdin, 4 upper-case hex digits + "\n"
 * In a real job you would only have the binary. Here the source is kept so the demo is offline. */
#include <stdio.h>
#include <string.h>

static unsigned char buf[1 << 20];

static int hexval(int c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

int main(int argc, char **argv) {
    if (argc != 2 || (strcmp(argv[1], "-e") && strcmp(argv[1], "-d") && strcmp(argv[1], "-c"))) {
        fprintf(stderr, "usage: kcode -e|-d|-c < input\n");
        return 2;
    }
    size_t n = fread(buf, 1, sizeof buf, stdin);
    if (!strcmp(argv[1], "-c")) {
        unsigned crc = 0xFFFF;
        for (size_t i = 0; i < n; i++) {
            crc ^= (unsigned)buf[i] << 8;
            for (int k = 0; k < 8; k++) crc = (crc & 0x8000) ? ((crc << 1) ^ 0x1021) : (crc << 1);
            crc &= 0xFFFF;
        }
        printf("%04X\n", crc);
        return 0;
    }
    if (!strcmp(argv[1], "-e")) {
        size_t i = 0;
        while (i < n) {
            unsigned char b = buf[i];
            size_t run = 1;
            while (i + run < n && buf[i + run] == b && run < 255) run++;
            printf("%02x%02x", (unsigned)run, b);
            i += run;
        }
        printf("\n");
        return 0;
    }
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r')) n--;
    if (n % 4) {
        fprintf(stderr, "error: length %zu is not a multiple of 4\n", n);
        return 3;
    }
    for (size_t i = 0; i < n; i += 4) {
        int v[4];
        for (int k = 0; k < 4; k++) {
            v[k] = hexval(buf[i + k]);
            if (v[k] < 0) {
                fprintf(stderr, "error: bad hex at %zu\n", i + k);
                return 3;
            }
        }
        int run = v[0] * 16 + v[1], b = v[2] * 16 + v[3];
        if (run == 0) {
            fprintf(stderr, "error: zero run at %zu\n", i);
            return 3;
        }
        for (int k = 0; k < run; k++) putchar(b);
    }
    return 0;
}
