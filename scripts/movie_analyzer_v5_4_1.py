from pathlib import Path
import json, re, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "data" / "movie_v51_result.json"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

WORKERS = 12
CONNECT_TIMEOUT = 4
READ_TIMEOUT = 6
MAX_PLAYLIST_BYTES = 512 * 1024
USER_AGENT = "Mozilla/5.0 IPTV-Metadata-Analyzer/5.4.1"

KEYWORDS = {
    "邵氏": ["邵氏", "shaw brothers", "shaw movies", "celestial", "celestial movies"],
    "香港": ["香港", "香港电影", "香港片", "hong kong", "hk movie", "hk movies",
            "mei ah", "meiah", "golden harvest"],
    "粤语": ["粤语", "粵語", "cantonese"],
    "功夫": ["功夫", "kung fu", "kungfu", "martial arts"],
    "武侠": ["武侠", "武俠", "wuxia"],
    "恐怖": ["恐怖", "horror"],
    "惊悚": ["惊悚", "驚悚", "thriller"],
    "经典": ["经典电影", "經典電影", "classic movie", "classic movies",
            "classic film", "classic films"],
    "老电影": ["老电影", "老電影", "old movie", "old movies", "old film", "old films"],
    "怀旧": ["怀旧", "懷舊", "nostalgia", "retro movie", "retro movies", "retro film"],
    "动作": ["动作电影", "動作電影", "action movie", "action movies",
            "action film", "action films"],
    "犯罪": ["犯罪电影", "犯罪片", "crime movie", "crime movies", "crime film", "crime films"],
    "西部": ["西部电影", "西部片", "western movie", "western movies",
            "western film", "western films"],
    "喜剧": ["喜剧电影", "喜劇電影", "comedy movie", "comedy movies",
            "comedy film", "comedy films"],
    "剧情": ["剧情电影", "劇情電影", "drama movie", "drama movies",
            "drama film", "drama films"],
}

CATEGORY_FILE = {
    "邵氏": "邵氏综合", "香港": "香港电影", "粤语": "粤语电影",
    "功夫": "功夫电影", "武侠": "武侠电影", "恐怖": "恐怖电影",
    "惊悚": "惊悚电影", "经典": "经典电影", "老电影": "老电影",
    "怀旧": "怀旧电影", "动作": "动作电影", "犯罪": "犯罪电影",
    "西部": "西部电影", "喜剧": "喜剧电影", "剧情": "剧情电影",
    "电影综合": "电影综合",
}

def norm(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()

def metadata_text(r):
    return norm(" | ".join(str(r.get(k, "")) for k in
                           ("name", "alt", "group", "tvg_id", "tvg_name")))

def score_text(text):
    low = text.lower()
    scores = Counter()
    evidence = {}
    for cat, words in KEYWORDS.items():
        for w in words:
            if w.lower() in low:
                weight = 3 if len(w) >= 7 else 2 if len(w) >= 4 else 1
                scores[cat] += weight
                evidence.setdefault(cat, []).append(w)
    return scores, evidence

def fetch_playlist(url):
    if not url:
        return {"ok": False, "text": "", "content_type": "", "error": "empty_url"}

    try:
        with requests.get(
            url,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            stream=True,
            allow_redirects=True,
        ) as resp:
            if not resp.ok:
                return {"ok": False, "text": "", "content_type": "",
                        "error": f"http_{resp.status_code}"}

            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=32768):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total >= MAX_PLAYLIST_BYTES:
                    break

            raw = b"".join(chunks)
            text = raw.decode("utf-8", errors="ignore")
            return {
                "ok": True,
                "text": text,
                "content_type": resp.headers.get("content-type", ""),
                "error": "",
            }
    except requests.exceptions.Timeout:
        return {"ok": False, "text": "", "content_type": "", "error": "timeout"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "text": "", "content_type": "", "error": type(e).__name__}
    except Exception as e:
        return {"ok": False, "text": "", "content_type": "", "error": str(e)[:120]}

def extract_titles(text):
    titles = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#EXTINF"):
            if "," in s:
                t = s.split(",", 1)[1].strip()
                if t:
                    titles.append(t)
            for attr in ("tvg-name", "tvg-id", "group-title", "tvg-language"):
                m = re.search(rf'{attr}="([^"]*)"', s, re.I)
                if m and m.group(1):
                    titles.append(m.group(1))
        elif s.startswith("#EXT-X-STREAM-INF"):
            for key in ("NAME", "VIDEO", "AUDIO"):
                m = re.search(rf'{key}=("[^"]+"|[^,]+)', s, re.I)
                if m:
                    titles.append(m.group(1).strip('"'))
    return list(dict.fromkeys(titles))[:100]

