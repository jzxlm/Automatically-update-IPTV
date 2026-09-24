from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_v55_ffprobe.json"
OUTPUT_FILE = BASE_DIR / "data" / "movie_v55_1_retry.json"
SUMMARY_FILE = BASE_DIR / "data" / "movie_v55_1_summary.json"

WORKERS = 8
RETRY_TIMEOUT = 12
MAX_RETRIES = 3

FFPROBE_CANDIDATES = [
    shutil.which("ffprobe"),
    shutil.which("ffprobe.exe"),
    str(BASE_DIR / "ffmpeg" / "bin" / "ffprobe.exe"),
    str(BASE_DIR / "tools" / "ffmpeg" / "bin" / "ffprobe.exe"),
    str(BASE_DIR / "tools" / "ffprobe.exe"),
]

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)


def clean_text(value: Any) -> str:
    return "" if value is None else str(value).strip()


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


def error_class(stderr: str, returncode: int | None = None) -> str:
    s = (stderr or "").lower()

    if "timed out" in s or "timeout" in s:
        return "timeout"
    if "403 forbidden" in s or "http error 403" in s:
        return "http_403"
    if "404 not found" in s or "http error 404" in s:
        return "http_404"
    if "401 unauthorized" in s or "http error 401" in s:
        return "http_401"
    if "429 too many requests" in s or "http error 429" in s:
        return "http_429"
    if "server returned 5" in s or re.search(r"http error 5\d\d", s):
        return "http_5xx"
    if "tls" in s or "ssl" in s or "certificate" in s:
        return "tls_ssl"
    if "connection refused" in s:
        return "connection_refused"
    if "connection reset" in s or "reset by peer" in s:
        return "connection_reset"
    if "could not resolve" in s or "name or service not known" in s:
        return "dns"
    if "invalid data found" in s:
        return "invalid_data"
    if "no video stream" in s:
        return "no_video"
    if "server returned 4" in s:
        return "http_4xx"
    if "m3u8" in s or "hls" in s:
        return "hls_error"
    if returncode == -9:
        return "killed"
    return "other"


def run_probe(
    ffprobe: str,
    url: str,
    mode: str,
) -> dict[str, Any]:
    """
    Three modes:
      1) normal: ordinary HTTP/HLS probe
      2) hls: explicitly prefer HLS and allow reconnect
      3) headers: stronger browser-like headers
    """
    common = [
        ffprobe,
        "-hide_banner",
        "-v", "error",
        "-rw_timeout", str(RETRY_TIMEOUT * 1_000_000),
        "-analyzeduration", "5000000",
        "-probesize", "5000000",
    ]

    if mode == "normal":
        extra = [
            "-user_agent", UA,
            "-http_persistent", "0",
        ]
    elif mode == "hls":
        extra = [
            "-user_agent", UA,
            "-http_persistent", "0",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-reconnect_delay_max", "3",
        ]
    else:
        extra = [
            "-user_agent", UA,
            "-http_persistent", "0",
            "-headers",
            "Accept: */*\r\n"
            "Accept-Language: zh-CN,zh;q=0.9,en;q=0.8\r\n"
            "Connection: keep-alive\r\n",
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_on_network_error", "1",
            "-reconnect_delay_max", "3",
        ]

    cmd = common + extra + [
        "-show_entries",
        "format=duration,bit_rate,format_name,size:"
        "stream=index,codec_type,codec_name,profile,width,height,"
        "r_frame_rate,avg_frame_rate,bit_rate,channels,sample_rate,"
        "language,codec_long_name",
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
            timeout=RETRY_TIMEOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "class": "timeout",
            "mode": mode,
            "elapsed": round(time.time() - started, 2),
            "stderr": "timeout",
        }
    except Exception as exc:
        return {
            "ok": False,
            "class": "exception",
            "mode": mode,
            "elapsed": round(time.time() - started, 2),
            "stderr": str(exc)[:500],
        }

    elapsed = round(time.time() - started, 2)
    stderr = (p.stderr or "").strip()
    if p.returncode != 0:
        return {
            "ok": False,
            "class": error_class(stderr, p.returncode),
            "mode": mode,
            "elapsed": elapsed,
            "returncode": p.returncode,
            "stderr": re.sub(r"\s+", " ", stderr)[:500],
        }

    try:
        data = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "ok": False,
            "class": "invalid_json",
            "mode": mode,
            "elapsed": elapsed,
            "stderr": re.sub(r"\s+", " ", stderr)[:500],
        }

    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    if not video:
        return {
            "ok": False,
            "class": "no_video",
            "mode": mode,
            "elapsed": elapsed,
            "stream_count": len(streams),
        }

    fmt = data.get("format") or {}
    return {
        "ok": True,
        "class": "ok",
        "mode": mode,
        "elapsed": elapsed,
        "format_name": fmt.get("format_name"),
        "duration": fmt.get("duration"),
        "bit_rate": fmt.get("bit_rate"),
        "video": video,
        "audio": audio or {},
        "stream_count": len(streams),
    }


