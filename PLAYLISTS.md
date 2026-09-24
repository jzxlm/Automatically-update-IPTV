# IPTV 播放器订阅地址

> 电视播放器请添加下面的 `.m3u` Raw 地址。
> 地址固定指向 GitHub `main` 分支，Actions 更新后播放器刷新即可获取新内容。

## ⭐ 主订阅

```text
https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/movies_tv_final.m3u
```

## 📺 常用组合订阅

| 名称 | M3U 地址 |
|---|---|
| CCTV_全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV_%E5%85%A8%E9%83%A8.m3u |
| 电影_全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E5%BD%B1_%E5%85%A8%E9%83%A8.m3u |
| 电视剧_全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E8%A7%86%E5%89%A7_%E5%85%A8%E9%83%A8.m3u |

## 📂 分类订阅

| 分类 | M3U 地址 |
|---|---|
| CCTV | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV.m3u |
| CCTV-1 综合 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV-1%20%E7%BB%BC%E5%90%88.m3u |
| CCTV-6 电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV-6%20%E7%94%B5%E5%BD%B1.m3u |
| CCTV-8 电视剧 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV-8%20%E7%94%B5%E8%A7%86%E5%89%A7.m3u |
| 电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E5%BD%B1.m3u |
| 恐怖电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E6%81%90%E6%80%96%E7%94%B5%E5%BD%B1.m3u |
| 惊悚电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E6%83%8A%E6%82%9A%E7%94%B5%E5%BD%B1.m3u |
| 功夫电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E5%8A%9F%E5%A4%AB%E7%94%B5%E5%BD%B1.m3u |
| 香港电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E9%A6%99%E6%B8%AF%E7%94%B5%E5%BD%B1.m3u |
| 电视剧 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E8%A7%86%E5%89%A7.m3u |
| 其他 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E5%85%B6%E4%BB%96.m3u |

## 📺 使用方法

1. 复制某个 `.m3u` Raw 地址。
2. 在电视 IPTV 播放器中选择「网络订阅 / M3U URL / 播放列表 URL」。
3. 粘贴地址并保存。
4. 后续 GitHub Actions 更新文件后，刷新订阅即可。

## ⚠️ 说明

- `PLAYLISTS.md` 只是订阅地址说明页，不是 M3U 播放列表。
- 主订阅 `movies_tv_final.m3u` 是当前完整播放列表。
- 分类文件来自 `scripts/movie_organizer_v6.py` 的实际输出。
