from __future__ import annotations

import json
import re
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

TONKIANG_URL = "https://tonkiang.us/"
IPTV_ORG_CHANNELS = "https://iptv-org.github.io/api/channels.json"
IPTV_ORG_STREAMS = "https://iptv-org.github.io/api/streams.json"
FREE_TV = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
IPTV_NEXUS_INDEX = "https://raw.githubusercontent.com/dearbulut/iptv/main/PLAYLISTS.md"

REMOTE_SOURCES = {
    "iptv2025_ipv4_txt": "https://live.zbds.top/tv/iptv4.txt",
    "iptv2025_ipv4_m3u": "https://live.zbds.top/tv/iptv4.m3u",
    "iptv2025_ipv6_txt": "https://live.zbds.top/tv/iptv6.txt",
    "iptv2025_ipv6_m3u": "https://live.zbds.top/tv/iptv6.m3u",
    "iptvjs_o_cn": "https://raw.githubusercontent.com/iptvjs/iptv/main/o_cn.m3u",
    "iptvjs_o_s_cn": "https://raw.githubusercontent.com/iptvjs/iptv/main/o_s_cn.m3u",
    "iptvjs_ew_hk": "https://raw.githubusercontent.com/iptvjs/iptv/main/ew_hk.m3u",
    "iptvjs_ew_om": "https://raw.githubusercontent.com/iptvjs/iptv/main/ew_om.m3u",
    "iptvjs_ew_tw": "https://raw.githubusercontent.com/iptvjs/iptv/main/ew_tw.m3u",
    "iptvjs_ew_all": "https://raw.githubusercontent.com/iptvjs/iptv/main/ew_all.m3u",
    "iptvjs_fmml_ipv6": "https://raw.githubusercontent.com/iptvjs/iptv/main/fmml_ipv6.m3u",
    "iptvjs_ycl": "https://raw.githubusercontent.com/iptvjs/iptv/main/ycl_iptv.m3u",
    "iptvjs_y_g": "https://raw.githubusercontent.com/iptvjs/iptv/main/y_g.m3u",
    "iptvjs_hc_cntv": "https://raw.githubusercontent.com/iptvjs/iptv/main/hc_cntv.m3u",
}

TONKIANG_TERMS = [
    "经典电影", "classic movie", "classic movies", "动作电影", "成龙",
    "武侠", "horror", "horror movie", "thriller", "怀旧", "nostalgia",
    "邵氏武侠", "邵氏动作", "邵氏", "邵氏电影",
]

MOVIE_TERMS = [
    "电影", "movie", "movies", "film", "films", "cinema",
    "经典", "classic", "classics", "老电影", "老片",
    "old movie", "old movies", "old film", "old films",
    "怀旧", "nostalgia", "retro",
    "香港电影", "香港片", "hong kong movie", "hong kong movies",
    "hk movie", "hk movies",
    "粤语电影", "粤语片", "cantonese movie", "cantonese movies",
    "功夫", "kung fu", "kung-fu",
    "武侠", "wuxia", "martial arts",
    "恐怖", "horror", "惊悚", "thriller",
    "成龙", "jackie chan", "李小龙", "bruce lee",
]

MOVIE_NEGATIVE = [
    "news", "新闻", "finance", "财经", "weather", "天气",
    "sports", "sport", "体育", "kids", "儿童", "cartoon", "动漫",
    "music", "音乐", "radio", "电台", "shopping", "购物",
    "religion", "宗教", "shopping channel",
]

SHAW_TERMS = [
    "邵氏", "邵氏兄弟", "邵氏电影", "邵氏老片",
    "shaw brothers", "shaw brothers ltd", "shaw movie", "shaw movies",
    "shaw", "celestial", "celestial movies", "celestial movie",
    "celestial classic", "celestial classics",
]

SHAW_SUBCATS = [
    ("邵氏武侠", ["武侠", "wuxia", "martial arts"]),
    ("邵氏功夫", ["功夫", "kung fu", "kung-fu"]),
    ("邵氏动作", ["动作", "action"]),
    ("邵氏恐怖", ["恐怖", "horror"]),
    ("邵氏经典", ["经典", "classic", "classics", "老片", "老电影"]),
]

