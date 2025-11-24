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
# 确保 Google News RSS 返回 10 条日本实时新闻
JAPAN_NEWS_LIMIT = 10 

# ================= 辅助函数 =================

def simple_translate(text):
    """
    模拟一个翻译函数，将日文/英文文本翻译成中文，并返回简洁的中文摘要。
    本次更新：大规模扩充日文电商/趋势词汇的翻译词典，并清理日文助词，力求实现“全中文”效果。
    """
    if not text:
        return "内容缺失"

    # 移除新闻源后缀（如 - Yahoo!ニュース / - Fashionsnap.com）
    clean_text = re.sub(r' - [^-\s]+$', '', text).strip()
    
    # === 大幅增强翻译词典 (优先翻译长词/复杂短语) ===
    translation_map = {
        # 复杂短语/热词
        "自己満足型消費": "悦己消费", 
        "急浮上": "迅速崛起", 
        "売れ筋ランキング": "热销排行榜",
        "デイリーランキング": "每日榜单",
        "リアルタイム": "实时",
        "新商品": "新品",
        "成功事例": "成功案例", 
        "秘訣": "诀窍",
        "コスメ": "美妆/化妆品",
        "パーソナルケア": "个人护理",
        "スキンケア": "皮肤护理",
        "アパレル": "服饰",
        "ライフスタイル": "生活方式",
        "デジタル": "数码",
        "最新動向": "最新动态",
        "トップ": "顶部",
        "ランキング入り": "进入榜单",
        "販売": "销售",
        "小売": "零售",
        "戦略": "战略",

        # 核心电商词汇
        "EC": "电商", "ランキン": "榜单", "トレンド": "趋势", "ニュース": "新闻", "注目": "关注", 
        "最新": "最新", "売れ筋": "热销", "楽天市場": "乐天市场", "Yahoo!ショッピング": "雅虎购物", 
        "商品": "商品", "レポート": "报告", "ブランド": "品牌", "ストリート": "街头", "売上高": "销售额",
        "ショップ": "店铺", "セール": "促销", "キャンペーン": "活动",
        
        # 常见日文动词/形容词/名词
        "伸び": "增长", "公開": "公布", "発表": "发布", "開催": "举行", "影響": "影响", 
        "導入": "引入", "解説": "解读", "突破": "突破", "特集": "特辑", "急伸": "暴涨", 
        "好調": "势头良好", "人気": "热门", "若者": "年轻人", "世代": "世代", "ユーザー": "用户", 
        "カテゴリ": "品类", "カテゴリー": "品类", "市場": "市场",
        
        # 常见日文助词/连词 (重点清理，确保中文流畅)
        "が": "", "の": "的", "に": "在", "を": "", "と": "和", "へ": "向", "で": "在",
        "は": "", "より": "比", "から": "从", "まで": "到", "など": "等", 
        "そして": "并且", "しかし": "但是", "ため": "因为",
        "について": "关于", 
        "に関する": "相关", 
        "として": "作为", 
        "に対する": "针对",
        
        # 标点符号清理
        "「": "“", "」": "”", "『": "“", "』": "”",
    }
    
    translated_text = clean_text
    
    # 1. 执行翻译替换 (关键：按照键的长度降序排列，确保长词优先被替换)
    sorted_map = dict(sorted(translation_map.items(), key=lambda item: len(item[0]), reverse=True))
    
    for jp, cn in sorted_map.items():
        translated_text = translated_text.replace(jp, cn)
        
    # 2. 移除括号内的日期、年份或额外信息，专注于主要内容
    translated_text = re.sub(r'【.*?】', '', translated_text)
    translated_text = re.sub(r'\（.*?）', '', translated_text)
    translated_text = re.sub(r'\d{4}年', 'X年', translated_text) 
    
    # 3. 清理可能残留的日文语法结构和多余空格
    # 替换日文逗号和句号为中文标点
    translated_text = re.sub(r'[、。]', '，', translated_text).strip()
    # 移除连续空格
    translated_text = re.sub(r'\s+', ' ', translated_text).strip()
    
    # 4. 如果文本太长，截断
    if len(translated_text) > 45: 
        translated_text = f"{translated_text[:45]}..."
        
    # 5. 确保没有冗余空格或换行
    return translated_text.strip()


def fetch_google_news_rss(query, limit=5, is_jp_query=True):
    """
    通用函数：通过 Google News RSS 获取相关新闻
    """
    # 调整语言和地区参数，以优化搜索结果的相关性
    hl = 'ja' if is_jp_query else 'en'
    gl = 'JP' if is_jp_query else 'US'
    ceid = 'JP:ja' if is_jp_query else 'US:en'
    
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
                
                # 翻译处理：获取纯净的中文标题
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
    return fetch_google_news_rss("TikTok Shop 売れ筋 商品 注目", limit=5)

# --- 2. 日本 TikTok 热门标签词 (保持原文) ---
def get_tiktok_hashtag_trends():
    print("正在获取 TikTok 热门标签词...")
    # 热门标签词通常是英文/日文，保持原文
    items = fetch_google_news_rss("TikTok トレンド ハッシュタグ", limit=5, is_jp_query=False)
    for item in items:
        item['title_cn'] = None 
    return items

