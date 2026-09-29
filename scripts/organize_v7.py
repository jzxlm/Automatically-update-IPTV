from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parent.parent
INPUT = BASE / "data" / "movie_tv_v59_result.json"
DATA_OUT = BASE / "data" / "movie_tv_v7_result.json"
SUMMARY = BASE / "data" / "movie_tv_v7_summary.json"
OUTPUT = BASE / "output"
FINAL = OUTPUT / "final"
MASTER = OUTPUT / "movies_tv_final.m3u"

CATEGORY_ORDER = [
    "央视", "卫视", "4K影视", "港澳", "台湾省", "国际",
    "轮播1", "轮播2", "轮播3", "无奇不有", "经典电影", "恐怖电影", "其他",
]

COUNTRY_GROUPS = {
    "US", "DE", "ES", "IN", "RU", "PL", "SE", "BR", "Iran", "MN", "UA",
    "HU", "CA", "CZ", "UK", "PK", "FR", "CL", "SA", "EE", "PT", "UZ",
    "AR", "EG", "PR", "NL", "CN", "Japan / Japan", "Music", "Animation", "Family",
}

CCTV_NAMES = {
    "1": "CCTV-1 综合", "2": "CCTV-2 财经", "3": "CCTV-3 综艺", "4": "CCTV-4 中文国际",
    "5": "CCTV-5 体育", "5+": "CCTV-5+ 体育赛事", "6": "CCTV-6 电影", "7": "CCTV-7 国防军事",
    "8": "CCTV-8 电视剧", "9": "CCTV-9 纪录", "10": "CCTV-10 科教", "11": "CCTV-11 戏曲",
    "12": "CCTV-12 社会与法", "13": "CCTV-13 新闻", "14": "CCTV-14 少儿", "15": "CCTV-15 音乐",
    "16": "CCTV-16 体育赛事", "17": "CCTV-17 农业农村", "4K": "CCTV-4K", "8K": "CCTV-8K",
}


def load():
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("rows") or data.get("results") or data.get("data") or []
    return data


def norm(s: object) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def source(row):
    return row.get("source") if isinstance(row.get("source"), dict) else {}


def original_name(row):
    s = source(row)
    return norm(row.get("name") or row.get("channel_name") or row.get("title") or s.get("name") or "未知频道")


def tvg_id(row):
    s = source(row)
    return norm(row.get("tvg_id") or s.get("tvg_id"))


def cctv_number(row):
    blob = " ".join([original_name(row), tvg_id(row), norm(source(row).get("group")), norm(source(row).get("final_group"))]).lower()
    patterns = [
        r"cctv[- _]?(5\+|4k|8k|1[0-7]|[1-9])(?:\\.cn|@|\\b)",
        r"cctv[- _]?(5\+|4k|8k|1[0-7]|[1-9])$",
    ]
    for p in patterns:
        m = re.search(p, blob, re.I)
        if m:
            return m.group(1).upper()
    m = re.search(r"中央\s*([1-9]|1[0-7])套", blob)
    return m.group(1) if m else None


def canonical_name(row):
    n = cctv_number(row)
    if n:
        return CCTV_NAMES.get(n, original_name(row))
    return original_name(row)


def classify(row):
    s = source(row)
    name = original_name(row)
    group = norm(s.get("final_group") or s.get("group"))
    old = norm(row.get("primary_category"))
    blob = f"{name} {group} {old} {tvg_id(row)}".lower()

    if cctv_number(row):
        return "央视"
    if "4k" in blob or "8k" in blob or "uhd" in blob or "2160p" in blob:
        return "4K影视"
    if group == "HK" or "香港" in blob or "澳门" in blob or "macau" in blob:
        return "港澳"
    if "台湾" in blob or "台灣" in blob or re.search(r"\bTW\b", blob):
        return "台湾省"
    if old == "恐怖电影" or "恐怖" in name:
        return "恐怖电影"
    if group == "Classic" or old == "经典电影":
        return "经典电影"
    if group in {"Movies", "电影", "电影｜CCTV-6"} or old in {"电影", "CCTV-6 电影"}:
        return "轮播1"
    if group in {"Series", "电视剧｜CCTV-8"} or old in {"电视剧", "CCTV-8 电视剧"}:
        return "轮播2"
    if group in {"VOD Movies (EN)", "VOD Italy", "Comedy", "影视剧场"}:
        return "轮播3"
    if group in COUNTRY_GROUPS or group.startswith("VOD ") or group in {"US", "DE", "ES", "IN", "RU", "PL", "SE", "BR", "Iran", "MN", "UA", "HU", "CA", "CZ", "UK", "PK", "FR", "CL", "SA", "EE", "PT", "UZ", "AR", "EG", "PR", "NL", "Japan / Japan"}:
        return "国际"
    if group in {"综合", "综艺", "Family", "Music", "Animation", "运动"}:
        return "无奇不有"
    return "其他"


