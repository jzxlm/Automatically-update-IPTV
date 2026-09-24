from pathlib import Path
import json
import csv
import re
from collections import Counter, defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT = BASE_DIR / "data" / "movie_v51_result.json"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

KEYWORDS = {
    "邵氏": ["邵氏", "shaw", "celestial"],
    "香港": ["香港", "港片", "hk"],
    "粤语": ["粤语", "粵語", "cantonese"],
    "功夫": ["功夫", "kung fu", "kungfu"],
    "武侠": ["武侠", "武俠", "wuxia"],
    "恐怖": ["恐怖", "horror"],
    "惊悚": ["惊悚", "驚悚", "thriller"],
    "经典": ["经典", "經典", "classic"],
    "老电影": ["老电影", "老電影", "old movie", "old movies"],
    "怀旧": ["怀旧", "懷舊", "nostalgia"],
    "电影": ["movie", "movies", "film", "films", "cinema", "电影", "電影"],
}

def norm(v):
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()

def row_blob(row):
    # V5.2 deliberately analyzes metadata only.
    # Do NOT include playlist URL/source here, otherwise URL path words can create false hits.
    fields = [
        row.get("name", ""),
        row.get("alt", ""),
        row.get("group", ""),
        row.get("tvg_id", ""),
        row.get("tvg_name", ""),
    ]
    return norm(" | ".join(fields)).lower()

def top_counter(rows, field, limit=50):
    c = Counter()
    for r in rows:
        v = norm(r.get(field, ""))
        if v:
            c[v] += 1
    return [{"value": k, "count": v} for k, v in c.most_common(limit)]

def keyword_hits(rows):
    result = {}
    for category, words in KEYWORDS.items():
        hits = []
        for r in rows:
            blob = row_blob(r)
            matched = [w for w in words if w.lower() in blob]
            if matched:
                item = dict(r)
                item["matched_keywords"] = matched
                hits.append(item)
        result[category] = hits
    return result

def tokenize(rows):
    # Chinese: retain contiguous CJK chunks.
    # Latin/digits: retain useful words of length >= 2.
    c = Counter()
    for r in rows:
        text = " ".join(
            norm(r.get(k, "")) for k in ("name", "alt", "group", "tvg_id", "tvg_name")
        )
        for x in re.findall(r"[\u4e00-\u9fff]{2,}", text):
            c[x] += 1
        for x in re.findall(r"[A-Za-z][A-Za-z0-9_-]{1,}", text):
            c[x.lower()] += 1
    return [{"token": k, "count": v} for k, v in c.most_common(200)]

def main():
    if not INPUT.exists():
        print(f"ERROR: input not found: {INPUT}")
        print("Please copy movie_v51_result.json into data\\ and run again.")
        raise SystemExit(1)

    raw = json.loads(INPUT.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        rows = raw.get("results") or raw.get("items") or raw.get("data") or []
    else:
        rows = raw

    if not isinstance(rows, list):
        raise SystemExit("ERROR: unsupported JSON structure in movie_v51_result.json")

    final_rows = [r for r in rows if r.get("final_ok", True)]
    generic = [r for r in final_rows if norm(r.get("category")) == "电影综合"]
    shaw = [r for r in final_rows if "邵氏" in row_blob(r) or "shaw" in row_blob(r) or "celestial" in row_blob(r)]

    groups = top_counter(generic, "group")
    names = top_counter(generic, "name")
    alts = top_counter(generic, "alt")
    tvg_ids = top_counter(generic, "tvg_id")
    sources = top_counter(generic, "source")

    hits = keyword_hits(generic)

    report = {
        "input": str(INPUT),
        "total_rows": len(rows),
        "final_ok_rows": len(final_rows),
        "movie_generic_rows": len(generic),
        "shaw_context_rows": len(shaw),
        "top_groups": groups,
        "top_names": names,
        "top_alts": alts,
        "top_tvg_ids": tvg_ids,
        "top_sources": sources,
        "keyword_summary": {k: len(v) for k, v in hits.items()},
        "keyword_hits": hits,
        "top_tokens": tokenize(generic),
    }

    report_path = DATA_DIR / "movie_v52_metadata_report.json"
    hits_path = DATA_DIR / "movie_v52_keyword_hits.json"
    generic_path = DATA_DIR / "movie_v52_generic.json"
    csv_path = DATA_DIR / "movie_v52_generic.csv"
    review_m3u = OUTPUT_DIR / "movie_generic_review.m3u"
    shaw_m3u = OUTPUT_DIR / "shaw_context_review.m3u"

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    hits_path.write_text(json.dumps(hits, ensure_ascii=False, indent=2), encoding="utf-8")
    generic_path.write_text(json.dumps(generic, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = [
        "name", "alt", "group", "tvg_id", "tvg_name", "category",
        "source", "playlist_url", "url", "elapsed_ms", "speed_score", "final_ok"
    ]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in generic:
            w.writerow({k: r.get(k, "") for k in fields})

    def write_m3u(path, selected):
        with path.open("w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for r in selected:
                url = norm(r.get("url") or r.get("playlist_url"))
                if not url:
                    continue
                name = norm(r.get("name") or r.get("tvg_name") or "未命名")
                group = norm(r.get("group") or "电影综合")
                f.write(f'#EXTINF:-1 group-title="{group}",{name}\n{url}\n')

    write_m3u(review_m3u, generic)
    write_m3u(shaw_m3u, shaw)

    print("=== V5.2 Metadata Analyzer ===")
    print(f"Input rows: {len(rows)}")
    print(f"Final OK: {len(final_rows)}")
    print(f"电影综合: {len(generic)}")
    print(f"邵氏上下文命中: {len(shaw)}")
    print()
    print("=== Keyword summary ===")
    for k, v in report["keyword_summary"].items():
        print(f"{k}: {v}")

    print()
    print("=== Top groups in 电影综合 ===")
    for x in groups[:30]:
        print(f'{x["count"]:>5}  {x["value"]}')

    print()
    print("=== Top names in 电影综合 ===")
    for x in names[:30]:
        print(f'{x["count"]:>5}  {x["value"]}')

    print()
    print("=== Top tokens ===")
    for x in report["top_tokens"][:50]:
        print(f'{x["count"]:>5}  {x["token"]}')

    print()
    print("=== Output ===")
    for p in (report_path, hits_path, generic_path, csv_path, review_m3u, shaw_m3u):
        print(p)

if __name__ == "__main__":
    main()
