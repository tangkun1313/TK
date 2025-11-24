# 文件基于用户原始上传：/mnt/data/111.py
# B+ 增强版 — 规则化摘要（无 GPT、可在 GitHub Actions 直接运行）
# 功能：抓取 Google News RSS（日语） -> 规则化生成可读中文标题/摘要 -> 发送飞书卡片
# 说明：将此文件保存为 111_B_plus.py 并在 GitHub Actions 中运行。请在仓库 Secrets 中设置 FEISHU_WEBHOOK。

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

# ================= 词库与模板（可扩展） =================
# 行业/常用词映射（日文 token -> 中文）
BASE_KEYWORD_MAP = {
    # 行业/领域
    "自動車": "汽车", "自動車業界": "汽车行业", "家電": "家电", "金融": "金融", "経済": "经济",
    "市場": "市场", "販売": "销售", "販売台数": "销量", "増加": "增加", "減少": "减少",
    "回復": "回升", "予測": "预测", "発表": "发布", "速報": "快讯", "発生": "发生",
    "地震": "地震", "事故": "事故", "調査": "调查", "開始": "开始", "終了": "结束",
    "政府": "政府", "企業": "企业", "報告": "报告", "公表": "公布", "割引": "折扣",
    # 品类/生活相关
    "コスメ": "美妆", "スキンケア": "护肤", "食品": "食品", "グルメ": "美食", "アウトドア": "户外",
    "ベビー": "婴儿", "キッズ": "儿童",
    # 指示词
    "最新": "最新", "注目": "关注", "人気": "热门", "ランキング": "榜单",
}

# 摘要模板
TEMPLATES = {
    'publish': "{subject}{time}发布{obj}。",
    'trend': "{subject}{time}{field}{trend}。",
    'sales': "{subject}{time}{field}销量{trend}。",
    'event': "{subject}{time}发生{event}，最新情况。",
    'fallback': "{subject}{time}相关消息更新。"
}

# 用于清洗不需要的媒体/作者关键词
NOISE_WORDS = [
    '朝日', '共同通信', '日経', 'NHK', 'スポーツ', '記者', '提供', 'PR TIMES', '配信', '写真']

# 时间词正则
TIME_PATTERNS = [
    (re.compile(r'(\d{4})年'), '{year}年'),
    (re.compile(r'(\d{1,2})月'), '{month}月'),
    (re.compile(r'\b(10月|11月|12月)\b'), '{month}'),
]

# ================= 辅助函数 =================

def safe_text(text):
    return text if text else ""


def remove_noise(text):
    """移除记名媒体、PR tag、奇怪的括号与尾部来源"""
    if not text:
        return ""
    t = re.sub(r' - [^\-\s]+$', '', text)
    t = re.sub(r'\(.*?\)', ' ', t)
    t = re.sub(r'【.*?】', ' ', t)
    # 去掉常见媒体/作者词
    for w in NOISE_WORDS:
        t = t.replace(w, ' ')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def extract_time(text):
    """尝试从标题中提取时间信息，返回格式化字符串：如 ' 10月' 或 ' 2025年' 等"""
    if not text:
        return ''
    # 优先查找 年/月 模式
    m = re.search(r'(\d{4})年', text)
    if m:
        return f" {m.group(1)}年"
    m2 = re.search(r'(\d{1,2})月', text)
    if m2:
        return f" {m2.group(1)}月"
    # 无时间信息返回空
    return ''


