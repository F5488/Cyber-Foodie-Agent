"""Agent 管理服务（US04）：CRUD + 克隆，预设 Agent 受保护。"""
from __future__ import annotations

from typing import Optional

from . import db
from .agents import build_default_agents
from .models import Agent, AgentCreateRequest, AgentUpdateRequest
from .orm_models import AgentModel


class AgentNotFoundError(Exception):
    """Agent 不存在。"""


class PresetAgentProtectedError(Exception):
    """预设 Agent 不可删除。"""


class AgentNameConflictError(Exception):
    """Agent 名称已存在。"""


def _to_pydantic(a: AgentModel) -> Agent:
    return Agent(
        agent_id=a.agent_id,
        name=a.name,
        system_prompt=a.system_prompt,
        avatar=a.avatar,
        description=a.description or "",
        is_preset=bool(a.is_preset),
        created_by=a.created_by,
        created_at=a.created_at,
    )


class AgentService:
    """Agent CRUD 服务。"""

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or db.SessionLocal

    def seed_presets(self) -> None:
        """确保预设大厨存在（幂等）。"""
        with self._session_factory() as dbs:
            for a in build_default_agents():
                if dbs.get(AgentModel, a.agent_id) is None:
                    dbs.add(
                        AgentModel(
                            agent_id=a.agent_id,
                            name=a.name,
                            system_prompt=a.system_prompt,
                            avatar=a.avatar,
                            description=a.description,
                            is_preset=1,
                        )
                    )
            dbs.commit()

    def list_agents(self) -> list[Agent]:
        """列出全部 Agent（预设在前，按名称排序）。"""
        self.seed_presets()
        with self._session_factory() as dbs:
            rows = (
                dbs.query(AgentModel)
                .order_by(AgentModel.is_preset.desc(), AgentModel.name.asc())
                .all()
            )
            return [_to_pydantic(r) for r in rows]

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        with self._session_factory() as dbs:
            row = dbs.get(AgentModel, agent_id)
            return _to_pydantic(row) if row else None

    def create_agent(self, req: AgentCreateRequest) -> Agent:
        """创建自定义 Agent。"""
        with self._session_factory() as dbs:
            if dbs.query(AgentModel).filter(AgentModel.name == req.name).first():
                raise AgentNameConflictError(f"名称 {req.name} 已存在")
            row = AgentModel(
                name=req.name,
                system_prompt=req.system_prompt,
                avatar=req.avatar,
                description=req.description,
                is_preset=0,
                created_by="user",
            )
            dbs.add(row)
            dbs.commit()
            dbs.refresh(row)
            return _to_pydantic(row)

    def update_agent(self, agent_id: str, req: AgentUpdateRequest) -> Agent:
        """更新 Agent 字段（仅更新提供的字段）。"""
        with self._session_factory() as dbs:
            row = dbs.get(AgentModel, agent_id)
            if row is None:
                raise AgentNotFoundError(agent_id)
            if req.name is not None:
                dup = (
                    dbs.query(AgentModel)
                    .filter(AgentModel.name == req.name, AgentModel.agent_id != agent_id)
                    .first()
                )
                if dup:
                    raise AgentNameConflictError(f"名称 {req.name} 已存在")
                row.name = req.name
            if req.system_prompt is not None:
                row.system_prompt = req.system_prompt
            if req.avatar is not None:
                row.avatar = req.avatar
            if req.description is not None:
                row.description = req.description
            dbs.commit()
            dbs.refresh(row)
            return _to_pydantic(row)

    def delete_agent(self, agent_id: str) -> None:
        """删除 Agent，预设不可删。"""
        self.seed_presets()
        with self._session_factory() as dbs:
            row = dbs.get(AgentModel, agent_id)
            if row is None:
                raise AgentNotFoundError(agent_id)
            if row.is_preset:
                raise PresetAgentProtectedError(f"预设 Agent {row.name} 不可删除")
            dbs.delete(row)
            dbs.commit()

    def clone_agent(self, agent_id: str, new_name: Optional[str] = None) -> Agent:
        """克隆一个 Agent（含预设），返回副本。"""
        self.seed_presets()
        with self._session_factory() as dbs:
            row = dbs.get(AgentModel, agent_id)
            if row is None:
                raise AgentNotFoundError(agent_id)
            name = new_name or f"{row.name}（副本）"
            # 若重名则追加序号
            base = name
            n = 2
            while dbs.query(AgentModel).filter(AgentModel.name == name).first():
                name = f"{base}{n}"
                n += 1
            clone = AgentModel(
                name=name,
                system_prompt=row.system_prompt,
                avatar=row.avatar,
                description=row.description,
                is_preset=0,
                created_by="user",
            )
            dbs.add(clone)
            dbs.commit()
            dbs.refresh(clone)
            return _to_pydantic(clone)
