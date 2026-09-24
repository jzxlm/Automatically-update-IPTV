# Automatically-update-IPTV

自动整理并发布 IPTV M3U 播放列表。

## 📺 电视 / IPTV 播放器订阅入口

### 主订阅（推荐）

把下面地址直接复制到电视 IPTV 播放器的 **M3U / 网络订阅 / 播放列表 URL**：

```text
https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/movies_tv_final.m3u
```

这个地址始终指向 `main` 分支最新版本。GitHub 的 Raw 文件会直接提供文件内容，适合播放器读取。 

### 分类订阅

完整分类入口：

```text
https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/PLAYLISTS.md
```

分类 M3U 地址见 [`PLAYLISTS.md`](PLAYLISTS.md)。

常用分类：

| 分类 | M3U 订阅地址 |
|---|---|
| CCTV 全部 | `https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV_%E5%85%A8%E9%83%A8.m3u` |
| 电影全部 | `https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E5%BD%B1_%E5%85%A8%E9%83%A8.m3u` |
| 电视剧全部 | `https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E8%A7%86%E5%89%A7_%E5%85%A8%E9%83%A8.m3u` |

> 注意：`PLAYLISTS.md` 是说明/入口页面，不是给播放器直接添加的 M3U。电视播放器请添加具体的 `.m3u` Raw 地址。

## 🔄 自动更新

GitHub Actions 每天自动整理播放列表；也可以在 Actions 页面手动运行。

当前流程：

1. 读取已有可用源
2. 去重
3. 按 CCTV / 电影 / 电视剧等分类
4. 生成主 M3U 和分类 M3U
5. 自动生成订阅地址入口
6. 校验主 M3U
7. 有变化才自动提交

不会在 Actions 中重新进行 FFprobe、视频画面分析或 AI 分析。

## 📁 主要文件

- `output/movies_tv_final.m3u` — 750 源主订阅
- `output/final/` — 分类 M3U
- `PLAYLISTS.md` — 播放器订阅地址总入口
- `scripts/movie_organizer_v6.py` — M3U 整理器
- `scripts/generate_playlist_index.py` — 自动生成分类订阅入口
- `.github/workflows/publish-iptv.yml` — GitHub Actions 自动发布
