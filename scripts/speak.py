#!/usr/bin/env python3
"""Read the annual report aloud in a chosen dialect.

Backends are tried in order and fall through automatically:

  1. VoxCPM2  - local Gradio endpoint, set VOXCPM_API_URL
                (optionally VOXCPM_REF_AUDIO to point at a dialect reference clip)
  2. macOS say - built-in zh-CN / zh-HK / zh-TW voices, zero dependency
  3. text-only - --dry-run prints the script and exits

Examples:
    python3 scripts/speak.py --dialect cantonese
    python3 scripts/speak.py --dialect voxcpm --ref /path/to/dialect.wav
    python3 scripts/speak.py --dry-run
"""

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_report import compute_metrics  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DEFAULT_DATA = os.path.join(ROOT, "data", "report_data.json")

# macOS built-in voices. Real regional TTS needs VoxCPM2; these give an
# immediately runnable, honest fallback.
MACOS_VOICES = {
    "mandarin": "Tingting",
    "cantonese": "Sinji",
    "taiwanese": "Meijia",
}

DIALECT_LABEL = {
    "mandarin": "普通话",
    "cantonese": "粤语",
    "taiwanese": "闽南语调",
    "voxcpm": "方言克隆",
}


def build_script(m):
    """Compose the narration. Factual and upbeat, no health judgement."""
    top = m["top_items"][0]["name"] if m["top_items"] else "麦当劳"
    return (
        "欢迎收看你的麦当劳年度报告。"
        "在过去这段时间里，你一共下单 {count} 笔，累计消费 {spend} 元，"
        "平均每一单 {ticket} 元。"
        "你最常点的单品是 {top}，一年点了 {topqty} 份。"
        "你最常去的门店是 {store}，一共去了 {storeqty} 次。"
        "你有 {late} 笔订单发生在晚上十点以后，深夜编译指数百分之 {ratio}。"
        "你最长的连续打卡纪录是 {streak} 天，麦龄 {span} 天。"
        "优惠券一共帮你省下 {save} 元。"
        "感谢这一年，麦麦与你同行。"
    ).format(
        count=m["order_count"],
        spend=int(m["total_spend"]),
        ticket=m["avg_ticket"],
        top=top,
        topqty=m["top_items"][0]["qty"] if m["top_items"] else 0,
        store=m["top_store"][0],
        storeqty=m["top_store"][1],
        late=m["late_night"],
        ratio=int(m["late_ratio"]),
        streak=m["best_streak"],
        span=m["span_days"],
        save=int(m["total_discount"]),
    )


def say_macos(text, voice, out_path):
    cmd = ["say", "-v", voice, "-o", out_path]
    if not out_path.endswith(".aiff"):
        cmd += ["--file-format=AIFF"]
    cmd.append(text)
    subprocess.run(cmd, check=True)
    return out_path


def voxcpm(text, out_path, ref_audio=None):
    """Call a local VoxCPM2 Gradio endpoint.

    Payload shape follows Gradio's /api/predict convention; adjust
    VOXCPM_FN_INDEX if the demo exposes a different function index.
    """
    import urllib.request
    import urllib.error
    import base64

    url = os.environ.get("VOXCPM_API_URL", "http://127.0.0.1:7860")
    fn_index = int(os.environ.get("VOXCPM_FN_INDEX", "0"))
    ref = ref_audio or os.environ.get("VOXCPM_REF_AUDIO", "")

    payload = {"fn_index": fn_index, "data": [text, ref] if ref else [text]}
    for endpoint in ("/api/predict", "/run/predict", "/gradio_api/call/predict"):
        req = urllib.request.Request(
            url.rstrip("/") + endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8", "replace"))
            break
        except (urllib.error.URLError, ValueError, urllib.error.HTTPError):
            continue
    else:
        raise RuntimeError("VoxCPM2 endpoint unreachable at %s" % url)

    b64 = None
    for node in (body, body.get("data") if isinstance(body, dict) else None):
        if isinstance(node, list):
            for item in node:
                if isinstance(item, str) and len(item) > 200:
                    b64 = item
                elif isinstance(item, dict) and "path" in item:
                    b64 = item.get("data") or item["path"]
    if not b64:
        raise RuntimeError("unexpected VoxCPM2 response: %s" % str(body)[:200])
    if b64.startswith("http") or os.path.exists(b64):
        raise RuntimeError("VoxCPM2 returned a path, not inline audio: %s" % b64[:120])
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64.split(",")[-1]))
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--dialect", default="mandarin",
                    choices=list(MACOS_VOICES) + ["voxcpm"])
    ap.add_argument("--text", help="override the generated script")
    ap.add_argument("--ref", help="dialect reference audio for VoxCPM2")
    ap.add_argument("--out", help="output audio path")
    ap.add_argument("--dry-run", action="store_true", help="print script only")
    args = ap.parse_args()

    if args.text:
        text = args.text
    else:
        if not os.path.exists(args.data):
            print("no data file: %s" % args.data, file=sys.stderr)
            sys.exit(1)
        with open(args.data, encoding="utf-8") as f:
            m = compute_metrics(json.load(f))
        text = build_script(m)

    if args.dry_run:
        print(text)
        return

    out = args.out or os.path.join(ROOT, "out", "wrapped-%s.aiff" % args.dialect)
    os.makedirs(os.path.dirname(out), exist_ok=True)

    if args.dialect == "voxcpm":
        try:
            voxcpm(text, out, args.ref)
            print("audio written (VoxCPM2): %s" % out)
            return
        except Exception as e:
            print("VoxCPM2 failed (%s), falling back to macOS voices" % e, file=sys.stderr)
            args.dialect = "mandarin"

    voice = MACOS_VOICES[args.dialect]
    try:
        say_macos(text, voice, out)
        print("audio written (%s / %s): %s" % (DIALECT_LABEL[args.dialect], voice, out))
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print("say failed: %s" % e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
