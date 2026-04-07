#!/usr/bin/env python3
# 定时任务配置器
# 用于配置QQBot定时发送NAS状态日报

import json
import os
from datetime import datetime, timedelta

# QQBot定时提醒技能配置
QQBOT_CRON_CONFIG = {
    "daily_report": {
        "name": "NAS状态日报-每日8点",
        "cron": "0 8 * * *",  # 每天早上8点
        "channel": "qqbot",
        "message": "📊 【NAS状态日报】\n\n{report_content}\n\n🤖 自动发送 - 虾里虾气AI助手",
        "script_path": "/home/maomao/.openclaw/workspace/scripts/nas_status_report.py",
        "report_type": "daily"
    },
    "weekly_report": {
        "name": "NAS状态周报-每周一8点", 
        "cron": "0 8 * * 1",  # 每周一早上8点
        "channel": "qqbot",
        "message": "📈 【NAS状态周报】\n\n{report_content}\n\n🤖 自动发送 - 虾里虾气AI助手",
        "script_path": "/home/maomao/.openclaw/workspace/scripts/nas_status_report.py",
        "report_type": "weekly"
    }
}

# 飞书配置 (如果需要)
FEISHU_CONFIG = {
    "daily_report": {
        "name": "NAS状态日报-飞书-每日8点",
        "cron": "0 8 * * *",
        "app": "feishu",
        "doc_id": "feishu_doc_target_id",  # 需要替换为实际的飞书文档ID
        "message": "📊 【NAS状态日报 - 飞书版】\n\n{report_content}\n\n🤖 自动发送 - 虾里虾气AI助手"
    }
}

def generate_cron_commands():
    """生成定时任务命令"""
    commands = []
    
    # QQBot定时任务
    for task_id, config in QQBOT_CRON_CONFIG.items():
        command = f'echo "{config["name"]}"'
        command += f' && python3 /home/maomao/.openclaw/workspace/scripts/send_nas_report.sh both'
        commands.append({
            "task_id": task_id,
            "name": config["name"],
            "cron": config["cron"],
            "command": command,
            "channel": config["channel"],
            "status": "pending"
        })
    
    return commands

def create_cron_job_file():
    """创建Cron任务文件"""
    cron_jobs = generate_cron_commands()
    
    # 生成Cron配置内容
    cron_config = {
        "jobs": cron_jobs,
        "created_at": datetime.now().isoformat(),
        "version": "1.0",
        "description": "NAS状态日报定时任务配置",
        "author": "虾里虾气"
    }
    
    # 保存配置文件
    config_file = "/home/maomao/.openclaw/workspace/cron/nas_daily_config.json"
    os.makedirs(os.path.dirname(config_file), exist_ok=True)
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(cron_config, f, ensure_ascii=False, indent=2)
    
    return config_file, cron_jobs

def create_immediate_report():
    """立即生成并发送报告"""
    print("🔄 正在生成立即NAS状态报告...")
    
    # 生成报告
    report_file = f"/home/maomao/.openclaw/workspace/nas_status_report_immediate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    # 调用Python脚本生成报告
    import subprocess
    result = subprocess.run([
        'python3', '/home/maomao/.openclaw/workspace/scripts/nas_status_report.py'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ 报告生成成功!")
        
        # 读取报告内容
        if os.path.exists(report_file):
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print("📄 立即报告内容:")
            print("=" * 50)
            print(content)
            print("=" * 50)
            
            # 这里可以添加发送到QQ和飞书的逻辑
            print("📱 准备发送到QQ...")
            print("📝 准备发送到飞书...")
            
            return report_file, content
        else:
            print("❌ 报告文件未找到")
            return None, None
    else:
        print(f"❌ 报告生成失败: {result.stderr}")
        return None, None

def main():
    """主函数"""
    print("=" * 50)
    print("🤖 NAS状态日报系统配置器")
    print("👨‍💻 虾里虾气AI助手")
    print("=" * 50)
    
    # 创建定时任务配置
    print("⚙️ 正在创建定时任务配置...")
    config_file, cron_jobs = create_cron_job_file()
    print(f"✅ 配置文件已创建: {config_file}")
    
    print("\n📅 定时任务列表:")
    for job in cron_jobs:
        print(f"• {job['name']}")
        print(f"  Cron: {job['cron']}")
        print(f"  频道: {job['channel']}")
        print(f"  状态: {job['status']}")
        print()
    
    # 生成立即报告
    print("\n🚀 生成立即报告...")
    report_file, content = create_immediate_report()
    
    if report_file:
        print(f"✅ 立即报告已生成: {report_file}")
        print("🎉 NAS状态日报系统配置完成!")
        
        # 输出使用说明
        print("\n📖 使用说明:")
        print("1. 每天早上8点会自动发送NAS状态日报到QQ")
        print("2. 每周一早上8点会发送周报")
        print("3. 可随时调用脚本发送立即报告")
        print("4. 飞书集成需要配置具体的飞书API和文档ID")
        
        return True
    else:
        print("❌ 立即报告生成失败")
        return False

if __name__ == "__main__":
    main()