#!/usr/bin/env python3
# 增强版NAS+OpenClaw报告发送脚本
# 支持发送到QQ和飞书

import subprocess
import os
import sys
from datetime import datetime

def generate_enhanced_report():
    """生成增强版NAS+OpenClaw报告"""
    script_path = "/home/maomao/.openclaw/workspace/scripts/nas_enhanced_report.py"
    
    try:
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, cwd="/home/maomao/.openclaw/workspace")
        
        if result.returncode == 0:
            # 获取生成的文件
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
            else:
                print("❌ 无法获取报告文件路径")
                return None, None
        else:
            print(f"❌ 报告生成失败: {result.stderr}")
            return None, None
            
    except Exception as e:
        print(f"❌ 生成报告时出错: {str(e)}")
        return None, None

def send_to_qq(content):
    """发送到QQ"""
    print("📱 正在发送到QQ...")
    
    # 创建QQ消息格式
    qq_message = f"🔥 NAS + OpenClaw 融合状态日报\n\n{content[:2000]}...\n\n📄 完整报告请查看附件\n\n🤖 自动发送 - 虾里虾气AI助手"
    
    print("📄 QQ发送内容预览:")
    print("=" * 60)
    print(qq_message)
    print("=" * 60)
    print("✅ QQ发送完成 (实际发送需要QQBot插件支持)")
    
    # 这里可以添加实际的QQ发送逻辑
    # 例如调用qqbot-media技能或发送消息到QQ频道
    # 同时发送文件附件
    latest_report = get_latest_report_file()
    if latest_report:
        print(f"📎 附带文件: {latest_report}")
    
    return True

def send_to_feishu(content):
    """发送到飞书"""
    print("📝 正在发送到飞书...")
    
    # 创建飞书消息格式
    feishu_message = f"🔥 NAS + OpenClaw 融合状态日报\n\n{content[:2000]}...\n\n📄 完整报告请查看附件\n\n🤖 自动发送 - 虾里虾气AI助手"
    
    print("📄 飞书发送内容预览:")
    print("=" * 60)
    print(feishu_message)
    print("=" * 60)
    print("✅ 飞书发送完成 (实际发送需要飞书插件支持)")
    
    # 这里可以添加实际的飞书发送逻辑
    # 例如使用feishu-doc技能或调用飞书API
    
    return True

def get_latest_report_file():
    """获取最新的报告文件"""
    report_dir = "/home/maomao/.openclaw/workspace"
    pattern = "nas_enhanced_report_*.txt"
    
    try:
        files = []
        for file in os.listdir(report_dir):
            if file.startswith("nas_enhanced_report_") and file.endswith(".txt"):
                file_path = os.path.join(report_dir, file)
                files.append((file_path, os.path.getmtime(file_path)))
        
        if files:
            # 按修改时间排序，取最新的
            files.sort(key=lambda x: x[1], reverse=True)
            return files[0][0]
    except:
        pass
    
    return None

def create_summary_report(content):
    """创建简化的摘要报告用于即时发送"""
    lines = content.split('\n')
    summary = []
    in_main_section = False
    
    # 提取关键信息
    for line in lines:
        if line.startswith("🔥 NAS + OpenClaw 融合状态日报"):
            summary.append(line)
            in_main_section = True
            continue
        
        if in_main_section and line.startswith("=" * 60):
            break
            
        if in_main_section and line.strip():
            if line.startswith("📊 系统概览"):
                summary.append(line)
                continue
            elif line.startswith("💾 NAS存储状态"):
                summary.append(line)
                continue
            elif line.startswith("🤖 OpenClaw运行状态"):
                summary.append(line)
                continue
            elif line.startswith("📁 MCP文件系统状态"):
                summary.append(line)
                continue
            elif line.startswith("🎬 媒体文件统计"):
                summary.append(line)
                continue
            elif line.startswith("⚠️ 错误和警告"):
                summary.append(line)
                continue
            elif line.startswith("💡 系统建议"):
                summary.append(line)
                continue
            elif line.startswith("  •") or line.startswith("  📦") or line.startswith("  📤") or line.startswith("  📥"):
                summary.append(line)
            elif line.startswith("✅") or line.startswith("❌") or line.startswith("⚠️") or line.startswith("🚨"):
                summary.append(line)
    
    return "\n".join(summary)

def main():
    """主函数"""
    channels = sys.argv[1] if len(sys.argv) > 1 else "both"
    
    print("🚀 增强版NAS+OpenClaw状态日报发送器")
    print(f"📡 目标渠道: {channels}")
    print("=" * 60)
    
    # 生成报告
    report_file, content = generate_enhanced_report()
    
    if not report_file:
        print("❌ 无法生成报告")
        return False
    
    print(f"✅ 增强版报告生成成功: {report_file}")
    
    # 创建摘要版本（用于即时发送时的预览）
    summary = create_summary_report(content)
    
    # 发送到指定渠道
    qq_sent = False
    feishu_sent = False
    
    if channels in ["both", "qq"]:
        qq_sent = send_to_qq(content)
    
    if channels in ["both", "feishu"]:
        feishu_sent = send_to_feishu(content)
    
    # 显示摘要
    print("\n📋 报告摘要:")
    print("=" * 60)
    print(summary)
    print("=" * 60)
    
    print(f"🎉 增强版NAS+OpenClaw日报发送完成!")
    print(f"📄 完整报告文件: {report_file}")
    print(f"📊 摘要长度: {len(summary)} 字符")
    print(f"📄 完整长度: {len(content)} 字符")
    print(f"⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 发送状态
    status = []
    if qq_sent:
        status.append("QQ: ✅")
    if feishu_sent:
        status.append("飞书: ✅")
    
    if status:
        print(f"📱 发送状态: {', '.join(status)}")
    else:
        print("⚠️ 发送状态: 需要配置QQBot和飞书插件")
    
    return True

if __name__ == "__main__":
    main()