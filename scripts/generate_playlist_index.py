from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
FINAL_DIR = BASE_DIR / "output" / "final"
INDEX_FILE = BASE_DIR / "PLAYLISTS.md"

RAW_BASE = "https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main"

PREFERRED = [
    "CCTV_全部.m3u",
    "电影_全部.m3u",
    "电视剧_全部.m3u",
    "CCTV.m3u",
    "CCTV-1 综合.m3u",
    "CCTV-6 电影.m3u",
    "CCTV-8 电视剧.m3u",
    "电影.m3u",
    "恐怖电影.m3u",
    "惊悚电影.m3u",
    "功夫电影.m3u",
    "香港电影.m3u",
    "电视剧.m3u",
    "经典电视剧.m3u",
    "经典电影.m3u",
    "其他.m3u",
]


def raw_url(filename: str) -> str:
    # Keep "/" unescaped, but URL-encode Chinese, spaces, etc.
    return f"{RAW_BASE}/output/final/{quote(filename, safe='')}"


def display_name(filename: str) -> str:
    return Path(filename).stem


def main() -> None:
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    files = sorted(
        p.name
        for p in FINAL_DIR.glob("*.m3u")
        if p.is_file()
    )

    if not files:
        raise SystemExit("ERROR: no M3U files found in output/final")

    preferred = [x for x in PREFERRED if x in files]
    remaining = [x for x in files if x not in preferred]

    combined = [x for x in preferred if x.endswith("_全部.m3u")]
    categories = [
        x for x in preferred
        if not x.endswith("_全部.m3u")
    ]

    lines = [
        "# IPTV 播放器订阅地址",
        "",
        "> 电视播放器请添加下面的 `.m3u` Raw 地址。",
        "> 地址固定指向 GitHub `main` 分支，Actions 更新后播放器刷新即可获取新内容。",
        "",
        "## ⭐ 主订阅",
        "",
        f"```text",
        f"{RAW_BASE}/output/movies_tv_final.m3u",
        "```",
        "",
        "## 📺 常用组合订阅",
        "",
        "| 名称 | M3U 地址 |",
        "|---|---|",
    ]

    for filename in combined:
        lines.append(
            f"| {display_name(filename)} | {raw_url(filename)} |"
        )

    lines += [
        "",
        "## 📂 分类订阅",
        "",
        "| 分类 | M3U 地址 |",
        "|---|---|",
    ]

    for filename in categories:
        lines.append(
            f"| {display_name(filename)} | {raw_url(filename)} |"
        )

    if remaining:
        lines += [
            "",
            "## 🎬 其他自动生成订阅",
            "",
            "| 名称 | M3U 地址 |",
            "|---|---|",
        ]
        for filename in remaining:
            lines.append(
                f"| {display_name(filename)} | {raw_url(filename)} |"
            )

    lines += [
        "",
        "## 📺 使用方法",
        "",
        "1. 复制某个 `.m3u` Raw 地址。",
        "2. 在电视 IPTV 播放器中选择「网络订阅 / M3U URL / 播放列表 URL」。",
        "3. 粘贴地址并保存。",
        "4. 后续 GitHub Actions 更新文件后，刷新订阅即可。",
        "",
        "## ⚠️ 说明",
        "",
        "- `PLAYLISTS.md` 只是订阅地址说明页，不是 M3U 播放列表。",
        "- 主订阅 `movies_tv_final.m3u` 是当前完整播放列表。",
        "- 分类文件来自 `scripts/movie_organizer_v6.py` 的实际输出。",
    ]

    INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Generated: {INDEX_FILE}")
    print(f"M3U files: {len(files)}")


if __name__ == "__main__":
    main()
