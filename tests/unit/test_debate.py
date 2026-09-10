"""单元测试：覆盖 Agent 响应解析、辩论轮次控制、输入校验等核心逻辑。"""
from __future__ import annotations

import pytest

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


def _make_req(**overrides):
    params = {
        "taste": TastePreference.SPICY,
        "budget": BudgetLevel.MEDIUM,
        "weather": WeatherCondition.SUNNY,
    }
    params.update(overrides)
    return DebateStartRequest(**params)


def test_start_debate_creates_session_with_rounds():
    service = DebateService(llm=_FakeLLM(), rounds=3)
    session = service.start_debate(_make_req())

    assert session.session_id
    assert session.status == SessionStatus.SUCCESS
    assert session.current_round == 3
    # 两位大厨 × 3 轮 = 6 条发言
    assert len(session.rounds) == 6


def test_rounds_alternate_between_agents():
    service = DebateService(llm=_FakeLLM(), rounds=2)
    session = service.start_debate(_make_req())

    speakers = [r.speaker_id for r in session.rounds]
    assert speakers[0] == "agent-spicy"
    assert speakers[1] == "agent-cantonese"
    assert speakers[2] == "agent-spicy"
    assert speakers[3] == "agent-cantonese"


def test_get_status_returns_session():
    service = DebateService(llm=_FakeLLM(), rounds=1)
    session = service.start_debate(_make_req())

    assert service.get_status(session.session_id) is session
    assert service.get_status("nonexistent") is None


def test_list_rounds_sorted():
    service = DebateService(llm=_FakeLLM(), rounds=3)
    session = service.start_debate(_make_req())
    rounds = service.list_rounds(session.session_id)

    assert len(rounds) == 6
    round_nums = [r.round_number for r in rounds]
    assert round_nums == sorted(round_nums)


def test_invalid_taste_rejected():
    with pytest.raises(Exception):
        DebateStartRequest(taste="甜", budget="中", weather="晴")


def test_sanitize_removes_control_chars():
    # \x00 与 \n 均属控制字符被移除，连续空白被压缩为单个空格
    assert _sanitize("a\x00b  c\nd") == "ab cd"


def test_rounds_bounded_by_max():
    # 轮次参数异常时应被限制（防御性编程）
    service = DebateService(llm=_FakeLLM(), rounds=99)
    session = service.start_debate(_make_req())
    assert session.current_round <= 10
