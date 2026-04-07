#!/usr/bin/env python3
"""
事件系统基础实现 - 参照 Claw-Code Lane Events 设计
用于标准化的内部事件追踪和发布
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime
import json
import threading

class EventType(Enum):
    """事件类型枚举 - 基础版本"""
    # Session 事件
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    
    # 工具事件
    TOOL_INVOKED = "tool.invoked"
    TOOL_SUCCEEDED = "tool.succeeded"
    TOOL_FAILED = "tool.failed"
    
    # Skill 事件
    SKILL_LOADED = "skill.loaded"
    SKILL_INVOKED = "skill.invoked"
    SKILL_FAILED = "skill.failed"
    
    # 系统事件
    HEARTBEAT_TRIGGERED = "heartbeat.triggered"
    CRON_TRIGGERED = "cron.triggered"
    NOTIFICATION_SENT = "notification.sent"
    
    # 错误事件
    ERROR_OCCURRED = "error.occurred"
    RECOVERY_ATTEMPTED = "recovery.attempted"


@dataclass
class Event:
    """事件结构"""
    event: EventType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: dict = field(default_factory=dict)
    session_id: Optional[str] = None
    source: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "event": self.event.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "session_id": self.session_id,
            "source": self.source,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


@dataclass
class EventBlocker:
    """阻塞者信息"""
    failure_class: str
    detail: str
    
    def to_dict(self) -> dict:
        return {
            "failure_class": self.failure_class,
            "detail": self.detail,
        }


class EventBus:
    """轻量级事件总线"""
    
    def __init__(self):
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._lock = threading.Lock()
        self._history: list[Event] = []
        self._max_history = 1000
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """订阅事件"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """取消订阅"""
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type].remove(handler)
    
    def publish(self, event: Event):
        """发布事件"""
        # 记录到历史
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history.pop(0)
        
        # 分发到订阅者
        with self._lock:
            handlers = self._subscribers.get(event.event, []).copy()
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> list[Event]:
        """获取事件历史"""
        with self._lock:
            if event_type is None:
                return self._history[-limit:]
            return [e for e in self._history if e.event == event_type][-limit:]
    
    def clear_history(self):
        """清空历史"""
        with self._lock:
            self._history.clear()


# 全局事件总线
_global_event_bus: EventBus = None

def get_event_bus() -> EventBus:
    """获取全局事件总线"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus


def emit(event_type: EventType, data: dict = None, session_id: str = None, source: str = None):
    """快捷函数：发布事件"""
    event = Event(
        event=event_type,
        data=data or {},
        session_id=session_id,
        source=source,
    )
    get_event_bus().publish(event)
    return event


def on_event(event_type: EventType):
    """装饰器：订阅事件"""
    def decorator(handler: Callable[[Event], None]):
        get_event_bus().subscribe(event_type, handler)
        return handler
    return decorator


class EventSummary:
    """事件摘要生成器"""
    
    @staticmethod
    def generate_summary(events: list[Event], max_chars: int = 1200) -> str:
        """生成事件摘要"""
        if not events:
            return "No events recorded."
        
        lines = ["## Event Summary", ""]
        lines.append(f"Total events: {len(events)}")
        
        # 按类型统计
        by_type = {}
        for e in events:
            event_name = e.event.value
            by_type[event_name] = by_type.get(event_name, 0) + 1
        
        lines.append("\n### By Type:")
        for event_name, count in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"- {event_name}: {count}")
        
        # 最近的错误
        errors = [e for e in events if "failed" in e.event.value or "error" in e.event.value]
        if errors:
            lines.append(f"\n### Recent Errors ({len(errors)}):")
            for e in errors[-5:]:
                lines.append(f"- [{e.event.value}] {e.data.get('message', 'No message')}")
        
        result = "\n".join(lines)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n\n[truncated]"
        
        return result


if __name__ == "__main__":
    # 测试
    @on_event(EventType.TOOL_INVOKED)
    def on_tool_invoked(event: Event):
        print(f"Tool invoked: {event.data}")
    
    emit(EventType.TOOL_INVOKED, {"tool_name": "feishu_doc", "action": "read"})
    emit(EventType.TOOL_SUCCEEDED, {"tool_name": "feishu_doc", "duration_ms": 150})
    emit(EventType.TOOL_FAILED, {"tool_name": "weather", "error": "timeout"})
    
    history = get_event_bus().get_history()
    print(f"\nEvent history ({len(history)} events):")
    for e in history:
        print(f"  {e.event.value}: {e.data}")
    
    print("\n" + EventSummary.generate_summary(history))
