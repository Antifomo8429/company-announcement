import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
KEYWORDS = ["發行", "現金增資", "買回庫藏股", "公司債"]
SENT_IDS_FILE = "sent_ids.json"


def get_today_roc_date():
    now = datetime.now()
    roc_year = now.year - 1911
    return f"{roc_year}{now.month:02d}{now.day:02d}"


def load_sent_ids():
    if os.path.exists(SENT_IDS_FILE):
        with open(SENT_IDS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_sent_ids(sent_ids):
    with open(SENT_IDS_FILE, "w") as f:
        json.dump(list(sent_ids), f)


def make_unique_id(item):
    return f"{item['時間']}_{item['代號']}_{item['主旨'][:20]}"


def fetch_today_all_news(date):
    url = "https://mops.twse.com.tw/mops/web/ajax_t05st02"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://mops.twse.com.tw/mops/web/t05st02",
    }
    data = {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "queryDate": date,
    }
    res = requests.post(url, headers=headers, data=data, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    results = []
    for row in soup.select("table tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        link_tag = row.find("a")
        results.append({
            "時間": cols[0].text.strip(),
            "代號": cols[1].text.strip(),
            "公司": cols[2].text.strip(),
            "主旨": cols[3].text.strip(),
            "連結": "https://mops.twse.com.tw" + link_tag["href"] if link_tag else "",
        })
    return results


def filter_by_keywords(news_list, keywords):
    matched = []
    for item in news_list:
        for kw in keywords:
            if kw in item["主旨"]:
                item["命中關鍵字"] = kw
                matched.append(item)
                break
    return matched


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


def send_discord_summary(date, total, matched, new_count):
    if new_count > 0:
        color = 0x00cc44
        status = f"發現 {new_count} 則新重訊，已推送通知 ✅"
    else:
        color = 0x888888
        status = "無新命中重訊"

    embed = {
        "embeds": [{
            "title": f"📋 MOPS 監控摘要｜{date}",
            "color": color,
            "fields": [
                {"name": "今日重訊總數", "value": str(total), "inline": True},
                {"name": "命中關鍵字", "value": str(matched), "inline": True},
                {"name": "本次新推送", "value": str(new_count), "inline": True},
                {"name": "狀態", "value": status, "inline": False},
                {"name": "監控關鍵字", "value": "、".join(KEYWORDS), "inline": False},
            ],
            "footer": {"text": f"執行時間：{datetime.now().strftime('%H:%M:%S')}"},
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)


def run():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 開始執行")

    date = get_today_roc_date()
    sent_ids = load_sent_ids()

    news = fetch_today_all_news(date)
    print(f"今日重訊共 {len(news)} 則")

    matched = filter_by_keywords(news, KEYWORDS)
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
    send_discord_summary(date, len(news), len(matched), len(new_items))
    print("完成")


if __name__ == "__main__":
    run()
