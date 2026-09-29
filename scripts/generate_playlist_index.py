from pathlib import Path
from urllib.parse import quote

BASE = "https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main"
ROOT = Path(__file__).resolve().parent.parent
FINAL = ROOT / "output" / "final"
OUT = ROOT / "PLAYLISTS.md"
ORDER = ["央视", "卫视", "4K影视", "港澳", "台湾省", "国际", "轮播1", "轮播2", "轮播3", "无奇不有", "经典电影", "恐怖电影", "其他"]

def url(name):
    return f"{BASE}/output/final/{quote(name, safe='')}"

def main():
    files = {p.name for p in FINAL.glob('*.m3u')}
    lines = [
        "# IPTV 播放器订阅地址", "",
        "> V7：以真实/原始频道名称和现有元数据为基础整理；不猜节目名，不生成虚假 EPG。", "",
        "## ⭐ 主订阅", "", "```text",
        f"{BASE}/output/movies_tv_final.m3u", "```", "",
        "## 📺 分类订阅", "", "| 分类 | M3U 地址 |", "|---|---|",
    ]
    for c in ORDER:
        fn = f"{c}.m3u"
        if fn in files:
            lines.append(f"| {c} | {url(fn)} |")
    lines += ["", "## 🔗 组合订阅", "", "| 名称 | M3U 地址 |", "|---|---|"]
    for fn in ["央视_全部.m3u", "电影_全部.m3u", "电视剧_全部.m3u"]:
        if fn in files:
            lines.append(f"| {Path(fn).stem} | {url(fn)} |")
    lines += ["", "## 使用", "", "1. 复制 `.m3u` Raw 地址。", "2. 在电视播放器选择网络订阅 / M3U URL。", "3. 粘贴并保存。", "4. GitHub Actions 更新后刷新订阅。", "", "## EPG", "", "当前只保留源本身提供的 `tvg-id`；没有可靠映射就不强行生成节目单。"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == '__main__':
    main()
