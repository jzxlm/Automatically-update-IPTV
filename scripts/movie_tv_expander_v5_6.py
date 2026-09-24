from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE_DIR = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE_DIR / "data" / "movie_v55_1_retry.json"
OUTPUT_FILE = BASE_DIR / "data" / "movie_tv_v56_result.json"
SUMMARY_FILE = BASE_DIR / "data" / "movie_tv_v56_summary.json"
OUTPUT_M3U = BASE_DIR / "output" / "movies_tv_v56_all.m3u"

WORKERS = 12
TIMEOUT = (5, 12)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0 Safari/537.36"

# Public playlist indexes. We use the playlist repositories as discovery sources,
# then deduplicate and keep the actual stream URLs found in them.
PLAYLIST_SOURCES = [
    (
        "iptvjs_cctv",
        "https://raw.githubusercontent.com/iptvjs/iptv/main/o_s_cn_cctv.m3u",
    ),
    (
        "iptvjs_cn_streams",
        "https://raw.githubusercontent.com/iptvjs/iptv/main/o_s_cn.m3u",
    ),
    (
        "iptvjs_cc",
        "https://raw.githubusercontent.com/iptvjs/iptv/main/ew_cc.m3u",
    ),
    (
        "iptvjs_cn",
        "https://raw.githubusercontent.com/iptvjs/iptv/main/ew_cn.m3u",
    ),
]

# These are classification labels, not direct single-episode download targets.
DRAMA_RULES = {
    "康熙微服私访记": ["康熙微服私访记", "康熙微服", "kangxi"],
    "宰相刘罗锅": ["宰相刘罗锅", "刘罗锅"],
    "白鹿原": ["白鹿原"],
    "爱情公寓": ["爱情公寓", "爱情公寓系列"],
    "还珠格格": ["还珠格格"],
    "西游记": ["西游记"],
    "红楼梦": ["红楼梦"],
    "三国演义": ["三国演义"],
    "水浒传": ["水浒传"],
    "武林外传": ["武林外传"],
    "家有儿女": ["家有儿女"],
    "亮剑": ["亮剑"],
    "甄嬛传": ["甄嬛传"],
    "琅琊榜": ["琅琊榜"],
    "大宅门": ["大宅门"],
    "雍正王朝": ["雍正王朝"],
    "铁齿铜牙纪晓岚": ["铁齿铜牙纪晓岚", "铁齿铜牙纪晓兰"],
    "神雕侠侣": ["神雕侠侣"],
    "天龙八部": ["天龙八部"],
    "射雕英雄传": ["射雕英雄传"],
    "倚天屠龙记": ["倚天屠龙记"],
}

STAR_RULES = {
    "成龙": ["成龙", "jackie chan"],
    "李连杰": ["李连杰", "jet li"],
    "李小龙": ["李小龙", "bruce lee"],
    "周润发": ["周润发", "发哥", "chow yun-fat"],
    "周星驰": ["周星驰", "星爷", "stephen chow"],
    "甄子丹": ["甄子丹", "donnie yen"],
    "洪金宝": ["洪金宝", "sammo hung"],
    "元彪": ["元彪", "yuen biao"],
    "狄龙": ["狄龙", "ti lung"],
    "姜大卫": ["姜大卫", "david chiang"],
    "刘德华": ["刘德华", "andy lau"],
    "梁朝伟": ["梁朝伟", "tony leung"],
    "张国荣": ["张国荣", "leslie cheung"],
    "林正英": ["林正英", "lam ching-ying"],
    "黄秋生": ["黄秋生", "anthony wong"],
    "吴镇宇": ["吴镇宇", "francis ng"],
    "史泰龙": ["史泰龙", "stallone", "sylvester stallone"],
    "施瓦辛格": ["施瓦辛格", "arnold schwarzenegger"],
    "汤姆·克鲁斯": ["汤姆·克鲁斯", "tom cruise"],
    "基努·里维斯": ["基努·里维斯", "keanu reeves"],
    "布鲁斯·威利斯": ["布鲁斯·威利斯", "bruce willis"],
    "杰森·斯坦森": ["杰森·斯坦森", "jason statham"],
}

CHANNEL_RULES = [
    ("CCTV", [r"\bcctv\b", "央视"]),
    ("CCTV-1 综合", ["cctv-1", "cctv1", "cctv 1", "cctv一"]),
    ("CCTV-6 电影", ["cctv-6", "cctv6", "cctv 6", "电影频道"]),
    ("CCTV-8 电视剧", ["cctv-8", "cctv8", "cctv 8", "电视剧频道"]),
    ("影视剧场", ["影视剧场", "电视剧场", "欢笑剧场", "怀旧剧场"]),
]


