#!/usr/bin/env python3
"""
每日AI资讯推送脚本
抓取来源：Web搜索、微博热搜、知乎、Twitter/X
推送渠道：Telegram
"""

import subprocess
import json
import re
from datetime import datetime
import os

# ============ 配置 ============
TELEGRAM_BOT_TOKEN = "7872184056:AAETmipYxa8sS8mGHFUcERcOI-DZdxNDlH4"
TELEGRAM_CHAT_ID = "1955150637"

# AI相关关键词
AI_KEYWORDS = ['AI', '人工智能', '大模型', 'ChatGPT', 'GPT', 'LLM', 'Gemini', 'Claude', 
               'OpenAI', 'DeepSeek', 'Kimi', '豆包', '文心一言', '通义千问', '智谱AI',
               '机器学习', '深度学习', '神经网络', '自动驾驶', '智能驾驶', '机器人']

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://weibo.com',
    'Accept': 'application/json',
}

def make_request(url, headers=None):
    """发送HTTP请求"""
    cmd = ['curl', '-s', url]
    if headers:
        for k, v in headers.items():
            cmd.extend(['-H', f'{k}: {v}'])
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    return result.stdout.decode('utf-8', errors='ignore')

def get_weibo_hot():
    """获取微博热搜榜 - 过滤AI相关内容"""
    try:
        data_str = make_request('https://weibo.com/ajax/side/hotSearch', HEADERS)
        data = json.loads(data_str)
        
        ai_items = []
        all_items = []
        
        # 遍历所有热搜
        for category in ['realtime', 'hotgovs', 'hotgov', 'hot']:
            category_data = data.get('data', {}).get(category)
            if not category_data:
                continue
            if isinstance(category_data, list):
                items = category_data
            else:
                items = [category_data]
            
            for item in items:
                word = item.get('word', '')
                num = item.get('num', 0)
                if word:
                    all_items.append((word, num))
                    # 检查是否包含AI关键词
                    for kw in AI_KEYWORDS:
                        if kw.lower() in word.lower():
                            ai_items.append((word, num))
                            break
        
        # 如果有AI相关内容，显示AI相关内容 + 总榜前5
        result_lines = []
        if ai_items:
            result_lines.append("【AI相关】")
            for word, num in ai_items[:3]:
                num_str = f"{num/10000:.0f}万" if num else ""
                result_lines.append(f"• {word} {num_str}")
            result_lines.append("")
        
        result_lines.append("【总榜TOP5】")
        for word, num in all_items[:5]:
            num_str = f"{num/10000:.0f}万" if num else ""
            result_lines.append(f"• {word} {num_str}")
        
        return '\n'.join(result_lines) if result_lines else "暂无数据"
    except Exception as e:
        return f"获取失败: {e}"

def get_zhihu_hot():
    """获取知乎热榜"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.zhihu.com/',
        }
        data_str = make_request('https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=5', headers)
        data = json.loads(data_str)
        
        items = []
        for item in data.get('data', [])[:5]:
            target = item.get('target', {})
            title = target.get('title', '')[:35]
            if title:
                items.append(f"• {title}")
        
        return '\n'.join(items) if items else "暂无数据"
    except Exception as e:
        return f"获取失败: {e}"

def get_ai_news():
    """通过 web search 获取 AI 新闻"""
    try:
        # 使用 web_search 命令
        result = subprocess.run(
            ['bash', '-c', 'web_search "AI artificial intelligence news 2024" 2>/dev/null | head -20 || echo ""'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
        )
        output = result.stdout.decode('utf-8', errors='ignore')
        
        # 解析web_search输出，提取标题
        lines = [l.strip() for l in output.split('\n') if l.strip()]
        items = []
        for line in lines[:5]:
            # 提取标题（通常在第一行或URL之后）
            if line and not line.startswith('http') and len(line) > 10:
                items.append(f"• {line[:50]}")
        
        return '\n'.join(items) if items else "• 查看 https://news.ycombinator.com 获得更多AI资讯"
    except:
        return "• 查看 https://news.ycombinator.com 获得更多AI资讯"

def build_report():
    """构建推送报告"""
    now = datetime.now()
    date_str = now.strftime('%Y-%m-%d')
    time_str = now.strftime('%H:%M')
    
    report = f"🤖 *每日AI资讯* 🤖\n"
    report += f"📅 {date_str} {time_str}\n"
    report += f"{'='*26}\n\n"
    
    # 微博热搜
    report += "📱 *微博热搜*\n"
    weibo = get_weibo_hot()
    report += weibo + "\n\n"
    
    # 知乎
    report += "💬 *知乎热榜·科技*\n"
    zhihu = get_zhihu_hot()
    report += zhihu + "\n\n"
    
    # AI新闻
    report += "📰 *AI快讯*\n"
    ai_news = get_ai_news()
    report += ai_news + "\n\n"
    
    # 来源链接
    report += "🔗 *来源*\n"
    report += "• 微博: https://weibo.com/hot/search\n"
    report += "• 知乎: https://www.zhihu.com/topic/19550517\n"
    report += "• HackerNews: https://news.ycombinator.com\n"
    report += "\n"
    report += "—— 由 虾里虾气 自动推送"
    
    return report

def send_telegram(text):
    """发送 Telegram 消息"""
    try:
        cmd = [
            'curl', '-s', '-X', 'POST',
            f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage',
            '-d', f'chat_id={TELEGRAM_CHAT_ID}',
            '-d', f'text={text}',
            '-d', 'parse_mode=Markdown'
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        response = json.loads(result.stdout.decode('utf-8'))
        
        if response.get('ok'):
            print("✅ Telegram 发送成功")
        else:
            print(f"❌ Telegram 发送失败: {response.get('description')}")
    except Exception as e:
        print(f"❌ Telegram 错误: {e}")

def main():
    print("=== 每日AI资讯推送 ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    report = build_report()
    print("\n--- 报告预览 ---")
    print(report[:800] + "..." if len(report) > 800 else report)
    print("--- 分割线 ---\n")
    
    send_telegram(report)
    print("\n=== 完成 ===")

if __name__ == "__main__":
    main()