def classify(r):
    meta = metadata_text(r)
    scores, evidence = score_text(meta)

    url = norm(r.get("url") or r.get("playlist_url"))
    playlist = fetch_playlist(url)

    titles = extract_titles(playlist["text"]) if playlist["ok"] else []
    title_text = " | ".join(titles)
    pscores, pevidence = score_text(title_text)

    for k, v in pscores.items():
        scores[k] += v
    for k, vals in pevidence.items():
        evidence.setdefault(k, []).extend(vals)

    ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    if ranked:
        category, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0
        category = category if best_score >= 3 or best_score > second else "电影综合"
    else:
        category, best_score = "电影综合", 0

    previous = norm(r.get("v53_category"))
    if category == "电影综合" and previous and previous != "电影综合":
        category = previous

    x = dict(r)
    x["v54_category"] = CATEGORY_FILE[category]
    x["v54_score"] = best_score
    x["v54_keyword_evidence"] = {
        k: list(dict.fromkeys(v)) for k, v in evidence.items()
    }
    x["v54_playlist_ok"] = playlist["ok"]
    x["v54_playlist_error"] = playlist["error"]
    x["v54_program_titles"] = titles
    return x

def write_m3u(path, items, group_name):
    with path.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for r in items:
            url = norm(r.get("url") or r.get("playlist_url"))
            if not url:
                continue
            name = norm(r.get("name") or r.get("tvg_name") or "未命名")
            group = norm(r.get("group") or group_name)
            f.write(f'#EXTINF:-1 group-title="{group}",{name}\n{url}\n')

def main():
    if not INPUT.exists():
        print("ERROR: input not found:", INPUT)
        raise SystemExit(1)

    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else (
        raw.get("results") or raw.get("items") or raw.get("data") or []
    )
    rows = [r for r in rows if r.get("final_ok", True)]

    print("=== V5.4.1 Fast Metadata + Playlist Analyzer ===")
    print("Input final rows:", len(rows))
    print(f"Workers: {WORKERS}")
    print(f"Connect timeout: {CONNECT_TIMEOUT}s")
    print(f"Read timeout: {READ_TIMEOUT}s")
    print(f"Max playlist read: {MAX_PLAYLIST_BYTES // 1024} KB")
    print()

    results = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = {ex.submit(classify, r): i for i, r in enumerate(rows, 1)}
        done = 0
        for fut in as_completed(futures):
            done += 1
            try:
                results.append(fut.result())
            except Exception as e:
                r = dict(rows[futures[fut] - 1])
                r["v54_category"] = "电影综合"
                r["v54_score"] = 0
                r["v54_keyword_evidence"] = {}
                r["v54_playlist_ok"] = False
                r["v54_playlist_error"] = type(e).__name__
                r["v54_program_titles"] = []
                results.append(r)
            if done % 25 == 0 or done == len(rows):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed else 0
                print(f"Analyzed: {done}/{len(rows)} | {rate:.1f}/s")

    counts = Counter(r["v54_category"] for r in results)
    playlist_ok = sum(1 for r in results if r.get("v54_playlist_ok"))

    payload = {
        "version": "V5.4.1",
        "final_input_rows": len(rows),
        "playlist_ok": playlist_ok,
        "classification_counts": dict(counts),
        "results": sorted(results, key=lambda r: (r["v54_category"], norm(r.get("name")))),
    }
    out_json = DATA_DIR / "movie_v54_1_result.json"
    out_summary = DATA_DIR / "movie_v54_1_summary.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_summary.write_text(json.dumps({
        "version": "V5.4.1",
        "final_input_rows": len(rows),
        "playlist_ok": playlist_ok,
        "classification_counts": dict(counts),
        "note": "Faster bounded playlist reads. No FFprobe and no visual AI."
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    OUTPUT_DIR.mkdir(exist_ok=True)
    for cat in counts:
        write_m3u(OUTPUT_DIR / f"{cat}.m3u",
                  [r for r in results if r["v54_category"] == cat], cat)
    write_m3u(OUTPUT_DIR / "movies_v54_1_all.m3u", results, "电影")

    print("\n=== V5.4.1 Result ===")
    print("Playlist OK:", playlist_ok)
    for k, v in counts.most_common():
        print(f"{k}: {v}")
    print("\nDone.")
    print(out_json)
    print(out_summary)

if __name__ == "__main__":
    main()
