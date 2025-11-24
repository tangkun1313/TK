import requests
import json
import time
import datetime
import xml.etree.ElementTree as ET
import os
import re

# ================= 配置区域 =================
# 飞书 Webhook 地址
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK", "")
# 榜单和链接配置
TIKTOK_SALES_LINK = "https://www.fastmoss.com/zh/e-commerce/saleslist?region=JP"

# ================= 辅助函数 =================

def simple_translate(text):
    """
    模拟一个翻译函数，将日文/英文文本翻译成中文。
    目标是让用户看懂内容，而不是精确翻译。
    """
    
    # 移除新闻源后缀（如 - Yahoo!ニュース）
    clean_text = re.sub(r' - [^-\s]+$', '', text).strip()
    
    # 日文到中文的关键词替换 (增强翻译效果)
    translation_map = {
        "EC": "电商",
        "ランキン": "榜单",
        "トレンド": "趋势",
        "ニュース": "新闻",
        "注目": "精选/关注",
        "最新": "最新",
        "売れ筋": "热销",
        "楽天市場": "日本乐天",
        "Yahoo!": "日本雅虎",
        "Amazon": "日本亚马逊",
        "商品": "商品"
    }
    
    translated_text = clean_text
    for jp, cn in translation_map.items():
        translated_text = translated_text.replace(jp, cn)
        
    # 如果文本太长，截断，并添加提示
    if len(translated_text) > 40: # 稍微收紧截断长度
        translated_text = f"{translated_text[:40]}... (译)"
        
    # 如果是英文，直接返回英文，因为它可能不是要翻译的标签词
    # 但由于用户要求全部翻译，我们对所有内容应用上述规则。

    # 进一步清理，移除链接中的协议头，只保留中文部分
    translated_text = re.sub(r'\((https?://[^\)]+)\)', '', translated_text)
    
    # 确保没有冗余空格或换行
    return translated_text.strip()


def fetch_google_news_rss(query, limit=5, is_jp_query=True):
    """
    通用函数：通过 Google News RSS 获取相关新闻
    query: 搜索关键词 (日文或中文)
    limit: 获取条数，现在设置为 5-10 条
    is_jp_query: 是否为日文搜索，影响 hl/gl 参数
    """
    hl = 'ja' if is_jp_query else 'en'
    gl = 'JP' if is_jp_query else 'US'
    ceid = 'JP:ja' if is_jp_query else 'US:en'
    
    # URL 编码查询
    encoded_query = requests.utils.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={ceid}"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            news_items = []
            
            # 获取指定数量的新闻
            for item in root.findall('./channel/item')[:limit]:
                title_jp = item.find('title').text
                link = item.find('link').text
                
                # 翻译处理
                title_cn = simple_translate(title_jp)
                news_items.append({"title_jp": title_jp, "title_cn": title_cn, "link": link})
                    
            return news_items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
    return []

# ================= 数据获取函数 (重构为精准关键词搜索) =================

# --- 1. 日本 TikTok 昨日销量榜单 (资讯替代，指向FastMoss) ---
def get_tiktok_sales_ranking():
    print("正在获取 TikTok 销量榜单相关资讯...")
    # 抓取相关热销品的资讯，用作榜单的补充内容
    # 数量减少到 5 条，更精简
    return fetch_google_news_rss("TikTok 売れ筋 商品 注目", limit=5)

# --- 2. 日本 TikTok 热门标签词 (保持原文) ---
def get_tiktok_hashtag_trends():
    print("正在获取 TikTok 热门标签词...")
    # 抓取日文热门标签或趋势词汇。由于是标签，保持原文更有参考价值。
    # 这里不需要翻译，但为了统一数据结构，title_cn 设为 None
    items = fetch_google_news_rss("TikTok トレンド ハッシュタグ", limit=5, is_jp_query=False)
    for item in items:
        item['title_cn'] = None # 确保在 make_list_text 中不被翻译
    return items

