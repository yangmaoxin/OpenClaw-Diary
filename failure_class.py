#!/usr/bin/env python3
"""
失败分类枚举 - 参照 Claw-Code LaneFailureClass 设计
用于标准化所有 Skill/工具的错误返回
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

class FailureClass(Enum):
    """失败分类枚举"""
    NETWORK_TIMEOUT = "network_timeout"
    PERMISSION_DENIED = "permission_denied"
    TOOL_NOT_FOUND = "tool_not_found"
    API_RATE_LIMIT = "api_rate_limit"
    AUTH_EXPIRED = "auth_expired"
    CONFIG_INVALID = "config_invalid"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    INVALID_INPUT = "invalid_input"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"
    
    @property
    def recoverable(self) -> bool:
        """判断该错误是否可恢复"""
        recoverable_errors = {
            FailureClass.NETWORK_TIMEOUT,
            FailureClass.API_RATE_LIMIT,
            FailureClass.AUTH_EXPIRED,
            FailureClass.TIMEOUT,
        }
        return self in recoverable_errors
    
    @property
    def description(self) -> str:
        """获取错误描述"""
        descriptions = {
            FailureClass.NETWORK_TIMEOUT: "网络请求超时",
            FailureClass.PERMISSION_DENIED: "权限被拒绝",
            FailureClass.TOOL_NOT_FOUND: "工具不存在",
            FailureClass.API_RATE_LIMIT: "API调用频率超限",
            FailureClass.AUTH_EXPIRED: "认证令牌已过期",
            FailureClass.CONFIG_INVALID: "配置文件无效",
            FailureClass.NETWORK_ERROR: "网络连接错误",
            FailureClass.TIMEOUT: "操作超时",
            FailureClass.INVALID_INPUT: "输入参数无效",
            FailureClass.SERVICE_UNAVAILABLE: "服务不可用",
            FailureClass.UNKNOWN: "未知错误",
        }
        return descriptions.get(self, "未知错误")


@dataclass
class StructuredError:
    """结构化错误返回"""
    failure_class: FailureClass
    message: str
    tool_name: Optional[str] = None
    timestamp: Optional[str] = None
    detail: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "failure_class": self.failure_class.value,
            "recoverable": self.failure_class.recoverable,
            "description": self.failure_class.description,
            "message": self.message,
            "tool_name": self.tool_name,
            "timestamp": self.timestamp,
            "detail": self.detail,
        }
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_exception(cls, exc: Exception, tool_name: Optional[str] = None) -> "StructuredError":
        """从异常创建结构化错误"""
        failure_class = cls.classify_exception(exc)
        return cls(
            failure_class=failure_class,
            message=str(exc),
            tool_name=tool_name,
        )
    
    @staticmethod
    def classify_exception(exc: Exception) -> FailureClass:
        """根据异常类型分类"""
        exc_name = type(exc).__name__.lower()
        exc_msg = str(exc).lower()
        
        if "timeout" in exc_name or "timeout" in exc_msg:
            return FailureClass.TIMEOUT
        elif "network" in exc_name or "network" in exc_msg or "connection" in exc_name:
            return FailureClass.NETWORK_ERROR
        elif "permission" in exc_name or "permission" in exc_msg or "denied" in exc_msg:
            return FailureClass.PERMISSION_DENIED
        elif "auth" in exc_name or "auth" in exc_msg or "token" in exc_msg or "credential" in exc_name:
            return FailureClass.AUTH_EXPIRED
        elif "rate limit" in exc_msg or "too many" in exc_msg:
            return FailureClass.API_RATE_LIMIT
        elif "not found" in exc_msg or "does not exist" in exc_msg:
            return FailureClass.TOOL_NOT_FOUND
        elif "config" in exc_name or "config" in exc_msg:
            return FailureClass.CONFIG_INVALID
        elif "invalid" in exc_msg or "illegal" in exc_msg:
            return FailureClass.INVALID_INPUT
        else:
            return FailureClass.UNKNOWN


class ErrorRegistry:
    """错误注册表 - 用于追踪历史错误"""
    
    def __init__(self, max_size: int = 100):
        self.errors: list[StructuredError] = []
        self.max_size = max_size
    
    def record(self, error: StructuredError):
        """记录一个错误"""
        self.errors.append(error)
        if len(self.errors) > self.max_size:
            self.errors.pop(0)
    
    def get_recent(self, count: int = 10) -> list[StructuredError]:
        """获取最近的错误"""
        return self.errors[-count:]
    
    def get_by_class(self, failure_class: FailureClass) -> list[StructuredError]:
        """按类型筛选错误"""
        return [e for e in self.errors if e.failure_class == failure_class]
    
    def get_unrecovered_count(self) -> int:
        """获取不可恢复错误数量"""
        return sum(1 for e in self.errors if not e.failure_class.recoverable)
    
    def summary(self) -> dict:
        """获取错误摘要"""
        class_counts = {}
        for error in self.errors:
            fc = error.failure_class.value
            class_counts[fc] = class_counts.get(fc, 0) + 1
        
        return {
            "total_errors": len(self.errors),
            "unrecovered_count": self.get_unrecovered_count(),
            "by_class": class_counts,
        }


# 全局错误注册表
_global_error_registry: ErrorRegistry = None

def get_error_registry() -> ErrorRegistry:
    """获取全局错误注册表"""
    global _global_error_registry
    if _global_error_registry is None:
        _global_error_registry = ErrorRegistry()
    return _global_error_registry


def record_error(error: StructuredError):
    """快捷函数：记录错误到全局注册表"""
    get_error_registry().record(error)


if __name__ == "__main__":
    # 测试
    err = StructuredError(
        failure_class=FailureClass.NETWORK_TIMEOUT,
        message="Connection timed out after 30s",
        tool_name="feishu_doc"
    )
    print(err.to_json())
    
    # 测试异常分类
    try:
        raise TimeoutError("Request timed out")
    except Exception as e:
        err = StructuredError.from_exception(e, "weather")
        print(err.to_json())
