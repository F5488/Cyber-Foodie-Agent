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
