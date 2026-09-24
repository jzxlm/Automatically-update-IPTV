from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_v54_1_result.json"
OUTPUT_FILE = BASE_DIR / "data" / "movie_v55_ffprobe.json"
SUMMARY_FILE = BASE_DIR / "data" / "movie_v55_summary.json"

WORKERS = 8
PROBE_TIMEOUT = 18
MAX_ROWS = 0  # 0 = all

# Common local FFmpeg/FFprobe locations. The script does not install anything automatically.
FFPROBE_CANDIDATES = [
    shutil.which("ffprobe"),
    shutil.which("ffprobe.exe"),
    str(BASE_DIR / "ffmpeg" / "bin" / "ffprobe.exe"),
    str(BASE_DIR / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"),
    str(BASE_DIR / "tools" / "ffprobe.exe"),
]


STAR_RULES = {
    "成龙": ["成龙", "jackie chan"],
    "李连杰": ["李连杰", "jet li"],
    "李小龙": ["李小龙", "bruce lee"],
    "周润发": ["周润发", "chow yun-fat", "chow yun fat"],
    "周星驰": ["周星驰", "stephen chow"],
    "甄子丹": ["甄子丹", "donnie yen"],
    "洪金宝": ["洪金宝", "sammo hung"],
    "元彪": ["元彪", "yuen biao"],
    "狄龙": ["狄龙", "ti lung"],
    "姜大卫": ["姜大卫", "david chiang"],
    "刘德华": ["刘德华", "andy lau"],
    "梁朝伟": ["梁朝伟", "tony leung"],
    "张国荣": ["张国荣", "leslie cheung"],
    "林正英": ["林正英", "lam ching-ying", "lam ching ying"],
    "黄秋生": ["黄秋生", "anthony wong"],
    "吴镇宇": ["吴镇宇", "francis ng"],
    "史泰龙": ["史泰龙", "sylvester stallone"],
    "施瓦辛格": ["施瓦辛格", "arnold schwarzenegger", "arnold schwarzenegger"],
    "汤姆·克鲁斯": ["汤姆·克鲁斯", "tom cruise"],
    "基努·里维斯": ["基努·里维斯", "keanu reeves"],
    "布鲁斯·威利斯": ["布鲁斯·威利斯", "bruce willis"],
    "尼古拉斯·凯奇": ["尼古拉斯·凯奇", "nicolas cage"],
    "杰森·斯坦森": ["杰森·斯坦森", "jason statham"],
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def find_ffprobe() -> str | None:
    for item in FFPROBE_CANDIDATES:
        if item and Path(item).exists():
            return str(Path(item))
    return None


def pick_url(row: dict[str, Any]) -> str:
    for key in ("playlist_url", "url", "stream_url", "source_url"):
        value = clean_text(row.get(key))
        if value.startswith(("http://", "https://")):
            return value
    return ""


def metadata_text(row: dict[str, Any]) -> str:
    keys = (
        "name", "alt", "group", "group_title", "tvg_id", "tvg_name",
        "title", "channel", "playlist_title", "category", "source",
    )
    return " | ".join(clean_text(row.get(k)) for k in keys if row.get(k))


def star_hits(text: str) -> list[str]:
    low = text.lower()
    hits: list[str] = []
    for star, words in STAR_RULES.items():
        if any(w.lower() in low for w in words):
            hits.append(star)
    return hits


def run_ffprobe(ffprobe: str, url: str) -> dict[str, Any]:
    cmd = [
        ffprobe,
        "-hide_banner",
        "-v", "error",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36",
        "-rw_timeout", "12000000",
        "-analyzeduration", "3000000",
        "-probesize", "3000000",
        "-show_entries",
        "format=duration,bit_rate,format_name,size:stream=index,codec_type,codec_name,profile,width,height,r_frame_rate,avg_frame_rate,bit_rate,channels,sample_rate,language,codec_long_name",
        "-of", "json",
        url,
    ]

    started = time.time()
    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROBE_TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "elapsed": round(time.time() - started, 2)}
    except Exception as exc:
        return {"ok": False, "error": f"exception:{type(exc).__name__}:{exc}", "elapsed": round(time.time() - started, 2)}

    elapsed = round(time.time() - started, 2)
    if p.returncode != 0:
        err = (p.stderr or "").strip().replace("\r", " ").replace("\n", " ")
        return {"ok": False, "error": err[:500], "elapsed": elapsed, "returncode": p.returncode}

    try:
        data = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_json", "elapsed": elapsed}

    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    result = {
        "ok": bool(video),
        "elapsed": elapsed,
        "format": data.get("format") or {},
        "video": video or {},
        "audio": audio or {},
        "stream_count": len(streams),
    }
    if not video:
        result["error"] = "no_video_stream"
    return result


def simplify_probe(probe: dict[str, Any]) -> dict[str, Any]:
    video = probe.get("video") or {}
    audio = probe.get("audio") or {}
    fmt = probe.get("format") or {}
    return {
        "ok": bool(probe.get("ok")),
        "elapsed": probe.get("elapsed"),
        "format_name": fmt.get("format_name"),
        "duration": fmt.get("duration"),
        "bit_rate": fmt.get("bit_rate"),
        "video_codec": video.get("codec_name"),
        "video_profile": video.get("profile"),
        "width": video.get("width"),
        "height": video.get("height"),
        "fps": video.get("avg_frame_rate") or video.get("r_frame_rate"),
        "video_bitrate": video.get("bit_rate"),
        "audio_codec": audio.get("codec_name"),
        "audio_channels": audio.get("channels"),
        "audio_sample_rate": audio.get("sample_rate"),
        "language": video.get("language") or audio.get("language"),
        "stream_count": probe.get("stream_count", 0),
    }


def analyze_row(ffprobe: str, row: dict[str, Any]) -> dict[str, Any]:
    url = pick_url(row)
    text = metadata_text(row)
    base = dict(row)
    base["v55"] = {
        "url_used": url,
        "metadata_star_hits": star_hits(text),
        "ffprobe": {"ok": False, "error": "no_url"},
    }
    if not url:
        return base

    probe = run_ffprobe(ffprobe, url)
    base["v55"]["ffprobe"] = simplify_probe(probe)
    return base


def load_rows() -> list[dict[str, Any]]:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"找不到输入文件: {INPUT_FILE}")
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        for key in ("rows", "items", "results", "data"):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise ValueError("输入 JSON 不是列表结构")
    rows = [x for x in data if isinstance(x, dict)]
    if MAX_ROWS > 0:
        rows = rows[:MAX_ROWS]
    return rows


