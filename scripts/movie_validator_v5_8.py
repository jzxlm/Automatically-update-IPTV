from __future__ import annotations

import json
import re
import ssl
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_tv_v57_1_result.json"
OUTPUT_FILE = BASE_DIR / "data" / "movie_tv_v58_result.json"
SUMMARY_FILE = BASE_DIR / "data" / "movie_tv_v58_summary.json"
M3U_FILE = BASE_DIR / "output" / "movies_tv_v58_all.m3u"
CAT_DIR = BASE_DIR / "output" / "v58_categories"

WORKERS = 24
NORMAL_RETRIES = 3
HEADER_RETRIES = 3
SSL_RETRIES = 2

CONNECT_TIMEOUT = 4
READ_TIMEOUT = 6
MAX_BYTES = 256 * 1024

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)

NORMAL_HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Connection": "close",
}

BROWSER_HEADERS = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Connection": "close",
    "Referer": "https://www.google.com/",
    "Origin": "https://www.google.com",
}

# Keep the user's desired category priority stable.
CATEGORY_PRIORITY = [
    ("CCTV-1 综合", ["cctv1", "cctv-1", "cctv 1", "中央一台", "中央1台"]),
    ("CCTV-6 电影", ["cctv6", "cctv-6", "cctv 6", "中央六套", "中央6台"]),
    ("CCTV-8 电视剧", ["cctv8", "cctv-8", "cctv 8", "中央八套", "中央8台"]),
    ("经典电视剧", [
        "康熙微服私访记", "宰相刘罗锅", "白鹿原", "爱情公寓",
        "还珠格格", "西游记", "红楼梦", "三国演义", "水浒传",
        "武林外传", "家有儿女", "亮剑", "甄嬛传", "琅琊榜",
        "大宅门", "雍正王朝", "铁齿铜牙纪晓岚",
        "神雕侠侣", "天龙八部", "射雕英雄传", "倚天屠龙记"
    ]),
    ("恐怖电影", ["恐怖", "horror", "鬼片", "僵尸", "丧尸"]),
    ("惊悚电影", ["惊悚", "thriller", "suspense"]),
    ("功夫电影", ["功夫", "kung fu", "martial arts", "武打"]),
    ("武侠电影", ["武侠", "wuxia"]),
    ("香港电影", ["香港电影", "香港片", "hk movie", "hong kong movie"]),
    ("经典电影", ["经典电影", "classic movie", "classic movies", "经典影片"]),
    ("电视剧", ["电视剧", "tv drama", "drama", "series", "tv series"]),
    ("电影", ["电影", "movies", "movie", "films", "film", "cinema"]),
    ("CCTV", ["cctv", "中央电视台", "央视"]),
]

DRAMA_KEYWORDS = [
    "康熙微服私访记", "宰相刘罗锅", "白鹿原", "爱情公寓",
    "还珠格格", "西游记", "红楼梦", "三国演义", "水浒传",
    "武林外传", "家有儿女", "亮剑", "甄嬛传", "琅琊榜",
    "大宅门", "雍正王朝", "铁齿铜牙纪晓岚",
    "神雕侠侣", "天龙八部", "射雕英雄传", "倚天屠龙记"
]

STAR_KEYWORDS = [
    "成龙", "李连杰", "李小龙", "周润发", "周星驰", "甄子丹",
    "洪金宝", "元彪", "狄龙", "姜大卫", "刘德华", "梁朝伟",
    "张国荣", "林正英", "黄秋生", "吴镇宇", "史泰龙",
    "施瓦辛格", "汤姆·克鲁斯", "基努·里维斯", "布鲁斯·威利斯",
    "杰森·斯坦森"
]


def norm_url(url: str) -> str:
    try:
        p = urlsplit(str(url).strip())
        scheme = p.scheme.lower()
        host = (p.hostname or "").lower()
        if not scheme or not host:
            return str(url).strip()
        netloc = host
        if p.port:
            default = (scheme == "http" and p.port == 80) or (
                scheme == "https" and p.port == 443
            )
            if not default:
                netloc = f"{host}:{p.port}"
        return urlunsplit((scheme, netloc, p.path or "/", p.query, ""))
    except Exception:
        return str(url).strip()


