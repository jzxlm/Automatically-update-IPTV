from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_tv_v58_result.json"
OUTPUT_FILE = BASE_DIR / "data" / "movie_tv_v59_result.json"
SUMMARY_FILE = BASE_DIR / "data" / "movie_tv_v59_summary.json"
M3U_FILE = BASE_DIR / "output" / "movies_tv_v59_all.m3u"
CAT_DIR = BASE_DIR / "output" / "v59_categories"

# Deliberately conservative: do not classify generic "drama", "series",
# "film", etc. as a category by themselves.
CATEGORY_RULES = [
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
    ("恐怖电影", ["恐怖电影", "恐怖片", "horror movie", "horror movies", "horror"]),
    ("惊悚电影", ["惊悚电影", "惊悚片", "thriller movie", "thriller"]),
    ("功夫电影", ["功夫电影", "功夫片", "kung fu", "martial arts"]),
    ("武侠电影", ["武侠电影", "武侠片", "wuxia"]),
    ("香港电影", ["香港电影", "香港片", "hong kong movie", "hong kong film"]),
    ("经典电影", ["经典电影", "经典影片", "classic movie", "classic movies"]),
    ("电视剧", [
        "电视剧", "电视剧频道", "连续剧", "tv drama", "tv dramas",
        "tv series", "tv series channel", "港剧", "台剧", "韩剧",
        "日剧", "美剧", "国产剧"
    ]),
    ("电影", [
        "电影频道", "电影专区", "电影台", "movie channel",
        "movies channel", "film channel", "cinema channel"
    ]),
    ("CCTV", ["cctv", "中央电视台", "央视"]),
]

DRAMAS = [
    "康熙微服私访记", "宰相刘罗锅", "白鹿原", "爱情公寓",
    "还珠格格", "西游记", "红楼梦", "三国演义", "水浒传",
    "武林外传", "家有儿女", "亮剑", "甄嬛传", "琅琊榜",
    "大宅门", "雍正王朝", "铁齿铜牙纪晓岚",
    "神雕侠侣", "天龙八部", "射雕英雄传", "倚天屠龙记"
]

STARS = [
    "成龙", "李连杰", "李小龙", "周润发", "周星驰", "甄子丹",
    "洪金宝", "元彪", "狄龙", "姜大卫", "刘德华", "梁朝伟",
    "张国荣", "林正英", "黄秋生", "吴镇宇", "史泰龙",
    "施瓦辛格", "汤姆·克鲁斯", "基努·里维斯", "布鲁斯·威利斯",
    "杰森·斯坦森"
]


def norm_url(url: str) -> str:
    try:
        p = urlsplit(str(url).strip())
        if not p.scheme or not p.hostname:
            return str(url).strip()
        scheme = p.scheme.lower()
        host = p.hostname.lower()
        netloc = host
        if p.port:
            if not ((scheme == "http" and p.port == 80) or
                    (scheme == "https" and p.port == 443)):
                netloc = f"{host}:{p.port}"
        return urlunsplit((scheme, netloc, p.path or "/", p.query, ""))
    except Exception:
        return str(url).strip()


def blob(row: dict) -> str:
    keys = [
        "name", "channel_name", "title", "group", "category", "genre",
        "source", "url", "tvg_name", "tvg_group", "drama", "star",
        "matched_keywords", "matched_dramas", "matched_stars"
    ]
    return " ".join(str(row.get(k, "")) for k in keys).lower()


def contains(text: str, kw: str) -> bool:
    return kw.lower() in text


def classify(row: dict) -> str:
    t = blob(row)

    # Specific CCTV channels first.
    for cat, kws in CATEGORY_RULES[:3]:
        if any(contains(t, k) for k in kws):
            return cat

    # Explicit classic drama names.
    for k in DRAMAS:
        if contains(t, k):
            return "经典电视剧"

    # Genre-specific movie groups.
    for cat, kws in CATEGORY_RULES[4:9]:
        if any(contains(t, k) for k in kws):
            return cat

    # Conservative TV category.
    for k in CATEGORY_RULES[9][1]:
        if contains(t, k):
            return "电视剧"

    # Conservative movie category.
    for k in CATEGORY_RULES[10][1]:
        if contains(t, k):
            return "电影"

    # General CCTV only after specific CCTV channels.
    if any(contains(t, k) for k in CATEGORY_RULES[11][1]):
        return "CCTV"

    # If an old category is already a meaningful specific group, retain it.
    old = str(row.get("primary_category", "")).strip()
    allowed = {
        "电影综合", "经典电影", "恐怖电影", "惊悚电影",
        "功夫电影", "武侠电影", "香港电影", "怀旧电影",
        "喜剧电影", "动作电影", "剧情电影", "西部电影",
        "犯罪电影"
    }
    if old in allowed:
        return old

    return "其他"