GENERAL_CATEGORIES = {
    "经典电影": ["经典电影", "classic movie", "classic movies", "classic film", "classics"],
    "老电影": ["老电影", "老片", "old movies", "old movie", "old films"],
    "香港电影": ["香港电影", "香港片", "hong kong movie", "hong kong movies", "hk movie", "hk movies"],
    "粤语电影": ["粤语电影", "粤语片", "cantonese movie", "cantonese movies", "cantonese film"],
    "功夫电影": ["功夫电影", "功夫", "kung fu", "kung-fu"],
    "武侠电影": ["武侠电影", "武侠", "wuxia", "martial arts"],
    "恐怖电影": ["恐怖电影", "恐怖", "horror", "horror movie", "horror movies"],
    "惊悚电影": ["惊悚电影", "惊悚", "thriller", "thrillers"],
    "怀旧电影": ["怀旧电影", "怀旧", "nostalgia", "retro movie", "retro movies"],
}

CATEGORY_FILES = {
    "邵氏综合": "shaw.m3u",
    "邵氏武侠": "shaw_wuxia.m3u",
    "邵氏功夫": "shaw_kungfu.m3u",
    "邵氏动作": "shaw_action.m3u",
    "邵氏恐怖": "shaw_horror.m3u",
    "邵氏经典": "shaw_classic.m3u",
    "经典电影": "classic_movies.m3u",
    "老电影": "old_movies.m3u",
    "香港电影": "hongkong_movies.m3u",
    "粤语电影": "cantonese_movies.m3u",
    "功夫电影": "kungfu_movies.m3u",
    "武侠电影": "wuxia_movies.m3u",
    "恐怖电影": "horror_movies.m3u",
    "惊悚电影": "thriller_movies.m3u",
    "怀旧电影": "retro_movies.m3u",
}


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def fetch(url, timeout=25, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            session = requests.Session()
            session.headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0 Safari/537.36"
            )
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.text
        except Exception as exc:
            last = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    print(f"[WARN] fetch failed: {url} -> {last}")
    return ""


def parse_m3u(text, source, playlist_url=""):
    result = []
    current = None

    for line in (x.strip() for x in text.splitlines()):
        if not line:
            continue

        if line.startswith("#EXTINF"):
            current = {
                "source": source,
                "playlist_url": playlist_url,
                "name": "",
                "alt": "",
                "group": "",
                "tvg_id": "",
            }

            match = re.search(r'tvg-name="([^"]*)"', line, re.I)
            if match:
                current["name"] = clean(match.group(1))

            match = re.search(r'tvg-id="([^"]*)"', line, re.I)
            if match:
                current["tvg_id"] = clean(match.group(1))

            match = re.search(r'group-title="([^"]*)"', line, re.I)
            if match:
                current["group"] = clean(match.group(1))

            if not current["name"] and "," in line:
                current["name"] = clean(line.split(",", 1)[1])

        elif not line.startswith("#") and line.startswith(("http://", "https://")):
            if current is not None:
                current["url"] = line
                result.append(current)
            current = None

    return result


def parse_txt(text, source, playlist_url=""):
    result = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("http://", "https://")):
            result.append({
                "source": source,
                "playlist_url": playlist_url,
                "name": "",
                "alt": "",
                "group": "",
                "tvg_id": "",
                "url": line,
            })
    return result


def url_key(url):
    try:
        parsed = urlparse(url.strip())
        return (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.query,
        )
    except Exception:
        return (url.strip(),)


def dedup(rows):
    seen = {}

    for row in rows:
        url = clean(row.get("url"))
        if not url.startswith(("http://", "https://")):
            continue

        key = url_key(url)
        score = sum(
            bool(clean(row.get(field)))
            for field in ("name", "alt", "group", "tvg_id", "source", "playlist_url")
        )

        old = seen.get(key)
        if old is None:
            seen[key] = row
            continue

        old_score = sum(
            bool(clean(old.get(field)))
            for field in ("name", "alt", "group", "tvg_id", "source", "playlist_url")
        )
        if score > old_score:
            seen[key] = row

    return list(seen.values())


def metadata_blob(row):
    # V4.1 的关键修复：
    # 分类绝不再把 source / playlist_url 当成“电影关键词”。
    # 否则 playlist URL 里出现 movie，就会把整张 playlist 的所有频道误判成电影。
    return " ".join(
        clean(row.get(field))
        for field in ("name", "alt", "group", "tvg_id")
        if clean(row.get(field))
    ).lower()


def playlist_context(row):
    return " ".join(
        clean(row.get(field))
        for field in ("source", "playlist_url")
        if clean(row.get(field))
    ).lower()


def hits(text, terms):
    return sum(1 for term in terms if term.lower() in text)


