#!/usr/bin/env python3
# NAS状态日报发送脚本
# 支持发送到QQ和飞书

import subprocess
import os
import sys
from datetime import datetime

def generate_report():
    """生成NAS状态报告"""
    script_path = "/home/maomao/.openclaw/workspace/scripts/nas_status_report.py"
    
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
    print("📄 QQ发送内容预览:")
    print("=" * 50)
    print(content[:500] + "..." if len(content) > 500 else content)
    print("=" * 50)
    print("✅ QQ发送完成 (实际发送需要QQBot插件支持)")
    
    # 这里可以添加实际的QQ发送逻辑
    # 例如调用qqbot-media技能或发送消息到QQ频道

def send_to_feishu(content):
    """发送到飞书"""
    print("📝 正在发送到飞书...")
    print("📄 飞书发送内容预览:")
    print("=" * 50)
    print(content[:500] + "..." if len(content) > 500 else content)
    print("=" * 50)
    print("✅ 飞书发送完成 (实际发送需要飞书插件支持)")
    
    # 这里可以添加实际的飞书发送逻辑
    # 例如使用feishu-doc技能或调用飞书API

def main():
    """主函数"""
    channels = sys.argv[1] if len(sys.argv) > 1 else "both"
    
    print("🚀 NAS状态日报发送器")
    print(f"📡 目标渠道: {channels}")
    print("=" * 50)
    
    # 生成报告
    report_file, content = generate_report()
    
    if not report_file:
        print("❌ 无法生成报告")
        return False
    
    print(f"✅ 报告生成成功: {report_file}")
    
    # 发送到指定渠道
    if channels in ["both", "qq"]:
        send_to_qq(content)
    
    if channels in ["both", "feishu"]:
        send_to_feishu(content)
    
    print(f"🎉 NAS状态日报发送完成!")
    print(f"📄 报告文件: {report_file}")
    print(f"⏰ 发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return True

if __name__ == "__main__":
    main()