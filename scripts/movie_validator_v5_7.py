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
OUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"

WORKERS = 24
CONNECT_TIMEOUT = 4
READ_TIMEOUT = 6
MAX_BYTES = 256 * 1024

# Only these response types are treated as playlist candidates.
PLAYLIST_EXTS = (".m3u8", ".m3u", ".txt")
CONTENT_HINTS = ("mpegurl", "x-mpegurl", "application/vnd.apple.mpegurl", "audio/mpegurl")

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
    for key in ("rows", "items", "results", "sources", "data"):
        if isinstance(obj.get(key), list):
            return obj[key]
    raise ValueError("无法在 JSON 中找到列表数据。")

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
        return ""
    for k in ("name", "channel_name", "title", "channel", "display_name"):
        v = row.get(k)
        if v:
            return str(v)
    return ""

def norm_url(url):
    try:
        p = urlsplit(url.strip())
        # Preserve query because tokens/signatures can be required for playback.
        host = (p.hostname or "").lower()
        port = p.port
        netloc = host
        if port and not ((p.scheme == "http" and port == 80) or (p.scheme == "https" and port == 443)):
            netloc += f":{port}"
        return urlunsplit((p.scheme.lower(), netloc, p.path or "/", p.query, ""))
    except Exception:
        return url.strip()

def classify(name, row):
    text = " ".join([
        name,
        str(row.get("group", "") if isinstance(row, dict) else ""),
        str(row.get("group_title", "") if isinstance(row, dict) else ""),
        str(row.get("category", "") if isinstance(row, dict) else ""),
        str(row.get("tags", "") if isinstance(row, dict) else ""),
    ]).lower()

    groups = []
    def add(label):
        if label not in groups:
            groups.append(label)

    # Channel classification
    if re.search(r"\bcctv[- _]?1\b|cctv1|央视一套|综合频道", text):
        add("CCTV-1 综合")
    if re.search(r"\bcctv[- _]?6\b|cctv6|央视六套|电影频道", text):
        add("CCTV-6 电影")
    if re.search(r"\bcctv[- _]?8\b|cctv8|央视八套|电视剧频道", text):
        add("CCTV-8 电视剧")
    if "cctv" in text or "央视" in text:
        add("CCTV")

    # Drama / movie metadata
    drama_keywords = {
        "康熙微服私访记": "康熙微服私访记",
        "宰相刘罗锅": "宰相刘罗锅",
        "白鹿原": "白鹿原",
        "爱情公寓": "爱情公寓",
        "还珠格格": "还珠格格",
        "西游记": "西游记",
        "红楼梦": "红楼梦",
        "三国演义": "三国演义",
        "水浒传": "水浒传",
        "武林外传": "武林外传",
        "家有儿女": "家有儿女",
        "亮剑": "亮剑",
        "甄嬛传": "甄嬛传",
        "琅琊榜": "琅琊榜",
        "大宅门": "大宅门",
        "雍正王朝": "雍正王朝",
        "铁齿铜牙纪晓岚": "铁齿铜牙纪晓岚",
        "神雕侠侣": "神雕侠侣",
        "天龙八部": "天龙八部",
        "射雕英雄传": "射雕英雄传",
        "倚天屠龙记": "倚天屠龙记",
    }
    for k, v in drama_keywords.items():
        if k.lower() in text:
            add(v)
            add("经典电视剧")

    if any(x in text for x in ("电视剧", "tv drama", "drama", "series")):
        add("电视剧")
    if any(x in text for x in ("电影", "movie", "movies", "cinema", "film")):
        add("电影")
    if any(x in text for x in ("恐怖", "horror")):
        add("恐怖电影")
    if any(x in text for x in ("惊悚", "thriller")):
        add("惊悚电影")
    if any(x in text for x in ("功夫", "kung fu")):
        add("功夫电影")
    if any(x in text for x in ("武侠", "wuxia")):
        add("武侠电影")
    if any(x in text for x in ("香港", "hong kong", "mei ah")):
        add("香港电影")
    if any(x in text for x in ("经典", "classic", "retro", "怀旧", "nostalgia")):
        add("经典电影")

    stars = [
        "成龙", "李连杰", "李小龙", "周润发", "周星驰", "甄子丹",
        "洪金宝", "元彪", "狄龙", "姜大卫", "刘德华", "梁朝伟",
        "张国荣", "林正英", "黄秋生", "吴镇宇", "史泰龙",
        "施瓦辛格", "汤姆·克鲁斯", "基努·里维斯", "布鲁斯·威利斯",
        "杰森·斯坦森",
    ]
    for star in stars:
        if star.lower() in text:
            add(star)

    return groups