def better(a: dict, b: dict) -> dict:
    ae = a.get("elapsed_ms", 999999)
    be = b.get("elapsed_ms", 999999)
    return a if ae <= be else b


def load_rows():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("rows") or data.get("results") or data.get("data") or []
    return data


def m3u_text(rows):
    lines = ["#EXTM3U"]
    for r in rows:
        name = r.get("name") or r.get("channel_name") or r.get("title") or "Unknown"
        url = r.get("url", "")
        group = r.get("primary_category", "其他")
        tvg_id = r.get("tvg_id", "")
        logo = r.get("tvg_logo") or r.get("logo") or ""
        attrs = [f'group-title="{group}"']
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if logo:
            attrs.append(f'tvg-logo="{logo}"')
        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
        lines.append(url)
    return "\n".join(lines) + "\n"


def safe_filename(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "其他"


def main():
    print("=== V5.9 Current 750-Source Organizer ===")
    print("Input: data/movie_tv_v58_result.json")
    print("Only current playable sources are organized.")
    print("No new network probing. No video frame analysis. No AI.")

    rows = load_rows()
    playable = [r for r in rows if r.get("status") == "ok"]

    # URL dedup: keep the faster playable record.
    unique = {}
    for r in playable:
        url = norm_url(r.get("url", ""))
        if not url:
            continue
        r = dict(r)
        r["url"] = url
        if url not in unique:
            unique[url] = r
        else:
            unique[url] = better(unique[url], r)

    final = list(unique.values())

    cat_counts = Counter()
    drama_counts = Counter()
    star_counts = Counter()

    for r in final:
        t = blob(r)
        r["primary_category"] = classify(r)
        r["matched_dramas"] = [x for x in DRAMAS if contains(t, x)]
        r["matched_stars"] = [x for x in STARS if contains(t, x)]
        for x in r["matched_dramas"]:
            drama_counts[x] += 1
        for x in r["matched_stars"]:
            star_counts[x] += 1
        cat_counts[r["primary_category"]] += 1

    # Stable category order for the all-in-one M3U.
    order = {
        "CCTV-1 综合": 1, "CCTV-6 电影": 2, "CCTV-8 电视剧": 3,
        "经典电视剧": 4, "恐怖电影": 5, "惊悚电影": 6,
        "功夫电影": 7, "武侠电影": 8, "香港电影": 9,
        "经典电影": 10, "电视剧": 11, "电影": 12,
        "CCTV": 13, "其他": 99
    }

    final.sort(key=lambda r: (
        order.get(r.get("primary_category", "其他"), 98),
        str(r.get("name") or r.get("channel_name") or r.get("title") or ""),
        r.get("url", "")
    ))

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAT_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(final, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    M3U_FILE.write_text(m3u_text(final), encoding="utf-8")

    # One M3U per category.
    category_rows = {}
    for r in final:
        category_rows.setdefault(r["primary_category"], []).append(r)

    for cat, items in category_rows.items():
        (CAT_DIR / f"{safe_filename(cat)}.m3u").write_text(
            m3u_text(items), encoding="utf-8"
        )

    # Special playlists by drama/star match.
    for drama in DRAMAS:
        items = [r for r in final if drama in r.get("matched_dramas", [])]
        if items:
            (CAT_DIR / f"电视剧_{safe_filename(drama)}.m3u").write_text(
                m3u_text(items), encoding="utf-8"
            )

    for star in STARS:
        items = [r for r in final if star in r.get("matched_stars", [])]
        if items:
            (CAT_DIR / f"演员_{safe_filename(star)}.m3u").write_text(
                m3u_text(items), encoding="utf-8"
            )

    summary = {
        "input_rows": len(rows),
        "input_playable": len(playable),
        "final_unique_playable": len(final),
        "primary_categories": dict(cat_counts.most_common()),
        "drama_matches": dict(drama_counts.most_common()),
        "star_matches": dict(star_counts.most_common()),
        "network_retest": False,
        "video_frame_analysis": False,
        "ai": False,
    }

    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print()
    print("=== V5.9 Result ===")
    print(f"V5.8 playable input: {len(playable)}")
    print(f"Final unique playable: {len(final)}")
    print()
    print("Primary categories:")
    for k, v in cat_counts.most_common():
        print(f"  {k}: {v}")
    print()
    print("Drama matches:")
    for k, v in drama_counts.most_common():
        print(f"  {k}: {v}")
    print()
    print("Star matches:")
    for k, v in star_counts.most_common():
        print(f"  {k}: {v}")
    print()
    print("Done.")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)
    print(M3U_FILE)
    print(CAT_DIR)


if __name__ == "__main__":
    main()
