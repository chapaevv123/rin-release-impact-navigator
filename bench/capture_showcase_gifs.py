"""Capture genuine local RIN UI interactions as compact GitHub GIFs."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import time
import urllib.request
from pathlib import Path

import websocket
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE = ROOT / "artifacts/browser_showcase_capture_profile"
OUT = ROOT / "docs/media"
PORT = 9251
URL = "http://127.0.0.1:8000/ui/"


def main() -> None:
    if not CHROME.is_file() or not PROFILE.resolve().is_relative_to(ROOT.resolve()):
        raise RuntimeError("isolated Chrome capture prerequisites unavailable")
    OUT.mkdir(parents=True, exist_ok=True)
    browser = subprocess.Popen([
        str(CHROME), "--headless=new", "--no-first-run", "--disable-extensions",
        "--disable-background-networking", "--remote-allow-origins=*",
        f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
        "--window-size=1920,1080", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    ws = None
    try:
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=1))
                page = next(x for x in targets if x.get("type") == "page")
                ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=8, origin="http://localhost")
                break
            except (OSError, ValueError, StopIteration):
                time.sleep(.25)
        if ws is None:
            raise RuntimeError("isolated Chrome CDP unavailable")
        counter = 0

        def cdp(method, params=None):
            nonlocal counter
            counter += 1
            ident = counter
            ws.send(json.dumps({"id": ident, "method": method, "params": params or {}}))
            while True:
                message = json.loads(ws.recv())
                if message.get("id") == ident:
                    if "error" in message:
                        raise RuntimeError(f"CDP {method}: {message['error']}")
                    return message.get("result", {})

        def evaluate(expression):
            result = cdp("Runtime.evaluate", {"expression": expression, "returnByValue": True,
                                             "awaitPromise": True})
            if result.get("exceptionDetails"):
                raise RuntimeError(f"UI expression failed: {expression}")
            return result["result"].get("value")

        def until(expression, expected=True):
            for _ in range(60):
                actual = evaluate(expression)
                if actual == expected:
                    return
                time.sleep(.1)
            raise AssertionError(f"{expression}: expected {expected!r}, got {actual!r}")

        def click(selector):
            evaluate(f"document.querySelector({json.dumps(selector)}).scrollIntoView({{block:'center',behavior:'instant'}})")
            time.sleep(.1)
            bounds = evaluate(f"(() => {{ const r=document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return {{x:r.x+r.width/2,y:r.y+r.height/2}}; }})()")
            for kind in ("mouseMoved", "mousePressed", "mouseReleased"):
                cdp("Input.dispatchMouseEvent", {"type": kind, "x": bounds["x"], "y": bounds["y"],
                                                 "button": "left", "clickCount": 1})

        def capture(crop):
            screenshot = cdp("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})["data"]
            frame = Image.open(io.BytesIO(base64.b64decode(screenshot))).convert("RGB")
            frame = frame.crop(crop)
            width = 1100
            return frame.resize((width, round(frame.height * width / frame.width)), Image.Resampling.LANCZOS)

        manifest = {"source": "genuine local Chrome/CDP interaction captures", "url": URL,
                    "viewport": "1920x1080", "mode": "saved replay; no external sponsor requests", "animations": []}

        def save(name, labels, frames, duration):
            if len(labels) != len(frames):
                raise AssertionError("frame provenance mismatch")
            palette = [f.quantize(colors=64, method=Image.Quantize.FASTOCTREE,
                                  dither=Image.Dither.NONE) for f in frames]
            path = OUT / name
            palette[0].save(path, save_all=True, append_images=palette[1:], duration=duration,
                            loop=0, optimize=True, disposal=2)
            with Image.open(path) as check:
                if check.n_frames != len(frames):
                    raise AssertionError(f"GIF frame count mismatch: {path}")
            payload = path.read_bytes()
            manifest["animations"].append({"file": str(path.relative_to(ROOT)).replace('\\', '/'),
                "states": labels, "frames": len(frames), "duration_ms_per_frame": duration,
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()})

        cdp("Runtime.enable")
        cdp("Page.enable")
        cdp("Network.enable")
        cdp("Network.setCacheDisabled", {"cacheDisabled": True})
        cdp("Emulation.setDeviceMetricsOverride", {"width": 1920, "height": 1080,
            "screenWidth": 1920, "screenHeight": 1080, "deviceScaleFactor": 1, "mobile": False})
        cdp("Page.navigate", {"url": URL})
        until("document.getElementById('inspector-status')?.textContent", "VERIFIED RECEIPT")
        until("!document.getElementById('trace-model').disabled")
        until("!document.getElementById('trace-zetaris').disabled")
        evaluate("document.documentElement.style.scrollBehavior='auto'")
        canvas_frames = []
        canvas_labels = []
        for stage in ("release", "api", "use", "runtime", "decision"):
            click(f"[data-stage={stage}]")
            until(f"document.querySelector('[data-stage={stage}]').getAttribute('aria-pressed')", "true")
            until("document.getElementById('inspector-status').textContent.includes('VERIFIED') || document.getElementById('inspector-status').textContent.includes('BOUNDED')")
            canvas_frames.append(capture((95, 365, 1885, 895)))
            canvas_labels.append(f"selected {stage}; Evidence Inspector updated")
        save("investigation_canvas.gif", canvas_labels, canvas_frames, 1100)

        evaluate("location.hash='#/hypotheses'")
        until("document.querySelector('[data-view]:not([hidden])').dataset.view", "hypotheses")
        hypothesis_frames = []
        hypothesis_labels = []
        for index, state in ((1, "SUPPORTED"), (2, "REFUTED"), (3, "UNRESOLVED")):
            click(f"#hypothesis-list button:nth-child({index})")
            until("document.querySelector('#hypothesis-detail .route-kicker').textContent.includes(" + json.dumps(state) + ")")
            evaluate("window.scrollTo(0,0)")
            hypothesis_frames.append(capture((125, 175, 1870, 950)))
            hypothesis_labels.append(f"selected recorded {state} hypothesis")
        save("hypothesis_ledger.gif", hypothesis_labels, hypothesis_frames, 1500)

        evaluate("location.hash='#/replays'")
        until("document.querySelector('[data-view]:not([hidden])').dataset.view", "replays")
        replay_frames = []
        replay_labels = []
        for index, label in ((1, "Zetaris saved SQL JOIN"), (2, "Meterless saved graph"),
                             (3, "NVIDIA saved hypothesis")):
            click(f"#replay-list button:nth-child({index})")
            until("document.getElementById('receipt-dialog').open")
            replay_frames.append(capture((510, 130, 1410, 880)))
            replay_labels.append(label + " receipt dialog")
            evaluate("document.getElementById('receipt-dialog').close()")
            until("!document.getElementById('receipt-dialog').open")
        save("sponsor_replays.gif", replay_labels, replay_frames, 1700)
        (OUT / "showcase_capture_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                                              encoding="utf-8")
        print(json.dumps({"animations": manifest["animations"]}, indent=2))
    finally:
        if ws:
            ws.close()
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()


if __name__ == "__main__":
    main()