def collect_tonkiang():
    print("\n=== Tonkiang ===")
    rows = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            for term in TONKIANG_TERMS:
                count = 0
                try:
                    page.goto(
                        TONKIANG_URL,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )

                    inputs = page.locator("input")
                    for index in range(min(inputs.count(), 12)):
                        element = inputs.nth(index)
                        input_type = (element.get_attribute("type") or "").lower()
                        placeholder = (element.get_attribute("placeholder") or "").lower()
                        name = (element.get_attribute("name") or "").lower()

                        if input_type in ("hidden", "submit", "button"):
                            continue

                        if (
                            "search" in placeholder
                            or "搜索" in placeholder
                            or "keyword" in name
                            or "search" in name
                            or input_type == "text"
                        ):
                            element.fill(term)
                            element.press("Enter")
                            break

                    page.wait_for_timeout(2200)
                    body = page.locator("body").inner_text()

                    for url in re.findall(r'https?://[^\s<>"\']+', body):
                        url = url.rstrip("),]}>")
                        if url.startswith(("http://", "https://")):
                            rows.append({
                                "source": "tonkiang",
                                "playlist_url": "",
                                "name": term,
                                "alt": "",
                                "group": term,
                                "tvg_id": "",
                                "url": url,
                            })
                            count += 1

                except Exception as exc:
                    print(f"{term}: ERROR -> {exc}")

                print(f"{term}: {count}")

            browser.close()

    except Exception as exc:
        print("[WARN] Tonkiang:", exc)

    return rows


def collect_iptv_org():
    print("\n=== iptv-org ===")

    channels_text = fetch(IPTV_ORG_CHANNELS, retries=3)
    streams_text = fetch(IPTV_ORG_STREAMS, retries=3)

    if not channels_text or not streams_text:
        return []

    try:
        channels = json.loads(channels_text)
        streams = json.loads(streams_text)
    except Exception as exc:
        print("[WARN] iptv-org JSON:", exc)
        return []

    by_id = {item.get("id"): item for item in channels if item.get("id")}
    rows = []

    for stream in streams:
        channel = by_id.get(stream.get("channel"))
        if not channel:
            continue

        rows.append({
            "source": "iptv-org",
            "playlist_url": "",
            "name": clean(channel.get("name") or stream.get("channel")),
            "alt": " ".join(clean(x) for x in (channel.get("alt_names") or [])),
            "group": " ".join([
                clean(channel.get("country")),
                " ".join(channel.get("languages") or []),
            ]).strip(),
            "tvg_id": clean(stream.get("channel")),
            "url": clean(stream.get("url")),
        })

    print(f"channels: {len(channels):,}")
    print(f"streams: {len(streams):,}")
    print(f"matched: {len(rows):,}")
    return rows


def collect_simple():
    rows = []

    text = fetch(
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
        retries=3,
    )
    parsed = parse_m3u(text, "Free-TV") if text else []
    rows.extend(parsed)
    print(f"Free-TV: {len(parsed):,}")

    for source, url in REMOTE_SOURCES.items():
        text = fetch(url)
        if not text:
            continue

        if ".m3u" in url.lower():
            parsed = parse_m3u(text, source)
        else:
            parsed = parse_txt(text, source)

        rows.extend(parsed)
        print(f"{source}: {len(parsed):,}")

    return rows


def collect_iptv_nexus():
    print("\n=== IPTV-Nexus movie playlists ===")

    index = fetch(IPTV_NEXUS_INDEX, retries=3)
    if not index:
        return []

    hint = re.compile(
        r"(movie|movies|film|films|cinema|classic|retro|old|shaw|celestial|"
        r"horror|wuxia|kung.?fu|martial|hong.?kong|cantonese|action|"
        r"武侠|电影|邵氏|功夫|恐怖|经典|怀旧|香港|粤语)",
        re.I,
    )

    refs = []
    selected = []

    for line in index.splitlines():
        urls = re.findall(r'https?://[^\s)\]>"\']+', line)

        for url in urls:
            url = url.rstrip("`.,;")

            if not url.lower().endswith((".m3u", ".m3u8", ".txt")):
                continue

            refs.append(url)

            if hint.search(line):
                selected.append(url)

    refs = list(dict.fromkeys(refs))
    selected = list(dict.fromkeys(selected))

    print(f"playlist refs: {len(refs):,}")
    print(f"movie-relevant refs: {len(selected):,}")

    if not selected:
        selected = refs[:50]
        print(f"fallback refs: {len(selected):,}")

    rows = []

    for index_number, url in enumerate(selected, 1):
        text = fetch(url, timeout=20, retries=1)
        if not text:
            continue

        source = f"IPTV-Nexus:{index_number}"

        if ".m3u" in url.lower() or ".m3u8" in url.lower():
            parsed = parse_m3u(text, source, url)
        else:
            parsed = parse_txt(text, source, url)

        # 保存 playlist 本身的电影提示，供后续“没有频道名但 playlist 明确是电影”
        # 的情况使用；但不直接把它当作每个频道的电影名称。
        playlist_name = Path(urlparse(url).path).stem
        for row in parsed:
            row["playlist_name"] = playlist_name

        rows.extend(parsed)

    print(f"parsed: {len(rows):,}")
    return rows


