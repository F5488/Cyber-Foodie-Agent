"""单元测试：Agent 管理服务（US04）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.agent_service import (
    AgentNameConflictError,
    AgentNotFoundError,
    AgentService,
    PresetAgentProtectedError,
)
from src.db import Base
from src.models import AgentCreateRequest, AgentUpdateRequest


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    from src import orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    Base.metadata.drop_all(bind=engine)


def _svc(session_factory) -> AgentService:
    return AgentService(session_factory=session_factory)


def test_list_agents_seeds_presets(session_factory):
    svc = _svc(session_factory)
    agents = svc.list_agents()
    names = {a.name for a in agents}
    assert {"川辣派", "粤式养生派"} <= names
    assert all(a.is_preset for a in agents)


def test_create_agent(session_factory):
    svc = _svc(session_factory)
    a = svc.create_agent(
        AgentCreateRequest(name="日式轻食", system_prompt="你是日式料理大厨", avatar="🍣")
    )
    assert a.agent_id
    assert a.is_preset is False
    assert a.name == "日式轻食"


def test_create_duplicate_name_conflict(session_factory):
    svc = _svc(session_factory)
    svc.create_agent(AgentCreateRequest(name="日式", system_prompt="p"))
    with pytest.raises(AgentNameConflictError):
        svc.create_agent(AgentCreateRequest(name="日式", system_prompt="q"))


def test_update_agent(session_factory):
    svc = _svc(session_factory)
    a = svc.create_agent(AgentCreateRequest(name="日式", system_prompt="p"))
    updated = svc.update_agent(a.agent_id, AgentUpdateRequest(system_prompt="新提示词"))
    assert updated.system_prompt == "新提示词"
    assert updated.name == "日式"


def test_update_not_found(session_factory):
    svc = _svc(session_factory)
    with pytest.raises(AgentNotFoundError):
        svc.update_agent("nonexistent", AgentUpdateRequest(name="x"))


def test_delete_custom_agent(session_factory):
    svc = _svc(session_factory)
    a = svc.create_agent(AgentCreateRequest(name="日式", system_prompt="p"))
    svc.delete_agent(a.agent_id)
    assert svc.get_agent(a.agent_id) is None


def test_delete_preset_protected(session_factory):
    svc = _svc(session_factory)
    with pytest.raises(PresetAgentProtectedError):
        svc.delete_agent("agent-spicy")


def test_clone_preset(session_factory):
    svc = _svc(session_factory)
    clone = svc.clone_agent("agent-spicy")
    assert clone.agent_id != "agent-spicy"
    assert clone.is_preset is False
    assert "川辣派" in clone.name
    assert clone.system_prompt  # 继承了预设提示词


def test_clone_not_found(session_factory):
    svc = _svc(session_factory)
    with pytest.raises(AgentNotFoundError):
        svc.clone_agent("nonexistent")


# ---------------------------------------------------------------------------
# 模板库 与 一句话生成 Prompt（US04 体验优化）
# ---------------------------------------------------------------------------
def test_templates_count_and_fields():
    from src.agent_templates import AGENT_TEMPLATES

    assert len(AGENT_TEMPLATES) >= 6
    for t in AGENT_TEMPLATES:
        assert t.avatar and t.name and t.description and t.system_prompt
        assert len(t.system_prompt) <= 2000


def test_get_template_by_name():
    from src.agent_templates import get_template

    assert get_template("川辣派") is not None
    assert get_template("不存在的风格") is None


def test_generate_prompt_with_mock(session_factory):
    from src.agent_service import AgentService
    from src.llm import MockLLMClient

    svc = AgentService(session_factory=session_factory, llm=MockLLMClient())
    prompt = svc.generate_prompt("喜欢日料、不吃辣")
    assert prompt
    assert len(prompt) <= 2000


def test_generate_prompt_fallback_on_llm_error(session_factory):
    """LLM 抛异常时应降级为规则模板，而非报错。"""
    from src.agent_service import AgentService
    from src.llm import LLMClient, LLMError

    class _BrokenLLM(LLMClient):
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise LLMError("模拟失败")

    svc = AgentService(session_factory=session_factory, llm=_BrokenLLM())
    prompt = svc.generate_prompt("喜欢日料")
    assert "日料" in prompt