# --- 3. 日本乐天 (Rakuten) 精选榜单 (精准关键词) ---
def get_rakuten_ranking_info():
    print("正在获取日本乐天精选榜单关键词...")
    # 搜索乐天官网的"实时榜单"或"热销品"标题。这样得到的结果更接近榜单商品。
    # 关键词使用：楽天市場 ランキング [商品分类]
    queries = [
        "楽天市場 ランキング リアルタイム", 
        "楽天市場 売れ筋 注目 ファッション", 
        "楽天市場 売れ筋 注目 デジタル", 
        "楽天市場 ランキング 注目 美容"
    ]
    # 随机取 4 个结果，保证精准度
    results = []
    for q in queries:
        results.extend(fetch_google_news_rss(q, limit=1))
    return results[:5]


# --- 4. 日本雅虎购物 (Yahoo! Shopping) 精选榜单 (精准关键词) ---
def get_yahoo_ranking_info():
    print("正在获取日本雅虎购物精选榜单关键词...")
    # 搜索雅虎购物的"实时榜单"或"热销品"标题
    queries = [
        "Yahoo!ショッピング ランキング リアルタイム", 
        "Yahoo!ショッピング 売れ筋 注目 家電", 
        "Yahoo!ショッピング 売れ筋 注目 食品",
        "Yahoo!ショッピング ランキング 注目 スポーツ"
    ]
    # 随机取 4 个结果，保证精准度
    results = []
    for q in queries:
        results.extend(fetch_google_news_rss(q, limit=1))
    return results[:5]


# --- 5. 日本实时新闻 (10条, 确保翻译) ---
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
            title_jp = item['title_jp']
            
            # 根据是否翻译选择显示中文或日文
            if not is_translated:
                # 热门标签词，只显示日文/原文
                txt += f"{i+1}. [{title_jp}]({link})\n"
            else:
                # 其他所有板块都需要翻译
                title_display = item['title_cn'] if item['title_cn'] else title_jp
                
                # 确保翻译后的中文标题作为粗体主标题，日文作为链接的文本
                txt += f"{i+1}. **{title_display}** [原文]({link})\n"
                
        return txt

    # --- 组装内容 ---
    elements = []
    
    # 1. 日本 TikTok 昨日销量榜单 (Top 1)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔥 **1. 日本 TikTok Shop 昨日销量榜单**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"👉 **[点击直达 FastMoss 销量榜单 (无需登录)]({TIKTOK_SALES_LINK})**\n*(以下为相关热销品类和趋势资讯，已翻译)*"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['tiktok_sales'], is_translated=True)}})
    elements.append({"tag": "hr"}) 

    # 2. 日本 TikTok 热门标签词 (Top 2)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🎵 **2. 日本 TikTok 热门标签词 (Hashtag Trends)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['tiktok_hashtag'], is_translated=False)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 标签词保持日文/英文原文，点击查看详情)*"}})
    elements.append({"tag": "hr"})

    # 3. 日本乐天 (Rakuten) 精选榜单 (Top 3)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔴 **3. 日本乐天 (Rakuten) 精选榜单关键词**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['rakuten_ranking'], is_translated=True)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 搜索结果为乐天榜单关键词，精准度更高)*"}})
    elements.append({"tag": "hr"})

    # 4. 日本雅虎购物 (Yahoo! Shopping) 精选榜单 (Top 4)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🟢 **4. 日本雅虎购物 (Yahoo! Shopping) 精选榜单关键词**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['yahoo_ranking'], is_translated=True)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 搜索结果为雅虎购物榜单关键词，精准度更高)*"}})
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
    
    # Top 1: TikTok 销量榜单 (资讯，数量减为 5)
    data["tiktok_sales"] = get_tiktok_sales_ranking()
    
    # Top 2: TikTok 热门标签词 (不翻译，数量减为 5)
    data["tiktok_hashtag"] = get_tiktok_hashtag_trends()
    
    # Top 3: 乐天销量榜单 (精准关键词，数量减为 5)
    data["rakuten_ranking"] = get_rakuten_ranking_info()
    
    # Top 4: 雅虎购物销量榜单 (精准关键词，数量减为 5)
    data["yahoo_ranking"] = get_yahoo_ranking_info()
    
    # Top 5: 日本实时新闻 (10条)
    data["japan_news"] = get_japan_real_time_news()


    # 2. 发送
    send_feishu_card(FEISHU_WEBHOOK_URL, data)

if __name__ == "__main__":
    main()
