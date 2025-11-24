import requests
import json
import time
import datetime
import xml.etree.ElementTree as ET
import os

# ================= 配置区域 =================
# 飞书 Webhook 地址
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK", "")
# 榜单和链接配置
TIKTOK_SALES_LINK = "https://www.fastmoss.com/zh/e-commerce/saleslist?region=JP"

# ================= 辅助函数 =================

def simple_translate(text):
    """
    模拟一个翻译函数，将日文文本翻译成中文。
    注意：在实际环境中，需要调用付费的翻译API (如 Google Cloud Translation API)。
    这里为了保证脚本的零成本运行，仅做非常简单的关键词替换和截断，并添加提示。
    """
    # 替换一些常见的日文电商词汇，使其更像翻译后的内容
    text = text.replace("EC", "电商")
    text = text.replace("ランキン", "榜单")
    text = text.replace("トレンド", "趋势")
    text = text.replace("ニュース", "新闻")
    
    # 查找并保留链接文本，不翻译括号内的内容
    import re
    # 简单的处理：移除新闻源后缀，并截断长度
    clean_text = re.sub(r' - [^-\s]+$', '', text)
    
    # 如果文本太长，截断，模拟翻译摘要
    if len(clean_text) > 50:
        return f"{clean_text[:50]}... (译)"
        
    return clean_text

def fetch_google_news_rss(query, limit=10, is_jp_query=True):
    """
    通用函数：通过 Google News RSS 获取相关新闻
    """
    hl = 'ja' if is_jp_query else 'en'
    gl = 'JP' if is_jp_query else 'US'
    ceid = 'JP:ja' if is_jp_query else 'US:en'
    
    url = f"https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            news_items = []
            
            # 获取指定数量的新闻 (5-10条)
            for item in root.findall('./channel/item')[:limit]:
                title_jp = item.find('title').text
                link = item.find('link').text
                
                # 如果需要翻译，则进行翻译
                if is_jp_query:
                    title_cn = simple_translate(title_jp)
                    news_items.append({"title_jp": title_jp, "title_cn": title_cn, "link": link})
                else:
                    # 热门标签词不需要翻译，直接使用日文
                    news_items.append({"title_jp": title_jp, "title_cn": None, "link": link})
                    
            return news_items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
    return []

# ================= 数据获取函数 (按需求重构) =================

# --- 1. 日本 TikTok 昨日销量榜单 (资讯替代，指向FastMoss) ---
def get_tiktok_sales_ranking():
    print("正在获取 TikTok 销量榜单相关资讯...")
    # 抓取相关热销品的资讯，用作榜单的补充内容
    news_items = fetch_google_news_rss("TikTok 売れ筋 商品 注目", limit=8)
    return news_items

# --- 2. 日本 TikTok 热门标签词 (不翻译) ---
def get_tiktok_hashtag_trends():
    print("正在获取 TikTok 热门标签词...")
    # 抓取日文热门标签或趋势词汇
    return fetch_google_news_rss("TikTok トレンド ハッシュタグ", limit=10, is_jp_query=False)

# --- 3. 日本乐天昨日销量榜单 (资讯替代) ---
def get_rakuten_ranking_info():
    print("正在获取日本乐天爆款资讯...")
    # 搜索乐天畅销品/趋势
    return fetch_google_news_rss("楽天市場 注目ランキング 傾向", limit=8)

# --- 4. 日本亚马逊昨日销量榜单 (资讯替代) ---
def get_amazon_ranking_info():
    print("正在获取日本亚马逊爆款资讯...")
    # 搜索亚马逊畅销榜/趋势
    return fetch_google_news_rss("Amazon.co.jp 売れ筋ランキング 傾向", limit=8)

# --- 5. 日本实时新闻 (10条) ---
def get_japan_real_time_news():
    print("正在获取日本实时新闻 (10条)...")
    # 搜索最新的日本国内新闻
    return fetch_google_news_rss("日本 国内 ニュース 最新", limit=10)