def clean_attr(s: object) -> str:
    return str(s or "").replace('"', "'").replace("\n", " ").strip()


def m3u(rows):
    lines = ["#EXTM3U"]
    for i, row in enumerate(rows, 1):
        url = norm(row.get("url"))
        if not url:
            continue
        name = clean_attr(row["display_name"])
        group = clean_attr(row["final_category"])
        attrs = [f'tvg-chno="{i}"', f'group-title="{group}"']
        tid = clean_attr(row.get("tvg_id"))
        logo = clean_attr(row.get("tvg_logo") or row.get("logo"))
        if tid:
            attrs.append(f'tvg-id="{tid}"')
        if logo:
            attrs.append(f'tvg-logo="{logo}"')
        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"


def safe_filename(s):
    return re.sub(r'[\\/:*?"<>|]+', "_", s).strip() or "其他"


def main():
    rows = load()
    playable = [r for r in rows if norm(r.get("url")) and r.get("status") == "ok"]
    unique = {}
    for r in playable:
        url = norm(r.get("url"))
        unique.setdefault(url, dict(r))

    final = []
    for r in unique.values():
        r["display_name"] = canonical_name(r)
        r["tvg_id"] = tvg_id(r)
        r["final_category"] = classify(r)
        final.append(r)

    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    final.sort(key=lambda r: (rank.get(r["final_category"], 99), r["display_name"].lower(), r["url"]))

    OUTPUT.mkdir(exist_ok=True)
    FINAL.mkdir(parents=True, exist_ok=True)
    for p in FINAL.glob("*.m3u"):
        p.unlink()
    for p in OUTPUT.glob("*.m3u"):
        p.unlink()

    MASTER.write_text(m3u(final), encoding="utf-8")
    groups = {c: [] for c in CATEGORY_ORDER}
    for r in final:
        groups.setdefault(r["final_category"], []).append(r)
    for c in CATEGORY_ORDER:
        if groups.get(c):
            (FINAL / f"{safe_filename(c)}.m3u").write_text(m3u(groups[c]), encoding="utf-8")

    # Combined playlists useful for players.
    combos = {
        "央视_全部.m3u": groups.get("央视", []),
        "电影_全部.m3u": groups.get("轮播1", []) + groups.get("轮播3", []) + groups.get("经典电影", []) + groups.get("恐怖电影", []),
        "电视剧_全部.m3u": groups.get("轮播2", []),
    }
    for fn, rs in combos.items():
        if rs:
            (FINAL / fn).write_text(m3u(rs), encoding="utf-8")

    DATA_OUT.write_text(json.dumps(final, ensure_ascii=False, indent=2), encoding="utf-8")
    counts = Counter(r["final_category"] for r in final)
    summary = {
        "input_rows": len(rows),
        "playable_input": len(playable),
        "final_unique": len(final),
        "categories": {c: counts.get(c, 0) for c in CATEGORY_ORDER},
        "epg_policy": "Keep only source-provided tvg-id; no guessed EPG and no fabricated program schedule.",
        "classification_policy": "Deterministic metadata rules; unknown items stay in 其他.",
    }
    SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=== IPTV V7 Organizer ===")
    print(f"Input: {len(rows)} | playable: {len(playable)} | unique: {len(final)}")
    for c in CATEGORY_ORDER:
        print(f"  {c}: {counts.get(c, 0)}")
    print(f"Master: {MASTER}")

if __name__ == "__main__":
    main()
