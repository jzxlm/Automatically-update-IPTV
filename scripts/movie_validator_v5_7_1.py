from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_tv_v56_result.json"
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "output"

WORKERS = 24
CONNECT_TIMEOUT = 4
READ_TIMEOUT = 6
MAX_BYTES = 256 * 1024

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/153.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Connection": "close",
}

def load_rows():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if isinstance(obj, list):
        return obj
    for k in ("rows", "items", "results", "sources", "data"):
        if isinstance(obj.get(k), list):
            return obj[k]
    raise ValueError("找不到输入列表")

def pick_url(row):
    if isinstance(row, str):
        return row.strip()
    for k in ("url", "stream_url", "stream", "source_url", "play_url", "playurl"):
        v = row.get(k)
        if isinstance(v, str) and v.startswith(("http://", "https://")):
            return v.strip()
    return ""

def pick_name(row):
    if isinstance(row, str):
        return "Unnamed"
    for k in ("name", "channel_name", "title", "channel", "display_name"):
        if row.get(k):
            return str(row[k])
    return "Unnamed"

def norm_url(url):
    try:
        p = urlsplit(url.strip())
        host = (p.hostname or "").lower()
        port = p.port
        netloc = host
        if port and not ((p.scheme == "http" and port == 80) or
                         (p.scheme == "https" and port == 443)):
            netloc += f":{port}"
        return urlunsplit((p.scheme.lower(), netloc, p.path or "/", p.query, ""))
    except Exception:
        return url.strip()

def check(row):
    url = row["url"]
    result = dict(row)
    result.update({
        "status": "failed",
        "http_status": None,
        "content_type": "",
        "bytes": 0,
        "elapsed_ms": None,
        "playlist": False,
        "error": "",
    })
    t0 = time.perf_counter()
    try:
        with requests.get(
            url,
            headers=HEADERS,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
            allow_redirects=True,
        ) as r:
            result["http_status"] = r.status_code
            result["content_type"] = r.headers.get("Content-Type", "")
            buf = b""
            for chunk in r.iter_content(chunk_size=16384):
                if chunk:
                    buf += chunk
                    if len(buf) >= MAX_BYTES:
                        break

            result["bytes"] = len(buf)
            ct = result["content_type"].lower()
            head = buf[:8192].decode("utf-8", errors="ignore").lower()
            path = urlsplit(r.url).path.lower()

            is_playlist = (
                "#extm3u" in head
                or "#ext-x-" in head
                or path.endswith((".m3u8", ".m3u", ".txt"))
                or "mpegurl" in ct
            )
            result["playlist"] = is_playlist

            if r.status_code >= 400:
                result["error"] = f"http_{r.status_code}"
            elif not buf:
                result["error"] = "empty_response"
            elif not is_playlist:
                result["error"] = "not_playlist"
            else:
                result["status"] = "ok"
    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.SSLError:
        result["error"] = "sslerror"
    except requests.exceptions.RequestException as e:
        result["error"] = type(e).__name__.lower()
    except Exception as e:
        result["error"] = type(e).__name__.lower()
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return result

def speed(ms):
    if ms is None:
        return "FAIL"
    if ms < 1000:
        return "S1"
    if ms < 2000:
        return "S2"
    if ms < 4000:
        return "S3"
    if ms < 8000:
        return "S4"
    return "S5"

def main():
    print("=== V5.7.1 Full Result Validator ===")
    print("IMPORTANT: success and failure rows are BOTH saved.")
    print("No video frame analysis. No AI.")
    print(f"Input: {INPUT_FILE}")

    rows = load_rows()
    candidates = []
    seen = set()

    for row in rows:
        url = pick_url(row)
        if not url:
            continue
        key = norm_url(url)
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "url": url,
            "name": pick_name(row),
            "source": row,
        })

    print(f"Input rows: {len(rows)}")
    print(f"Unique URLs before test: {len(candidates)}")
    print(f"Workers: {WORKERS}")
    print(f"Timeout: {CONNECT_TIMEOUT}s connect / {READ_TIMEOUT}s read")
    print()

    results = []
    done = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(check, x) for x in candidates]
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 50 == 0 or done == len(futures):
                print(f"Checked: {done}/{len(futures)}")

    results.sort(key=lambda x: (x["status"] != "ok", x.get("elapsed_ms") or 999999))

    ok = [x for x in results if x["status"] == "ok"]
    failed = [x for x in results if x["status"] != "ok"]

    for x in ok:
        x["speed"] = speed(x["elapsed_ms"])

    DATA_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(exist_ok=True)

    # KEY FIX: save ALL rows, including failures.
    result_path = DATA_DIR / "movie_tv_v57_1_result.json"
    summary_path = DATA_DIR / "movie_tv_v57_1_summary.json"

    result_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    speed_counts = {}
    for x in ok:
        s = x["speed"]
        speed_counts[s] = speed_counts.get(s, 0) + 1

    failure_counts = {}
    for x in failed:
        e = x.get("error") or "unknown"
        failure_counts[e] = failure_counts.get(e, 0) + 1

    summary = {
        "version": "V5.7.1",
        "input_rows": len(rows),
        "unique_urls_tested": len(candidates),
        "playlist_ok": len(ok),
        "failed": len(failed),
        "success_rate": round(len(ok) / len(candidates) * 100, 1) if candidates else 0,
        "speed_counts": speed_counts,
        "failure_counts": failure_counts,
        "all_rows_saved": True,
    }

    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    print("=== V5.7.1 Result ===")
    print(f"Unique URLs tested: {len(candidates)}")
    print(f"Playlist OK: {len(ok)}")
    print(f"Failed: {len(failed)}")
    print(f"Success rate: {summary['success_rate']}%")
    print()
    print("Speed:")
    for k in ("S1", "S2", "S3", "S4", "S5"):
        if k in speed_counts:
            print(f"  {k}: {speed_counts[k]}")
    print()
    print("Failure classes:")
    for k, v in sorted(failure_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {k}: {v}")
    print()
    print("ALL success + failure rows saved to:")
    print(result_path)
    print(summary_path)

if __name__ == "__main__":
    main()