# --- 3. 日本乐天 (Rakuten) 精选榜单 (更精准关键词，排除竞争对手) ---
def get_rakuten_ranking_info():
    print("正在获取日本乐天精选榜单关键词 (已排除Amazon/Yahoo)...")
    # 关键词针对具体的榜单或 Top 商品，使用 -排除竞争对手
    queries = [
        "楽天市場 デイリーランキング 総合 1位 -Amazon -Yahoo!ショッピング",  
        "楽天市場 ランキング 注目 美容 コスメ -Amazon -Yahoo!ショッピング", 
        "楽天市場 ランキング 売れ筋 食品 グルメ -Amazon -Yahoo!ショッピング", 
        "楽天市場 ランキング リアルタイム ファッション -Amazon -Yahoo!ショッピング", 
        "楽天市場 ランキング 注目 家电 デジタル -Amazon -Yahoo!ショッピング" 
    ]
    results = []
    for q in queries:
        # 每个查询只取 1 条，保证最高的精准度
        results.extend(fetch_google_news_rss(q, limit=1))
    return results[:5]


# --- 4. 日本雅虎购物 (Yahoo! Shopping) 精选榜单 (更精准关键词，排除竞争对手) ---
def get_yahoo_ranking_info():
    print("正在获取日本雅虎购物精选榜单关键词 (已排除乐天/Amazon)...")
    # 关键词针对具体的榜单或 Top 商品，使用 -排除竞争对手
    queries = [
        "Yahoo!ショッピング 売れ筋 ランキング 1位 -楽天市場 -Amazon", 
        "Yahoo!ショッピング 売れ筋 注目 工具 DIY -楽天市場 -Amazon", 
        "Yahoo!ショッピング 売れ筋 注目 スポーツ アウトドア -楽天市場 -Amazon", 
        "Yahoo!ショッピング ランキング 注目 ベビー キッズ -楽天市場 -Amazon", 
        "Yahoo!ショッピング ランキング リアルタイム 雑貨 -楽天市場 -Amazon" 
    ]
    results = []
    for q in queries:
        # 每个查询只取 1 条，保证最高的精准度
        results.extend(fetch_google_news_rss(q, limit=1))
    return results[:5]


# --- 5. 日本实时新闻 (10条, 确保翻译) ---
def get_japan_real_time_news():
    print(f"正在获取日本实时新闻 ({JAPAN_NEWS_LIMIT}条)...")
    # 搜索最新的日本国内新闻，确保数量为 10
    return fetch_google_news_rss("日本 国内 ニュース 最新", limit=JAPAN_NEWS_LIMIT)

# ================= 飞书发送函数 =================

def send_feishu_card(webhook_url, data):
    """
    发送飞书富文本卡片消息
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    template_color = "blue" 
    
    # 辅助函数：生成列表文本 (关键：强制显示中文，日文/英文作为链接文本)
    def make_list_text(items, is_translated=True):
        if not items:
            return "暂无数据更新或抓取失败，请检查关键词或稍后重试。"
        
        txt = ""
        for i, item in enumerate(items):
            link = item['link']
            title_jp = item['title_jp']
            
            if not is_translated:
                # 热门标签词，只显示日文/英文原文作为链接文本
                txt += f"{i+1}. [{title_jp}]({link})\n"
            else:
                # 其他所有板块：强制显示中文翻译作为标题，日文原文作为链接文本
                title_display = item['title_cn'] if item['title_cn'] else "翻译失败内容"
                
                # 关键：**中文标题** 确保了加粗和突出，解决了您截图中的问题
                txt += f"{i+1}. **{title_display}** [日文原文]({link})\n"
                
        return txt

    # --- 组装内容 ---
    elements = []
    
    # 1. 日本 TikTok 昨日销量榜单 (Top 1)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔥 **1. 日本 TikTok Shop 昨日销量榜单 (5条)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": f"👉 **[点击直达 FastMoss 销量榜单 (无需登录)]({TIKTOK_SALES_LINK})**\n*(以下为相关热销品类和趋势资讯，已翻译)*"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['tiktok_sales'], is_translated=True)}})
    elements.append({"tag": "hr"}) 

    # 2. 日本 TikTok 热门标签词 (Top 2)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🎵 **2. 日本 TikTok 热门标签词 (Hashtag Trends - 5条)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['tiktok_hashtag'], is_translated=False)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 标签词保持日文/英文原文，点击查看详情)*"}})
    elements.append({"tag": "hr"})

    # 3. 日本乐天 (Rakuten) 精选榜单 (Top 3)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔴 **3. 日本乐天 (Rakuten) 精选榜单关键词 (5条)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['rakuten_ranking'], is_translated=True)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 搜索结果为乐天 Top 商品关键词，已翻译)*"}})
    elements.append({"tag": "hr"})

    # 4. 日本雅虎购物 (Yahoo! Shopping) 精选榜单 (Top 4)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🟢 **4. 日本雅虎购物 (Yahoo! Shopping) 精选榜单关键词 (5条)**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['yahoo_ranking'], is_translated=True)}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "*(注: 搜索结果为雅虎购物 Top 商品关键词，已翻译)*"}})
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

    # 1. 获取各项数据
    data = {}
    
    # Top 1: TikTok 销量榜单 (资讯，数量 5)
    data["tiktok_sales"] = get_tiktok_sales_ranking()
    
    # Top 2: TikTok 热门标签词 (不翻译，数量 5)
    data["tiktok_hashtag"] = get_tiktok_hashtag_trends()
    
    # Top 3: 乐天销量榜单 (精准关键词，数量 5)
    data["rakuten_ranking"] = get_rakuten_ranking_info()
    
    # Top 4: 雅虎购物销量榜单 (精准关键词，数量 5)
    data["yahoo_ranking"] = get_yahoo_ranking_info()
    
    # Top 5: 日本实时新闻 (10条)
    data["japan_news"] = get_japan_real_time_news()


    # 2. 发送
    send_feishu_card(FEISHU_WEBHOOK_URL, data)

if __name__ == "__main__":
    main()
