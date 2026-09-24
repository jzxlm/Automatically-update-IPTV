from pathlib import Path
import json
import re
import shutil
import subprocess
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "data" / "movie_v53_result.json"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

TIMEOUT = 12
WORKERS = 8
MAX_SEGMENTS = 2

# V5.4 first uses metadata/EPG-like information available in the playlist.
# Video-frame AI is deliberately optional: no external AI API/key is required.
# Unclassified records remain "电影综合".
KEYWORDS = {
    "邵氏": ["邵氏", "shaw brothers", "shaw movies", "celestial", "celestial movies"],
    "香港": ["香港", "香港电影", "香港片", "hong kong", "hk movie", "hk movies", "mei ah", "meiah", "golden harvest"],
    "粤语": ["粤语", "粵語", "cantonese"],
    "功夫": ["功夫", "kung fu", "kungfu", "martial arts"],
    "武侠": ["武侠", "武俠", "wuxia"],
    "恐怖": ["恐怖", "horror"],
    "惊悚": ["惊悚", "驚悚", "thriller"],
    "经典": ["经典电影", "經典電影", "classic movie", "classic movies", "classic film", "classic films"],
    "老电影": ["老电影", "老電影", "old movie", "old movies", "old film", "old films"],
    "怀旧": ["怀旧", "懷舊", "nostalgia", "retro movie", "retro movies", "retro film"],
    "动作": ["动作电影", "動作電影", "action movie", "action movies", "action film", "action films"],
    "犯罪": ["犯罪电影", "犯罪片", "crime movie", "crime movies", "crime film", "crime films"],
    "西部": ["西部电影", "西部片", "western movie", "western movies", "western film", "western films"],
    "喜剧": ["喜剧电影", "喜劇電影", "comedy movie", "comedy movies", "comedy film", "comedy films"],
    "剧情": ["剧情电影", "劇情電影", "drama movie", "drama movies", "drama film", "drama films"],
}

CATEGORY_ORDER = [
    "邵氏",
    "香港",
    "粤语",
    "功夫",
    "武侠",
    "恐怖",
    "惊悚",
    "经典",
    "老电影",
    "怀旧",
    "动作",
    "犯罪",
    "西部",
    "喜剧",
    "剧情",
    "电影综合",
]

CATEGORY_FILE = {
    "邵氏": "邵氏综合",
    "香港": "香港电影",
    "粤语": "粤语电影",
    "功夫": "功夫电影",
    "武侠": "武侠电影",
    "恐怖": "恐怖电影",
    "惊悚": "惊悚电影",
    "经典": "经典电影",
    "老电影": "老电影",
    "怀旧": "怀旧电影",
    "动作": "动作电影",
    "犯罪": "犯罪电影",
    "西部": "西部电影",
    "喜剧": "喜剧电影",
    "剧情": "剧情电影",
    "电影综合": "电影综合",
}

def norm(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()

def metadata_text(r):
    return norm(" | ".join(
        r.get(k, "") for k in ("name", "alt", "group", "tvg_id", "tvg_name")
    ))

def score_metadata(text):
    low = text.lower()
    scores = Counter()
    evidence = {}
    for cat, words in KEYWORDS.items():
        for w in words:
            if w.lower() in low:
                # Longer, more specific phrases get more weight.
                weight = 3 if len(w) >= 7 else 2 if len(w) >= 4 else 1
                scores[cat] += weight
                evidence.setdefault(cat, []).append(w)
    return scores, evidence

def fetch_text(url):
    try:
        r = requests.get(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": "Mozilla/5.0 IPTV-Metadata-Analyzer/5.4"},
        )
        if r.ok:
            return r.text[:300000], r.headers.get("content-type", "")
    except Exception:
        pass
    return "", ""

def extract_playlist_metadata(url):
    text, ctype = fetch_text(url)
    if not text:
        return {"playlist_ok": False, "playlist_type": "", "program_titles": [], "playlist_text": ""}

    titles = []
    # EXTINF metadata:
    # #EXTINF:-1 tvg-name="..." group-title="...",Channel
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#EXTINF"):
            title = s.split(",", 1)[1].strip() if "," in s else ""
            if title:
                titles.append(title)
            for attr in ("tvg-name", "tvg-id", "group-title", "tvg-language"):
                m = re.search(rf'{attr}="([^"]*)"', s, re.I)
                if m and m.group(1):
                    titles.append(m.group(1))

    # HLS variant / stream-info metadata.
    for line in text.splitlines():
        if line.startswith("#EXT-X-STREAM-INF"):
            for key in ("NAME", "VIDEO", "AUDIO"):
                m = re.search(rf'{key}=("[^"]+"|[^,]+)', line, re.I)
                if m:
                    titles.append(m.group(1).strip('"'))

    return {
        "playlist_ok": "#EXTM3U" in text[:5000] or "#EXTINF" in text[:10000],
        "playlist_type": ctype,
        "program_titles": list(dict.fromkeys(titles))[:80],
        "playlist_text": text[:120000],
    }

def probe_ffprobe(url):
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"available": False, "ok": False}

    cmd = [
        ffprobe, "-v", "error",
        "-rw_timeout", "10000000",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration",
        "-of", "json", url
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=18)
        if p.returncode != 0:
            return {"available": True, "ok": False, "error": p.stderr[-500:]}
        data = json.loads(p.stdout or "{}")
        streams = data.get("streams") or []
        return {"available": True, "ok": bool(streams), "streams": streams}
    except Exception as e:
        return {"available": True, "ok": False, "error": str(e)}