def pct(n: int, total: int) -> str:
    return f"{n / total * 100:.1f}%" if total else "0.0%"


def main() -> None:
    print("=== V5.5 FFprobe Real Video Analyzer ===")
    print(f"Input: {INPUT_FILE}")

    ffprobe = find_ffprobe()
    if not ffprobe:
        print("\nFFprobe: NOT INSTALLED / NOT FOUND")
        print("V5.5 requires FFprobe. The script will NOT install software automatically.")
        print("\nRecommended Windows install:")
        print("1. Install FFmpeg (ffprobe is included).")
        print("2. Add FFmpeg\\bin to PATH, or put ffprobe.exe in:")
        print(f"   {BASE_DIR / 'tools' / 'ffmpeg' / 'bin'}")
        print("3. Verify with: ffprobe -version")
        print("\nNo output was generated because actual video probing cannot run without FFprobe.")
        return

    rows = load_rows()
    print(f"Input rows: {len(rows)}")
    print(f"FFprobe: {ffprobe}")
    print(f"Workers: {WORKERS}")
    print(f"Probe timeout: {PROBE_TIMEOUT}s")
    print()

    results: list[dict[str, Any] | None] = [None] * len(rows)
    done = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(analyze_row, ffprobe, row): i for i, row in enumerate(rows)}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as exc:
                results[idx] = {
                    **rows[idx],
                    "v55": {"url_used": pick_url(rows[idx]), "metadata_star_hits": [], "ffprobe": {"ok": False, "error": f"worker:{exc}"}},
                }
            done += 1
            if done % 25 == 0 or done == len(rows):
                elapsed = time.time() - started
                rate = done / elapsed if elapsed else 0
                print(f"Analyzed: {done}/{len(rows)} | {rate:.1f}/s")

    final_rows = [r for r in results if r is not None]
    ok = [r for r in final_rows if r.get("v55", {}).get("ffprobe", {}).get("ok")]
    failed = [r for r in final_rows if not r.get("v55", {}).get("ffprobe", {}).get("ok")]

    codec_counts: dict[str, int] = {}
    resolution_counts: dict[str, int] = {}
    fps_counts: dict[str, int] = {}
    star_counts: dict[str, int] = {}
    error_counts: dict[str, int] = {}

    for row in final_rows:
        p = row.get("v55", {}).get("ffprobe", {})
        if p.get("ok"):
            codec = clean_text(p.get("video_codec")) or "unknown"
            res = f"{p.get('width')}x{p.get('height')}" if p.get("width") and p.get("height") else "unknown"
            fps = clean_text(p.get("fps")) or "unknown"
            codec_counts[codec] = codec_counts.get(codec, 0) + 1
            resolution_counts[res] = resolution_counts.get(res, 0) + 1
            fps_counts[fps] = fps_counts.get(fps, 0) + 1
        else:
            err = clean_text(p.get("error")) or "unknown"
            err = re.sub(r"\s+", " ", err)[:120]
            error_counts[err] = error_counts.get(err, 0) + 1
        for star in row.get("v55", {}).get("metadata_star_hits", []):
            star_counts[star] = star_counts.get(star, 0) + 1

    summary = {
        "version": "V5.5",
        "input_rows": len(rows),
        "ffprobe_path": ffprobe,
        "workers": WORKERS,
        "probe_timeout": PROBE_TIMEOUT,
        "ffprobe_ok": len(ok),
        "ffprobe_failed": len(failed),
        "ffprobe_success_rate": round(len(ok) / len(final_rows), 4) if final_rows else 0,
        "metadata_star_hits": dict(sorted(star_counts.items(), key=lambda x: (-x[1], x[0]))),
        "video_codec": dict(sorted(codec_counts.items(), key=lambda x: (-x[1], x[0]))),
        "resolution": dict(sorted(resolution_counts.items(), key=lambda x: (-x[1], x[0]))),
        "fps": dict(sorted(fps_counts.items(), key=lambda x: (-x[1], x[0]))),
        "errors": dict(sorted(error_counts.items(), key=lambda x: (-x[1], x[0]))),
        "next_stage": "V5.6 frame sampling -> V6 visual/content classification",
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(final_rows, f, ensure_ascii=False, indent=2)
    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== V5.5 Result ===")
    print(f"FFprobe OK: {len(ok)}")
    print(f"FFprobe Failed: {len(failed)}")
    print(f"Success rate: {pct(len(ok), len(final_rows))}")
    print("\nTop codecs:")
    for k, v in list(summary["video_codec"].items())[:10]:
        print(f"  {k}: {v}")
    print("\nTop resolutions:")
    for k, v in list(summary["resolution"].items())[:10]:
        print(f"  {k}: {v}")
    print("\nMetadata star hits:")
    if star_counts:
        for k, v in list(summary["metadata_star_hits"].items())[:20]:
            print(f"  {k}: {v}")
    else:
        print("  none")

    print("\nDone.")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()