def is_obvious_non_movie(row):
    metadata = metadata_blob(row)

    strong = [
        "news", "新闻", "sports", "sport", "体育",
        "radio", "电台", "weather", "天气",
        "finance", "财经", "kids", "儿童",
        "shopping", "购物",
    ]

    if hits(metadata, strong) >= 1:
        return True

    # 只有元数据里同时出现多个非电影词时才强制排除。
    if hits(metadata, MOVIE_NEGATIVE) >= 2:
        return True

    station_words = ["卫视", "tv station", "television", "tv channel"]
    if hits(metadata, station_words) >= 1 and hits(metadata, MOVIE_TERMS) < 2:
        return True

    return False


def is_shaw(row):
    metadata = metadata_blob(row)
    context = playlist_context(row)

    if hits(metadata, SHAW_TERMS) >= 1:
        return True

    # 对 IPTV-Nexus 允许 playlist 本身提供 Shaw 线索，
    # 但只有 playlist/source 命中 Shaw 时才使用。
    if row.get("source", "").startswith("IPTV-Nexus") and hits(context, SHAW_TERMS) >= 1:
        return True

    return False


def is_movie_candidate(row):
    metadata = metadata_blob(row)

    if is_obvious_non_movie(row):
        return False

    if is_shaw(row):
        return True

    # 关键：普通电影必须在频道元数据中出现电影相关词。
    # 不再因为 URL / source 名称出现 movie 就整张 playlist 入选。
    if hits(metadata, MOVIE_TERMS) >= 1:
        return True

    # IPTV-Nexus 的特殊情况：
    # playlist 明确是电影，但频道行没有名称/分类时，允许进入，
    # 但只限 Nexus，避免污染其它来源。
    if row.get("source", "").startswith("IPTV-Nexus"):
        context = playlist_context(row)
        if hits(context, MOVIE_TERMS) >= 1:
            return True

    return False


def shaw_category(row):
    if not is_shaw(row):
        return None

    text = metadata_blob(row) + " " + playlist_context(row)

    for category, terms in SHAW_SUBCATS:
        if hits(text, terms) >= 1:
            return category

    return "邵氏综合"


def general_categories(row):
    text = metadata_blob(row)
    result = []

    for category, terms in GENERAL_CATEGORIES.items():
        if hits(text, terms) >= 1:
            result.append(category)

    return result


def write_m3u(path, rows):
    lines = ["#EXTM3U"]

    for row in rows:
        name = clean(row.get("name")) or clean(row.get("tvg_id")) or "Unknown"
        group = clean(row.get("category")) or clean(row.get("group")) or "Movies"
        tvg_id = clean(row.get("tvg_id"))
        url = clean(row.get("url"))

        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}" group-title="{group}",{name}'
        )
        lines.append(url)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    raw = []
    raw.extend(collect_tonkiang())
    raw.extend(collect_iptv_org())
    raw.extend(collect_simple())
    raw.extend(collect_iptv_nexus())

    print(f"\nRaw total: {len(raw):,}")

    unique = dedup(raw)
    print(f"Global deduped: {len(unique):,}")

    movie_candidates = dedup([
        row for row in unique
        if is_movie_candidate(row)
    ])

    print(f"High-confidence movie candidates: {len(movie_candidates):,}")

    categories = defaultdict(list)

    for row in movie_candidates:
        shaw = shaw_category(row)

        if shaw:
            copy = dict(row)
            copy["category"] = shaw
            categories[shaw].append(copy)

        for category in general_categories(row):
            copy = dict(row)
            copy["category"] = category
            categories[category].append(copy)

    for category in list(categories):
        categories[category] = dedup(categories[category])

    print("\n=== Movie categories ===")

    for category, filename in CATEGORY_FILES.items():
        rows = categories.get(category, [])
        print(f"{category}: {len(rows):,}")
        write_m3u(OUTPUT_DIR / filename, rows)

    write_m3u(OUTPUT_DIR / "movies.m3u", movie_candidates)

    (DATA_DIR / "movie_candidates.json").write_text(
        json.dumps(movie_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (DATA_DIR / "category_counts.json").write_text(
        json.dumps(
            {
                category: len(categories.get(category, []))
                for category in CATEGORY_FILES
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nDone. Output: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
