import requests
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

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


def fetch_by_keyword(keyword: str) -> list:
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    roc_year = now.year - 1911
    month = now.month

    url = "https://mops.twse.com.tw/mops/web/ajax_t51sb10"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://mops.twse.com.tw/mops/web/t51sb10",
    }
    data = (
        f"encodeURIComponent=1&step=1&firstin=true&id=&key=&TYPEK=&Stp=4"
        f"&go=false&co_id=&r1=1&KIND=C&CODE=&keyWord={keyword}"
        f"&Condition2=2&keyWord2=&year={roc_year}&month1={month}"
        f"&begin_day=1&end_day=1&Orderby=1"
    )

    res = requests.post(url, data=data, headers=headers, timeout=15)
    res.encoding = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")

    results = []
    table = soup.find("table")
    if not table:
        return results

    for row in table.find_all("tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 4:
            continue
        link_tag = row.find("a")
        results.append({
            "代號": cols[0].text.strip(),
            "公司": cols[1].text.strip(),
            "日期": cols[2].text.strip(),
            "主旨": cols[3].text.strip(),
            "連結": "https://mops.twse.com.tw" + link_tag["href"] if link_tag else "",
            "命中關鍵字": keyword,
        })

    return results


def make_unique_id(item: dict) -> str:
    return f"{item['日期']}_{item['代號']}_{item['主旨'][:20]}"


def send_discord(item: dict):
    embed = {
        "embeds": [{
            "title": f"【{item['命中關鍵字']}】{item['公司']}（{item['代號']}）",
            "description": item["主旨"],
            "url": item["連結"] or None,
            "color": 0x0099ff,
            "footer": {"text": f"公告日期：{item['日期']}"},
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=embed)
    time.sleep(0.5)


def send_discord_summary(total, new_count):
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
                {"name": "本月命中總數", "value": str(total), "inline": True},
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
    all_matched = []

    for kw in KEYWORDS:
        items = fetch_by_keyword(kw)
        print(f"  關鍵字「{kw}」：{len(items)} 則")
        all_matched.extend(items)
        time.sleep(1)

    print(f"命中總數：{len(all_matched)} 則")

    new_items = []
    for item in all_matched:
        uid = make_unique_id(item)
        if uid not in sent_ids:
            new_items.append(item)
            sent_ids.add(uid)

    print(f"新增（未發送過）：{len(new_items)} 則")

    for item in new_items:
        send_discord(item)
        print(f"  ✅ 已發送：{item['公司']} - {item['主旨'][:30]}")

    save_sent_ids(sent_ids)
    send_discord_summary(len(all_matched), len(new_items))
    print("完成")


if __name__ == "__main__":
    run()