def keep_chinese_hanzi_and_digits(text):
    """保留汉字/数字/英文(短词)，去掉假名和多余符号，便于后续关键词匹配"""
    if not text:
        return ''
    # 先删除片假名和平假名
    t = re.sub(r'[ぁ-んァ-ン]', ' ', text)
    # 删除特殊符号但保留中文、英文、数字
    t = re.sub(r'[^0-9A-Za-z\u4e00-\u9fa5 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def map_keywords(tokens):
    """把 tokens（汉字或词）映射为中文友好词，如果没有映射就原样返回"""
    mapped = []
    for t in tokens:
        if not t:
            continue
        if t in BASE_KEYWORD_MAP:
            mapped.append(BASE_KEYWORD_MAP[t])
        else:
            mapped.append(t)
    # 去重并返回
    return list(dict.fromkeys(mapped))


def classify_and_assemble(mapped_tokens, raw_text):
    """根据关键词与原始文本，选择模板生成中文摘要"""
    subject = ''
    obj = ''
    field = ''
    trend = ''
    event = ''
    time_str = extract_time(raw_text)

    # 简单规则：从 mapped_tokens 中寻找主体/领域/趋势词
    # 主体优先选择：日本/政府/企业/机构/地名
    for t in mapped_tokens:
        if t in ('日本', '日本国内', '东京', '大阪'):
            subject = t
            break
    if not subject and mapped_tokens:
        subject = mapped_tokens[0]

    # 领域/对象选择
    for t in mapped_tokens:
        if t in ('汽车', '汽车行业', '家电', '金融', '经济', '市场', '美妆', '护肤', '食品'):
            field = t
            break

    # 趋势词
    for t in mapped_tokens:
        if t in ('增加', '增长', '回升', '下滑', '减少', '回落'):
            trend = '回升' if t in ('回復','回升') else t
            break

    # 事件词（事故/发布/报告）
    for t in mapped_tokens:
        if t in ('发布', '公布', '报告', '快讯', '发生', '事故', '地震', '调查', '开始'):
            event = t
            break

    # 对象（商品/销量等）
    if '销量' in mapped_tokens or '销售' in mapped_tokens:
        obj = '销量'

    # 选择模板
    if event and event in ('发布', '公布', '报告'):
        # publish
        obj_str = obj if obj else (field if field else '')
        return TEMPLATES['publish'].format(subject=subject, time=time_str, obj=obj_str)
    if obj == '销量' or field in ('汽车','家电','护肤','美妆','食品'):
        # sales/trend
        t_word = trend if trend else '变化'
        return TEMPLATES['sales'].format(subject=subject, time=time_str, field=field if field else '', trend=t_word)
    if event in ('事故','地震','发生'):
        return TEMPLATES['event'].format(subject=subject, time=time_str, event=event)

    # fallback：尝试用前几个关键词组合
    # 组合前 4 个关键词，保证不空
    comb = ''.join(mapped_tokens[:4]) if mapped_tokens else subject
    return TEMPLATES['fallback'].format(subject=comb, time=time_str)


def normalize_japanese_title_to_chinese_better(text):
    """增强版标题规范化主函数：结合所有步骤，输出可读中文短句"""
    if not text:
        return '内容缺失'

    raw = safe_text(text)
    t = remove_noise(raw)
    t2 = keep_chinese_hanzi_and_digits(t)

    # tok: 提取连贯的中文/汉字 token（按连续汉字序列分割）
    tokens = re.findall(r'[\u4e00-\u9fa5]+', t2)

    # 映射词库
    mapped = map_keywords(tokens)

    # 如果映射结果为空，作为 fallback 返回一个简化干净版的原文（去掉假名与多余符号）
    if not mapped:
        fallback = t2[:60] + ('...' if len(t2) > 60 else '')
        return fallback + '。'

    # 生成最终摘要句
    summary = classify_and_assemble(mapped, raw)

    # 清理重复、连续相似词
    summary = re.sub(r'(。){2,}', '。', summary)
    summary = re.sub(r'\s+', ' ', summary).strip()

    return summary

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
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=20)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)

            for item in root.findall('./channel/item')[:limit]:
                title_jp = safe_text(item.find('title').text)
                link = safe_text(item.find('link').text)

                title_cn = normalize_japanese_title_to_chinese_better(title_jp)

                news_items.append({
                    'title_jp': title_jp,
                    'title_cn': title_cn,
                    'link': link
                })

            return news_items

        except Exception as e:
            # 打印异常以便 GitHub Actions 日志查看
            print(f"抓取失败 (query={query}) 第 {attempt+1} 次: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(INITIAL_BACKOFF * (2 ** attempt))

    return []

# ================= 数据抓取模块 =================

def get_tiktok_sales_ranking():
    return fetch_google_news_rss("TikTok 売れ筋 商品", limit=5)

def get_tiktok_hashtag_trends():
    items = fetch_google_news_rss("TikTok ハッシュタグ トレンド", limit=5, is_jp_query=False)
    for it in items:
        it['title_cn'] = None
    return items

def get_rakuten_ranking_info():
    queries = [
        "楽天市場 ランキング 総合",
        "楽天市場 ランキング 美容",
        "楽天市場 ランキング グルメ",
        "楽天市場 ランキング ファッション",
        "楽天市場 ランキング 家電"
    ]
    results = []
    for q in queries:
        results.extend(fetch_google_news_rss(q, limit=1))
    return results


def get_yahoo_ranking_info():
    queries = [
        "Yahoo!ショッピング ランキング",
        "Yahoo!ショッピング 売れ筋",
        "Yahoo!ショッピング 人気",
        "Yahoo!ショッピング 注目",
        "Yahoo!ショッピング 家電"
    ]
    results = []
    for q in queries:
        results.extend(fetch_google_news_rss(q, limit=1))
    return results


def get_japan_real_time_news():
    return fetch_google_news_rss("日本 国内 最新 ニュース", limit=JAPAN_NEWS_LIMIT)

# ================= 飞书发送 =================

def send_feishu_card(webhook_url, data):
    today = datetime.datetime.now().strftime('%Y-%m-%d')

    def make_list_text(items, is_translated=True):
        if not items:
            return '暂无数据'
        txt = ''
        for i, item in enumerate(items):
            if is_translated:
                txt += f"{i+1}. **{item['title_cn']}** [查看原文]({item['link']})\n"
            else:
                txt += f"{i+1}. [{item['title_jp']}]({item['link']})\n"
        return txt

    card = {
        'msg_type': 'interactive',
        'card': {
            'header': {
                'title': {'tag': 'plain_text', 'content': f'🇯🇵 日本电商日报 {today}'},
                'template': 'blue'
            },
            'elements': [
                {'tag':'div','text':{'tag':'lark_md','content':'🔥 **1. 日本 TikTok 昨日销量榜单**'}},
                {'tag':'div','text':{'tag':'lark_md','content':make_list_text(data['tiktok_sales'])}},
                {'tag':'hr'},
                {'tag':'div','text':{'tag':'lark_md','content':'🎵 **2. TikTok 热门标签词**'}},
                {'tag':'div','text':{'tag':'lark_md','content':make_list_text(data['tiktok_hashtag'], is_translated=False)}},
                {'tag':'hr'},
                {'tag':'div','text':{'tag':'lark_md','content':'🔴 **3. 乐天精选榜单**'}},
                {'tag':'div','text':{'tag':'lark_md','content':make_list_text(data['rakuten_ranking'])}},
                {'tag':'hr'},
                {'tag':'div','text':{'tag':'lark_md','content':'🟢 **4. 雅虎购物精选榜单**'}},
                {'tag':'div','text':{'tag':'lark_md','content':make_list_text(data['yahoo_ranking'])}},
                {'tag':'hr'},
                {'tag':'div','text':{'tag':'lark_md','content':'📰 **5. 日本实时新闻**'}},
                {'tag':'div','text':{'tag':'lark_md','content':make_list_text(data['japan_news'])}},
            ]
        }
    }

    try:
        resp = requests.post(webhook_url, headers={'Content-Type':'application/json'}, data=json.dumps(card))
        print('飞书发送响应：', resp.status_code, resp.text)
    except Exception as e:
        print('发送飞书失败：', e)

# ================= 主程序 =================

def main():
    if not FEISHU_WEBHOOK_URL:
        print('错误：未设置飞书 Webhook（请在 GitHub 仓库 Secrets 中设置 FEISHU_WEBHOOK）')
        return

    data = {
        'tiktok_sales': get_tiktok_sales_ranking(),
        'tiktok_hashtag': get_tiktok_hashtag_trends(),
        'rakuten_ranking': get_rakuten_ranking_info(),
        'yahoo_ranking': get_yahoo_ranking_info(),
        'japan_news': get_japan_real_time_news()
    }

    send_feishu_card(FEISHU_WEBHOOK_URL, data)


if __name__ == '__main__':
    main()
