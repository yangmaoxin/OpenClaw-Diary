"""
Policy Engine - 策略引擎实现

支持条件组合、链式动作、优先级排序的规则引擎
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import Any, Callable, Optional


# =============================================================================
# GreenLevel 枚举 - 绿色等级
# =============================================================================


class GreenLevel(Enum):
    """CI/CD 绿色等级，从严到松"""

    TargetedTests = auto()  # 定向测试 - 最严格
    Package = auto()  # 打包测试
    Workspace = auto()  # 工作区测试
    MergeReady = auto()  # 可合并 - 最宽松

    def __repr__(self) -> str:
        return self.name


# =============================================================================
# PolicyCondition 枚举 - 策略条件
# =============================================================================


class PolicyCondition(Enum):
    """策略条件，支持组合逻辑"""

    # --- 组合逻辑 ---
    AND = auto()  # 所有子条件必须满足
    OR = auto()  # 任一子条件满足

    # --- 时间条件 ---
    TimeAfter = auto()  # 在指定时间之后
    TimeBefore = auto()  # 在指定时间之前
    TimeBetween = auto()  # 在时间范围内
    TimeExpired = auto()  # 超时

    # --- 状态条件 ---
    StatusEqual = auto()  # 状态等于
    StatusNotEqual = auto()  # 状态不等于
    StatusIn = auto()  # 状态在列表中
    StatusContains = auto()  # 状态包含

    # --- 级别条件 ---
    GreenLevelAtLeast = auto()  # 绿色等级至少为
    GreenLevelAtMost = auto()  # 绿色等级最多为

    # --- 计数条件 ---
    CountAbove = auto()  # 计数大于
    CountBelow = auto()  # 计数小于
    CountEqual = auto()  # 计数等于

    # --- 错误条件 ---
    HasError = auto()  # 存在错误
    ErrorContains = auto()  # 错误信息包含

    # --- 始终/永不 ---
    Always = auto()  # 始终触发
    Never = auto()  # 从不触发


# =============================================================================
# PolicyAction 枚举 - 策略动作
# =============================================================================


class PolicyAction(Enum):
    """策略动作类型"""

    Notify = auto()  # 通知
    Retry = auto()  # 重试
    Escalate = auto()  # 升级
    Cleanup = auto()  # 清理
    Chain = auto()  # 链式动作（执行多个动作）


# =============================================================================
# 条件值与上下文
# =============================================================================


@dataclass
class ConditionContext:
    """条件评估的上下文数据"""

    status: Optional[str] = None
    green_level: Optional[GreenLevel] = None
    error: Optional[str] = None
    count: int = 0
    timestamp: Optional[datetime] = None
    start_time: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)


@dataclass
class Condition:
    """单个条件定义"""

    cond_type: PolicyCondition
    value: Any = None  # 条件值或子条件列表
    threshold: Any = None  # 阈值（如时间）

    def evaluate(self, ctx: ConditionContext) -> bool:
        """评估条件是否满足"""
        return _evaluate_condition(self, ctx)


def _evaluate_condition(cond: Condition, ctx: ConditionContext) -> bool:
    """内部条件评估函数"""
    cond_type = cond.cond_type

    # --- 组合逻辑 ---
    if cond_type == PolicyCondition.AND:
        sub_conds = cond.value or []
        return all(_evaluate_condition(c, ctx) for c in sub_conds)

    if cond_type == PolicyCondition.OR:
        sub_conds = cond.value or []
        return any(_evaluate_condition(c, ctx) for c in sub_conds)

    # --- 时间条件 ---
    now = ctx.timestamp or datetime.now()

    if cond_type == PolicyCondition.TimeAfter:
        threshold = cond.threshold or cond.value
        if isinstance(threshold, datetime):
            return now >= threshold
        return False

    if cond_type == PolicyCondition.TimeBefore:
        threshold = cond.threshold or cond.value
        if isinstance(threshold, datetime):
            return now <= threshold
        return False

    if cond_type == PolicyCondition.TimeBetween:
        start = cond.value
        end = cond.threshold
        if isinstance(start, datetime) and isinstance(end, datetime):
            return start <= now <= end
        return False

    if cond_type == PolicyCondition.TimeExpired:
        if ctx.start_time is None:
            return False
        duration = cond.value  # 秒数
        elapsed = (now - ctx.start_time).total_seconds()
        return elapsed >= duration

    # --- 状态条件 ---
    status = ctx.status or ""

    if cond_type == PolicyCondition.StatusEqual:
        return status == cond.value

    if cond_type == PolicyCondition.StatusNotEqual:
        return status != cond.value

    if cond_type == PolicyCondition.StatusIn:
        return status in (cond.value or [])

    if cond_type == PolicyCondition.StatusContains:
        return cond.value in status

    # --- 绿色等级条件 ---
    if ctx.green_level is None:
        return False

    level_values = {
        GreenLevel.TargetedTests: 0,
        GreenLevel.Package: 1,
        GreenLevel.Workspace: 2,
        GreenLevel.MergeReady: 3,
    }
    current_level = level_values.get(ctx.green_level, -1)

    if cond_type == PolicyCondition.GreenLevelAtLeast:
        required = level_values.get(cond.value, -1)
        return current_level >= required

    if cond_type == PolicyCondition.GreenLevelAtMost:
        required = level_values.get(cond.value, 999)
        return current_level <= required

    # --- 计数条件 ---
    count = ctx.count

    if cond_type == PolicyCondition.CountAbove:
        return count > (cond.value or 0)

    if cond_type == PolicyCondition.CountBelow:
        return count < (cond.value or 0)

    if cond_type == PolicyCondition.CountEqual:
        return count == (cond.value or 0)

    # --- 错误条件 ---
    error = ctx.error or ""

    if cond_type == PolicyCondition.HasError:
        return len(error) > 0

    if cond_type == PolicyCondition.ErrorContains:
        return cond.value in error

    # --- 始终/永不 ---
    if cond_type == PolicyCondition.Always:
        return True

    if cond_type == PolicyCondition.Never:
        return False

    return False


# =============================================================================
# PolicyRule 数据类
# =============================================================================


@dataclass
class PolicyRule:
    """策略规则"""

    name: str
    condition: Condition
    action: PolicyAction | list[PolicyAction]
    priority: int = 0  # 越大优先级越高
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        """规范化 action 为列表"""
        if isinstance(self.action, PolicyAction):
            self.action = [self.action]

    def matches(self, ctx: ConditionContext) -> bool:
        """检查规则是否匹配上下文"""
        if not self.enabled:
            return False
        return self.condition.evaluate(ctx)


# =============================================================================
# 动作处理器
# =============================================================================

ActionHandler = Callable[[PolicyRule, ConditionContext], Any]


class ActionHandlers:
    """动作处理器注册表"""

    _handlers: dict[PolicyAction, ActionHandler] = {}

    @classmethod
    def register(cls, action: PolicyAction, handler: ActionHandler):
        """注册动作处理器"""
        cls._handlers[action] = handler

    @classmethod
    def get(cls, action: PolicyAction) -> Optional[ActionHandler]:
        """获取动作处理器"""
        return cls._handlers.get(action)

    @classmethod
    def handle(
        cls, actions: list[PolicyAction], rule: PolicyRule, ctx: ConditionContext
    ) -> list[Any]:
        """执行动作列表"""
        results = []
        for action in actions:
            handler = cls.get(action)
            if handler:
                results.append(handler(rule, ctx))
            else:
                results.append(
                    {"action": action.name, "status": "no_handler", "rule": rule.name}
                )
        return results


def _default_notify_handler(rule: PolicyRule, ctx: ConditionContext) -> dict:
    """默认通知处理器"""
    return {
        "action": "notify",
        "rule": rule.name,
        "status": "pending",
        "timestamp": datetime.now().isoformat(),
        "metadata": rule.metadata,
    }


def _default_retry_handler(rule: PolicyRule, ctx: ConditionContext) -> dict:
    """默认重试处理器"""
    max_retries = rule.metadata.get("max_retries", 3)
    retry_delay = rule.metadata.get("retry_delay", 5)  # 秒
    current_retry = ctx.get("retry_count", 0)

    return {
        "action": "retry",
        "rule": rule.name,
        "status": "retrying" if current_retry < max_retries else "exhausted",
        "retry_count": current_retry + 1,
        "next_retry_in": retry_delay if current_retry < max_retries else None,
    }


def _default_escalate_handler(rule: PolicyRule, ctx: ConditionContext) -> dict:
    """默认升级处理器"""
    escalation_level = rule.metadata.get("escalation_level", "high")
    recipients = rule.metadata.get("recipients", [])

    return {
        "action": "escalate",
        "rule": rule.name,
        "status": "escalated",
        "escalation_level": escalation_level,
        "recipients": recipients,
        "timestamp": datetime.now().isoformat(),
    }


def _default_cleanup_handler(rule: PolicyRule, ctx: ConditionContext) -> dict:
    """默认清理处理器"""
    cleanup_targets = rule.metadata.get("cleanup_targets", [])

    return {
        "action": "cleanup",
        "rule": rule.name,
        "status": "cleaned",
        "targets": cleanup_targets,
        "timestamp": datetime.now().isoformat(),
    }


def _default_chain_handler(rule: PolicyRule, ctx: ConditionContext) -> dict:
    """默认链式动作处理器"""
    chain_actions = rule.metadata.get("chain_actions", [])

    return {
        "action": "chain",
        "rule": rule.name,
        "status": "chaining",
        "chain_actions": chain_actions,
        "timestamp": datetime.now().isoformat(),
    }


# 注册默认处理器
ActionHandlers.register(PolicyAction.Notify, _default_notify_handler)
ActionHandlers.register(PolicyAction.Retry, _default_retry_handler)
ActionHandlers.register(PolicyAction.Escalate, _default_escalate_handler)
ActionHandlers.register(PolicyAction.Cleanup, _default_cleanup_handler)
ActionHandlers.register(PolicyAction.Chain, _default_chain_handler)


# =============================================================================
# PolicyEngine 类
# =============================================================================


class PolicyEngine:
    """
    策略引擎

    功能：
    - 规则注册与管理
    - 条件匹配
    - 动作执行
    - 优先级排序
    """

    def __init__(self):
        self._rules: list[PolicyRule] = []
        self._action_handlers = ActionHandlers()
        self._history: list[dict] = []

    # -------------------------------------------------------------------------
    # 规则管理
    # -------------------------------------------------------------------------

    def add_rule(self, rule: PolicyRule) -> None:
        """添加规则"""
        self._rules.append(rule)
        self._sort_rules()

    def remove_rule(self, name: str) -> bool:
        """移除规则"""
        for i, rule in enumerate(self._rules):
            if rule.name == name:
                del self._rules[i]
                return True
        return False

    def get_rule(self, name: str) -> Optional[PolicyRule]:
        """获取规则"""
        for rule in self._rules:
            if rule.name == name:
                return rule
        return None

    def list_rules(self, enabled_only: bool = False) -> list[PolicyRule]:
        """列出所有规则"""
        if enabled_only:
            return [r for r in self._rules if r.enabled]
        return list(self._rules)

    def enable_rule(self, name: str, enabled: bool = True) -> bool:
        """启用/禁用规则"""
        rule = self.get_rule(name)
        if rule:
            rule.enabled = enabled
            self._sort_rules()
            return True
        return False

    def _sort_rules(self) -> None:
        """按优先级排序规则"""
        self._rules.sort(key=lambda r: r.priority, reverse=True)

    def clear_rules(self) -> None:
        """清除所有规则"""
        self._rules.clear()

    # -------------------------------------------------------------------------
    # 动作处理
    # -------------------------------------------------------------------------

    def register_action_handler(
        self, action: PolicyAction, handler: ActionHandler
    ) -> None:
        """注册自定义动作处理器"""
        self._action_handlers.register(action, handler)

    def execute_action(
        self, actions: list[PolicyAction], rule: PolicyRule, ctx: ConditionContext
    ) -> list[Any]:
        """执行动作列表"""
        return self._action_handlers.handle(actions, rule, ctx)

    # -------------------------------------------------------------------------
    # 规则评估与执行
    # -------------------------------------------------------------------------

    def evaluate(self, ctx: ConditionContext) -> list[tuple[PolicyRule, bool]]:
        """
        评估所有规则，返回匹配列表

        Returns:
            [(rule, matched), ...]
        """
        results = []
        for rule in self._rules:
            matched = rule.matches(ctx)
            results.append((rule, matched))
        return results

    def match(self, ctx: ConditionContext) -> list[PolicyRule]:
        """
        获取所有匹配的规则（按优先级排序）

        Returns:
            [matched_rule, ...]
        """
        matched = []
        for rule in self._rules:
            if rule.enabled and rule.matches(ctx):
                matched.append(rule)
        return matched

    def execute(self, ctx: ConditionContext) -> list[dict]:
        """
        执行所有匹配规则的动作

        Returns:
            [{"rule": ..., "matched": ..., "actions": [...], "results": [...]}, ...]
        """
        results = []
        matched_rules = self.match(ctx)

        for rule in matched_rules:
            action_results = self.execute_action(rule.action, rule, ctx)

            entry = {
                "rule": rule.name,
                "condition": rule.condition.cond_type.name,
                "matched": True,
                "actions": [a.name for a in rule.action],
                "results": action_results,
                "timestamp": datetime.now().isoformat(),
            }
            results.append(entry)
            self._history.append(entry)

        return results

    def execute_first(self, ctx: ConditionContext) -> Optional[dict]:
        """
        执行第一个匹配的规则（最高优先级）

        Returns:
            {"rule": ..., "results": [...]} or None
        """
        matched_rules = self.match(ctx)
        if not matched_rules:
            return None

        rule = matched_rules[0]
        action_results = self.execute_action(rule.action, rule, ctx)

        entry = {
            "rule": rule.name,
            "condition": rule.condition.cond_type.name,
            "matched": True,
            "actions": [a.name for a in rule.action],
            "results": action_results,
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append(entry)
        return entry

    # -------------------------------------------------------------------------
    # 历史记录
    # -------------------------------------------------------------------------

    def get_history(self, limit: int = 100) -> list[dict]:
        """获取执行历史"""
        return self._history[-limit:]

    def clear_history(self) -> None:
        """清除历史记录"""
        self._history.clear()

    # -------------------------------------------------------------------------
    # 便捷构造函数
    # -------------------------------------------------------------------------

    @classmethod
    def create_simple_rule(
        cls,
        name: str,
        cond_type: PolicyCondition,
        cond_value: Any = None,
        action: PolicyAction = PolicyAction.Notify,
        priority: int = 0,
        **metadata,
    ) -> PolicyRule:
        """创建简单规则"""
        condition = Condition(cond_type=cond_type, value=cond_value)
        return PolicyRule(
            name=name,
            condition=condition,
            action=[action],
            priority=priority,
            metadata=metadata,
        )

    @classmethod
    def create_and_rule(
        cls,
        name: str,
        sub_conditions: list[Condition],
        action: PolicyAction = PolicyAction.Notify,
        priority: int = 0,
        **metadata,
    ) -> PolicyRule:
        """创建 AND 组合规则"""
        condition = Condition(
            cond_type=PolicyCondition.AND, value=sub_conditions
        )
        return PolicyRule(
            name=name,
            condition=condition,
            action=[action],
            priority=priority,
            metadata=metadata,
        )

    @classmethod
    def create_or_rule(
        cls,
        name: str,
        sub_conditions: list[Condition],
        action: PolicyAction = PolicyAction.Notify,
        priority: int = 0,
        **metadata,
    ) -> PolicyRule:
        """创建 OR 组合规则"""
        condition = Condition(
            cond_type=PolicyCondition.OR, value=sub_conditions
        )
        return PolicyRule(
            name=name,
            condition=condition,
            action=[action],
            priority=priority,
            metadata=metadata,
        )


# =============================================================================
# 辅助函数
# =============================================================================


def make_time_condition(
    cond_type: PolicyCondition,
    value: Any = None,
    threshold: Any = None,
) -> Condition:
    """创建时间条件"""
    return Condition(cond_type=cond_type, value=value, threshold=threshold)


def make_status_condition(
    cond_type: PolicyCondition,
    value: Any = None,
) -> Condition:
    """创建状态条件"""
    return Condition(cond_type=cond_type, value=value)


def make_count_condition(
    cond_type: PolicyCondition,
    value: Any = None,
) -> Condition:
    """创建计数条件"""
    return Condition(cond_type=cond_type, value=value)


def and_conditions(*conditions: Condition) -> Condition:
    """创建 AND 组合条件"""
    return Condition(cond_type=PolicyCondition.AND, value=list(conditions))


def or_conditions(*conditions: Condition) -> Condition:
    """创建 OR 组合条件"""
    return Condition(cond_type=PolicyCondition.OR, value=list(conditions))


# =============================================================================
# 示例用法
# =============================================================================


if __name__ == "__main__":
    engine = PolicyEngine()

    # 示例1: 简单规则 - 错误时通知
    rule1 = PolicyEngine.create_simple_rule(
        name="error_notify",
        cond_type=PolicyCondition.HasError,
        action=PolicyAction.Notify,
        priority=10,
        message="检测到错误",
    )
    engine.add_rule(rule1)

    # 示例2: 组合规则 - 错误且超时则升级
    rule2 = PolicyRule(
        name="error_timeout_escalate",
        condition=and_conditions(
            Condition(cond_type=PolicyCondition.HasError),
            Condition(
                cond_type=PolicyCondition.TimeExpired,
                value=300,  # 5分钟
            ),
        ),
        action=[PolicyAction.Escalate, PolicyAction.Notify],
        priority=20,
        description="错误且超时则升级",
        metadata={"escalation_level": "critical", "recipients": ["admin"]},
    )
    engine.add_rule(rule2)

    # 示例3: 绿色等级规则 - TargetedTests 时不允许合并
    rule3 = PolicyRule(
        name="block_merge_targeted",
        condition=Condition(
            cond_type=PolicyCondition.GreenLevelAtMost,
            value=GreenLevel.TargetedTests,
        ),
        action=[PolicyAction.Notify, PolicyAction.Cleanup],
        priority=30,
        description="TargetedTests 等级禁止合并",
        metadata={"cleanup_targets": ["temp_files"]},
    )
    engine.add_rule(rule3)

    # 示例4: 重试规则
    rule4 = PolicyEngine.create_simple_rule(
        name="auto_retry",
        cond_type=PolicyCondition.CountBelow,
        cond_value=3,
        action=PolicyAction.Retry,
        priority=5,
        max_retries=3,
        retry_delay=5,
    )
    engine.add_rule(rule4)

    # 测试评估
    print("=" * 60)
    print("策略引擎示例")
    print("=" * 60)

    # 测试上下文
    ctx1 = ConditionContext(
        status="failed",
        green_level=GreenLevel.TargetedTests,
        error="Build failed: compilation error",
        count=2,
        timestamp=datetime.now(),
        start_time=datetime.now() - timedelta(minutes=10),
    )

    print("\n[测试1] 错误上下文")
    print(f"上下文: status={ctx1.status}, green_level={ctx1.green_level.name}, error={ctx1.error}")
    results = engine.execute(ctx1)
    for r in results:
        print(f"  -> 规则 '{r['rule']}' 匹配，动作: {r['actions']}")

    # 测试绿色等级通过
    ctx2 = ConditionContext(
        status="passed",
        green_level=GreenLevel.MergeReady,
        count=0,
        timestamp=datetime.now(),
    )

    print("\n[测试2] 通过上下文")
    print(f"上下文: status={ctx2.status}, green_level={ctx2.green_level.name}")
    results = engine.execute(ctx2)
    if results:
        for r in results:
            print(f"  -> 规则 '{r['rule']}' 匹配，动作: {r['actions']}")
    else:
        print("  -> 无匹配规则")

    # 显示所有规则
    print("\n[规则列表]")
    for rule in engine.list_rules():
        print(f"  [{rule.priority}] {rule.name}: {rule.description or '无描述'}")

    # 历史记录
    print("\n[执行历史]")
    for entry in engine.get_history():
        print(f"  {entry['timestamp']} - {entry['rule']}: {entry['actions']}")
