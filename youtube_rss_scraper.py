#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YouTube手游频道 RSS 采集脚本（GitHub Actions海外环境运行）
用途：补海外手游新游测试/公测/首发视频信号，从YouTube频道官方RSS提取视频标题和简介
数据源：YouTube各频道官方 feeds/videos.xml（需海外网络环境访问）
产出：
  youtube_rss_YYYYMMDD.json  结构化快照（与 overseas_media_*.json 同构，便于周报复用）
  youtube_rss_YYYYMMDD.md    可读汇总（按频道分组，信号词标注）
信号逻辑：标题/简介命中新游测试/上线相关关键词 → 标 🔥，辅助周报快速定位
"""
import json
import os
import sys
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

OUT_DIR = os.environ.get("OUTPUT_DIR", os.path.dirname(os.path.abspath(__file__)))

# ============ 频道配置 ============
# id: YouTube channel_id（UC开头），name/display: 展示名，category: 分类
# 说明：这些频道主要做海外手游新游测试/CBT/首发实机，对应国内"公众号自媒体"定位
CHANNELS = [
    # ===== CBT / 测试服 / 早期测试类 =====
    {
        "id": "UCfKqMs1pvtASaunLYeAvtbQ",
        "name": "Beta Games Revolution Mobile",
        "handle": "@BetaGamesMobile",
        "region": "全球",
        "category": "CBT测试",
        "focus": "手游Beta封闭测试录播，生存/开放世界/SLG/ARPG，NDA解禁后首测一手画面",
    },
    {
        "id": "UCBRRJOzY5mtgTWmwoDVFHIg",
        "name": "TheMobileGamerHD",
        "handle": "@TheMobileGamerHD",
        "region": "全球",
        "category": "CBT测试+首发",
        "focus": "老牌综合手游频道，CBT首测+全球上线首发实况双覆盖，SLG/开放世界/二游素材量大",
    },
    {
        "id": "UC7SIaeUWuuIrWTIOBpayDVQ",
        "name": "Sameway",
        "handle": "@sameway",
        "region": "韩国",
        "category": "CBT测试",
        "focus": "韩语主播，国产出海二游/开放世界海外CBT核心频道，韩服首测独家实机多",
    },
    # MOBO GAME ZONE (@mobogamezone629) - channel_id 待补
    {
        "id": "UCfTBJHPAhpsHyvilX8MWzgQ",
        "name": "Only4GamersXyz",
        "handle": "@Only4GamersXyz",
        "region": "全球",
        "category": "测试版试玩",
        "focus": "偏安卓手游，大量测试版APK试玩，策略/RPG/足球手游，附官网 only4gamers.xyz",
    },

    # ===== 新游上线 / 全球首发类 =====
    {
        "id": "UChJWfOP9b-0UclIynsUuNUA",
        "name": "Maximumandroid",
        "handle": "@Maximumandroid",
        "region": "全球",
        "category": "全球首发",
        "focus": "游戏上线第一时间录实机，覆盖全品类，上线首日素材多，适合看正式版完整玩法",
    },
    {
        "id": "UCBcfEifmET-HYuu8audsPuQ",
        "name": "NewMobileGames",
        "handle": "@NewMobileGames9",
        "region": "全球",
        "category": "全球首发",
        "focus": "专门展示新上线手游，首发开荒实机，偏轻量化新游，海外独立手游/轻度策略上线素材",
    },
    {
        "id": "UC7tDN9kJtfQjOxekZwWyFVw",
        "name": "MobileGamesDaily",
        "handle": "@MobileGamesDaily",
        "region": "全球",
        "category": "全球首发",
        "focus": "厂商提前寄送测试包/上线版本，第一时间First Look，剪辑干净，官方合作向实机演示",
    },

    # ===== 专业媒体 / 评测类 =====
    {
        "id": "UCTjH1fZ1-vM8-0t3H8YqYtQ",
        "name": "Pocket Gamer",
        "handle": "@PocketGamerVideo",
        "region": "英国",
        "category": "专业媒体",
        "focus": "手游专业媒体，新游评测+行业资讯，最像国内\"金角游戏\"定位",
    },
    {
        "id": "UCyo4ROy9-8ymQTBWcPA5Fjg",
        "name": "Techzamazing",
        "handle": "@Techzamazing",
        "region": "全球",
        "category": "新游评测",
        "focus": "手游新游评测/推荐，覆盖面广，更新频率高",
    },

    # ===== 日系 / 二游出海类 =====
    {
        "id": "UCW7htl9_IlxgjrXkn4Vu33w",
        "name": "Yomi_Vtuber",
        "handle": "@Yomi_Vtuber",
        "region": "日本",
        "category": "日系二游测试",
        "focus": "日本Vtuber，国产开放世界手游海外首测试玩，日系视角评测",
    },
]

# 信号词：命中标题/描述的视频在 md 里标 🔥
SIGNAL_KW = [
    # 测试相关
    "beta", "cbt", "closed beta", "open beta", "early access",
    "test server", "test", "alpha", "alpha test",
    "soft launch", "soft-launch", "pre-registration", "preregister",
    # 上线相关
    "launch", "launches", "release", "releases", "out now",
    "global", "worldwide", "now available", "is out",
    "first look", "first gameplay", "gameplay",
    # 产品信号
    "new game", "new games", "upcoming", "coming soon",
    "downloads", "million", "top", "grossing",
    # 品类关键词（SLG/策略相关重点）
    "strategy", "slg", "survival", "open world", "mmorpg",
    "idle", "rpg", "4x", "simulation", "tower defense",
]

DAYS_WINDOW = 14   # 保留最近14天视频
STALE_DAYS = 10    # 最新视频早于10天前 = 频道疑似停更


def strip_html(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_feed(channel_id):
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; YouTube-RSS-Scraper/1.0)",
        "Accept": "application/atom+xml,application/xml,text/xml,*/*",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_entries(xml_text):
    """解析 YouTube Atom feed（<entry> 标签）"""
    ns = {"atom": "http://www.w3.org/2005/Atom",
          "yt": "http://www.youtube.com/xml/schemas/2015",
          "media": "http://search.yahoo.com/mrss/"}

    root = ET.fromstring(xml_text)
    entries = []

    for entry in root.findall("atom:entry", ns):
        # 标题
        title_el = entry.find("atom:title", ns)
        title = (title_el.text or "").strip() if title_el is not None else ""

        # 视频链接
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href", "") if link_el is not None else ""

        # 发布时间
        pub_el = entry.find("atom:published", ns)
        pub_str = pub_el.text.strip() if pub_el is not None and pub_el.text else ""

        # 视频ID
        vid_el = entry.find("yt:videoId", ns)
        video_id = vid_el.text.strip() if vid_el is not None and vid_el.text else ""

        # 频道名
        name_el = entry.find("atom:author/atom:name", ns)
        author = name_el.text.strip() if name_el is not None and name_el.text else ""

        # 描述（从 media:group/media:description 取）
        desc_el = entry.find("media:group/media:description", ns)
        description = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

        # 缩略图
        thumb_el = entry.find("media:group/media:thumbnail", ns)
        thumbnail = thumb_el.get("url", "") if thumb_el is not None else ""

        # 分类/标签
        categories = []
        for cat in entry.findall("media:group/media:category", ns):
            if cat.text and cat.text.strip():
                categories.append(cat.text.strip())

        # 解析时间
        try:
            dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            dt = None

        # 信号词命中
        plain = strip_html(description)
        low = (title + " " + plain).lower()
        hits = [kw for kw in SIGNAL_KW if kw in low]

        entries.append({
            "title": html.unescape(title),
            "link": link if link else f"https://www.youtube.com/watch?v={video_id}",
            "video_id": video_id,
            "thumbnail": thumbnail,
            "pub_date_raw": pub_str,
            "pub_iso": dt.isoformat() if dt else "",
            "pub_ts": dt.timestamp() if dt else 0,
            "categories": categories,
            "author": author,
            "summary": plain[:600],
            "signal_hits": hits,
        })

    return entries


def main():
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    cutoff = now - timedelta(days=DAYS_WINDOW)

    os.makedirs(OUT_DIR, exist_ok=True)

    sources_out, md_lines = [], []
    md_lines.append(f"# YouTube手游频道 RSS 采集（{now.strftime('%Y-%m-%d')}）\n")
    md_lines.append(f"窗口：最近 {DAYS_WINDOW} 天（cutoff {cutoff.strftime('%Y-%m-%d')} UTC）｜"
                    f"频道数 {len(CHANNELS)}｜脚本 youtube_rss_scraper.py\n")

    total_kept = 0
    for ch in CHANNELS:
        src = {
            "name": ch["name"],
            "handle": ch["handle"],
            "channel_id": ch["id"],
            "region": ch["region"],
            "category": ch["category"],
            "url": f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['id']}",
            "channel_url": f"https://www.youtube.com/channel/{ch['id']}",
            "focus": ch["focus"],
            "fetched_at": now.isoformat(),
            "status": "ok",
            "error": "",
            "total_in_feed": 0,
            "kept": 0,
            "latest_pub": "",
            "stale": False,
            "items": [],
        }
        md_lines.append(f"\n## {ch['name']}（{ch['region']} · {ch['category']}）")
        md_lines.append(f"> {ch['focus']}  \n> 频道: {ch['handle']} | feed: {src['url']}\n")

        try:
            xml_text = fetch_feed(ch["id"])
            items = parse_entries(xml_text)
            src["total_in_feed"] = len(items)

            recent = [x for x in items if x["pub_ts"] and
                      datetime.fromtimestamp(x["pub_ts"], tz=timezone.utc) >= cutoff]
            recent.sort(key=lambda x: x["pub_ts"], reverse=True)
            src["items"] = recent
            src["kept"] = len(recent)
            total_kept += len(recent)

            if recent:
                latest = datetime.fromtimestamp(recent[0]["pub_ts"], tz=timezone.utc)
                src["latest_pub"] = latest.isoformat()
                age_days = (now - latest).days
                src["stale"] = age_days > STALE_DAYS
                if src["stale"]:
                    md_lines.append(f"⚠️ **STALE：最新视频 {latest.strftime('%Y-%m-%d')}，"
                                    f"已 {age_days} 天未更新，疑似停更/频道活跃度下降**\n")
                md_lines.append(f"最新视频：{latest.strftime('%Y-%m-%d')}｜窗口内 {len(recent)} 个\n")
            else:
                src["stale"] = True
                md_lines.append("⚠️ **窗口内0条（feed可拉但近期无新视频）**\n")

            for x in recent:
                flag = "🔥 " if x["signal_hits"] else "   "
                d = datetime.fromtimestamp(x["pub_ts"], tz=timezone.utc).strftime("%m-%d")
                cats = f" [{', '.join(x['categories'][:3])}]" if x["categories"] else ""
                md_lines.append(f"- {flag}{d} **{x['title']}**{cats}")
                md_lines.append(f"  {x['link']}")
                if x["signal_hits"]:
                    md_lines.append(f"  信号词: {', '.join(sorted(set(x['signal_hits']))[:8])}")
                if x["summary"]:
                    md_lines.append(f"  > {x['summary'][:280]}")

        except Exception as e:
            src["status"] = "fail"
            src["error"] = f"{type(e).__name__}: {e}"
            md_lines.append(f"❌ **抓取失败：{src['error']}**\n")

        sources_out.append(src)

    snapshot = {
        "meta": {
            "script": "youtube_rss_scraper.py",
            "version": "v1.0",
            "generated_at": now.isoformat(),
            "days_window": DAYS_WINDOW,
            "channels_total": len(CHANNELS),
            "channels_ok": sum(1 for s in sources_out if s["status"] == "ok"),
            "channels_fail": sum(1 for s in sources_out if s["status"] != "ok"),
            "channels_stale": sum(1 for s in sources_out if s["stale"]),
            "total_kept_videos": total_kept,
        },
        "channels": sources_out,
    }

    json_path = os.path.join(OUT_DIR, f"youtube_rss_{date_str}.json")
    md_path = os.path.join(OUT_DIR, f"youtube_rss_{date_str}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # 控制台输出（GitHub Actions日志可见）
    print(f"[OK] 频道 {snapshot['meta']['channels_ok']}/{len(CHANNELS)} 正常，"
          f"{snapshot['meta']['channels_fail']} 失败，{snapshot['meta']['channels_stale']} 疑似停更，"
          f"窗口内共 {total_kept} 个视频")
    for s in sources_out:
        mark = {"ok": "✅", "fail": "❌"}.get(s["status"], "⚠️")
        extra = f" STALE" if s["stale"] else ""
        print(f"  {mark} {s['name']}({s['region']}): kept={s['kept']}/{s['total_in_feed']}{extra}"
              + (f" err={s['error'][:60]}" if s["error"] else ""))
    print(f"产出: {json_path}")
    print(f"产出: {md_path}")

    # 也保存一份 latest 别名，方便外部拉取最新结果
    latest_json = os.path.join(OUT_DIR, "youtube_rss_latest.json")
    latest_md = os.path.join(OUT_DIR, "youtube_rss_latest.md")
    with open(latest_json, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    with open(latest_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"latest 别名: {latest_json}")


if __name__ == "__main__":
    main()