def text_blob(row: dict) -> str:
    parts = []
    for key in (
        "name", "channel_name", "title", "group", "category",
        "genre", "source", "url", "tvg_name", "tvg_group",
        "drama", "star", "matched_keywords"
    ):
        value = row.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts).lower()


def classify(row: dict) -> str:
    text = text_blob(row)

    for category, keywords in CATEGORY_PRIORITY:
        for kw in keywords:
            if kw.lower() in text:
                return category

    return "其他"


def matched_items(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [kw for kw in keywords if kw.lower() in low]


def request_once(url: str, headers: dict, verify: bool = True) -> dict:
    started = time.perf_counter()
    try:
        with requests.get(
            url,
            headers=headers,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True,
            allow_redirects=True,
            verify=verify,
        ) as r:
            status = r.status_code
            content_type = (r.headers.get("Content-Type") or "").lower()

            chunks = []
            total = 0
            for chunk in r.iter_content(chunk_size=16384):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total >= MAX_BYTES:
                    break

            body = b"".join(chunks)
            elapsed = int((time.perf_counter() - started) * 1000)

            if status >= 400:
                return {
                    "status": "failed",
                    "http_status": status,
                    "content_type": content_type,
                    "bytes": len(body),
                    "elapsed_ms": elapsed,
                    "playlist": False,
                    "error": f"http_{status}",
                }

            sample = body[:MAX_BYTES].decode("utf-8", errors="ignore")
            is_playlist = (
                "#EXTM3U" in sample
                or "#EXTINF" in sample
                or ".m3u8" in sample.lower()
                or "application/vnd.apple.mpegurl" in content_type
                or "application/x-mpegurl" in content_type
                or "mpegurl" in content_type
            )

            if not is_playlist:
                return {
                    "status": "failed",
                    "http_status": status,
                    "content_type": content_type,
                    "bytes": len(body),
                    "elapsed_ms": elapsed,
                    "playlist": False,
                    "error": "not_playlist",
                }

            if elapsed < 1000:
                speed = "S1"
            elif elapsed < 2000:
                speed = "S2"
            elif elapsed < 4000:
                speed = "S3"
            elif elapsed < 8000:
                speed = "S4"
            else:
                speed = "S5"

            return {
                "status": "ok",
                "http_status": status,
                "content_type": content_type,
                "bytes": len(body),
                "elapsed_ms": elapsed,
                "playlist": True,
                "speed": speed,
                "error": "",
            }

    except requests.exceptions.SSLError:
        return {"status": "failed", "error": "sslerror"}
    except requests.exceptions.Timeout:
        return {"status": "failed", "error": "timeout"}
    except requests.exceptions.ProxyError:
        return {"status": "failed", "error": "proxyerror"}
    except requests.exceptions.ConnectionError:
        return {"status": "failed", "error": "connectionerror"}
    except requests.exceptions.RequestException as e:
        return {"status": "failed", "error": type(e).__name__.lower()}
    except Exception as e:
        return {"status": "failed", "error": type(e).__name__.lower()}


def retry_failed(row: dict) -> dict:
    url = row.get("url", "")
    if not url:
        return {**row, "status": "failed", "error": "missing_url"}

    # 404 is normally permanent; retry once only.
    old_error = str(row.get("error", ""))
    if old_error == "http_404":
        attempts = 1
    else:
        attempts = NORMAL_RETRIES

    last = dict(row)
    retry_log = []

    for i in range(attempts):
        result = request_once(url, NORMAL_HEADERS, verify=True)
        retry_log.append(result.get("error", "ok"))
        if result.get("status") == "ok":
            return merge_result(row, result, "normal", retry_log)

    for i in range(HEADER_RETRIES):
        result = request_once(url, BROWSER_HEADERS, verify=True)
        retry_log.append(result.get("error", "ok"))
        if result.get("status") == "ok":
            return merge_result(row, result, "headers", retry_log)

    # SSL fallback only makes sense after an SSL failure or for stubborn HTTPS sources.
    if url.lower().startswith("https://"):
        for i in range(SSL_RETRIES):
            result = request_once(url, BROWSER_HEADERS, verify=False)
            retry_log.append(result.get("error", "ok"))
            if result.get("status") == "ok":
                return merge_result(row, result, "ssl_fallback", retry_log)

    last.update({
        "status": "failed",
        "retry_recovered": False,
        "retry_mode": "",
        "retry_attempts": len(retry_log),
        "retry_errors": retry_log,
    })
    return last


def merge_result(old: dict, result: dict, mode: str, retry_log: list[str]) -> dict:
    out = dict(old)
    out.update(result)
    out["status"] = "ok"
    out["retry_recovered"] = True
    out["retry_mode"] = mode
    out["retry_attempts"] = len(retry_log)
    out["retry_errors"] = retry_log
    return out


def choose_better(a: dict, b: dict) -> dict:
    a_ok = a.get("status") == "ok"
    b_ok = b.get("status") == "ok"
    if a_ok and not b_ok:
        return a
    if b_ok and not a_ok:
        return b
    if a_ok and b_ok:
        ae = a.get("elapsed_ms", 999999)
        be = b.get("elapsed_ms", 999999)
        return a if ae <= be else b
    return a


def load_rows() -> list[dict]:
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        rows = data.get("rows") or data.get("results") or data.get("data") or []
    else:
        rows = data

    if not isinstance(rows, list):
        raise ValueError("Input JSON does not contain a row list")

    return rows


def build_m3u(rows: list[dict]) -> None:
    M3U_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAT_DIR.mkdir(parents=True, exist_ok=True)

    category_rows: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("status") != "ok":
            continue
        category = row.get("primary_category") or classify(row)
        category_rows.setdefault(category, []).append(row)

    def render(items: list[dict]) -> str:
        lines = ["#EXTM3U"]
        for row in items:
            name = row.get("name") or row.get("channel_name") or row.get("title") or "Unknown"
            url = row.get("url", "")
            group = row.get("primary_category") or "其他"
            tvg_id = row.get("tvg_id", "")
            logo = row.get("tvg_logo", "") or row.get("logo", "")
            attrs = [f'group-title="{group}"']
            if tvg_id:
                attrs.append(f'tvg-id="{tvg_id}"')
            if logo:
                attrs.append(f'tvg-logo="{logo}"')
            lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
            lines.append(url)
        return "\n".join(lines) + "\n"

    M3U_FILE.write_text(render(rows), encoding="utf-8")

    for category, items in sorted(category_rows.items()):
        safe = re.sub(r'[\\/:*?"<>|]+', "_", category).strip() or "其他"
        (CAT_DIR / f"{safe}.m3u").write_text(render(items), encoding="utf-8")


def main():
    print("=== V5.8 Failed-Source Recovery + Classification Fix ===")
    print("Retries timeout/403/503/502/567/SSL sources.")
    print("404 gets limited retry.")
    print("No video frame analysis. No AI.")
    print(f"Input: {INPUT_FILE}")

    rows = load_rows()
    print(f"Input rows: {len(rows)}")

    # Normalize and deduplicate input while keeping the best existing record.
    by_url: dict[str, dict] = {}
    for row in rows:
        url = norm_url(row.get("url", ""))
        if not url:
            continue
        r = dict(row)
        r["url"] = url
        by_url[url] = choose_better(by_url.get(url, r), r)

    unique_rows = list(by_url.values())
    good = [r for r in unique_rows if r.get("status") == "ok"]
    failed = [r for r in unique_rows if r.get("status") != "ok"]

    print(f"Unique URLs: {len(unique_rows)}")
    print(f"Existing OK: {len(good)}")
    print(f"Failed to retry: {len(failed)}")
    print(f"Retry workers: {WORKERS}")
    print(f"Retries per mode: normal={NORMAL_RETRIES}, headers={HEADER_RETRIES}, ssl={SSL_RETRIES}")

    recovered = []
    remaining = []

    if failed:
        completed = 0
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(retry_failed, row) for row in failed]
            for fut in as_completed(futures):
                result = fut.result()
                completed += 1
                if result.get("status") == "ok" and result.get("retry_recovered"):
                    recovered.append(result)
                else:
                    remaining.append(result)
                if completed % 25 == 0 or completed == len(failed):
                    print(f"Retried: {completed}/{len(failed)}")

    merged: dict[str, dict] = {}

    for row in good:
        merged[row["url"]] = row

    for row in recovered:
        url = row["url"]
        merged[url] = choose_better(merged.get(url, row), row)

    for row in remaining:
        url = row["url"]
        if url not in merged:
            merged[url] = row

    final_rows = list(merged.values())

    # Reclassify every final row and attach metadata matches.
    category_counts = Counter()
    drama_counts = Counter()
    star_counts = Counter()

    for row in final_rows:
        text = text_blob(row)
        row["primary_category"] = classify(row)

        dramas = matched_items(text, DRAMA_KEYWORDS)
        stars = matched_items(text, STAR_KEYWORDS)

        row["matched_dramas"] = dramas
        row["matched_stars"] = stars

        if dramas:
            row["drama_matches"] = dramas
        if stars:
            row["star_matches"] = stars

        category_counts[row["primary_category"]] += 1
        for d in dramas:
            drama_counts[d] += 1
        for s in stars:
            star_counts[s] += 1

    ok_rows = [r for r in final_rows if r.get("status") == "ok"]
    fail_rows = [r for r in final_rows if r.get("status") != "ok"]

    speed_counts = Counter()
    failure_counts = Counter()
    retry_mode_counts = Counter()

    for row in ok_rows:
        speed_counts[row.get("speed", "unknown")] += 1
        if row.get("retry_recovered"):
            retry_mode_counts[row.get("retry_mode", "unknown")] += 1

    for row in fail_rows:
        failure_counts[row.get("error", "unknown")] += 1

    final_rows.sort(
        key=lambda r: (
            r.get("primary_category", "其他"),
            str(r.get("name", "")),
            str(r.get("url", "")),
        )
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(final_rows, f, ensure_ascii=False, indent=2)

    summary = {
        "input_rows": len(rows),
        "unique_urls": len(unique_rows),
        "existing_ok": len(good),
        "failed_before_retry": len(failed),
        "retry_attempted": len(failed),
        "recovered": len(recovered),
        "remaining_retry_failures": len(remaining),
        "final_unique": len(final_rows),
        "final_ok": len(ok_rows),
        "final_failed": len(fail_rows),
        "final_success_rate": round(
            len(ok_rows) / len(final_rows) * 100, 1
        ) if final_rows else 0,
        "speed_counts": dict(sorted(speed_counts.items())),
        "failure_counts": dict(failure_counts.most_common()),
        "retry_mode_counts": dict(retry_mode_counts.most_common()),
        "primary_categories": dict(category_counts.most_common()),
        "drama_counts": dict(drama_counts.most_common()),
        "star_counts": dict(star_counts.most_common()),
        "no_video_frame_analysis": True,
        "no_ai": True,
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    build_m3u(ok_rows)

    print()
    print("=== V5.8 Result ===")
    print(f"V5.7.1 OK: {len(good)}")
    print(f"V5.7.1 failed: {len(failed)}")
    print(f"Retry attempted: {len(failed)}")
    print(f"Recovered: {len(recovered)}")
    print(f"Remaining retry failures: {len(remaining)}")
    print(f"Final unique OK: {len(ok_rows)}")
    print(f"Final success rate: {summary['final_success_rate']}%")
    print()
    print("Recovery modes:")
    for k, v in retry_mode_counts.items():
        print(f"  {k}: {v}")
    print()
    print("Top primary categories:")
    for k, v in category_counts.most_common(20):
        print(f"  {k}: {v}")
    print()
    print("Top drama matches:")
    for k, v in drama_counts.most_common(20):
        print(f"  {k}: {v}")
    print()
    print("Top star matches:")
    for k, v in star_counts.most_common(20):
        print(f"  {k}: {v}")
    print()
    print("Remaining retry failures:")
    for k, v in failure_counts.most_common():
        print(f"  {k}: {v}")
    print()
    print("Done.")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)
    print(M3U_FILE)
    print(CAT_DIR)


if __name__ == "__main__":
    main()
