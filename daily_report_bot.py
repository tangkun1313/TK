import requests
import json
import time
import datetime
import xml.etree.ElementTree as ET
import os

# ================= 配置区域 =================
# 在本地运行时，请将你的 Webhook 地址填入下方引号中
# 在 GitHub Actions 运行时，我们会通过环境变量传入，不需要修改这里
FEISHU_WEBHOOK_URL = os.environ.get("FEISHU_WEBHOOK", "")

# 如果你没有配置环境变量且在本地测试，请取消下面这行的注释并填入地址：
# FEISHU_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxx"

# ================= 数据获取函数 =================

def fetch_google_news_rss(query):
    """
    通过 Google News RSS 获取相关新闻
    """
    # Google News RSS 地址 (针对日本地区搜索)
    # hl=ja&gl=JP&ceid=JP:ja 表示获取日本当地日语新闻
    # 也可以改成 hl=en-US&gl=US&ceid=US:en 搜索英语内容
    url = f"https://news.google.com/rss/search?q={query}&hl=ja&gl=JP&ceid=JP:ja"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            news_items = []
            # 获取前 3 条新闻
            for item in root.findall('./channel/item')[:3]:
                title = item.find('title').text
                link = item.find('link').text
                pub_date = item.find('pubDate').text
                news_items.append({"title": title, "link": link, "date": pub_date})
            return news_items
    except Exception as e:
        print(f"Error fetching news for {query}: {e}")
    return []

def get_japan_ecommerce_news():
    print("正在获取日本电商新闻...")
    # 搜索关键词：日本 E-commerce (EC)
    return fetch_google_news_rss("日本 EC市場")

def get_japan_tiktok_news():
    print("正在获取日本 TikTok 新闻...")
    # 搜索关键词：TikTok Japan
    return fetch_google_news_rss("TikTok 日本")

def get_general_japan_news():
    print("正在获取日本每日新闻...")
    # 搜索关键词：日本 News
    return fetch_google_news_rss("日本 ニュース")

def get_tiktok_shop_ranking_mock():
    """
    【注意】
    TikTok Shop 的实时销量 Top10 是极高价值的商业数据，
    通常受到严格的反爬虫保护，无法直接通过简单的 Python 脚本免费获取。
    
    这里演示如何构建数据结构。如果你有第三方数据 API (如 Kalodata)，可以在这里接入。
    目前这里返回的是为了演示格式的【模拟数据/相关新闻】。
    """
    print("正在获取 TikTok Shop 排名数据 (模拟/替代方案)...")
    
    # 替代方案：我们可以抓取关于"热销商品"的新闻
    ranking_news = fetch_google_news_rss("TikTok 売れ筋")
    
    # 或者是硬编码的模拟数据结构（真实场景中需要接入付费 API 或复杂爬虫）
    mock_ranking = [
        "1. 这里的真实数据需要接入专业API",
        "2. 目前自动抓取销量榜单非常困难",
        "3. 建议此处替换为手动填写的链接",
        "4. 或者关注特定的选品博主RSS",
        "5. (示例) 美妆蛋套装 - 销量: 5000+",
    ]
    
    return ranking_news, mock_ranking

# ================= 飞书发送函数 =================

def send_feishu_card(webhook_url, data_dict):
    """
    发送飞书富文本卡片消息
    """
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # 构建内容块
    elements = []
    
    # 1. 日本电商新闻
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🛒 日本电商昨日新闻**"}})
    if data_dict['ec_news']:
        txt = ""
        for i, news in enumerate(data_dict['ec_news']):
            txt += f"{i+1}. [{news['title']}]({news['link']})\n"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": txt}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "暂无更新"}})
    
    elements.append({"tag": "hr"}) # 分割线

    # 2. TikTok 新闻
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🎵 日本 TikTok 昨日新闻**"}})
    if data_dict['tiktok_news']:
        txt = ""
        for i, news in enumerate(data_dict['tiktok_news']):
            txt += f"{i+1}. [{news['title']}]({news['link']})\n"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": txt}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "暂无更新"}})

    elements.append({"tag": "hr"})

    # 3. TikTok Shop 销量 (难点)
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🏆 日本 TikTok Shop 商品趋势**"}})
    # 这里展示抓取到的相关“热销”新闻作为替代
    if data_dict['ranking_news']:
        txt = "*(由于销量数据难以直接抓取，以下展示'热销'相关资讯)*\n"
        for i, news in enumerate(data_dict['ranking_news']):
            txt += f"🔥 [{news['title']}]({news['link']})\n"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": txt}})
    else:
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "数据源暂时不可用"}})

    elements.append({"tag": "hr"})

    # 4. 日本综合新闻
    elements.append({"tag": "div", "text": {"tag": "lark_md", "content": "**🇯🇵 日本昨日综合新闻**"}})
    if data_dict['general_news']:
        txt = ""
        for i, news in enumerate(data_dict['general_news']):
            txt += f"{i+1}. [{news['title']}]({news['link']})\n"
        elements.append({"tag": "div", "text": {"tag": "lark_md", "content": txt}})
    
    # 组装最终 JSON
    card_content = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📅 日本市场早报 ({today})"
                },
                "template": "blue"
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
    ec_news = get_japan_ecommerce_news()
    tiktok_news = get_japan_tiktok_news()
    ranking_news, _ = get_tiktok_shop_ranking_mock()
    general_news = get_general_japan_news()

    # 2. 整合数据
    daily_data = {
        "ec_news": ec_news,
        "tiktok_news": tiktok_news,
        "ranking_news": ranking_news,
        "general_news": general_news
    }

    # 3. 发送
    send_feishu_card(FEISHU_WEBHOOK_URL, daily_data)

if __name__ == "__main__":
    main()
