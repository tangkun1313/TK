import requests
import json
import time
import datetime
import xml.etree.ElementTree as ET
import os
import re

# ================= 配置区域 =================
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK", "")
TIKTOK_SALES_LINK = "https://www.fastmoss.com/zh/e-commerce/saleslist?region=JP"
JAPAN_NEWS_LIMIT = 10 
MAX_RETRIES = 3
INITIAL_BACKOFF = 2

# ================= 强化翻译函数（最终版，全中文输出） =================

def aggressive_translate_and_clean(text):
    """
    最终版：强制 100% 输出中文
    处理步骤：
    1. 翻译词典（日→中）
    2. 清理假名
    3. 日本汉字词 → 对应中文
    4. 过滤非中文字符
    """

    if not text:
        return "内容缺失"

    # 基础预处理
    clean_text = re.sub(r' - [^-\s]+$', '', text).strip()
    clean_text = re.sub(r'\(.*?\)', '', clean_text)

    # ========== 日本汉字词 → 中文（新增） ==========
    jp_to_cn_word_map = {
        "東京都": "东京",
        "大阪府": "大阪",
        "北海道": "北海道",
        "神奈川県": "神奈川",
        "国内": "日本国内",
        "日経": "日本经济新闻",
        "総務省": "日本总务省",
        "厚生労働省": "日本厚生劳动省",
        "岸田": "岸田文雄",
        "政府": "日本政府",
        "能登地震": "能登半岛地震",
        "経済": "经济",
        "円安": "日元贬值",
        "円高": "日元升值",
        "新規": "新增",
        "感染者": "感染人数",
        "速報": "快讯",
        "発生": "发生",
        "会見": "记者会",
        "警察庁": "日本警察厅",
        "気象庁": "日本气象厅",
    }

    for jp, cn in sorted(jp_to_cn_word_map.items(), key=lambda x: len(x[0]), reverse=True):
        clean_text = clean_text.replace(jp, cn)

    translated_text = clean_text

    # ========== 日 → 中 词典替换（保留你原来的翻译逻辑） ==========
    translation_map = {
        "自己満足型消費": "悦己消费",
        "急浮上": "迅速崛起",
        "売れ筋ランキング": "热销排行榜",
        "デイリーランキング": "每日榜单",
        "リアルタイム": "实时",
        "新商品": "新品",
        "成功事例": "成功案例",
        "秘訣": "诀窍",
        "コスメ": "美妆",
        "パーソナルケア": "个人护理",
        "スキンケア": "皮肤护理",
        "アパレル": "服饰",
        "ライフスタイル": "生活方式",
        "デジタル": "数码",
        "最新動向": "最新动态",
        "ランキング入り": "进入榜单",
        "販売": "销售",
        "小売": "零售",
        "戦略": "战略",
        "注目": "关注",
        "レポート": "报告",
        "ブランド": "品牌",
        "ショップ": "店铺",
        "セール": "促销",
        "キャンペーン": "活动",
        "美食": "美食",
        "人気": "热门",
        "市場": "市场",
        "家电": "家电",
        "食品": "食品",
        "雑貨": "杂货",
    }

    for jp, cn in sorted(translation_map.items(), key=lambda x: len(x[0]), reverse=True):
        translated_text = translated_text.replace(jp, cn)

    # ========== 删除所有假名 ==========
    translated_text = re.sub(r'[ぁ-んァ-ン]', '', translated_text)

    # ========== 最终过滤：只保留中文/数字/标点 ==========
    translated_text = re.sub(r'[^0-9\u4e00-\u9fa5，。！？…]', ' ', translated_text)
    translated_text = re.sub(r'\s+', ' ', translated_text).strip()

    if len(translated_text) > 45:
        translated_text = translated_text[:45] + "..."

    return translated_text


# ================= Google RSS 抓取 =================

def fetch_google_news_rss(query, limit=5, is_jp_query=True):
    hl = 'ja' if is_jp_query else 'en'
    gl = 'JP' if is_jp_query else 'US'
    ceid = 'JP:ja' if is_jp_query else 'US:en'
    
    encoded_query = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
    news_items = []

    for attempt in range(MAX_RETRIES):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0'
            }
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for item in root.findall('./channel/item')[:limit]:
                title_jp = item.find('title').text
                link = item.find('link').text
                title_cn = aggressive_translate_and_clean(title_jp)

                news_items.append({
                    "title_jp": title_jp,
                    "title_cn": title_cn,
                    "link": link
                })
            return news_items
        
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(INITIAL_BACKOFF * (2 ** attempt))

    return []


