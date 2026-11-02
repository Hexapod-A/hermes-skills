#!/usr/bin/env python3
"""Drive the rig and record one lesson: real editor, real terminal, real browser preview.

    WORK=~/tutorial-work scripts/rig.sh start ~/projects/my-first-app
    python3 narrate.py lesson.json --voice voice/voice.json --out ~/tutorial-work/04_components
    python3 record_lesson.py lesson.json --out ~/tutorial-work/04_components

For every beat: show its caption/step, start its narration slot, do its actions (typing code
character by character, running terminal commands, clicking in the preview), then wait until
the narration for that beat has finished. Writes <out>/raw.mkv (silent screen recording) and
<out>/timeline.json (when each beat started), which assemble.py turns into the final video.

Lesson format: see examples/lesson.example.json and the action list in SKILL.md.
Needs: pip install playwright (the rig's Chromium is reused over CDP, no browser download).
"""
import argparse
import asyncio
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tvs_util import load_json, save_json, typing_delays  # noqa: E402

CS_PORT = int(os.environ.get("CS_PORT", 8091))
CDP_PORT = int(os.environ.get("CDP_PORT", 9333))
DISPLAY = ":" + os.environ.get("DISPLAY_NUM", "99")
WORK = os.path.expanduser(os.environ.get("WORK", "~/tutorial-work"))
NOISE = ("[vite] connecting", "[vite] connected", "Download the React DevTools", "[vite] hot updated", "[vite] page reload")


