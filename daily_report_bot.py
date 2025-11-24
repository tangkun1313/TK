import requests
import json
import time
import datetime
import xml.etree.ElementTree as ET
import os

# ================= 配置区域 =================
# 飞书 Webhook 地址 (本地运行时填入，GitHub Actions 会自动读取环境变量)
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK", "")
# 如果本地测试，请取消注释并填入:
# FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/你的Webhook地址"

# ================= 数据获取函数 =================

def fetch_google_news_rss(query, limit=8):
    """
    通用函数：通过 Google News RSS 获取相关新闻
    limit: 获取条数，默认提高到 8 条
    """
    # 针对日本地区搜索 (hl=ja, gl=JP)
    url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            news_items = []
            # 获取指定数量的新闻
            for item in root.findall('./channel/item')[:limit]:
                title = item.find('title').text
                link = item.find('link').text
                pub_date = item.find('pubDate').text
                # 简化时间格式
                try:
                    dt = datetime.datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
                    date_str = dt.strftime("%m-%d")
                except:
                    date_str = "近日"
                
                news_items.append({"title": title, "link": link, "date": date_str})
            return news_items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
    return []

# --- 1. TikTok Shop (FastMoss 替代方案) ---
def get_tiktok_shop_trends():
    print("正在获取 TikTok Shop 趋势 (FastMoss源/资讯)...")
    
    # 由于 FastMoss 无法通过简单脚本直接登录抓取，
    # 我们这里抓取"TikTok 爆款"相关的新闻，并附上 FastMoss 的直达链接。
    news_items = fetch_google_news_rss("TikTok 売れ筋 ランキング", limit=6)
    
    # 这里为了演示，保留一些模拟的爆款结构，实际使用中主要看上面的 News
    # 如果你有技术能力接入 FastMoss API，可在此处替换
    fastmoss_link = "https://www.fastmoss.com/zh/rank/product?region=JP"
    
    return news_items, fastmoss_link

# --- 2. 日本乐天爆款 ---
def get_rakuten_ranking():
    print("正在获取日本乐天爆款资讯...")
    # 搜索乐天排名相关的新闻/文章
    return fetch_google_news_rss("楽天市場 ランキング 注目标", limit=8)

# --- 3. 日本亚马逊爆款 ---
def get_amazon_ranking():
    print("正在获取日本亚马逊爆款资讯...")
    # 搜索亚马逊畅销榜相关的新闻
    return fetch_google_news_rss("Amazon.co.jp 売れ筋ランキング", limit=8)

# --- 4. 电商与 TikTok 新闻 ---
def get_ec_tiktok_news():
    print("正在获取行业新闻...")
    ec_news = fetch_google_news_rss("日本 EC市場 トレンド", limit=5)
    tiktok_news = fetch_google_news_rss("TikTok 日本 ニュース", limit=5)
    return ec_news, tiktok_news

# ================= 飞书发送函数 =================

def send_feishu_card(webhook_url, data):
    """
    发送飞书富文本卡片消息
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 构建内容块 elements
    elements = []
    
    # 辅助函数：生成列表文本
    def make_list_text(items):
        if not items:
            return "暂无更新"
        txt = ""
        for i, item in enumerate(items):
            # 移除标题中多余的网站名后缀，让标题更短
            clean_title = item['title'].split(' - ')[0]
            txt += f"{i+1}. [{clean_title}]({item['link']})\n"
        return txt

    # --- 第一板块：TikTok Shop 商品趋势 (置顶) ---
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔥🔥 **日本 TikTok Shop 商品趋势** 🔥🔥"}})
    
    # 插入 FastMoss 链接
    elements.append({
        "tag": "div", 
        "text": {
            "tag": "lark_md", 
            "content": f"👉 [点击查看 FastMoss 实时榜单 (需登录)]({data['fastmoss_link']})\n*(注: 脚本无法自动登录 FastMoss，以下展示相关热销资讯)*"
        }
    })
    
    tiktok_items, _ = data['tiktok_shop']
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(tiktok_items)}})
    elements.append({"tag": "hr"}) # 分割线

    # --- 第二板块：日本乐天爆款 ---
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "🔴 **日本乐天 (Rakuten) 爆款资讯**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['rakuten'])}})
    elements.append({"tag": "hr"})

    # --- 第三板块：日本亚马逊爆款 ---
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "📦 **日本亚马逊 (Amazon) 爆款资讯**"}})
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": make_list_text(data['amazon'])}})
    elements.append({"tag": "hr"})

    # --- 第四板块：行业新闻 (合并展示) ---
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "📰 **电商 & TikTok 行业简报**"}})
    
    ec_items, tiktok_news_items = data['news']
    
    news_txt = "**[电商动态]**\n" + make_list_text(ec_items) + "\n**[TikTok动态]**\n" + make_list_text(tiktok_news_items)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": news_txt}})

    # --- 组装最终 JSON ---
    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🇯🇵 日本电商选品早报 ({today})"
                },
                "template": "red" # 使用红色标题，更醒目
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

    # 1. 并行获取各项数据 (顺序执行)
    tiktok_shop_data = get_tiktok_shop_trends()
    rakuten_data = get_rakuten_ranking()
    amazon_data = get_amazon_ranking()
    news_data = get_ec_tiktok_news()

    # 2. 整合数据包
    all_data = {
        "tiktok_shop": tiktok_shop_data,
        "rakuten": rakuten_data,
        "amazon": amazon_data,
        "news": news_data
    }

    # 3. 发送
    send_feishu_card(FEISHU_WEBHOOK_URL, all_data)

if __name__ == "__main__":
    main()
