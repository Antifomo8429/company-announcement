import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from playwright.sync_api import sync_playwright
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
KEYWORDS = ["發行", "現金增資", "買回庫藏股", "公司債"]
SENT_IDS_FILE = "sent_ids.json"


def load_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(list(sent_ids), f)


def fetch_news():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://mops.twse.com.tw/mops/#/web/t05sr01_1", wait_until="networkidle", timeout=30000)
        page.wait_for_selector("table tr", timeout=15000)
        rows = page.query_selector_all("table tr")
        for row in rows[1:]:
            cols = row.query_selector_all("td")
            if len(cols) < 4:
                continue
            link = row.query_selector("a")
            results.append({
                "代號": cols[0].inner_text().strip(),
                "公司": cols[1].inner_text().strip(),
                "時間": cols[2].inner_text().strip(),
                "主旨": cols[3].inner_text().strip(),
                "連結": "https://mops.twse.com.tw" + link.get_attribute("href") if link else "",
            })
        browser.close()
    print(f"抓到 {len(results)} 則重訊")
    return results


def filter_by_keywords(news_list):
    matched = []
    for item in news_list:
        for kw in KEYWORDS:
            if kw in item["主旨"]:
                item["命中關鍵字"] = kw
                matched.append(item)
                break
    return matched


def make_unique_id(item):
    return f"{item['時間']}_{item['代號']}_{item['主旨'][:20]}"


def send_discord(item):
    embed = {
        "embeds": [{
            "title": f"【{item['命中關鍵字']}】{item['公司']}（{item['代號']}）",
            "description": item["主旨"],
            "url": item["連結"] or None,
            "color": 0x0099ff,
            "footer": {"text": f"公告時間：{item['時間']}"},
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)
    time.sleep(0.5)


def send_discord_summary(total, matched, new_count):
    now = datetime.now(ZoneInfo("Asia/Taipei")).strftime("%Y/%m/%d %H:%M")
    color = 0x00cc44 if new_count > 0 else 0x888888
    status = f"發現 {new_count} 則新重訊 ✅" if new_count > 0 else "無新命中重訊"
    embed = {
        "embeds": [{
            "title": f"📋 MOPS 監控摘要｜{now}",
            "color": color,
            "fields": [
                {"name": "今日重訊總數", "value": str(total), "inline": True},
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
    news = fetch_news()
    matched = filter_by_keywords(news)
    print(f"命中關鍵字：{len(matched)} 則")
    new_items = []
    for item in matched:
        uid = make_unique_id(item)
        if uid not in sent_ids:
            new_items.append(item)
            sent_ids.add(uid)
    print(f"新增（未發送過）：{len(new_items)} 則")
    for item in new_items:
        send_discord(item)
        print(f"  ✅ 已發送：{item['公司']} - {item['主旨'][:30]}")
    save_sent_ids(sent_ids)
    send_discord_summary(len(news), len(matched), len(new_items))
    print("完成")


if __name__ == "__main__":
    run()