def simplify(probe: dict[str, Any]) -> dict[str, Any]:
    video = probe.get("video") or {}
    audio = probe.get("audio") or {}
    return {
        "ok": bool(probe.get("ok")),
        "mode": probe.get("mode"),
        "elapsed": probe.get("elapsed"),
        "format_name": probe.get("format_name"),
        "duration": probe.get("duration"),
        "bit_rate": probe.get("bit_rate"),
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


def retry_failed(ffprobe: str, row: dict[str, Any]) -> dict[str, Any]:
    url = pick_url(row)
    v55 = row.get("v55") or {}
    old_probe = v55.get("ffprobe") or {}

    result = dict(row)
    new_v55 = dict(v55)
    retry_info = {
        "attempted": False,
        "success": False,
        "attempts": [],
    }

    if not url:
        retry_info["final_error_class"] = "no_url"
        new_v55["v55_1_retry"] = retry_info
        result["v55"] = new_v55
        return result

    if old_probe.get("ok"):
        retry_info["skipped"] = "already_ok_in_v55"
        new_v55["v55_1_retry"] = retry_info
        result["v55"] = new_v55
        return result

    retry_info["attempted"] = True

    for mode in ("normal", "hls", "headers"):
        probe = run_probe(ffprobe, url, mode)
        retry_info["attempts"].append({
            "mode": mode,
            "ok": probe.get("ok", False),
            "class": probe.get("class"),
            "elapsed": probe.get("elapsed"),
        })

        if probe.get("ok"):
            new_v55["ffprobe_retry"] = simplify(probe)
            retry_info["success"] = True
            retry_info["success_mode"] = mode
            retry_info["final_error_class"] = "recovered"
            new_v55["v55_1_retry"] = retry_info
            result["v55"] = new_v55
            return result

    retry_info["final_error_class"] = retry_info["attempts"][-1]["class"] if retry_info["attempts"] else "unknown"
    new_v55["v55_1_retry"] = retry_info
    result["v55"] = new_v55
    return result


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
    return [x for x in data if isinstance(x, dict)]


def main() -> None:
    print("=== V5.5.1 FFprobe Retry + Failure Diagnostics ===")
    print(f"Input: {INPUT_FILE}")

    ffprobe = find_ffprobe()
    if not ffprobe:
        print("FFprobe: NOT FOUND")
        return

    rows = load_rows()
    print(f"Input rows: {len(rows)}")

    old_ok = [
        r for r in rows
        if (r.get("v55") or {}).get("ffprobe", {}).get("ok")
    ]
    failed_rows = [
        r for r in rows
        if not (r.get("v55") or {}).get("ffprobe", {}).get("ok")
    ]

    print(f"Already OK from V5.5: {len(old_ok)}")
    print(f"Need retry: {len(failed_rows)}")
    print(f"Workers: {WORKERS}")
    print(f"Retry timeout: {RETRY_TIMEOUT}s")
    print("Retry modes: normal -> HLS reconnect -> browser headers")
    print()

    retry_results: list[dict[str, Any] | None] = [None] * len(failed_rows)
    done = 0
    started = time.time()

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(retry_failed, ffprobe, row): i
            for i, row in enumerate(failed_rows)
        }

        for future in as_completed(futures):
            idx = futures[future]
            try:
                retry_results[idx] = future.result()
            except Exception as exc:
                row = dict(failed_rows[idx])
                row.setdefault("v55", {})
                row["v55"]["v55_1_retry"] = {
                    "attempted": True,
                    "success": False,
                    "final_error_class": "worker_exception",
                    "error": str(exc)[:500],
                    "attempts": [],
                }
                retry_results[idx] = row

            done += 1
            if done % 25 == 0 or done == len(failed_rows):
                elapsed = time.time() - started
                rate = done / elapsed if elapsed else 0
                print(f"Retried: {done}/{len(failed_rows)} | {rate:.2f}/s")

    recovered = [
        r for r in retry_results
        if r and (r.get("v55") or {}).get("v55_1_retry", {}).get("success")
    ]

    final_rows = old_ok + [r for r in retry_results if r is not None]

    failure_classes: dict[str, int] = {}
    for r in retry_results:
        info = (r.get("v55") or {}).get("v55_1_retry") or {}
        if info.get("success"):
            continue
        cls = clean_text(info.get("final_error_class")) or "unknown"
        failure_classes[cls] = failure_classes.get(cls, 0) + 1

    recovered_codecs: dict[str, int] = {}
    recovered_resolutions: dict[str, int] = {}
    recovered_modes: dict[str, int] = {}

    for r in recovered:
        p = (r.get("v55") or {}).get("ffprobe_retry") or {}
        codec = clean_text(p.get("video_codec")) or "unknown"
        res = (
            f"{p.get('width')}x{p.get('height')}"
            if p.get("width") and p.get("height")
            else "unknown"
        )
        mode = clean_text(p.get("mode")) or "unknown"

        recovered_codecs[codec] = recovered_codecs.get(codec, 0) + 1
        recovered_resolutions[res] = recovered_resolutions.get(res, 0) + 1
        recovered_modes[mode] = recovered_modes.get(mode, 0) + 1

    total_ok = len(old_ok) + len(recovered)
    total = len(final_rows)

    summary = {
        "version": "V5.5.1",
        "input_rows": len(rows),
        "ffprobe_path": ffprobe,
        "workers": WORKERS,
        "retry_timeout": RETRY_TIMEOUT,
        "retry_modes": ["normal", "hls", "headers"],
        "already_ok": len(old_ok),
        "retry_attempted": len(failed_rows),
        "recovered": len(recovered),
        "still_failed": len(failed_rows) - len(recovered),
        "final_ffprobe_ok": total_ok,
        "final_ffprobe_failed": total - total_ok,
        "final_success_rate": round(total_ok / total, 4) if total else 0,
        "failure_classes": dict(sorted(
            failure_classes.items(), key=lambda x: (-x[1], x[0])
        )),
        "recovered_by_mode": dict(sorted(
            recovered_modes.items(), key=lambda x: (-x[1], x[0])
        )),
        "recovered_codecs": dict(sorted(
            recovered_codecs.items(), key=lambda x: (-x[1], x[0])
        )),
        "recovered_resolutions": dict(sorted(
            recovered_resolutions.items(), key=lambda x: (-x[1], x[0])
        )),
        "next_stage": "V5.6 frame sampling for confirmed playable sources",
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(final_rows, f, ensure_ascii=False, indent=2)

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== V5.5.1 Result ===")
    print(f"Original FFprobe OK: {len(old_ok)}")
    print(f"Retry attempted: {len(failed_rows)}")
    print(f"Recovered: {len(recovered)}")
    print(f"Still failed: {len(failed_rows) - len(recovered)}")
    print(f"Final FFprobe OK: {total_ok}")
    print(f"Final success rate: {total_ok / total * 100:.1f}%" if total else "Final success rate: 0.0%")

    print("\nFailure classes after retry:")
    for k, v in list(summary["failure_classes"].items())[:20]:
        print(f"  {k}: {v}")

    print("\nRecovered by mode:")
    for k, v in summary["recovered_by_mode"].items():
        print(f"  {k}: {v}")

    print("\nRecovered codecs:")
    for k, v in list(summary["recovered_codecs"].items())[:10]:
        print(f"  {k}: {v}")

    print("\nDone.")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)


if __name__ == "__main__":
    main()
