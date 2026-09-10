# YouTube手游频道RSS采集（GitHub Actions版）

## 用途
海外手游新游测试/公测/首发视频信号采集。利用GitHub Actions海外环境访问YouTube官方RSS，绕过国内网络限制。

## 部署步骤

### 1. 创建GitHub仓库
新建一个公开或私有仓库（比如 `youtube-rss-scraper`），把本目录下所有文件放进去。

文件结构：
```
youtube-rss-scraper/
├── youtube_rss_scraper.py     # 主脚本
├── .github/
│   └── workflows/
│       └── scraper.yml        # Actions定时任务配置
├── README.md
└── output/                    # 运行结果（自动生成，commit回仓库）
    ├── youtube_rss_YYYYMMDD.json
    ├── youtube_rss_YYYYMMDD.md
    ├── youtube_rss_latest.json
    └── youtube_rss_latest.md
```

### 2. 启用Actions
仓库创建后，默认Actions就是开启的。第一次推送文件后会自动识别 `.github/workflows/scraper.yml`。

### 3. 手动触发测试
- 进入仓库 → Actions → 左侧选 "YouTube RSS Scraper" → 点 "Run workflow"
- 跑完后检查 output/ 目录有没有新生成的文件

### 4. 定时规则
默认：**每周四 18:00 UTC**（北京时间周五凌晨2点）跑一次。
如果需要改频率，修改 `.github/workflows/scraper.yml` 里的 cron 表达式。

## 结果使用

### 方式A：直接从GitHub仓库拉取
`output/youtube_rss_latest.json` 始终是最新一份，周报脚本可以直接 curl 拉取。

公开仓库的话，raw链接格式：
```
https://raw.githubusercontent.com/{用户名}/{仓库名}/main/output/youtube_rss_latest.json
```

私有仓库的话需要加token，或者用方式B。

### 方式B：webhook推送（可选进阶）
如果需要结果推回飞书/本地，可以在脚本末尾加webhook调用，或者用Actions的repository_dispatch事件。

## 频道列表

当前配置10个频道，分4类：

| 频道 | 地区 | 分类 | 定位 |
|---|---|---|---|
| Beta Games Revolution Mobile | 全球 | CBT测试 | Beta封闭测试录播，生存/开放世界/SLG |
| TheMobileGamerHD | 全球 | CBT+首发 | 老牌综合频道，CBT+上线双覆盖 |
| Sameway | 韩国 | CBT测试 | 韩语主播，国产出海二游韩服首测 |
| Only4GamersXyz | 全球 | 测试版试玩 | 安卓测试版APK试玩，策略/RPG |
| Maximumandroid | 全球 | 全球首发 | 上线首日实机，全品类 |
| NewMobileGames | 全球 | 全球首发 | 新上线手游，首发开荒 |
| MobileGamesDaily | 全球 | 全球首发 | 厂商提前送测，First Look |
| Pocket Gamer | 英国 | 专业媒体 | 手游专业媒体，新游评测+行业资讯 |
| Techzamazing | 全球 | 新游评测 | 手游新游评测推荐 |
| Yomi_Vtuber | 日本 | 日系二游测试 | 日本Vtuber，国产手游海外首测 |

## 输出格式

JSON格式与现有 `overseas_media_*.json` 基本同构，便于周报复用：

```json
{
  "meta": {
    "generated_at": "2026-09-10T...",
    "channels_total": 10,
    "channels_ok": 9,
    "total_kept_videos": 47
  },
  "channels": [
    {
      "name": "TheMobileGamerHD",
      "category": "CBT测试+首发",
      "status": "ok",
      "items": [
        {
          "title": "...",
          "link": "https://www.youtube.com/watch?v=xxx",
          "pub_iso": "...",
          "signal_hits": ["beta", "strategy"],
          "summary": "..."
        }
      ]
    }
  ]
}
```

## 维护

- **加频道**：在 `youtube_rss_scraper.py` 的 `CHANNELS` 列表里追加即可，需要 channel_id（UC开头的ID）
- **改信号词**：修改 `SIGNAL_KW` 列表
- **调时间窗口**：修改 `DAYS_WINDOW`（默认14天）
