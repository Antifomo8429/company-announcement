import requests
import feedparser
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
KEYWORDS = ["發行", "現金增資", "買回庫藏股", "公司債"]
SENT_IDS_FILE = "sent_ids.json"
RSS_URL = "https://mops.twse.com.tw/mops/rss/t05sr01_1"


def load_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(list(sent_ids), f)


def fetch_rss_news():
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(RSS_URL, headers=headers, timeout=15)
    res.encoding = "utf-8"
    feed = feedparser.parse(res.content)

    results = []
    for entry in feed.entries:
        results.append({
            "id": entry.get("id", entry.get("link", "")),
            "主旨": entry.get("title", ""),
            "連結": entry.get("link", ""),
            "時間": entry.get("published", ""),
            "內容": entry.get("summary", ""),
        })

    print(f"RSS 共 {len(results)} 則")
    return results


def filter_by_keywords(news_list, keywords):
    matched = []
    for item in news_list:
        for kw in keywords:
            if kw in item["主旨"] or kw in item["內容"]:
                item["命中關鍵字"] = kw
                matched.append(item)
                break
    return matched


def send_discord(item):
    embed = {
        "embeds": [{
            "title": f"【{item['命中關鍵字']}】{item['主旨']}",
            "url": item["連結"] or None,
            "color": 0x0099ff,
            "footer": {"text": f"公告時間：{item['時間']}"},
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)
    time.sleep(0.5)


def send_discord_summary(total, matched, new_count):
    now = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y/%m/%d %H:%M")
    if new_count > 0:
        color = 0x00cc44
        status = f"發現 {new_count} 則新重訊，已推送通知 ✅"
    else:
        color = 0x888888
        status = "無新命中重訊"

    embed = {
        "embeds": [{
            "title": f"📋 MOPS 監控摘要｜{now}",
            "color": color,
            "fields": [
                {"name": "RSS 總則數", "value": str(total), "inline": True},
                {"name": "命中關鍵字", "value": str(matched), "inline": True},
                {"name": "本次新推送", "value": str(new_count), "inline": True},
                {"name": "狀態", "value": status, "inline": False},
                {"name": "監控關鍵字", "value": "、".join(KEYWORDS), "inline": False},
            ],
            "footer": {"text": f"執行時間：{now}"},
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)


def run():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 開始執行")

    sent_ids = load_sent_ids()
    news = fetch_rss_news()
    matched = filter_by_keywords(news, KEYWORDS)
    print(f"命中關鍵字：{len(matched)} 則")

    new_items = []
    for item in matched:
        uid = item["id"]
        if uid not in sent_ids:
            new_items.append(item)
            sent_ids.add(uid)

    print(f"新增（未發送過）：{len(new_items)} 則")

    for item in new_items:
        send_discord(item)
        print(f"  ✅ 已發送：{item['主旨'][:40]}")

    save_sent_ids(sent_ids)
    send_discord_summary(len(news), len(matched), len(new_items))
    print("完成")


if __name__ == "__main__":
    run()
