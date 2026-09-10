"""单元测试：覆盖 Agent 响应解析、辩论轮次控制、输入校验等核心逻辑。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db import Base
from src.debate import DebateService, _sanitize
from src.llm import LLMClient
from src.models import (
    BudgetLevel,
    DebateStartRequest,
    SessionStatus,
    TastePreference,
    WeatherCondition,
)


class _FakeLLM(LLMClient):
    """测试用假客户端，返回可预测的发言。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if "川辣派" in system_prompt:
            return "辣派发言"
        return "粤派发言"


@pytest.fixture()
def session_factory():
    """每个测试一个独立的内存 SQLite 数据库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    # 注册 ORM 模型并建表
    from src import orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    Base.metadata.drop_all(bind=engine)


def _make_service(session_factory, rounds=3) -> DebateService:
    return DebateService(llm=_FakeLLM(), rounds=rounds, session_factory=session_factory)


def _make_req(**overrides):
    params = {
        "taste": TastePreference.SPICY,
        "budget": BudgetLevel.MEDIUM,
        "weather": WeatherCondition.SUNNY,
    }
    params.update(overrides)
    return DebateStartRequest(**params)


def test_start_debate_creates_session_with_rounds(session_factory):
    service = _make_service(session_factory, rounds=3)
    session = service.start_debate(_make_req())

    assert session.session_id
    assert session.status == SessionStatus.SUCCESS
    assert session.current_round == 3
    # 两位大厨 × 3 轮 = 6 条发言
    assert len(session.rounds) == 6


def test_rounds_alternate_between_agents(session_factory):
    service = _make_service(session_factory, rounds=2)
    session = service.start_debate(_make_req())

    speakers = [r.speaker_id for r in session.rounds]
    assert speakers[0] == "agent-spicy"
    assert speakers[1] == "agent-cantonese"
    assert speakers[2] == "agent-spicy"
    assert speakers[3] == "agent-cantonese"


def test_get_status_returns_session(session_factory):
    service = _make_service(session_factory, rounds=1)
    session = service.start_debate(_make_req())

    assert service.get_status(session.session_id).session_id == session.session_id
    assert service.get_status("nonexistent") is None


def test_list_rounds_sorted(session_factory):
    service = _make_service(session_factory, rounds=3)
    session = service.start_debate(_make_req())
    rounds = service.list_rounds(session.session_id)

    assert len(rounds) == 6
    round_nums = [r.round_number for r in rounds]
    assert round_nums == sorted(round_nums)


def test_persistence_survives_new_service_instance(session_factory):
    """持久化验证：新 service 实例（模拟重启）仍能读到历史会话。"""
    service1 = _make_service(session_factory, rounds=1)
    session = service1.start_debate(_make_req())

    service2 = _make_service(session_factory, rounds=1)
    loaded = service2.get_status(session.session_id)
    assert loaded is not None
    assert loaded.session_id == session.session_id
    assert len(loaded.rounds) == 2


def test_list_sessions_returns_history(session_factory):
    service = _make_service(session_factory, rounds=1)
    service.start_debate(_make_req())
    sessions = service.list_sessions()
    assert len(sessions) == 1


def test_invalid_taste_rejected():
    with pytest.raises(Exception):
        DebateStartRequest(taste="甜", budget="中", weather="晴")


def test_sanitize_removes_control_chars():
    # \x00 与 \n 均属控制字符被移除，连续空白被压缩为单个空格
    assert _sanitize("a\x00b  c\nd") == "ab cd"


def test_rounds_bounded_by_max(session_factory):
    # 轮次参数异常时应被限制（防御性编程）
    service = _make_service(session_factory, rounds=99)
    session = service.start_debate(_make_req())
    assert session.current_round <= 10
