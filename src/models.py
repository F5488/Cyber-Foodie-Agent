"""数据契约层：定义系统全部核心数据模型（与 ER 图一一对应）。

所有请求/响应体均通过 Pydantic 进行校验，拒绝非法字段。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _now_utc() -> datetime:
    """返回当前 UTC 时间（naive，便于 SQLite 存储）。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id() -> str:
    """生成唯一标识（UUID4 十六进制）。"""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# 枚举类型
# ---------------------------------------------------------------------------
class TastePreference(str, Enum):
    """口味偏好枚举。"""

    SPICY = "辣"
    LIGHT = "清淡"


class BudgetLevel(str, Enum):
    """预算等级枚举。"""

    LOW = "低"
    MEDIUM = "中"
    HIGH = "高"


class WeatherCondition(str, Enum):
    """天气状况枚举。"""

    SUNNY = "晴"
    RAINY = "雨"
    SNOWY = "雪"


class SessionStatus(str, Enum):
    """会话状态机（见 system_design.md 2.6）。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# 请求模型
# ---------------------------------------------------------------------------
class DebateStartRequest(BaseModel):
    """启动辩论请求体。

    三个字段均为枚举，天然限制了合法取值；validator 做基础清洗，
    并额外截断长度，防止超长输入（Prompt 注入/DoS）。
    """

    taste: TastePreference = Field(..., description="口味偏好：辣 / 清淡")
    budget: BudgetLevel = Field(..., description="预算等级：低 / 中 / 高")
    weather: WeatherCondition = Field(..., description="天气：晴 / 雨 / 雪")
    agent_a_id: Optional[str] = Field(default=None, description="大厨 A 的 agent_id（不传用默认）")
    agent_b_id: Optional[str] = Field(default=None, description="大厨 B 的 agent_id（不传用默认）")

    @field_validator("taste", "budget", "weather", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        """对输入做基础清洗（去首尾空白 + 长度截断），避免注入与非法值。"""
        if isinstance(v, str):
            v = v.strip()[:64]
        return v


# ---------------------------------------------------------------------------
# 领域模型
# ---------------------------------------------------------------------------
class Agent(BaseModel):
    """辩论参与方（大厨）。"""

    agent_id: str = Field(default_factory=new_id)
    name: str
    system_prompt: str
    avatar: str = "👨‍🍳"
    description: str = ""
    is_preset: bool = False
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=_now_utc)


class AgentCreateRequest(BaseModel):
    """创建自定义 Agent 请求体（US04）。"""

    name: str = Field(..., max_length=50, description="Agent 名称（≤50 字符）")
    system_prompt: str = Field(..., max_length=2000, description="系统提示词（≤2000 字符）")
    avatar: str = Field(default="👨‍🍳", max_length=16)
    description: str = Field(default="", max_length=256)

    @field_validator("name", "system_prompt", "avatar", "description", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()[:2000]
        return v


class AgentUpdateRequest(BaseModel):
    """更新 Agent 请求体（US04），字段可选。"""

    name: Optional[str] = Field(default=None, max_length=50)
    system_prompt: Optional[str] = Field(default=None, max_length=2000)
    avatar: Optional[str] = Field(default=None, max_length=16)
    description: Optional[str] = Field(default=None, max_length=256)


class DebateRound(BaseModel):
    """单条发言。"""

    id: str = Field(default_factory=new_id)
    session_id: str
    round_number: int
    speaker_id: str
    speaker_name: str
    content: str
    created_at: datetime = Field(default_factory=_now_utc)


class ProsCons(BaseModel):
    """战报中的正反观点。"""

    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    """结构化战报结论（US03）。"""

    final_choice: str
    reason: str
    pros_cons: ProsCons = Field(default_factory=ProsCons)
    score: float = Field(ge=0.0, le=10.0, description="综合评分 0~10")
    winner_agent: str = ""
    created_at: datetime = Field(default_factory=_now_utc)


class Report(BaseModel):
    """战报生成器输出契约（US03），含获胜方。"""

    final_choice: str
    reason: str
    pros_cons: ProsCons = Field(default_factory=ProsCons)
    score: float = Field(ge=0.0, le=10.0, description="综合评分 0~10")
    winner_agent: str


class Session(BaseModel):
    """一次辩论会话（聚合根）。"""

    session_id: str = Field(default_factory=new_id)
    taste: TastePreference
    budget: BudgetLevel
    weather: WeatherCondition
    status: SessionStatus = SessionStatus.PENDING
    current_round: int = 0
    agents: list[Agent] = Field(default_factory=list)
    rounds: list[DebateRound] = Field(default_factory=list)
    recommendation: Optional[Recommendation] = None
    created_at: datetime = Field(default_factory=_now_utc)


class Menu(BaseModel):
    """可购买菜品（拓展 US05）。"""

    id: int
    name: str
    price: float
    category: str
    tags: list[str] = Field(default_factory=list)
    availability: bool = True