def norm(s: str) -> str:
    s = str(s or "").strip().lower()
    s = s.replace("　", " ")
    return re.sub(r"\s+", " ", s)


def fetch_source(item):
    source_name, url = item
    try:
        r = requests.get(
            url,
            timeout=TIMEOUT,
            headers={"User-Agent": UA, "Accept": "*/*"},
        )
        r.raise_for_status()
        return source_name, url, r.text, ""
    except Exception as exc:
        return source_name, url, "", str(exc)


def parse_m3u(text: str, source_name: str) -> list[dict]:
    rows = []
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            current = {"extinf": line, "source": source_name}
        elif current and not line.startswith("#"):
            current["url"] = line
            attrs = {}
            for m in re.finditer(r'([\w-]+)="([^"]*)"', current["extinf"]):
                attrs[m.group(1)] = m.group(2)
            title = current["extinf"].split(",", 1)[1].strip() if "," in current["extinf"] else ""
            current["name"] = attrs.get("tvg-name") or title
            current["group"] = attrs.get("group-title", "")
            current["tvg_id"] = attrs.get("tvg-id", "")
            rows.append(current)
            current = None
    return rows


def parse_plain_lines(text: str, source_name: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "," in line:
            name, url = line.split(",", 1)
            if url.strip().startswith(("http://", "https://")):
                rows.append({
                    "name": name.strip(),
                    "group": "",
                    "tvg_id": "",
                    "url": url.strip(),
                    "source": source_name,
                    "extinf": "",
                })
    return rows


def classify_name(name: str, group: str, tvg_id: str) -> tuple[list[str], list[str], list[str]]:
    blob = norm(" | ".join([name, group, tvg_id]))
    dramas = []
    stars = []
    channels = []

    for label, keys in DRAMA_RULES.items():
        if any(norm(k) in blob for k in keys):
            dramas.append(label)

    for label, keys in STAR_RULES.items():
        if any(norm(k) in blob for k in keys):
            stars.append(label)

    for label, keys in CHANNEL_RULES:
        for k in keys:
            if k.startswith("\\b"):
                if re.search(k, blob):
                    channels.append(label)
                    break
            elif norm(k) in blob:
                channels.append(label)
                break

    return sorted(set(dramas)), sorted(set(stars)), sorted(set(channels))


def url_key(url: str) -> str:
    # Normalize only obvious duplicate formatting. Do not rewrite the URL path.
    u = url.strip()
    return u.rstrip()


def make_extinf(row: dict) -> str:
    name = row.get("name") or "Unknown"
    group = row.get("final_group") or row.get("group") or "其他"
    tvg_id = row.get("tvg_id") or ""
    parts = ['#EXTINF:-1']
    if tvg_id:
        parts.append(f'tvg-id="{tvg_id}"')
    parts.append(f'group-title="{group}"')
    return " ".join(parts) + "," + name


def load_existing():
    if not INPUT_FILE.exists():
        return []
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    for k in ("rows", "items", "results", "data"):
        if isinstance(data.get(k), list):
            return data[k]
    return []


def main():
    print("=== V5.6 Channel + Drama Source Expander ===")
    print("No video frame analysis.")
    print("No AI visual recognition.")
    print(f"Input: {INPUT_FILE}")

    existing = load_existing()
    print(f"Existing V5.5.1 rows: {len(existing)}")
    print(f"Public playlist sources: {len(PLAYLIST_SOURCES)}")

    fetched = []
    with ThreadPoolExecutor(max_workers=min(WORKERS, len(PLAYLIST_SOURCES))) as ex:
        futures = [ex.submit(fetch_source, x) for x in PLAYLIST_SOURCES]
        for f in as_completed(futures):
            fetched.append(f.result())

    external = []
    fetch_errors = {}
    for source_name, url, text, err in fetched:
        if err:
            fetch_errors[source_name] = err
            continue
        parsed = parse_m3u(text, source_name)
        if not parsed:
            parsed = parse_plain_lines(text, source_name)
        external.extend(parsed)
        print(f"Fetched {source_name}: {len(parsed)} entries")

    # Merge existing + public playlists. Existing source fields are preserved.
    merged = []
    seen = set()

    for r in existing:
        url = r.get("url") or r.get("playlist_url") or r.get("stream_url") or ""
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        key = url_key(url)
        if key in seen:
            continue
        seen.add(key)
        item = dict(r)
        item["_source_kind"] = "existing"
        merged.append(item)

    added_external = 0
    for r in external:
        url = r.get("url", "")
        key = url_key(url)
        if not url.startswith(("http://", "https://")) or key in seen:
            continue
        seen.add(key)
        item = dict(r)
        item["_source_kind"] = "public_playlist"
        merged.append(item)
        added_external += 1

    # Classification.
    drama_counter = Counter()
    star_counter = Counter()
    channel_counter = Counter()
    target_hits = []

    for r in merged:
        name = r.get("name") or r.get("tvg_name") or r.get("title") or ""
        group = r.get("group") or r.get("group_title") or ""
        tvg_id = r.get("tvg_id") or ""

        dramas, stars, channels = classify_name(name, group, tvg_id)

        r["drama_tags"] = dramas
        r["star_tags"] = stars
        r["channel_tags"] = channels

        if "CCTV-8 电视剧" in channels:
            r["final_group"] = "电视剧｜CCTV-8"
        elif "CCTV-6 电影" in channels:
            r["final_group"] = "电影｜CCTV-6"
        elif dramas:
            r["final_group"] = "电视剧｜" + dramas[0]
        elif stars:
            r["final_group"] = "明星｜" + stars[0]
        elif "CCTV" in channels:
            r["final_group"] = "央视"
        elif channels:
            r["final_group"] = "影视剧场"
        else:
            r["final_group"] = group or "其他"

        for x in dramas:
            drama_counter[x] += 1
        for x in stars:
            star_counter[x] += 1
        for x in channels:
            channel_counter[x] += 1

        if dramas or stars:
            target_hits.append({
                "name": name,
                "url": r.get("url") or r.get("playlist_url"),
                "group": r.get("final_group"),
                "drama_tags": dramas,
                "star_tags": stars,
                "source_kind": r.get("_source_kind"),
            })

    # Sort: target TV dramas / CCTV / stars first, then everything else.
    merged.sort(
        key=lambda r: (
            0 if r.get("drama_tags") else
            1 if r.get("channel_tags") else
            2 if r.get("star_tags") else 3,
            r.get("final_group", ""),
            r.get("name", ""),
        )
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_M3U.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    with OUTPUT_M3U.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for r in merged:
            url = r.get("url") or r.get("playlist_url")
            if not url:
                continue
            f.write(make_extinf(r) + "\n")
            f.write(url.strip() + "\n")

    summary = {
        "version": "V5.6",
        "existing_rows": len(existing),
        "external_playlist_entries": len(external),
        "new_unique_external_sources": added_external,
        "merged_unique_sources": len(merged),
        "drama_matches": sum(drama_counter.values()),
        "star_matches": sum(star_counter.values()),
        "cctv_and_channel_matches": sum(channel_counter.values()),
        "drama_counts": dict(drama_counter.most_common()),
        "star_counts": dict(star_counter.most_common()),
        "channel_counts": dict(channel_counter.most_common()),
        "fetch_errors": fetch_errors,
        "target_hits": target_hits,
        "playlist_sources": [
            {"name": name, "url": url} for name, url in PLAYLIST_SOURCES
        ],
        "notes": [
            "No video frame extraction.",
            "No visual AI recognition.",
            "Drama labels are metadata/name/EPG-style matches.",
            "CCTV-8 is classified as a TV drama channel.",
            "Specific drama titles are only tagged when the title appears in source metadata; this does not imply a current broadcast.",
        ],
    }

    with SUMMARY_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("\n=== V5.6 Result ===")
    print(f"Existing rows: {len(existing)}")
    print(f"External playlist entries: {len(external)}")
    print(f"New unique external sources: {added_external}")
    print(f"Merged unique sources: {len(merged)}")
    print(f"Drama matches: {sum(drama_counter.values())}")
    print(f"Star matches: {sum(star_counter.values())}")

    print("\nDrama counts:")
    for k, v in drama_counter.most_common():
        print(f"  {k}: {v}")

    print("\nCCTV / channel counts:")
    for k, v in channel_counter.most_common():
        print(f"  {k}: {v}")

    print("\nStar counts:")
    for k, v in star_counter.most_common():
        print(f"  {k}: {v}")

    print("\nDone.")
    print(OUTPUT_FILE)
    print(SUMMARY_FILE)
    print(OUTPUT_M3U)


if __name__ == "__main__":
    main()
