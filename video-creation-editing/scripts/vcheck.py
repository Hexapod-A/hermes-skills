#!/usr/bin/env python3
"""Check a finished video before you send it: format, size, loudness, silence, black or frozen
frames, and a contact sheet to look at.

Usage:
  python3 vcheck.py OUT.mp4 [--target vertical|square|landscape|whatsapp|any] [--lufs -14]
                    [--sheet sheet.jpg] [--frames 12] [--json report.json]

Prints a report and PASS / WARN / FAIL lines. Exit code 0 = no FAIL, 2 = at least one FAIL.

Targets:
  vertical  1080x1920 (9:16)   square 1080x1080 (1:1)   landscape 1920x1080 (16:9)
  whatsapp  any of the above, H.264 + AAC, yuv420p, under 16 MB, fast start
"""
import argparse
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vutil import contact_sheet, ff, fmt_t, fps_of, need, probe  # noqa: E402

TARGETS = {"vertical": (1080, 1920), "square": (1080, 1080), "landscape": (1920, 1080)}


def faststart(path):
    """True when the 'moov' index comes before 'mdat' (the video can start playing before it fully downloads)."""
    with open(path, "rb") as fh:
        pos = 0
        size_total = os.path.getsize(path)
        while pos < size_total:
            fh.seek(pos)
            hdr = fh.read(16)
            if len(hdr) < 8:
                return None
            size = int.from_bytes(hdr[:4], "big")
            kind = hdr[4:8].decode("latin1")
            if size == 1:
                size = int.from_bytes(hdr[8:16], "big")
            elif size == 0:
                size = size_total - pos
            if kind == "moov":
                return True
            if kind == "mdat":
                return False
            if size < 8:
                return None
            pos += size
    return None


def analyse(path, lufs=-14.0):
    info = probe(path)
    fmt = info.get("format", {})
    v = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)
    dur = float(fmt.get("duration", 0) or 0)
    rep = {
        "file": path,
        "size_mb": round(os.path.getsize(path) / 1048576, 2),
        "duration": round(dur, 2),
        "container": fmt.get("format_name"),
        "bitrate_kbps": round(int(fmt.get("bit_rate", 0) or 0) / 1000),
        "video": None, "audio": None,
        "faststart": faststart(path) if path.lower().endswith((".mp4", ".mov", ".m4v")) else None,
    }
    if v:
        rep["video"] = {"codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
                        "fps": round(fps_of(v), 3), "pix_fmt": v.get("pix_fmt"),
                        "sar": v.get("sample_aspect_ratio", "1:1")}
    if a:
        rep["audio"] = {"codec": a.get("codec_name"), "sample_rate": int(a.get("sample_rate", 0)),
                        "channels": a.get("channels")}
    # one decode pass for the video detectors, one for the audio ones
    if v:
        err = ff(["-i", path, "-an", "-vf", "blackdetect=d=0.3:pix_th=0.10,freezedetect=n=0.003:d=1.5", "-f", "null", "-"])
        rep["black"] = [{"start": float(m.group(1)), "end": float(m.group(2))}
                        for m in re.finditer(r"black_start:([0-9.]+) black_end:([0-9.]+)", err)]
        starts = [float(x) for x in re.findall(r"freeze_start: ([0-9.]+)", err)]
        ends = [float(x) for x in re.findall(r"freeze_end: ([0-9.]+)", err)]
        rep["frozen"] = [{"start": s, "end": (ends[i] if i < len(ends) else dur)} for i, s in enumerate(starts)]
    if a:
        err = ff(["-i", path, "-vn", "-af", "silencedetect=noise=-45dB:d=0.6,loudnorm=I=%s:TP=-1.5:LRA=11:print_format=json" % lufs,
                  "-f", "null", "-"])
        ss = [float(x) for x in re.findall(r"silence_start: (-?[0-9.]+)", err)]
        se = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", err)]
        rep["silence"] = [{"start": max(0.0, s), "end": (se[i] if i < len(se) else dur)} for i, s in enumerate(ss)]
        m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", err, re.S)
        if m:
            j = json.loads(m.group(0))
            rep["loudness"] = {"integrated_lufs": float(j["input_i"]), "true_peak_db": float(j["input_tp"]),
                               "lra": float(j["input_lra"])}
    return rep


