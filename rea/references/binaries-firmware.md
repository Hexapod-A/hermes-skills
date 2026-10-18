# Binaries and firmware

Only analyze binaries you own, were hired to audit, or can lawfully inspect. Work on a disposable
VM or offline device. Never run unknown firmware directly on your main machine.

## Observe

- Keep the exact target bytes and SHA-256. Record platform, architecture, OS and input channel.
- Start with `file`, `strings`, `readelf` / `objdump` (ELF), or PE/Mach-O equivalents. Ghidra is for
  static structure, not proof of runtime behaviour. A decompiled branch is a hypothesis until a
  trace exercises it.
- Input/output traces are the ground truth: exit code, stdout/stderr **bytes**, files written,
  return values, side effects, ordering, timing when it matters. `strace`/`ltrace` on Linux and
  `procmon` on Windows may reveal file and syscall effects on your own process.
- Probe empty input, max sizes, malformed encodings, repeated runs, errors after partial output,
  endian boundaries, integer overflow and locale.

## Test

`target-cmd.json` + `run_cases.py` executes each case in a fresh temporary directory. Use
`stdin_hex` for binary input; `stdout_b64` appears when output is not UTF-8. `files_out` includes
SHA-256 of changed files. Use paired plans for mode/flag and input families. A failed run is a
harness error, not a behaviour match.

The `cli-rle` example shows why a diff loop matters: the v1 replica buffered decoded bytes and
lost partial output on an error. Tests found 165 misses in 3,029 cases; v2 streams before error and
passed those 3,029. A separate wrong CRC seed produced 765 misses. The score covers the tested
stdin/flag distribution only, not untested platform and 1 MiB+ inputs.

## Firmware-specific notes

Extract with vendor tools or `binwalk` on a copy; never flash a physical device as a test without
an approved rollback. Emulators (QEMU) and hardware-in-the-loop rigs are different test scopes.
Compare input/output, boot logs, protocol traces and persistent state after power loss separately.
A matching emulator trace does not certify a real board's timing, power or safety behaviour.
