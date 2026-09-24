from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_tv_v59_result.json"
OUTPUT_JSON = BASE_DIR / "data" / "movie_tv_final.json"
SUMMARY_JSON = BASE_DIR / "data" / "movie_tv_final_summary.json"

OUTPUT_DIR = BASE_DIR / "output"
FINAL_M3U = OUTPUT_DIR / "movies_tv_final.m3u"
FINAL_DIR = OUTPUT_DIR / "final"

CATEGORY_ORDER = [
    "CCTV",
    "CCTV-1 综合",
    "CCTV-6 电影",
    "CCTV-8 电视剧",
    "电影",
    "恐怖电影",
    "惊悚电影",
    "功夫电影",
    "香港电影",
    "电视剧",
    "经典电视剧",
    "经典电影",
    "其他",
]

CCTV_RULES = [
    ("CCTV-1 综合", ["cctv1", "cctv-1", "cctv 1", "中央一台", "中央1台"]),
    ("CCTV-6 电影", ["cctv6", "cctv-6", "cctv 6", "中央六套", "中央6台"]),
    ("CCTV-8 电视剧", ["cctv8", "cctv-8", "cctv 8", "中央八套", "中央8台"]),
]

DRAMA_NAMES = [
    "康熙微服私访记", "宰相刘罗锅", "白鹿原", "爱情公寓",
    "还珠格格", "西游记", "红楼梦", "三国演义", "水浒传",
    "武林外传", "家有儿女", "亮剑", "甄嬛传", "琅琊榜",
    "大宅门", "雍正王朝", "铁齿铜牙纪晓岚",
    "神雕侠侣", "天龙八部", "射雕英雄传", "倚天屠龙记",
]

STAR_NAMES = [
    "成龙", "李连杰", "李小龙", "周润发", "周星驰", "甄子丹",
    "洪金宝", "元彪", "狄龙", "姜大卫", "刘德华", "梁朝伟",
    "张国荣", "林正英", "黄秋生", "吴镇宇", "史泰龙",
    "施瓦辛格", "汤姆·克鲁斯", "基努·里维斯", "布鲁斯·威利斯",
    "杰森·斯坦森",
]


def load_rows():
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("rows") or data.get("results") or data.get("data") or []
    return data


def text_blob(row):
    fields = [
        "name", "channel_name", "title", "group", "category",
        "genre", "source", "url", "tvg_name", "tvg_group",
        "primary_category",
    ]
    return " ".join(str(row.get(k, "")) for k in fields).lower()


def display_name(row):
    return (
        row.get("name")
        or row.get("channel_name")
        or row.get("title")
        or row.get("tvg_name")
        or "Unknown"
    )


