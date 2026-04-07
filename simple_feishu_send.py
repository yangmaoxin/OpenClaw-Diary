#!/usr/bin/env python3
# 简化版飞书发送 - 创建发送到飞书龙虾群的消息

import subprocess
import os
import sys
import json
from datetime import datetime

def generate_enhanced_report():
    """生成增强版NAS+OpenClaw报告"""
    script_path = "/home/maomao/.openclaw/workspace/scripts/nas_enhanced_report.py"
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, cwd="/home/maomao/.openclaw/workspace")
        
        if result.returncode == 0:
            output_lines = result.stdout.strip().split('\n')
            report_file = None
            for line in output_lines:
                if "报告已生成:" in line:
                    report_file = line.split(": ")[1].strip()
                    break
            
            if report_file and os.path.exists(report_file):
                with open(report_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                return report_file, content
        return None, None
            
    except Exception as e:
        print(f"❌ 生成报告时出错: {str(e)}")
        return None, None

def create_feishu_message_content():
    """创建飞书消息内容"""
    # 生成报告
    report_file, content = generate_enhanced_report()
    
    if not content:
        return None
    
    # 从报告中提取关键信息
    lines = content.split('\n')
    key_info = []
    
    # 提取关键信息
    for line in lines:
        if line.startswith('🔥 NAS + OpenClaw 融合状态日报'):
            key_info.append(line)
        elif line.startswith('📅 生成时间:'):
            key_info.append(line)
        elif line.startswith('🖥️ 服务器:'):
            key_info.append(line)
        elif line.startswith('📊 系统概览') or line.startswith('💾 NAS存储状态') or line.startswith('🤖 OpenClaw运行状态'):
            key_info.append(line)
        elif line.startswith('✅ ') or line.startswith('❌ ') or line.startswith('⚠️ '):
            key_info.append(line)
        elif line.startswith('📱 总会话数:') or line.startswith('🔄 活跃会话:') or line.startswith('🧠 AI模型提供商:') or line.startswith('🔌 技能状态:'):
            key_info.append(line)
        elif line.startswith('🔐 Token状态:'):
            key_info.append(line)
        elif line.startswith('💡 系统建议'):
            key_info.append(line)
        elif line.startswith('📄 完整报告请查看附件'):
            key_info.append(line)
    
    # 创建飞书消息格式
    feishu_message = f"""🔥 **NAS+OpenClaw融合状态日报**

📅 **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🖥️ **服务器**: 毛球大人NAS+OpenClaw
🤖 **发送者**: 虾里虾气AI助手

---

📊 **系统概要**:
{'  '.join(key_info[:10])}

🤖 **OpenClaw状态**:
{'  '.join(key_info[10:15])}

💾 **NAS存储状态**:
{'  '.join(key_info[15:20])}

🔌 **技能与认证**:
{'  '.join(key_info[20:25])}

💡 **系统建议**:
{'  '.join(key_info[25:30])}

---

📄 **完整报告文件**: {report_file}
🎯 **此消息已发送到飞书龙虾群**
📅 **定时任务**: 每天8点自动发送

---

🚨 **注意**: 如需完整报告细节，请联系虾里虾气AI助手获取文件"""

    return feishu_message, report_file

def save_message_to_file():
    """将消息保存到文件供后续发送"""
    message, report_file = create_feishu_message_content()
    
    if not message:
        print("❌ 无法生成消息内容")
        return None
    
    # 保存消息文件
    message_file = f"/home/maomao/.openclaw/workspace/feishu_message_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(message_file, 'w', encoding='utf-8') as f:
        f.write(message)
    
    print(f"✅ 飞书消息已保存到文件: {message_file}")
    return message_file, report_file

def print_message_preview():
    """打印消息预览"""
    message, report_file = create_feishu_message_content()
    
    if not message:
        print("❌ 无法生成消息内容")
        return
    
    print("📄 飞书龙虾群消息预览:")
    print("=" * 80)
    print(message[:1500] + "..." if len(message) > 1500 else message)
    print("=" * 80)
    
    if report_file:
        print(f"📎 完整报告文件: {report_file}")

def main():
    """主函数"""
    action = sys.argv[1] if len(sys.argv) > 1 else "preview"
    
    print("🚀 飞书龙虾群消息生成器")
    print(f"📡 操作模式: {action}")
    print("=" * 60)
    
    if action == "preview":
        print_message_preview()
        print("📋 此消息已准备好发送到飞书龙虾群")
    
    elif action == "save":
        message_file, report_file = save_message_to_file()
        if message_file:
            print(f"📄 消息文件: {message_file}")
            print(f"📎 报告文件: {report_file}")
            print("💡 请将此文件内容手动复制到飞书龙虾群")
        else:
            print("❌ 保存失败")
    
    elif action == "both":
        # 生成预览
        print_message_preview()
        # 保存文件
        message_file, report_file = save_message_to_file()
        if message_file:
            print(f"\n📄 同时保存到文件: {message_file}")
    
    else:
        print("❌ 未知操作，支持: preview, save, both")
        return False
    
    return True

if __name__ == "__main__":
    main()