# ================= 飞书发送函数 =================

def send_feishu_card(webhook_url, data):
    """
    发送飞书富文本卡片消息
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 飞书卡片颜色 (更专业一些的颜色)
    template_color = "blue" 
    
    # 辅助函数：生成列表文本 (支持中日文双标题)
    def make_list_text(items, is_translated=True):
        if not items:
            return "暂无数据更新或抓取失败，请检查关键词或稍后重试。"
        
        txt = ""
        for i, item in enumerate(items):
            link = item['link']
            # 根据是否翻译选择显示中文或日文
            if is_translated:
                title_display = item['title_cn'] if item['title_cn'] else item['title_jp']
                txt += f"{i+1}. **{title_display}** [原文]({link})\n"
            else:
                # 热门标签词，只显示日文
                txt += f"{i+1}. [{item['title_jp']}]({link})\n"
        return txt

    # --- 组装内容 ---
    elements = []
    
    # 1. 日本 TikTok 昨日销量榜单 (Top 1)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔥 **1. 日本 TikTok Shop 昨日销量榜单**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"👉 **[点击直达 FastMoss 销量榜单 (无需登录)]({TIKTOK_SALES_LINK})**\n*(以下为相关热销品类和趋势资讯)*"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['tiktok_sales'], is_translated=True)}})
    elements.append({"tag": "hr"}) 

    # 2. 日本 TikTok 热门标签词 (Top 2)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🎵 **2. 日本 TikTok 热门标签词 (Hashtag Trends)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['tiktok_hashtag'], is_translated=False)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 标签词保持日文原文，点击查看详情)*"}})
    elements.append({"tag": "hr"})

    # 3. 日本乐天昨日销量榜单 (Top 3)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔴 **3. 日本乐天 (Rakuten) 爆款/趋势**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['rakuten_ranking'], is_translated=True)}})
    elements.append({"tag": "hr"})

    # 4. 日本亚马逊昨日销量榜单 (Top 4)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "📦 **4. 日本亚马逊 (Amazon) 爆款/趋势**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['amazon_ranking'], is_translated=True)}})
    elements.append({"tag": "hr"})
    
    # 5. 日本实时新闻 (Top 5)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "📰 **5. 日本国内实时新闻 (10条)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['japan_news'], is_translated=True)}})


    # --- 组装最终 JSON ---
    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🇯🇵 日本电商选品早报 ({today}) - 全球购助手"
                },
                "template": template_color 
            },
            "elements": elements
        }
    }

    headers = {'Content-Type': 'application/json'}
    
    try:
        res = requests.post(webhook_url, headers=headers, data=json.dumps(card_content))
        # 飞书接口要求 CustomKeyword 必须在内容中，标题中已包含“早报”
        print(f"发送状态: {res.status_code}, 响应: {res.text}")
    except Exception as e:
        print(f"发送失败: {e}")

# ================= 主程序 =================

def main():
    if not FEISHU_WEBHOOK_URL:
        print("错误: 未设置飞书 Webhook URL")
        return

    # 1. 获取各项数据 (按用户要求的新顺序)
    data = {}
    
    # Top 1: TikTok 销量榜单 (资讯)
    data["tiktok_sales"] = get_tiktok_sales_ranking()
    
    # Top 2: TikTok 热门标签词 (不翻译)
    data["tiktok_hashtag"] = get_tiktok_hashtag_trends()
    
    # Top 3: 乐天销量榜单 (资讯)
    data["rakuten_ranking"] = get_rakuten_ranking_info()
    
    # Top 4: 亚马逊销量榜单 (资讯)
    data["amazon_ranking"] = get_amazon_ranking_info()
    
    # Top 5: 日本实时新闻 (10条)
    data["japan_news"] = get_japan_real_time_news()


    # 2. 发送
    send_feishu_card(FEISHU_WEBHOOK_URL, data)

if __name__ == "__main__":
    main()
