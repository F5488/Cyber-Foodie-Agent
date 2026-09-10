"""ORM 映射层：SQLAlchemy 2.x 声明式模型，与 ER 图及 Pydantic 契约对齐。

四张核心表：sessions、agents、debate_rounds、recommendations。
"""
from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .db import Base
from .models import _now_utc, new_id


class SessionModel(Base):
    """辩论会话表。"""

    __tablename__ = "sessions"

    session_id = Column(String(32), primary_key=True, default=new_id)
    taste = Column(String(16), nullable=False)  # 存枚举 .value：辣 / 清淡
    budget = Column(String(16), nullable=False)  # 低 / 中 / 高
    weather = Column(String(16), nullable=False)  # 晴 / 雨 / 雪
    status = Column(String(16), nullable=False, default="PENDING")
    current_round = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=_now_utc, index=True)

    rounds = relationship(
        "DebateRoundModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DebateRoundModel.round_number",
    )
    recommendation = relationship(
        "RecommendationModel",
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )


class AgentModel(Base):
    """大厨 Agent 表（预设两位，Sprint 3 支持自定义）。"""

    __tablename__ = "agents"

    agent_id = Column(String(32), primary_key=True, default=new_id)
    name = Column(String(64), nullable=False, unique=True)
    system_prompt = Column(Text, nullable=False)
    avatar = Column(String(16), nullable=False, default="👨‍🍳")
    created_at = Column(DateTime, nullable=False, default=_now_utc)


class DebateRoundModel(Base):
    """单条发言表。"""

    __tablename__ = "debate_rounds"

    id = Column(String(32), primary_key=True, default=new_id)
    session_id = Column(
        String(32), ForeignKey("sessions.session_id"), nullable=False, index=True
    )
    speaker_id = Column(String(32), ForeignKey("agents.agent_id"), nullable=False)
    round_number = Column(Integer, nullable=False, index=True)
    speaker_name = Column(String(64), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now_utc, index=True)

    session = relationship("SessionModel", back_populates="rounds")


class RecommendationModel(Base):
    """结构化战报表。"""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(32), ForeignKey("sessions.session_id"), nullable=False, unique=True, index=True
    )
    final_choice = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    pros = Column(JSON, nullable=False, default=list)
    cons = Column(JSON, nullable=False, default=list)
    score = Column(Float, nullable=False)
    winner_agent = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=_now_utc)

    session = relationship("SessionModel", back_populates="recommendation")