def check_url(item):
    url = item["url"]
    result = dict(item)
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
            url, headers=HEADERS, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            stream=True, allow_redirects=True
        ) as r:
            result["http_status"] = r.status_code
            result["content_type"] = r.headers.get("Content-Type", "")
            if r.status_code >= 400:
                result["error"] = f"http_{r.status_code}"
                return result

            buf = b""
            for chunk in r.iter_content(chunk_size=16384):
                if chunk:
                    buf += chunk
                    if len(buf) >= MAX_BYTES:
                        break

            result["bytes"] = len(buf)
            head = buf[:8192].decode("utf-8", errors="ignore").lower()
            ct = result["content_type"].lower()
            path = urlsplit(r.url).path.lower()

            is_playlist = (
                "#extm3u" in head
                or "#ext-x-" in head
                or any(path.endswith(x) for x in PLAYLIST_EXTS)
                or any(x in ct for x in CONTENT_HINTS)
            )
            result["playlist"] = bool(is_playlist)

            if is_playlist and len(buf) > 0:
                result["status"] = "ok"
                result["error"] = ""
            else:
                result["error"] = "not_playlist"

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
    except requests.exceptions.RequestException as e:
        result["error"] = type(e).__name__.lower()
    except Exception as e:
        result["error"] = type(e).__name__.lower()
    finally:
        result["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    return result

def speed_level(ms):
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

def write_m3u(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("#EXTM3U\n")
        for r in rows:
            name = r.get("name") or "Unnamed"
            group = r.get("group") or "未分类"
            f.write(
                f'#EXTINF:-1 tvg-name="{name}" group-title="{group}",{name}\n'
            )
            f.write(r["url"] + "\n")

def main():
    print("=== V5.7 Speed + Playlist Availability Validator ===")
    print("HTTP/M3U8 only. No video frame analysis. No AI.")
    print(f"Input: {INPUT_FILE}")

    rows = load_rows()
    candidates = []
    seen = set()

    for row in rows:
        url = pick_url(row)
        if not url:
            continue
        nu = norm_url(url)
        if nu in seen:
            continue
        seen.add(nu)
        name = pick_name(row) or "Unnamed"
        item = {
            "url": url,
            "name": name,
            "source": row,
            "categories": classify(name, row if isinstance(row, dict) else {}),
        }
        candidates.append(item)

    print(f"Input rows: {len(rows)}")
    print(f"Unique URLs before test: {len(candidates)}")
    print(f"Workers: {WORKERS}")
    print(f"Timeout: {CONNECT_TIMEOUT}s connect / {READ_TIMEOUT}s read")
    print()

    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(check_url, x) for x in candidates]
        for fut in as_completed(futures):
            results.append(fut.result())
            done += 1
            if done % 50 == 0 or done == len(futures):
                print(f"Checked: {done}/{len(futures)}")

    ok = [r for r in results if r["status"] == "ok"]
    ok.sort(key=lambda x: (x["elapsed_ms"] is None, x["elapsed_ms"] or 999999))

    # Assign speed group.
    for r in ok:
        r["speed"] = speed_level(r["elapsed_ms"])
        if not r["categories"]:
            r["categories"] = ["其他"]
        # Keep a single primary group for player apps.
        primary = r["categories"][0]
        r["group"] = primary

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    result_file = DATA_DIR / "movie_tv_v57_result.json"
    summary_file = DATA_DIR / "movie_tv_v57_summary.json"
    result_file.write_text(json.dumps(ok, ensure_ascii=False, indent=2), encoding="utf-8")

    category_rows = {}
    for r in ok:
        for c in r["categories"]:
            category_rows.setdefault(c, []).append(r)

    # Deduplicate each category again by normalized URL.
    for c, items in category_rows.items():
        unique = {}
        for r in items:
            unique.setdefault(norm_url(r["url"]), r)
        category_rows[c] = list(unique.values())
        category_rows[c].sort(key=lambda x: (x["elapsed_ms"] is None, x["elapsed_ms"] or 999999))

    speed_counts = {}
    for r in ok:
        speed_counts[r["speed"]] = speed_counts.get(r["speed"], 0) + 1

    summary = {
        "version": "V5.7",
        "input_rows": len(rows),
        "unique_urls_tested": len(candidates),
        "playlist_ok": len(ok),
        "failed": len(results) - len(ok),
        "speed_counts": speed_counts,
        "category_counts": {k: len(v) for k, v in sorted(category_rows.items())},
        "failure_counts": {},
    }
    for r in results:
        if r["status"] != "ok":
            e = r.get("error") or "unknown"
            summary["failure_counts"][e] = summary["failure_counts"].get(e, 0) + 1

    summary_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # Main M3U and category M3Us.
    all_rows = []
    for r in ok:
        x = dict(r)
        x["group"] = x["categories"][0] if x["categories"] else "其他"
        all_rows.append(x)
    write_m3u(OUT_DIR / "movies_tv_v57_all.m3u", all_rows)

    for category, items in sorted(category_rows.items()):
        safe = re.sub(r'[\\/:*?"<>|]+', "_", category)
        write_m3u(OUT_DIR / f"{safe}.m3u", items)

    print()
    print("=== V5.7 Result ===")
    print(f"Unique URLs tested: {len(candidates)}")
    print(f"Playlist OK: {len(ok)}")
    print(f"Failed: {len(results) - len(ok)}")
    print()
    print("Speed:")
    for k in ("S1", "S2", "S3", "S4", "S5", "FAIL"):
        if k in speed_counts:
            print(f"  {k}: {speed_counts[k]}")

    print()
    print("Top categories:")
    for k, v in sorted(summary["category_counts"].items(), key=lambda x: (-x[1], x[0]))[:30]:
        print(f"  {k}: {v}")

    print()
    print("Failure classes:")
    for k, v in sorted(summary["failure_counts"].items(), key=lambda x: (-x[1], x[0])):
        print(f"  {k}: {v}")

    print()
    print(f"Done.\n{result_file}\n{summary_file}\n{OUT_DIR / 'movies_tv_v57_all.m3u'}")

if __name__ == "__main__":
    main()
