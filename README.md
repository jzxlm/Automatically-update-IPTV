# Automatically-update-IPTV

一个面向电视 IPTV 播放器的 M3U 整理项目。

## 订阅

主订阅：

```text
https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/movies_tv_final.m3u
```

分类订阅地址见 `PLAYLISTS.md`。

## V7 整理原则

- 优先使用原始频道名称、`tvg-id` 和来源元数据。
- CCTV 使用明确的频道 ID/名称标准化，不再把 `CCTV10` 错分成 `CCTV-1`。
- 未确认身份的频道保留原名并归入 `其他`，不凭 URL 猜节目名称。
- 不生成虚假的 EPG；没有可靠 `tvg-id` 映射就不强行添加节目单。
- URL 去重。
- 不使用 FFprobe、视频画面识别或 AI。

## 自动更新

GitHub Actions 每天自动运行，也支持手动运行：

1. 整理源数据
2. 生成主 M3U
3. 生成分类 M3U
4. 生成订阅地址索引
5. 校验并自动提交变化

> 当前仓库使用已有的 `data/movie_tv_v59_result.json` 作为源数据快照。V7 首先解决电视端的频道名称、分类和播放列表结构；后续根据电视实测结果继续筛选源。

## 测试反馈

电视端重点反馈三类问题：

- 能播 / 不能播
- 频道名称或分类错误
- EPG 是否匹配

不要为了追求源数量保留明显错误的频道。
