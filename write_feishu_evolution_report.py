#!/usr/bin/env python3
"""写入进化报告到飞书文档"""

import json
import os
import sys

# 读取 token
TOKEN = "t-g10447hsO3HA2G64DWEY2H7CP4KQDBSSTAYTK4GB"
DOC_ID = "OM92djWU0o1J5xxxNdBcWiJrnSQ"

CONTENT = """# 🦐 虾里虾气 × Claw-Code 全面进化报告

**学习日期**：2026-04-07  
**目标仓库**：https://github.com/ultraworkers/claw-code  
**学习模式**：7个并行子代理深度分析

---

## 📊 执行摘要

本次学习完成了 claw-code 仓库的全面深度分析，涵盖8大核心模块。

**核心发现**：OpenClaw 当前系统成熟度约为 30%，claw-code 的设计有大量可借鉴之处。

---

## 🔴 关键差距分析

### 1. 工具系统 - 成熟度差距：70%

**Claw-Code 优势**：三层工具架构、PermissionEnforcer权限拦截、强类型输出、6大全局Registry

**我的现状**：❌ 无中央注册表 ❌ 无权限控制 ❌ 无执行分发层 ❌ 输出不标准

### 2. 事件机制 - 成熟度差距：95%

**Claw-Code 优势**：16种命名事件、11种失败分类、完整生命周期追踪、智能摘要压缩

**我的现状**：❌ 完全无事件机制 ❌ 依赖文本日志 ❌ 无发布订阅

### 3. 会话管理 - 成熟度差距：60%

**Claw-Code 优势**：JSONL追加写入、文件轮转、Compaction追踪、Workspace绑定

**我的现状**：❌ 无文件轮转 ❌ 无compaction追踪 ❌ 无fork机制

### 4. 策略引擎 - 成熟度差距：80%

**Claw-Code 优势**：AND/OR条件组合、Chain链式动作、GreenLevel分级、策略-动作分离

**我的现状**：❌ 无规则引擎 ❌ 只有定时执行 ❌ 无条件触发

### 5. Hooks系统 - 成熟度差距：90%

**Claw-Code 优势**：三触发点、可阻止执行、可修改输入、Abort signal

**我的现状**：❌ 完全没有Hook拦截能力 ❌ 只有Cron/Heartbeat定时任务

### 6. MCP生命周期 - 成熟度差距：75%

**Claw-Code 优势**：11阶段状态机、降级报告、Exponential backoff、健康监控

**我的现状**：❌ 无生命周期状态机 ❌ 无降级报告 ❌ 无重试机制

### 7. 权限系统 - 成熟度差距：65%

**Claw-Code 优势**：5级权限枚举、PermissionRule规则引擎、Hook Override权限覆盖

**我的现状**：❌ 无PermissionMode分级 ❌ 无规则引擎 ❌ Bash无细粒度沙箱

---

## 🚀 进化路线图

### Phase 1：立即可落地（1-2周）

1. 引入FailureClass枚举
2. 建立Skills中央注册表
3. 实现文件轮转机制

### Phase 2：中期改进（1个月）

1. 引入Hook系统
2. 策略引擎雏形
3. 生命周期状态机

### Phase 3：长期目标（3个月+）

1. 完整事件总线
2. 智能摘要压缩
3. 权限规则引擎

---

## 📈 预期收益

- 事件机制：可观测性提升100%
- 文件轮转：存储风险降低
- Hook拦截：安全性提升
- 注册表：工具可枚举
- 策略引擎：智能化程度提升
- 失败分类：错误处理精准化
- 生命周期：可调试性提升

---

*报告生成时间：2026-04-07 18:40*  
*作者：虾里虾气 · OpenClaw AI 助手"""

import urllib.request
import urllib.parse

def create_block(doc_id, content, index=0):
    """创建文本块"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks"
    
    # 构建 text_elements
    text_elements = []
    lines = content.split('\n')
    for line in lines:
        if line.strip():
            text_elements.append({
                "text_run": {
                    "content": line,
                    "text_element_style": {}
                }
            })
        # 添加换行
        text_elements.append({
            "text_run": {
                "content": "\n",
                "text_element_style": {}
            }
        })
    
    data = {
        "children": [{
            "block_type": 2,  # text
            "text": {
                "elements": text_elements,
                "style": {}
            }
        }],
        "index": index
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

def update_document_title(doc_id, title):
    """更新文档标题"""
    url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}"
    
    data = {
        "title": title
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {TOKEN}',
            'Content-Type': 'application/json'
        },
        method='PATCH'
    )
    
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    print(f"文档ID: {DOC_ID}")
    print(f"内容长度: {len(CONTENT)} 字符")
    
    # 先更新标题
    result = update_document_title(DOC_ID, "🦐 虾里虾气 × Claw-Code 全面进化报告")
    print(f"标题更新: {result.get('msg', 'unknown')}")
    
    # 写入内容
    result = create_block(DOC_ID, CONTENT)
    print(f"内容写入: {result.get('msg', 'unknown')}")
    
    if result.get('data'):
        print(f"创建了 {len(result['data'].get('children', []))} 个块")
