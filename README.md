# V6.1 GitHub 自动发布

V6.1 在 V6.0 的基础上增加 GitHub Actions 自动发布与结果校验。

## 自动执行

每天 02:30 UTC，即中国/日本标准时间 10:30。

同时保留 GitHub Actions 的 Run workflow 手动运行入口。

## 每次运行

1. 检查 data/movie_tv_v59_result.json
2. 执行 scripts/movie_organizer_v6.py
3. 生成最终 M3U
4. 检查主 M3U 和 #EXTM3U
5. 检查播放列表是否仍然包含 750 条 EXTINF
6. 输出最终分类统计
7. 只有生成文件发生变化时才 commit + push

V6.1 不会重新测速、运行 FFprobe、视频分析，也不会绕过 Tonkiang/Cloudflare。