class Recorder:
    """ffmpeg x11grab in its own session; stopped with 'q' so the file is finalised."""

    def start(self, path, fps=25):
        self.path = path
        log = open(os.path.join(os.path.dirname(path), "rec.log"), "ab")
        self.p = subprocess.Popen(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "x11grab", "-draw_mouse", "1",
             "-framerate", str(fps), "-video_size", "1920x1080", "-i", DISPLAY,
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p", "-threads", "2", path],
            stdin=subprocess.PIPE, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        self.t0 = time.time()

    def now(self):
        return time.time() - self.t0

    async def stop(self):
        try:
            self.p.stdin.write(b"q")
            self.p.stdin.flush()
        except Exception:
            pass
        for _ in range(100):
            if self.p.poll() is not None:
                return
            await asyncio.sleep(0.2)
        self.p.kill()


class Stage:
    def __init__(self, page, lesson):
        self.page, self.lesson = page, lesson
        self.kb = page.keyboard
        self.project = os.path.expanduser(lesson.get("project", "."))
        self.preview = lesson.get("preview", "http://localhost:5173")
        self.console_on = False

    # ---------- helpers ----------
    def editor(self):
        for f in self.page.frames:
            if (":%d" % CS_PORT) in f.url:
                return f
        return None

    def preview_frame(self):
        host = self.preview.split("//")[-1].split("/")[0].replace("localhost", "")
        for f in self.page.frames:
            if f is not self.page.main_frame and host and host in f.url and (":%d" % CS_PORT) not in f.url:
                return f
        return None

    async def js(self, fn, *args):
        return await self.page.evaluate("(a)=>%s(...a)" % fn, list(args))

    async def key(self, k, pause=0.25):
        await self.kb.press(k)
        await asyncio.sleep(pause)

    async def human_type(self, text, budget=None, chunk="char"):
        if chunk == "word":  # long files: a word at a time still reads as typing, ~3x faster
            words = text.replace("\n", " \n ").split(" ")
            delays, _ = typing_delays("x" * len(words), budget, min_ms=40, max_ms=260)
            for w, d in zip(words, delays):
                if w == "\n":
                    await self.kb.press("Enter")
                elif w:
                    await self.kb.insert_text(w + " ")
                await asyncio.sleep(d)
            return
        delays, _ = typing_delays(text, budget)
        for ch, d in zip(text, delays):
            if ch == "\n":
                await self.kb.press("Enter")
            elif ch == "\t":
                await self.kb.insert_text("  ")
            else:
                await self.kb.type(ch)
            await asyncio.sleep(d)

    async def palette(self, name):
        await self.key("F1", 0.5)
        await self.kb.type(name, delay=18)
        await asyncio.sleep(0.6)
        await self.key("Enter", 0.6)

    async def focus_editor(self):
        await self.page.mouse.click(700, 520)
        await asyncio.sleep(0.2)

    async def open_file(self, rel):
        await self.key("Control+p", 0.5)
        await self.kb.type(rel, delay=25)
        await asyncio.sleep(0.7)
        await self.key("Enter", 0.7)

    async def new_file(self, rel):
        """Create a file the way a beginner would: explorer, folder, New File, type the name."""
        ed = self.editor()
        folder, name = os.path.split(rel)
        ok = False
        try:
            if folder:
                row = ed.locator('.explorer-folders-view .monaco-list-row[aria-label="%s"]' % os.path.basename(folder))
                await row.first.click(timeout=3000)
                await asyncio.sleep(0.4)
            await ed.locator('.explorer-viewlet a[aria-label^="New File"], a.codicon-new-file').first.click(timeout=3000)
            await asyncio.sleep(0.5)
            await self.kb.type(name, delay=60)
            await self.key("Enter", 1.0)
            ok = True
        except Exception as e:
            print("explorer new-file failed (%s); creating on disk and opening it" % e)
        if not ok:
            path = os.path.join(self.project, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "a").close()
            await asyncio.sleep(0.8)
            await self.open_file(rel)

    async def wait_for(self, cond, timeout=180):
        t0 = time.time()
        if isinstance(cond, (int, float)):
            await asyncio.sleep(cond)
            return True
        import urllib.request
        while time.time() - t0 < timeout:
            if "file" in cond and os.path.exists(os.path.join(self.project, os.path.expanduser(cond["file"]))):
                return True
            if "url" in cond:
                try:
                    urllib.request.urlopen(cond["url"], timeout=2)
                    return True
                except Exception:
                    pass
            await asyncio.sleep(1)
        print("WARN wait_for timed out:", cond)
        return False

    # ---------- actions ----------
    async def do(self, a, budget):
        if "slide" in a:
            await self.js("slide", a["slide"])
        elif "hide_slide" in a:
            await self.js("hideSlide")
        elif "cap" in a:
            await self.js("cap", a["cap"], bool(a.get("full")))
        elif "step" in a:
            await self.js("step", a["step"])
        elif "open" in a:
            await self.open_file(a["open"])
        elif "new_file" in a:
            await self.new_file(a["new_file"])
        elif "type" in a:
            await self.human_type(a["type"], a.get("budget", budget), a.get("chunk", "char"))
        elif "select_all" in a:
            await self.key("Control+a", 0.3)
        elif "clear" in a:
            await self.key("Control+a", 0.3)
            await self.key("Delete", 0.4)
        elif "goto" in a:
            await self.key("Control+g", 0.4)
            await self.kb.type(str(a["goto"]), delay=60)
            await self.key("Enter", 0.3)
            await self.key("End" if a.get("col", "end") == "end" else "Home", 0.2)
        elif "select_lines" in a:
            s, e = a["select_lines"]
            await self.do({"goto": s, "col": "start"}, None)
            await self.key("Home", 0.1)
            for _ in range(e - s + 1):
                await self.key("Shift+ArrowDown", 0.08)
        elif "save" in a:
            await self.key("Control+s", 0.8)
        elif "term" in a:
            await self.palette("Terminal: Focus Terminal")
            await asyncio.sleep(0.6)
            await self.human_type(a["term"], None)
            await asyncio.sleep(0.3)
            await self.key("Enter", 0.5)
            if a.get("wait_for") is not None:
                await self.wait_for(a["wait_for"], a.get("timeout", 180))
        elif "term_new" in a:
            await self.palette("Terminal: Create New Terminal")
            await asyncio.sleep(1.0)
        elif "term_keys" in a:  # answer an interactive prompt, e.g. ["ArrowDown", "Enter"]
            for k in a["term_keys"]:
                await self.key(k, 0.6)
        elif "palette" in a:
            await self.palette(a["palette"])
        elif "key" in a:
            await self.key(a["key"], a.get("pause", 0.3))
        elif "focus_editor" in a:
            await self.focus_editor()
        elif "preview" in a:
            await self.js("setPreview", a["preview"] or "")
            await asyncio.sleep(a.get("settle", 1.5))
        elif "reload" in a:
            await self.js("reloadPreview")
            await asyncio.sleep(a.get("settle", 1.5))
        elif "click" in a:
            fr = self.preview_frame()
            if fr is None:
                print("WARN no preview frame for click")
            else:
                for _ in range(a.get("times", 1)):
                    await fr.locator(a["click"]).first.click()
                    await asyncio.sleep(a.get("gap", 0.7))
        elif "fill" in a:
            fr = self.preview_frame()
            await fr.locator(a["fill"]).first.click()
            await self.human_type(a.get("text", ""), None)
        elif "console" in a:
            v = a["console"]
            if v == "clear":
                await self.js("consoleClear")
            else:
                self.console_on = v == "show"
                await self.js("consoleShow", self.console_on)
        elif "write_file" in a:  # off-screen file change (rarely: prefer typing it)
            p = os.path.join(self.project, a["write_file"])
            open(p, "w").write(a.get("text", ""))
        elif "wait" in a:
            await asyncio.sleep(a["wait"])
        elif "mouse" in a:
            x, y = a["mouse"]
            await self.page.mouse.move(x, y, steps=12)
        else:
            print("WARN unknown action", a)

    async def on_console(self, msg):
        try:
            loc = (msg.location or {}).get("url", "")
            if (":%d" % CS_PORT) in loc or loc.startswith("file:"):
                return
            t = msg.text.replace("%c", "").strip()
            if not t or any(n in t for n in NOISE):
                return
            await self.js("consoleLog", msg.type, t[:400])
        except Exception:
            pass


def prepare_files(lesson):
    proj = os.path.expanduser(lesson.get("project", "."))
    st = lesson.get("setup", {})
    for rel in st.get("delete", []):
        p = os.path.join(proj, rel)
        if os.path.exists(p):
            os.remove(p)
    for rel, text in st.get("files", {}).items():
        p = os.path.join(proj, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(text)


async def main_async(args):
    from playwright.async_api import async_playwright

    lesson = load_json(args.lesson)
    out = os.path.expanduser(args.out)
    os.makedirs(out, exist_ok=True)
    narr_path = os.path.join(out, "narration.json")
    narr = load_json(narr_path)["lines"] if os.path.exists(narr_path) else []
    beats = lesson["beats"]
    if narr and len(narr) != len(beats):
        raise SystemExit("narration.json has %d lines, lesson has %d beats: run narrate.py again" % (len(narr), len(beats)))
    prepare_files(lesson)

    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp("http://127.0.0.1:%d" % CDP_PORT)
        ctx = browser.contexts[0]
        page = [p for p in ctx.pages if "harness" in p.url][0]
        await page.reload()
        await asyncio.sleep(1)
        st = Stage(page, lesson)
        page.on("console", lambda m: asyncio.ensure_future(st.on_console(m)))
        await st.js("setEditor", "http://127.0.0.1:%d/?folder=%s" % (CS_PORT, st.project))
        await asyncio.sleep(args.editor_wait)
        # a clean stage: no toasts, no badges, start files open, preview loaded
        await st.focus_editor()
        await st.palette("Notifications: Clear All Notifications")
        for rel in lesson.get("setup", {}).get("open", []):
            await st.open_file(rel)
        await st.js("setPreview", lesson.get("start_preview", "") or "")
        await asyncio.sleep(1.5)
        await page.mouse.move(1180, 1075)
        if args.dry_run:
            print("stage ready (dry run): check it with rig.sh shot")
            return

        rec = Recorder()
        raw = os.path.join(out, "raw.mkv")
        rec.start(raw)
        await asyncio.sleep(args.lead)
        rows = []
        try:
            for i, b in enumerate(beats):
                d = narr[i]["dur"] if narr else 0.0
                t0 = rec.now()
                if "slide" in b:
                    await st.js("slide", b["slide"])
                elif b.get("hide_slide", True) and i and "slide" in beats[i - 1]:
                    await st.js("hideSlide")
                if "cap" in b:
                    await st.js("cap", b["cap"] or "", bool(b.get("full")))
                if "step" in b:
                    await st.js("step", b["step"] or "")
                acts = b.get("do", [])
                typed = sum(len(a["type"]) for a in acts if "type" in a and "budget" not in a)
                for a in acts:
                    bud = None
                    if "type" in a and "budget" not in a and typed and d:
                        # spread the narration over the typing so the voice explains while the code appears
                        bud = max(1.0, (d - 0.8) * len(a["type"]) / typed)
                    await st.do(a, bud)
                el = rec.now() - t0
                rest = d + b.get("pad", args.gap) - el
                if rest > 0:
                    await asyncio.sleep(rest)
                elif d and el > d + 2.5:
                    print("WARN beat %d ran %.1f s past its narration (silent stretch): add a line or type faster" % (i, el - d))
                rows.append({"i": i, "t": round(t0, 3), "dur": d, "clip": narr[i]["clip"] if narr else None,
                             "text": b.get("say", ""), "cap": b.get("cap")})
                print("beat %02d at %6.1fs  narr %4.1fs  screen %4.1fs" % (i, t0, d, rec.now() - t0))
            await asyncio.sleep(args.tail)
        finally:
            await rec.stop()
        total = rec.now()
        save_json({"slug": lesson.get("slug"), "title": lesson.get("title"), "raw": raw, "total": round(total, 3), "beats": rows},
                  os.path.join(out, "timeline.json"))
        print("recorded %.1f s -> %s" % (total, raw))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lead", type=float, default=0.6, help="seconds recorded before the first beat")
    ap.add_argument("--tail", type=float, default=1.5)
    ap.add_argument("--gap", type=float, default=0.35, help="breath between beats")
    ap.add_argument("--editor-wait", type=float, default=8.0, help="seconds for code-server to load")
    ap.add_argument("--dry-run", action="store_true", help="set the stage, do not record")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
