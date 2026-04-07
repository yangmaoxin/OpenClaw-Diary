#!/usr/bin/env python3
import json
import sys
import os

def write_to_doc(doc_id, content):
    """写入内容到飞书文档"""
    # 构造工具调用参数
    params = {
        "doc_id": doc_id,
        "mode": "append",
        "markdown": content
    }
    
    # 这里直接输出参数，由agent调用工具
    print(json.dumps(params, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python write_to_feishu_doc.py <doc_id> <content_file>")
        sys.exit(1)
    
    doc_id = sys.argv[1]
    content_file = sys.argv[2]
    
    with open(content_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    write_to_doc(doc_id, content)
