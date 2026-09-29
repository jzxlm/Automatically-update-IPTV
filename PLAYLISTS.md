# IPTV 播放器订阅地址

> V7：以真实/原始频道名称和现有元数据为基础整理；不猜节目名，不生成虚假 EPG。

## ⭐ 主订阅

```text
https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/movies_tv_final.m3u
```

## 📺 分类订阅

| 分类 | M3U 地址 |
|---|---|
| 央视 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E5%A4%AE%E8%A7%86.m3u |
| 4K影视 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/4K%E5%BD%B1%E8%A7%86.m3u |
| 港澳 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E6%B8%AF%E6%BE%B3.m3u |
| 国际 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E5%9B%BD%E9%99%85.m3u |
| 轮播1 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E8%BD%AE%E6%92%AD1.m3u |
| 轮播2 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E8%BD%AE%E6%92%AD2.m3u |
| 轮播3 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E8%BD%AE%E6%92%AD3.m3u |
| 无奇不有 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E6%97%A0%E5%A5%87%E4%B8%8D%E6%9C%89.m3u |
| 经典电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%BB%8F%E5%85%B8%E7%94%B5%E5%BD%B1.m3u |
| 恐怖电影 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E6%81%90%E6%80%96%E7%94%B5%E5%BD%B1.m3u |
| 其他 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E5%85%B6%E4%BB%96.m3u |

## 🔗 组合订阅

| 名称 | M3U 地址 |
|---|---|
| 央视_全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E5%A4%AE%E8%A7%86_%E5%85%A8%E9%83%A8.m3u |
| 电影_全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E5%BD%B1_%E5%85%A8%E9%83%A8.m3u |
| 电视剧_全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E8%A7%86%E5%89%A7_%E5%85%A8%E9%83%A8.m3u |

## 使用

1. 复制 `.m3u` Raw 地址。
2. 在电视播放器选择网络订阅 / M3U URL。
3. 粘贴并保存。
4. GitHub Actions 更新后刷新订阅。

## EPG

当前只保留源本身提供的 `tvg-id`；没有可靠映射就不强行生成节目单。
