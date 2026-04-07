"""
智能摘要压缩模块
参考 Claw-Code 优先级贪心算法设计

4级优先级:
  P0 = Summary 相关关键词行 (结论/总结/摘要等)
  P1 = 标题行 (短行、markdown标题、冒号结尾)
  P2 = Bullet 行 (-, *, •, 数字编号等)
  P3 = 其他内容

去重: 使用 BTreeSet (sortedcontainers) 高效去重
预算: 默认 1200 chars / 24 lines
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

try:
    from sortedcontainers import SortedSet
    _HAS_SORTEDSET = True
except ImportError:
    _HAS_SORTEDSET = False
    SortedSet = None  # type: ignore


# ----------------------------------------------------------------------
# 优先级定义
# ----------------------------------------------------------------------
class Priority:
    P0_SUMMARY = 0  # 摘要/结论相关
    P1_TITLE   = 1  # 标题行
    P2_BULLET  = 2  # bullet 列表项
    P3_OTHER   = 3  # 其他


# ----------------------------------------------------------------------
# 结果数据类
# ----------------------------------------------------------------------
@dataclass
class SummaryCompressionResult:
    """摘要压缩结果"""
    compressed_text: str
    original_chars: int
    compressed_chars: int
    original_lines: int
    lines_kept: int
    lines_removed: int
    removed_duplicates: int
    removed_by_budget: int
    budget_chars: int
    budget_lines: int

    @property
    def compression_ratio(self) -> float:
        if self.original_chars == 0:
            return 0.0
        return round((1 - self.compressed_chars / self.original_chars) * 100, 2)


# ----------------------------------------------------------------------
# 工具函数
# ----------------------------------------------------------------------
def normalize_lines(lines: List[str]) -> List[str]:
    """
    行规范化:
      - 去除首尾空白
      - 折叠连续空白为单个空格
      - 移除不可见字符
      - 跳过空行
    """
    result: List[str] = []
    for line in lines:
        # 去除首尾空白
        stripped = line.strip()
        if not stripped:
            continue
        # 折叠空白
        collapsed = re.sub(r'\s+', ' ', stripped)
        # 移除零宽字符等
        collapsed = ''.join(
            ch for ch in collapsed
            if not unicodedata.category(ch).startswith('C')
            or ch in (' ', '\t')
        )
        if collapsed:
            result.append(collapsed)
    return result


def _dedup_key(line: str) -> str:
    """生成用于去重的规范化 key（全小写 + 去除 bullet 标记）"""
    # 去除常见 bullet 前缀
    cleaned = re.sub(r'^[\-\*\•·]+\s*', '', line)
    # 去除末尾标点后空格
    cleaned = cleaned.lower().strip()
    return cleaned


# ----------------------------------------------------------------------
# 优先级判断
# ----------------------------------------------------------------------
SUMMARY_KEYWORDS = [
    '摘要', '总结', '结论', 'summary', 'overview',
    '概括', '核心', '要点', '关键', '简报',
    '提炼', '结论是', '总之', '综上所述',
]

TITLE_MARKERS = [
    r'^#{1,6}\s',          # markdown 标题 # ## ###
    r'^[一二三四五六七八九十百千零\d]+[、\.。：:]',  # 中文/数字编号标题
    r'^\[.*\]\s*:',         # [xxx]:
    r'.*[:：]\s*$',         # 末尾冒号，且不超过 60 字符
    r'^\*\*.+\*\*$',       # **bold** 标题
]

BULLET_PATTERNS = [
    r'^[\-\*\•·]\s+',       # - * • ·
    r'^\d+[、\.。\)\)]',     # 1. 1) 1、
    r'^[a-zA-Z][、\.)\)]',  # a. a) a、
]


def _classify_priority(line: str, original_idx: int) -> Tuple[int, int]:
    """
    判断行优先级，返回 (priority, original_idx)
    priority 越小越高；original_idx 用于同优先级时保持顺序
    """
    lower = line.lower()

    # P0: Summary 相关关键词
    for kw in SUMMARY_KEYWORDS:
        if kw in lower:
            return (Priority.P0_SUMMARY, original_idx)

    # P1: 标题行
    for pat in TITLE_MARKERS:
        if re.search(pat, line) and len(line) <= 120:
            return (Priority.P1_TITLE, original_idx)

    # P2: Bullet 行
    for pat in BULLET_PATTERNS:
        if re.search(pat, line):
            return (Priority.P2_BULLET, original_idx)

    # P3: 其他
    return (Priority.P3_OTHER, original_idx)


def select_line_indexes(
    lines: List[str],
    budget_chars: int = 1200,
    budget_lines: int = 24,
) -> List[int]:
    """
    优先级贪心选择:
      1. 按 P0→P1→P2→P3 顺序遍历
      2. 同优先级按原始顺序
      3. 尊重 budget_chars 和 budget_lines 约束
      4. 使用 BTreeSet (SortedSet) 高效去重

    Returns:
        保留行的原始索引列表（已排序）
    """
    n = len(lines)
    if n == 0:
        return []

    # 计算每行优先级
    classified: List[Tuple[int, int, str]] = [
        (_classify_priority(line, i), i, line)
        for i, line in enumerate(lines)
    ]
    # 按优先级排序 (priority, original_idx)
    classified.sort(key=lambda x: (x[0][0], x[0][1]))

    # 去重 set（使用 normalized key）
    if _HAS_SORTEDSET:
        seen: Optional["SortedSet"] = SortedSet()
    else:
        seen = set()

    selected_indexes: List[int] = []
    used_chars = 0
    used_lines = 0

    for (_priority, _orig_idx), orig_idx, line in classified:
        # 检查 budget 约束
        if used_lines >= budget_lines:
            break
        if used_chars + len(line) > budget_chars:
            # 尝试塞入当前行（不换行用空格连接）
            # 如果已经有内容，尝试加上
            if used_lines == 0:
                # 第一行就超了，直接截断
                break
            # 非第一行则不再添加
            continue

        key = _dedup_key(line)

        # 去重检查
        if _HAS_SORTEDSET:
            if key in seen:  # type: ignore
                continue
            seen.add(key)  # type: ignore
        else:
            if key in seen:  # type: ignore
                continue
            seen.add(key)  # type: ignore

        selected_indexes.append(orig_idx)
        used_chars += len(line)
        used_lines += 1

    # 按原始顺序返回
    selected_indexes.sort()
    return selected_indexes


def compress_summary_text(
    text: str,
    budget_chars: int = 1200,
    budget_lines: int = 24,
) -> SummaryCompressionResult:
    """
    压缩摘要文本

    Args:
        text: 原始文本
        budget_chars: 字符数上限
        budget_lines: 行数上限

    Returns:
        SummaryCompressionResult 包含压缩后文本和各项指标
    """
    original_chars = len(text)

    # 分行
    raw_lines = text.splitlines()
    original_lines = len(raw_lines)

    # 规范化
    normalized = normalize_lines(raw_lines)

    # 优先级选择
    selected = select_line_indexes(
        normalized,
        budget_chars=budget_chars,
        budget_lines=budget_lines,
    )

    # 收集保留的行（按原始顺序）
    kept_lines: List[str] = []
    removed_duplicates = 0

    # 重新去重计数（只统计规范段）
    if _HAS_SORTEDSET:
        seen = SortedSet()
    else:
        seen_set: set = set()

    for i, line in enumerate(normalized):
        key = _dedup_key(line)
        if _HAS_SORTEDSET:
            if key in seen:
                removed_duplicates += 1
                continue
            seen.add(key)
        else:
            if key in seen_set:
                removed_duplicates += 1
                continue
            seen_set.add(key)

        if i in selected:
            kept_lines.append(line)

    compressed_text = '\n'.join(kept_lines)
    compressed_chars = len(compressed_text)
    lines_kept = len(kept_lines)
    lines_removed = original_lines - lines_kept

    return SummaryCompressionResult(
        compressed_text=compressed_text,
        original_chars=original_chars,
        compressed_chars=compressed_chars,
        original_lines=original_lines,
        lines_kept=lines_kept,
        lines_removed=lines_removed,
        removed_duplicates=removed_duplicates,
        removed_by_budget=0,  # 简化版暂不细算
        budget_chars=budget_chars,
        budget_lines=budget_lines,
    )


# ----------------------------------------------------------------------
# CLI 测试
# ----------------------------------------------------------------------
if __name__ == '__main__':
    sample = """# 每日摘要

这是一个测试摘要文档。

## 核心要点

- 第一个要点很重要
- 第二个要点也很重要
- 第三个要点
- 第四个要点

结论: 今天表现不错

### 详细说明

今天完成了多项任务，包括代码编写、文档整理和会议参与。

## 总结

1. 上午完成了模块A的开发
2. 下午进行了代码评审
3. 晚上整理了文档
4. 明天计划开始模块B

总结: 今天是充实的一天

摘要: 本日工作已按计划完成
"""

    result = compress_summary_text(sample)
    print(f"原始字符: {result.original_chars}")
    print(f"压缩字符: {result.compressed_chars}")
    print(f"压缩率: {result.compression_ratio}%")
    print(f"原始行数: {result.original_lines}")
    print(f"保留行数: {result.lines_kept}")
    print(f"去重行数: {result.removed_duplicates}")
    print("--- 压缩后文本 ---")
    print(result.compressed_text)