def checks(rep, target="any", lufs=-14.0):
    out = []
    add = lambda level, msg: out.append((level, msg))  # noqa: E731
    v, a = rep.get("video"), rep.get("audio")
    if not v:
        add("FAIL", "no video stream")
    else:
        if v["width"] % 2 or v["height"] % 2:
            add("FAIL", f"odd size {v['width']}x{v['height']}: many players refuse it")
        if v["pix_fmt"] not in ("yuv420p", "yuvj420p"):
            add("WARN" if target != "whatsapp" else "FAIL", f"pix_fmt {v['pix_fmt']}: phones want yuv420p")
        if v["codec"] != "h264" and target == "whatsapp":
            add("FAIL", f"codec {v['codec']}: WhatsApp wants H.264")
        if v["fps"] < 23 or v["fps"] > 61:
            add("WARN", f"frame rate {v['fps']}")
        want = TARGETS.get(target)
        if want and (v["width"], v["height"]) != want:
            add("FAIL", f"size {v['width']}x{v['height']}, expected {want[0]}x{want[1]}")
        if target == "whatsapp" and (v["width"], v["height"]) not in TARGETS.values():
            add("WARN", f"size {v['width']}x{v['height']} is not 9:16, 1:1 or 16:9 at 1080p")
    if not a:
        add("WARN", "no audio stream (fine for silent loops; most platforms prefer a track)")
    else:
        if target == "whatsapp" and a["codec"] != "aac":
            add("FAIL", f"audio codec {a['codec']}: use AAC")
        L = rep.get("loudness")
        if L:
            if L["integrated_lufs"] < -60:
                add("FAIL", "audio is silent")
            elif abs(L["integrated_lufs"] - lufs) > 2:
                add("WARN", f"loudness {L['integrated_lufs']} LUFS (target {lufs}); run assemble.py --loudness or loudnorm")
            if L["true_peak_db"] > -0.5:
                add("WARN", f"true peak {L['true_peak_db']} dBTP: may clip after platform re-encode")
    if target == "whatsapp" and rep["size_mb"] >= 16:
        add("FAIL", f"{rep['size_mb']} MB is over WhatsApp's 16 MB video limit: run export_size.py --mb 15")
    if rep.get("faststart") is False:
        add("WARN" if target != "whatsapp" else "FAIL", "moov atom at the end: re-mux with -movflags +faststart")
    dur = rep["duration"] or 1
    for b in rep.get("black", []):
        if b["end"] - b["start"] > 0.5 or (b["start"] > 0.1 and b["end"] < dur - 0.1):
            add("WARN", f"black frames {fmt_t(b['start'])}-{fmt_t(b['end'])}")
    for fz in rep.get("frozen", []):
        add("WARN", f"frozen picture {fmt_t(fz['start'])}-{fmt_t(fz['end'])} (a held still is fine if planned)")
    for s in rep.get("silence", []):
        if s["end"] - s["start"] > 1.0 and s["start"] < dur - 1.5:
            add("WARN", f"silence {fmt_t(s['start'])}-{fmt_t(s['end'])}")
    if not out:
        add("PASS", "all checks passed")
    return out


def sheet(path, out, n=12, dur=None):
    dur = dur or float(probe(path)["format"]["duration"])
    with tempfile.TemporaryDirectory() as td:
        frames, labels = [], []
        for i in range(n):
            t = dur * (i + 0.5) / n
            f = os.path.join(td, f"f{i:03d}.jpg")
            ff(["-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", "scale=480:-2", f])
            if os.path.exists(f):
                frames.append(f)
                labels.append(fmt_t(t))
        return contact_sheet(frames, out, cols=4 if n >= 8 else n, width=1920, labels=labels)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("--target", default="any", choices=["any", "vertical", "square", "landscape", "whatsapp"])
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--sheet")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--json")
    a = ap.parse_args()
    need("ffmpeg")
    rep = analyse(a.video, a.lufs)
    res = checks(rep, a.target, a.lufs)
    rep["checks"] = [{"level": l, "msg": m} for l, m in res]
    if a.sheet:
        rep["sheet"] = sheet(a.video, a.sheet, a.frames, rep["duration"])
    print(json.dumps({k: rep[k] for k in ("size_mb", "duration", "video", "audio", "loudness", "faststart") if k in rep}))
    for l, m in res:
        print(f"{l}: {m}")
    if a.sheet:
        print(f"sheet: {a.sheet}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(rep, fh, indent=2)
    sys.exit(2 if any(l == "FAIL" for l, _ in res) else 0)


if __name__ == "__main__":
    main()
