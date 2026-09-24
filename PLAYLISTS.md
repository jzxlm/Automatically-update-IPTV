# IPTV 播放器订阅地址

> **电视播放器请使用下面的 `.m3u` Raw 地址。**
>
> GitHub Raw 地址会随着 `main` 分支更新而自动更新，不需要重新下载文件。

## ⭐ 主订阅

```text
https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/movies_tv_final.m3u
```

## 📺 常用组合订阅

| 名称 | M3U 地址 |
|---|---|
| CCTV 全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/CCTV_%E5%85%A8%E9%83%A8.m3u |
| 电影全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E5%BD%B1_%E5%85%A8%E9%83%A8.m3u |
| 电视剧全部 | https://raw.githubusercontent.com/jzxlm/Automatically-update-IPTV/main/output/final/%E7%94%B5%E8%A7%86%E5%89%A7_%E5%85%A8%E9%83%A8.m3u |

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

## 🧪 电视测试建议

第一次建议先添加 **主订阅**。

如果电视播放器加载太慢，再分别测试：

1. CCTV 全部
2. 电影全部
3. 电视剧全部
4. 恐怖电影
5. 香港电影

如果某一分类在电视上大量打不开，可以单独针对该分类做下一版筛选。

## 🔄 更新方式

以上地址全部指向 GitHub `main` 分支。

GitHub Actions 每次成功更新后，地址本身不变，播放器下次刷新订阅时即可获取最新内容。

**无需重新下载 M3U。**
