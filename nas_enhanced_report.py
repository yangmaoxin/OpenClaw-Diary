#!/usr/bin/env python3
# 增强版NAS+OpenClaw融合状态日报 (无psutil版本)
# 作者：虾里虾气
# 版本：2.0 - 轻量版

import os
import json
import subprocess
import re
import time
from datetime import datetime, timedelta
import glob

class OpenClawStatusChecker:
    """OpenClaw状态检查器"""
    
    def __init__(self, openclaw_path="/home/maomao/.openclaw"):
        self.openclaw_path = openclaw_path
        self.workspace_path = "/home/maomao/.openclaw/workspace"
        
    def get_openclaw_status(self):
        """获取OpenClaw运行状态"""
        status = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "process_status": {},
            "gateway_status": {},
            "sessions_status": {},
            "models_status": {},
            "plugins_status": {},
            "errors": [],
            "warnings": [],
            "info": {}
        }
        
        # 1. 检查进程状态
        try:
            # 使用ps命令检查进程
            result = subprocess.run(['ps', 'aux'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                openclaw_processes = []
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if 'openclaw' in line.lower() and 'grep' not in line:
                        openclaw_processes.append(line.split()[1])  # 获取PID
                        
                status["process_status"] = {
                    "found": len(openclaw_processes) > 0,
                    "count": len(openclaw_processes),
                    "pids": openclaw_processes,
                    "details": [
                        f"找到 {len(openclaw_processes)} 个OpenClaw相关进程",
                        f"PIDs: {', '.join(openclaw_processes)}"
                    ]
                }
            else:
                status["process_status"] = {"found": False, "error": result.stderr}
                
        except Exception as e:
            status["errors"].append(f"进程检查失败: {str(e)}")
            status["process_status"] = {"found": False, "error": str(e)}
        
        # 2. 检查网关状态
        try:
            result = subprocess.run(['openclaw', 'gateway', 'status'], 
                                  capture_output=True, text=True, cwd=self.openclaw_path)
            if result.returncode == 0:
                status["gateway_status"] = {
                    "running": True,
                    "output": result.stdout,
                    "config_loaded": True
                }
            else:
                status["gateway_status"] = {
                    "running": False,
                    "error": result.stderr
                }
                status["errors"].append(f"网关错误: {result.stderr}")
                
        except FileNotFoundError:
            status["gateway_status"] = {"running": False, "error": "openclaw命令未找到"}
            status["errors"].append("openclaw命令未找到，可能未正确安装")
        except Exception as e:
            status["gateway_status"] = {"running": False, "error": str(e)}
            status["errors"].append(f"网关检查失败: {str(e)}")
        
        # 3. 检查会话状态
        try:
            result = subprocess.run(['openclaw', 'sessions', 'list'], 
                                  capture_output=True, text=True, cwd=self.openclaw_path)
            if result.returncode == 0:
                # 解析会话列表
                session_count = 0
                active_sessions = []
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '|' in line and line.strip():
                        parts = line.split('|')
                        if len(parts) >= 3:
                            session_id = parts[0].strip()
                            session_name = parts[1].strip()
                            session_status = parts[2].strip()
                            session_count += 1
                            if "active" in session_status.lower() or "running" in session_status.lower():
                                active_sessions.append(f"{session_name}({session_id})")
                
                status["sessions_status"] = {
                    "total_sessions": session_count,
                    "active_sessions": len(active_sessions),
                    "active_list": active_sessions,
                    "raw_output": result.stdout[:500] + "..." if len(result.stdout) > 500 else result.stdout
                }
            else:
                status["sessions_status"] = {
                    "total_sessions": 0,
                    "active_sessions": 0,
                    "error": result.stderr
                }
                
        except Exception as e:
            status["sessions_status"] = {"error": str(e)}
            status["errors"].append(f"会话检查失败: {str(e)}")
        
        # 4. 检查模型状态
        try:
            config_file = os.path.join(self.openclaw_path, "openclaw.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                models = config.get("models", {})
                providers = models.get("providers", {})
                
                status["models_status"] = {
                    "providers_count": len(providers),
                    "providers": list(providers.keys()),
                    "primary_model": config.get("agents", {}).get("defaults", {}).get("model", {}).get("primary", "未知"),
                    "total_models": sum(len(p.get("models", [])) for p in providers.values())
                }
            else:
                status["models_status"] = {"error": "配置文件未找到"}
                status["errors"].append("openclaw.json配置文件未找到")
                
        except Exception as e:
            status["models_status"] = {"error": str(e)}
            status["errors"].append(f"模型检查失败: {str(e)}")
        
        # 5. 检查插件状态
        try:
            result = subprocess.run(['openclaw', 'skills', 'check'], 
                                  capture_output=True, text=True, cwd=self.openclaw_path)
            if result.returncode == 0:
                # 解析技能检查结果
                skill_stats = {}
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if "Total:" in line:
                        skill_stats["total"] = int(re.search(r'Total:\s*(\d+)', line).group(1))
                    elif "✓ Eligible:" in line:
                        skill_stats["eligible"] = int(re.search(r'✓ Eligible:\s*(\d+)', line).group(1))
                    elif "⏸ Disabled:" in line:
                        skill_stats["disabled"] = int(re.search(r'⏸ Disabled:\s*(\d+)', line).group(1))
                    elif "🚫 Blocked by allowlist:" in line:
                        skill_stats["blocked"] = int(re.search(r'🚫 Blocked by allowlist:\s*(\d+)', line).group(1))
                    elif "✗ Missing requirements:" in line:
                        skill_stats["missing"] = int(re.search(r'✗ Missing requirements:\s*(\d+)', line).group(1))
                
                status["plugins_status"] = {
                    "skill_stats": skill_stats,
                    "raw_output": result.stdout[:1000] + "..." if len(result.stdout) > 1000 else result.stdout,
                    "ready_skills": []
                }
                
                # 检查具体就绪的技能
                ready_skills_section = False
                for line in result.stdout.split('\n'):
                    if "Ready to use:" in line:
                        ready_skills_section = True
                        continue
                    elif ready_skills_section and line.strip() and "Missing requirements:" in line:
                        break
                    elif ready_skills_section and line.strip():
                        # 提取技能名称
                        skill_match = re.search(r'✓\s+([📦⏰📸🎞️🌤️🔐🧠💡\w\-]+)', line)
                        if skill_match:
                            status["plugins_status"]["ready_skills"].append(skill_match.group(1))
                
            else:
                status["plugins_status"] = {"error": result.stderr}
                
        except Exception as e:
            status["plugins_status"] = {"error": str(e)}
            status["errors"].append(f"插件检查失败: {str(e)}")
        
        # 6. 检查Token和认证状态
        try:
            config_file = os.path.join(self.openclaw_path, "openclaw.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                auth_profiles = config.get("auth", {}).get("profiles", {})
                status["token_status"] = {
                    "auth_profiles_count": len(auth_profiles),
                    "providers": list(auth_profiles.keys()),
                    "profile_details": {k: {"provider": v.get("provider", "未知"), "mode": v.get("mode", "未知")} 
                                     for k, v in auth_profiles.items()}
                }
                
                # 检查插件配置
                channels = config.get("channels", {})
                status["plugin_channels"] = {
                    "enabled_channels": [k for k, v in channels.items() if v.get("enabled", False)],
                    "disabled_channels": [k for k, v in channels.items() if not v.get("enabled", False)]
                }
                
        except Exception as e:
            status["token_status"] = {"error": str(e)}
            status["errors"].append(f"Token检查失败: {str(e)}")
        
        # 7. 检查日志和错误
        log_files = [
            os.path.join(self.openclaw_path, "logs", "*.log"),
            os.path.join(self.openclaw_path, "*.log"),
            os.path.join(self.workspace_path, "*.log")
        ]
        
        recent_errors = []
        for log_pattern in log_files:
            for log_file in glob.glob(log_pattern):
                try:
                    # 检查文件修改时间（最近24小时）
                    if os.path.getmtime(log_file) > time.time() - 86400:
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                            for line in lines[-20:]:  # 最后20行
                                if any(word in line.lower() for word in ['error', 'failed', 'exception', 'warn']):
                                    recent_errors.append(f"{os.path.basename(log_file)}: {line.strip()}")
                except:
                    pass
        
        if recent_errors:
            status["recent_errors"] = recent_errors[:10]  # 只保留最近10个错误
            status["errors"].append(f"发现{len(recent_errors)}个近期错误")
        
        return status

class EnhancedNASStatusChecker:
    """增强版NAS状态检查器"""
    
    def __init__(self):
        self.volume_path = "/vol1/1000"
        self.workspace_path = "/home/maomao/.openclaw/workspace"
        
    def get_nas_status(self):
        """获取NAS状态信息"""
        status = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "server_name": "毛球大人NAS+OpenClaw",
            "volume_info": {},
            "media_files": {},
            "directories": {},
            "filesystem_mcp": {},
            "system_info": {}
        }
        
        # 1. 获取卷信息
        try:
            vol1_info = os.statvfs("/vol1")
            status["volume_info"] = {
                "total_space": vol1_info.f_blocks * vol1_info.f_frsize,
                "free_space": vol1_info.f_bfree * vol1_info.f_frsize,
                "used_space": (vol1_info.f_blocks - vol1_info.f_bfree) * vol1_info.f_frsize,
                "usage_percent": ((vol1_info.f_blocks - vol1_info.f_bfree) / vol1_info.f_blocks) * 100
            }
        except Exception as e:
            status["volume_info"] = {"error": str(e)}
        
        # 2. 文件系统MCP状态
        try:
            config_file = os.path.join(self.workspace_path, "config", "mcporter.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    mcp_config = json.load(f)
                
                servers = mcp_config.get("mcpServers", {})
                status["filesystem_mcp"] = {
                    "servers_count": len(servers),
                    "servers": list(servers.keys()),
                    "filesystem_config": servers.get("filesystem", {}),
                    "allowed_directories": []
                }
                
                # 检查允许的目录
                try:
                    result = subprocess.run(['npx', 'mcporter', 'call', 'filesystem.list_allowed_directories'], 
                                          capture_output=True, text=True, cwd=self.workspace_path)
                    if result.returncode == 0:
                        status["filesystem_mcp"]["allowed_directories"] = result.stdout.strip().split('\n')
                except:
                    status["filesystem_mcp"]["allowed_directories"] = ["检查失败"]
                    
        except Exception as e:
            status["filesystem_mcp"] = {"error": str(e)}
        
        # 3. 媒体文件统计
        try:
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.flv', '.wmv', '.webm', '.rmvb']
            audio_extensions = ['.mp3', '.flac', '.wav', '.aac', '.ogg', '.m4a', '.wma']
            
            video_count = 0
            video_size = 0
            audio_count = 0
            audio_size = 0
            
            for root, dirs, files in os.walk("/vol1/1000"):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        file_size = os.path.getsize(file_path)
                        
                        if any(file.lower().endswith(ext) for ext in video_extensions):
                            video_count += 1
                            video_size += file_size
                        
                        if any(file.lower().endswith(ext) for ext in audio_extensions):
                            audio_count += 1
                            audio_size += file_size
                            
                    except Exception:
                        pass
            
            status["media_files"] = {
                "video_files": {
                    "count": video_count,
                    "total_size_bytes": video_size,
                    "total_size_gb": round(video_size / (1024**3), 2),
                    "note": "主要是《我的少年时代》4K剧集"
                },
                "audio_files": {
                    "count": audio_count,
                    "total_size_bytes": audio_size,
                    "total_size_gb": round(audio_size / (1024**3), 2),
                    "note": "主要是Docker系统音效文件"
                }
            }
            
        except Exception as e:
            status["media_files"] = {"error": str(e)}
        
        # 4. 目录统计
        try:
            directories = {}
            for item in os.listdir("/vol1/1000"):
                if os.path.isdir(os.path.join("/vol1/1000", item)):
                    try:
                        dir_size = sum(os.path.getsize(os.path.join(root, file)) 
                                     for root, _, files in os.walk(os.path.join("/vol1/1000", item)) 
                                     for file in files)
                        directories[item] = {
                            "type": "directory",
                            "size_bytes": dir_size,
                            "size_gb": round(dir_size / (1024**3), 2)
                        }
                    except Exception:
                        directories[item] = {"type": "directory", "error": "无法统计"}
            
            status["directories"] = directories
            
        except Exception as e:
            status["directories"] = {"error": str(e)}
        
        # 5. 系统信息 (使用标准命令)
        try:
            # 获取系统信息
            result = subprocess.run(['uname', '-a'], capture_output=True, text=True)
            system_info = result.stdout.strip() if result.returncode == 0 else "未知"
            
            # 获取运行时间
            result = subprocess.run(['uptime'], capture_output=True, text=True)
            uptime = result.stdout.strip() if result.returncode == 0 else "未知"
            
            # 获取磁盘使用情况
            result = subprocess.run(['df', '-h'], capture_output=True, text=True)
            disk_info = result.stdout.strip() if result.returncode == 0 else "未知"
            
            status["system_info"] = {
                "system_full_info": system_info,
                "uptime": uptime,
                "disk_usage": disk_info,
                "architecture": system_info.split()[4] if len(system_info.split()) > 4 else "未知"
            }
            
        except Exception as e:
            status["system_info"] = {"error": str(e)}
        
        return status

def generate_enhanced_report():
    """生成增强版报告"""
    
    # 检查OpenClaw状态
    openclaw_checker = OpenClawStatusChecker()
    openclaw_status = openclaw_checker.get_openclaw_status()
    
    # 检查NAS状态
    nas_checker = EnhancedNASStatusChecker()
    nas_status = nas_checker.get_nas_status()
    
    # 生成融合报告
    report = []
    
    # 标题
    report.append("=" * 60)
    report.append(f"🔥 NAS + OpenClaw 融合状态日报")
    report.append(f"📅 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"🖥️ 服务器: {nas_status['server_name']}")
    report.append("=" * 60)
    report.append("")
    
    # 1. 系统概览
    report.append("📊 系统概览")
    report.append("-" * 40)
    report.append(f"🖥️ 系统信息: {nas_status['system_info'].get('system_full_info', '未知')}")
    report.append(f"🔄 运行时间: {nas_status['system_info'].get('uptime', '未知')}")
    report.append(f"💿 架构: {nas_status['system_info'].get('architecture', '未知')}")
    report.append("")
    
    # 2. NAS存储状态
    report.append("💾 NAS存储状态")
    report.append("-" * 40)
    if "error" not in nas_status["volume_info"]:
        vol_info = nas_status["volume_info"]
        total_gb = vol_info["total_space"] / (1024**3)
        free_gb = vol_info["free_space"] / (1024**3)
        used_gb = vol_info["used_space"] / (1024**3)
        
        report.append(f"📦 总容量: {total_gb:.1f} GB")
        report.append(f"📤 已使用: {used_gb:.1f} GB ({vol_info['usage_percent']:.1f}%)")
        report.append(f"📥 可用空间: {free_gb:.1f} GB")
        
        # 存储状态判断
        if vol_info['usage_percent'] > 90:
            report.append("🚨 存储空间严重不足！")
        elif vol_info['usage_percent'] > 80:
            report.append("⚠️ 存储空间紧张")
        else:
            report.append("✅ 存储空间正常")
    else:
        report.append("❌ 无法获取NAS存储信息")
    report.append("")
    
    # 3. OpenClaw运行状态
    report.append("🤖 OpenClaw运行状态")
    report.append("-" * 40)
    
    # 进程状态
    if openclaw_status["process_status"].get("found"):
        report.append("✅ OpenClaw进程运行中")
        if openclaw_status["process_status"].get("details"):
            for detail in openclaw_status["process_status"]["details"][:2]:
                report.append(f"  • {detail}")
    else:
        report.append("❌ OpenClaw进程未运行")
    
    # 网关状态
    if openclaw_status["gateway_status"].get("running"):
        report.append("✅ 网关服务运行正常")
    else:
        report.append(f"❌ 网关服务异常: {openclaw_status['gateway_status'].get('error', '未知错误')}")
    
    # 会话状态
    sessions = openclaw_status["sessions_status"]
    report.append(f"📱 会话总数: {sessions.get('total_sessions', 0)}")
    report.append(f"🔄 活跃会话: {sessions.get('active_sessions', 0)}")
    if sessions.get("active_list"):
        report.append("  活跃会话列表:")
        for session in sessions["active_list"][:3]:  # 只显示前3个
            report.append(f"    • {session}")
    
    # 模型状态
    models = openclaw_status["models_status"]
    report.append(f"🧠 AI模型提供商: {models.get('providers_count', 0)}个")
    report.append(f"🎯 主要模型: {models.get('primary_model', '未知')}")
    report.append(f"📊 模型总数: {models.get('total_models', 0)}个")
    
    # 插件状态
    skills = openclaw_status["plugins_status"].get("skill_stats", {})
    if skills:
        report.append(f"🔌 技能状态:")
        report.append(f"  • 总计技能: {skills.get('total', 0)}个")
        report.append(f"  • 就绪技能: {skills.get('eligible', 0)}个")
        report.append(f"  • 缺失依赖: {skills.get('missing', 0)}个")
        report.append(f"  • 技能可用率: {skills.get('eligible', 0)/skills.get('total', 1)*100:.1f}%")
        
        # 显示就绪的具体技能
        ready_skills = openclaw_status["plugins_status"].get("ready_skills", [])
        if ready_skills:
            report.append(f"  • 就绪技能列表:")
            for skill in ready_skills[:5]:  # 只显示前5个
                report.append(f"    - {skill}")
    
    # Token状态
    token_status = openclaw_status.get("token_status", {})
    if token_status:
        report.append(f"🔐 Token状态:")
        report.append(f"  • 认证配置: {token_status.get('auth_profiles_count', 0)}个")
        report.append(f"  • 已启用渠道: {len(token_status.get('plugin_channels', {}).get('enabled_channels', []))}个")
        enabled_channels = token_status.get("plugin_channels", {}).get("enabled_channels", [])
        if enabled_channels:
            report.append(f"  • 启用渠道: {', '.join(enabled_channels)}")
    
    report.append("")
    
    # 4. MCP文件系统状态
    mcp = nas_status["filesystem_mcp"]
    report.append("📁 MCP文件系统状态")
    report.append("-" * 40)
    
    if "error" not in mcp:
        report.append(f"✅ MCP服务器数量: {mcp.get('servers_count', 0)}个")
        report.append(f"🔗 已配置服务器: {', '.join(mcp.get('servers', []))}")
        report.append("🎯 允许访问目录:")
        for directory in mcp.get('allowed_directories', []):
            if directory.strip():
                report.append(f"  • {directory}")
    else:
        report.append(f"❌ MCP配置错误: {mcp.get('error', '未知错误')}")
    report.append("")
    
    # 5. 媒体文件统计
    media = nas_status["media_files"]
    if "error" not in media:
        report.append("🎬 媒体文件统计")
        report.append("-" * 40)
        
        if "video_files" in media:
            video = media["video_files"]
            report.append(f"📹 视频文件: {video['count']} 个")
            report.append(f"📦 视频总大小: {video['total_size_gb']} GB")
            report.append(f"📝 备注: {video['note']}")
        
        if "audio_files" in media:
            audio = media["audio_files"]
            report.append(f"🎵 音频文件: {audio['count']} 个")
            report.append(f"📦 音频总大小: {audio['total_size_gb']} GB")
            report.append(f"📝 备注: {audio['note']}")
    report.append("")
    
    # 6. 目录结构分析
    directories = nas_status["directories"]
    if "error" not in directories:
        report.append("📁 目录结构分析")
        report.append("-" * 40)
        
        for dir_name, dir_info in directories.items():
            if isinstance(dir_info, dict) and "size_gb" in dir_info:
                size_gb = dir_info["size_gb"]
                if size_gb > 0:
                    report.append(f"📂 {dir_name}: {size_gb} GB")
                else:
                    report.append(f"📁 {dir_name}: 空目录")
    
    report.append("")
    
    # 7. 错误和警告
    report.append("⚠️ 错误和警告")
    report.append("-" * 40)
    
    if openclaw_status.get("errors"):
        report.append("🚨 OpenClaw错误:")
        for error in openclaw_status["errors"][:5]:  # 只显示前5个
            report.append(f"  • {error}")
    
    if openclaw_status.get("warnings"):
        report.append("⚠️ OpenClaw警告:")
        for warning in openclaw_status["warnings"][:5]:  # 只显示前5个
            report.append(f"  • {warning}")
    
    # 近期错误
    if openclaw_status.get("recent_errors"):
        report.append("📝 近期错误日志:")
        for error in openclaw_status["recent_errors"][:3]:  # 只显示前3个
            report.append(f"  • {error}")
    
    if not openclaw_status.get("errors") and not openclaw_status.get("warnings"):
        report.append("✅ 系统运行正常，无错误和警告")
    
    report.append("")
    
    # 8. 建议和提醒
    report.append("💡 系统建议")
    report.append("-" * 40)
    
    # 存储建议
    if "volume_info" in nas_status and "usage_percent" in nas_status["volume_info"]:
        usage = nas_status["volume_info"]["usage_percent"]
        if usage > 90:
            report.append("🚨 立即清理存储空间！")
        elif usage > 80:
            report.append("⚠️ 建议清理不必要的文件")
        else:
            report.append("✅ 存储空间管理良好")
    
    # OpenClaw建议
    skills = openclaw_status["plugins_status"].get("skill_stats", {})
    if skills.get("missing", 0) > 10:
        report.append("🔧 建议安装缺失的技能以获得完整功能")
    
    # MCP建议
    mcp = nas_status["filesystem_mcp"]
    if "error" not in mcp and len(mcp.get('servers', [])) > 0:
        report.append("✅ MCP文件系统配置正常，可远程访问NAS文件")
    
    # 通用建议
    report.append("🎯 建议定期检查系统状态")
    report.append("🔄 建议定期备份重要配置文件")
    report.append("🔧 如需扩展功能或修改配置，请联系虾里虾气AI助手")
    
    # 结尾
    report.append("")
    report.append("=" * 60)
    report.append("🤖 报告由虾里虾气AI助手自动生成")
    report.append("🕒 生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    report.append("=" * 60)
    
    return "\n".join(report)

def main():
    """主函数"""
    try:
        # 生成增强版报告
        report = generate_enhanced_report()
        
        # 保存报告到文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = f"/home/maomao/.openclaw/workspace/nas_enhanced_report_{timestamp}.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ 增强版NAS+OpenClaw报告已生成: {report_file}")
        print(f"📄 报告内容预览:")
        print("=" * 60)
        print(report[:800] + "..." if len(report) > 800 else report)
        
        return report_file, report
        
    except Exception as e:
        error_msg = f"❌ 生成增强版报告失败: {str(e)}"
        print(error_msg)
        return None, error_msg

if __name__ == "__main__":
    main()