#!/usr/bin/env python3
"""
生命周期状态机 - 参照 Claw-Code 设计
用于 Skill/工具的 11 阶段生命周期追踪
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

class LifecyclePhase(Enum):
    """生命周期阶段 - 11阶段"""
    CONFIG_LOAD = "config_load"           # 1. 配置加载
    DEPENDENCY_CHECK = "dep_check"         # 2. 依赖检查
    INITIALIZE = "initialize"              # 3. 初始化
    READY = "ready"                       # 4. 就绪
    INVOKING = "invoking"                 # 5. 调用中
    EXECUTING = "executing"                # 6. 执行中
    COMPLETING = "completing"             # 7. 完成中
    ERROR_SURFACING = "error_surfacing"   # 8. 错误暴露
    SHUTDOWN = "shutdown"                 # 9. 关闭
    CLEANUP = "cleanup"                  # 10. 清理
    TERMINATED = "terminated"             # 11. 终止

@dataclass
class PhaseRecord:
    """阶段记录"""
    phase: LifecyclePhase
    timestamp: str
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

@dataclass
class LifecycleState:
    """生命周期状态"""
    current_phase: LifecyclePhase = LifecyclePhase.CONFIG_LOAD
    phase_records: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    is_degraded: bool = False
    degraded_reason: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "current_phase": self.current_phase.value,
            "phase_count": len(self.phase_records),
            "error_count": len(self.errors),
            "is_degraded": self.is_degraded,
            "degraded_reason": self.degraded_reason,
            "phases": [r.phase.value for r in self.phase_records],
        }

class LifecycleValidator:
    """阶段转换验证器"""
    
    # 合法的阶段转换
    VALID_TRANSITIONS = {
        LifecyclePhase.CONFIG_LOAD: {LifecyclePhase.DEPENDENCY_CHECK, LifecyclePhase.ERROR_SURFACING},
        LifecyclePhase.DEPENDENCY_CHECK: {LifecyclePhase.INITIALIZE, LifecyclePhase.ERROR_SURFACING},
        LifecyclePhase.INITIALIZE: {LifecyclePhase.READY, LifecyclePhase.ERROR_SURFACING},
        LifecyclePhase.READY: {LifecyclePhase.INVOKING, LifecyclePhase.SHUTDOWN},
        LifecyclePhase.INVOKING: {LifecyclePhase.EXECUTING, LifecyclePhase.ERROR_SURFACING},
        LifecyclePhase.EXECUTING: {LifecyclePhase.COMPLETING, LifecyclePhase.ERROR_SURFACING},
        LifecyclePhase.COMPLETING: {LifecyclePhase.READY, LifecyclePhase.SHUTDOWN},
        LifecyclePhase.ERROR_SURFACING: {LifecyclePhase.SHUTDOWN, LifecyclePhase.CLEANUP},
        LifecyclePhase.SHUTDOWN: {LifecyclePhase.CLEANUP, LifecyclePhase.TERMINATED},
        LifecyclePhase.CLEANUP: {LifecyclePhase.TERMINATED},
        LifecyclePhase.TERMINATED: set(),
    }
    
    @classmethod
    def can_transition(cls, from_phase: LifecyclePhase, to_phase: LifecyclePhase) -> bool:
        """检查是否可以转换"""
        return to_phase in cls.VALID_TRANSITIONS.get(from_phase, set())
    
    @classmethod
    def get_allowed_next(cls, current: LifecyclePhase) -> list:
        """获取允许的下一阶段"""
        return [p.value for p in cls.VALID_TRANSITIONS.get(current, set())]

class SkillLifecycleManager:
    """Skill 生命周期管理器"""
    
    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        self.state = LifecycleState()
        self._phase_start: Optional[datetime] = None
        self._on_phase_change: Optional[Callable] = None
    
    def set_phase_change_callback(self, callback: Callable[[LifecyclePhase, LifecyclePhase], None]):
        """设置阶段转换回调"""
        self._on_phase_change = callback
    
    def transition(self, new_phase: LifecyclePhase, error: Optional[str] = None, metadata: dict = None) -> bool:
        """尝试转换到新阶段"""
        current = self.state.current_phase
        
        if not LifecycleValidator.can_transition(current, new_phase):
            return False
        
        # 计算上一阶段耗时
        duration_ms = None
        if self._phase_start:
            duration_ms = int((datetime.now() - self._phase_start).total_seconds() * 1000)
        
        # 记录上一阶段
        record = PhaseRecord(
            phase=current,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            error=error,
            metadata=metadata or {}
        )
        self.state.phase_records.append(record)
        
        if error:
            self.state.errors.append({"phase": current.value, "error": error, "timestamp": record.timestamp})
        
        # 转换到新阶段
        old_phase = self.state.current_phase
        self.state.current_phase = new_phase
        self._phase_start = datetime.now()
        
        # 触发回调
        if self._on_phase_change:
            try:
                self._on_phase_change(old_phase, new_phase)
            except Exception as e:
                pass
        
        return True
    
    def mark_degraded(self, reason: str):
        """标记为降级模式"""
        self.state.is_degraded = True
        self.state.degraded_reason = reason
    
    def get_summary(self) -> dict:
        """获取状态摘要"""
        return {
            "skill": self.skill_name,
            **self.state.to_dict(),
            "allowed_next": LifecycleValidator.get_allowed_next(self.state.current_phase),
        }
    
    def force_transition(self, new_phase: LifecyclePhase, error: Optional[str] = None):
        """强制转换（不检查合法性）"""
        duration_ms = None
        if self._phase_start:
            duration_ms = int((datetime.now() - self._phase_start).total_seconds() * 1000)
        
        record = PhaseRecord(
            phase=self.state.current_phase,
            timestamp=datetime.now().isoformat(),
            duration_ms=duration_ms,
            error=error,
        )
        self.state.phase_records.append(record)
        
        self.state.current_phase = new_phase
        self._phase_start = datetime.now()


if __name__ == "__main__":
    # 测试
    manager = SkillLifecycleManager("test_skill")
    
    def on_change(old, new):
        print(f"  Transition: {old.value} -> {new.value}")
    
    manager.set_phase_change_callback(on_change)
    
    print("Lifecycle State Machine Test")
    print("-" * 40)
    
    phases = [
        LifecyclePhase.CONFIG_LOAD,
        LifecyclePhase.DEPENDENCY_CHECK,
        LifecyclePhase.INITIALIZE,
        LifecyclePhase.READY,
        LifecyclePhase.INVOKING,
        LifecyclePhase.EXECUTING,
        LifecyclePhase.COMPLETING,
    ]
    
    for phase in phases:
        result = manager.transition(phase)
        print(f"{phase.value}: {'OK' if result else 'FAIL'}")
    
    print()
    print("Final State:")
    import json
    print(json.dumps(manager.get_summary(), indent=2))