def analyze_one(row):
    r = dict(row)
    url = norm(r.get("url") or r.get("playlist_url"))
    meta = metadata_text(r)
    scores, evidence = score_metadata(meta)

    playlist = {}
    if url:
        playlist = extract_playlist_metadata(url)
        ptext = " | ".join(playlist.get("program_titles", []))
        pscores, pevidence = score_metadata(ptext)
        for k, v in pscores.items():
            scores[k] += v
        for k, vals in pevidence.items():
            evidence.setdefault(k, []).extend(vals)

    # Only probe video stream when FFprobe is installed.
    probe = probe_ffprobe(url) if url else {"available": shutil.which("ffprobe") is not None, "ok": False}

    # Conservative decision: metadata evidence must exist.
    ranked = [(k, v) for k, v in scores.items() if v > 0]
    ranked.sort(key=lambda x: (-x[1], CATEGORY_ORDER.index(x[0]) if x[0] in CATEGORY_ORDER else 99))
    if ranked:
        best_cat, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0
        # Require stronger evidence when categories are close.
        if best_score >= 3 or best_score > second:
            category = best_cat
        else:
            category = "电影综合"
    else:
        category = "电影综合"
        best_score = 0

    # Keep previous V5.3 category as a secondary clue, not as the only reason.
    previous = norm(r.get("v53_category"))
    if category == "电影综合" and previous and previous != "电影综合":
        category = previous

    r["v54_category"] = CATEGORY_FILE[category]
    r["v54_score"] = best_score
    r["v54_keyword_evidence"] = {k: list(dict.fromkeys(v)) for k, v in evidence.items()}
    r["v54_playlist_ok"] = playlist.get("playlist_ok", False)
    r["v54_program_titles"] = playlist.get("program_titles", [])
    r["v54_ffprobe"] = probe
    r["v54_checked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return r

def write_m3u(path, items, default_group):
    with path.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for r in items:
            url = norm(r.get("url") or r.get("playlist_url"))
            if not url:
                continue
            name = norm(r.get("name") or r.get("tvg_name") or "未命名")
            group = norm(r.get("group") or default_group)
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

    ffprobe_path = shutil.which("ffprobe")
    print("=== V5.4 Metadata + Playlist + FFprobe Analyzer ===")
    print("Input final rows:", len(rows))
    print("FFprobe:", ffprobe_path or "NOT INSTALLED")
    print("Workers:", WORKERS)
    print()

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futures = [ex.submit(analyze_one, r) for r in rows]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                results.append(fut.result())
            except Exception as e:
                print("worker error:", e)
            if i % 25 == 0 or i == len(futures):
                print(f"Analyzed: {i}/{len(futures)}")

    counts = Counter(r["v54_category"] for r in results)
    ff_ok = sum(1 for r in results if r.get("v54_ffprobe", {}).get("ok"))
    playlist_ok = sum(1 for r in results if r.get("v54_playlist_ok"))

    out_json = DATA_DIR / "movie_v54_result.json"
    out_summary = DATA_DIR / "movie_v54_summary.json"

    results.sort(key=lambda r: (r["v54_category"], norm(r.get("name"))))
    payload = {
        "version": "V5.4",
        "final_input_rows": len(rows),
        "playlist_ok": playlist_ok,
        "ffprobe_ok": ff_ok,
        "ffprobe_installed": bool(ffprobe_path),
        "classification_counts": dict(counts),
        "results": results,
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_summary.write_text(json.dumps({
        "version": "V5.4",
        "final_input_rows": len(rows),
        "playlist_ok": playlist_ok,
        "ffprobe_ok": ff_ok,
        "ffprobe_installed": bool(ffprobe_path),
        "classification_counts": dict(counts),
        "note": "V5.4 uses metadata + playlist metadata and optional FFprobe. It does not perform visual AI analysis yet."
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    OUTPUT_DIR.mkdir(exist_ok=True)
    for cat, items_count in counts.items():
        write_m3u(
            OUTPUT_DIR / f"{cat}.m3u",
            [r for r in results if r["v54_category"] == cat],
            cat
        )
    write_m3u(OUTPUT_DIR / "movies_v54_all.m3u", results, "电影")

    print("\n=== V5.4 Result ===")
    print("Playlist OK:", playlist_ok)
    print("FFprobe OK:", ff_ok)
    print()
    for k, v in counts.most_common():
        print(f"{k}: {v}")

    print("\nOutput:")
    print(out_json)
    print(out_summary)
    print(OUTPUT_DIR / "movies_v54_all.m3u")
    print("\nDone.")

if __name__ == "__main__":
    main()