def safe_filename(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "其他"


def classify_final(row):
    text = text_blob(row)

    for category, keywords in CCTV_RULES:
        if any(k.lower() in text for k in keywords):
            return category

    # Preserve the meaningful V5.9 category instead of inventing new labels.
    old = str(row.get("primary_category", "")).strip()
    if old in CATEGORY_ORDER:
        return old

    return "其他"


def m3u_text(rows, group_override=None):
    lines = ["#EXTM3U"]
    for row in rows:
        name = display_name(row)
        url = str(row.get("url", "")).strip()
        if not url:
            continue

        group = group_override or row.get("primary_category") or "其他"
        attrs = [f'group-title="{group}"']

        tvg_id = row.get("tvg_id")
        logo = row.get("tvg_logo") or row.get("logo")

        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        if logo:
            attrs.append(f'tvg-logo="{logo}"')

        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
        lines.append(url)

    return "\n".join(lines) + "\n"


def write_playlist(path, rows, group_override=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(m3u_text(rows, group_override), encoding="utf-8")


def main():
    print("=== V6.0 Final IPTV Organizer ===")
    print("Uses the current 750 playable sources only.")
    print("No network probing. No FFprobe. No video frame analysis. No AI.")
    print(f"Input: {INPUT_FILE}")

    rows = load_rows()
    playable = [r for r in rows if r.get("status") == "ok"]

    # URL deduplication while preserving all metadata from the first record.
    unique = {}
    for row in playable:
        url = str(row.get("url", "")).strip()
        if not url:
            continue
        if url not in unique:
            unique[url] = dict(row)

    final_rows = list(unique.values())

    for row in final_rows:
        row["final_category"] = classify_final(row)

        text = text_blob(row)
        row["matched_dramas"] = [
            x for x in DRAMA_NAMES if x.lower() in text
        ]
        row["matched_stars"] = [
            x for x in STAR_NAMES if x.lower() in text
        ]

    # Stable category ordering.
    rank = {name: i for i, name in enumerate(CATEGORY_ORDER)}
    final_rows.sort(
        key=lambda r: (
            rank.get(r.get("final_category", "其他"), 999),
            display_name(r).lower(),
            str(r.get("url", "")),
        )
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(final_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Master playlist.
    master_rows = []
    for row in final_rows:
        copy = dict(row)
        copy["primary_category"] = row["final_category"]
        master_rows.append(copy)

    FINAL_M3U.write_text(m3u_text(master_rows), encoding="utf-8")

    # Category playlists.
    categories = {}
    for row in master_rows:
        categories.setdefault(row["final_category"], []).append(row)

    for category in CATEGORY_ORDER:
        items = categories.get(category, [])
        if items:
            write_playlist(
                FINAL_DIR / f"{safe_filename(category)}.m3u",
                items,
                category,
            )

    # A few convenient combined playlists.
    movie_categories = {
        "电影", "恐怖电影", "惊悚电影", "功夫电影",
        "香港电影", "经典电影", "CCTV-6 电影",
    }
    tv_categories = {
        "电视剧", "经典电视剧", "CCTV-8 电视剧",
    }
    cctv_categories = {
        "CCTV", "CCTV-1 综合", "CCTV-6 电影", "CCTV-8 电视剧",
    }

    write_playlist(
        FINAL_DIR / "电影_全部.m3u",
        [r for r in master_rows if r["final_category"] in movie_categories],
        "电影",
    )
    write_playlist(
        FINAL_DIR / "电视剧_全部.m3u",
        [r for r in master_rows if r["final_category"] in tv_categories],
        "电视剧",
    )
    write_playlist(
        FINAL_DIR / "CCTV_全部.m3u",
        [r for r in master_rows if r["final_category"] in cctv_categories],
        "CCTV",
    )

    # Match playlists where metadata actually contains a known drama/star.
    for drama in DRAMA_NAMES:
        items = [r for r in master_rows if drama in r["matched_dramas"]]
        if items:
            write_playlist(
                FINAL_DIR / f"电视剧_{safe_filename(drama)}.m3u",
                items,
                "经典电视剧",
            )

    for star in STAR_NAMES:
        items = [r for r in master_rows if star in r["matched_stars"]]
        if items:
            write_playlist(
                FINAL_DIR / f"演员_{safe_filename(star)}.m3u",
                items,
                "演员",
            )

    counts = Counter(r["final_category"] for r in master_rows)
    summary = {
        "input_rows": len(rows),
        "input_playable": len(playable),
        "final_unique_playable": len(master_rows),
        "categories": dict(
            sorted(counts.items(), key=lambda x: rank.get(x[0], 999))
        ),
        "drama_matches": dict(
            Counter(
                d
                for r in master_rows
                for d in r["matched_dramas"]
            ).most_common()
        ),
        "star_matches": dict(
            Counter(
                s
                for r in master_rows
                for s in r["matched_stars"]
            ).most_common()
        ),
        "network_probing": False,
        "ffprobe": False,
        "video_frame_analysis": False,
        "ai": False,
    }

    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("=== V6.0 Result ===")
    print(f"Playable input: {len(playable)}")
    print(f"Final unique playable: {len(master_rows)}")
    print()
    print("Categories:")
    for category in CATEGORY_ORDER:
        if counts.get(category):
            print(f"  {category}: {counts[category]}")
    print()
    print("Master M3U:")
    print(FINAL_M3U)
    print()
    print("Category directory:")
    print(FINAL_DIR)
    print()
    print("Summary:")
    print(SUMMARY_JSON)
    print()
    print("Done.")


if __name__ == "__main__":
    main()