# ================= 数据抓取模块 =================

def get_tiktok_sales_ranking():
    return fetch_google_news_rss("TikTok 売れ筋 商品", limit=5)

def get_tiktok_hashtag_trends():
    items = fetch_google_news_rss("TikTok ハッシュタグ トレンド", limit=5, is_jp_query=False)
    for item in items:
        item["title_cn"] = None  
    return items

def get_rakuten_ranking_info():
    queries = [
        "楽天市場 ランキング 総合 1位",
        "楽天市場 ランキング 美容",
        "楽天市場 ランキング グルメ",
        "楽天市場 ランキング ファッション",
        "楽天市場 ランキング 家電"
    ]
    results = []
    for q in queries:
        results.extend(fetch_google_news_rss(q, limit=1))
    return results[:5]

def get_yahoo_ranking_info():
    queries = [
        "Yahoo!ショッピング ランキング 1位",
        "Yahoo!ショッピング ランキング 工具",
        "Yahoo!ショッピング ランキング アウトドア",
        "Yahoo!ショッピング ランキング ベビー",
        "Yahoo!ショッピング ランキング 雑貨"
    ]
    results = []
    for q in queries:
        results.extend(fetch_google_news_rss(q, limit=1))
    return results[:5]

def get_japan_real_time_news():
    return fetch_google_news_rss("日本 国内 最新 ニュース", limit=10)


# ================= 飞书发送 =================

def send_feishu_card(webhook_url, data):
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    def make_list_text(items, is_translated=True):
        if not items:
            return "暂无数据"

        txt = ""
        for i, item in enumerate(items):
            link = item["link"]
            if is_translated:
                txt += f"{i+1}. **{item['title_cn']}** [查看原文]({link})\n"
            else:
                txt += f"{i+1}. [{item['title_jp']}]({link})\n"
        return txt

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"🇯🇵 日本电商日报 {today}"},
                "template": "blue"
            },
            "elements": [
                {"tag":"div","text":{"tag":"lark_md","content":"🔥 **1. 日本 TikTok 昨日销量榜单**"}},
                {"tag":"div","text":{"tag":"lark_md","content":make_list_text(data["tiktok_sales"])}},
                {"tag":"hr"},
                {"tag":"div","text":{"tag":"lark_md","content":"🎵 **2. TikTok 热门标签词**"}},
                {"tag":"div","text":{"tag":"lark_md","content":make_list_text(data["tiktok_hashtag"], is_translated=False)}},
                {"tag":"hr"},
                {"tag":"div","text":{"tag":"lark_md","content":"🔴 **3. 乐天精选榜单**"}},
                {"tag":"div","text":{"tag":"lark_md","content":make_list_text(data["rakuten_ranking"])}},
                {"tag":"hr"},
                {"tag":"div","text":{"tag":"lark_md","content":"🟢 **4. 雅虎购物精选榜单**"}},
                {"tag":"div","text":{"tag":"lark_md","content":make_list_text(data["yahoo_ranking"])}},
                {"tag":"hr"},
                {"tag":"div","text":{"tag":"lark_md","content":"📰 **5. 日本实时新闻**"}},
                {"tag":"div","text":{"tag":"lark_md","content":make_list_text(data["japan_news"])}},
            ]
        }
    }

    requests.post(webhook_url, headers={"Content-Type":"application/json"}, data=json.dumps(card))


# ================= 主程序 =================

def main():
    if not FEISHU_WEBHOOK_URL:
        print("错误：未设置飞书 Webhook")
        return

    data = {
        "tiktok_sales": get_tiktok_sales_ranking(),
        "tiktok_hashtag": get_tiktok_hashtag_trends(),
        "rakuten_ranking": get_rakuten_ranking_info(),
        "yahoo_ranking": get_yahoo_ranking_info(),
        "japan_news": get_japan_real_time_news()
    }

    send_feishu_card(FEISHU_WEBHOOK_URL, data)


if __name__ == "__main__":
    main()
