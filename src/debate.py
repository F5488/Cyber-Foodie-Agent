"""辩论服务层：编排两位大厨的多轮自动辩论，并持久化到数据库。

Sprint 2：内存字典替换为 SQLAlchemy 读写，服务重启后可查询历史会话。
"""
from __future__ import annotations

import os
import re
from typing import Optional

from sqlalchemy.orm import Session as DbSession

from . import db
from .agents import build_default_agents
from .llm import LLMClient, get_llm_client
from .models import (
    Agent,
    BudgetLevel,
    DebateRound,
    DebateStartRequest,
    ProsCons,
    Recommendation,
    Session,
    SessionStatus,
    TastePreference,
    WeatherCondition,
)
from .orm_models import AgentModel, DebateRoundModel, RecommendationModel, SessionModel
from .report import generate_report

# 允许的轮次上限，防御异常输入
MAX_ROUNDS = 10


def _sanitize(text: str) -> str:
    """基础输入清洗：去控制字符、压缩空白，降低 Prompt 注入风险。"""
    text = re.sub(r"[\x00-\x1f\x7f]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_context_prompt(req: DebateStartRequest) -> str:
    """将用户输入拼装为注入给 LLM 的上下文。"""
    return (
        f"用户口味偏好：{req.taste.value}；"
        f"预算等级：{req.budget.value}；"
        f"当前天气：{req.weather.value}。"
    )


def _build_history(rounds: list[DebateRound]) -> str:
    """将历史发言拼装为对话上下文，供后续轮次反驳。"""
    if not rounds:
        return "（尚无发言，请率先立论。）"
    lines = [f"{r.speaker_name}：{r.content}" for r in rounds]
    return "\n".join(lines)


class DebateService:
    """辩论控制器，负责 session 生命周期与轮流发言逻辑。"""

    def __init__(
        self,
        llm: Optional[LLMClient] = None,
        rounds: Optional[int] = None,
        session_factory=None,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._session_factory = session_factory or db.SessionLocal

        configured = rounds if rounds is not None else int(os.getenv("DEBATE_ROUNDS", "3"))
        # 钳制到上限，防御异常配置
        self._rounds = max(1, min(configured, MAX_ROUNDS))

    # ------------------------------------------------------------------
    # 对外接口
    # ------------------------------------------------------------------
    def start_debate(self, req: DebateStartRequest) -> Session:
        """创建会话、持久化并立即执行辩论，返回完整 Pydantic 会话。"""
        with self._session_factory() as dbs:
            self._seed_agents(dbs)
            session = SessionModel(
                taste=req.taste.value,
                budget=req.budget.value,
                weather=req.weather.value,
                status=SessionStatus.RUNNING.value,
                current_round=0,
            )
            dbs.add(session)
            dbs.flush()  # 触发 session_id 生成

            agents = self._load_default_agents(dbs)
            self._run_debate(dbs, session, agents, req)
            dbs.commit()
            return self._orm_to_pydantic(dbs, session)

    def get_status(self, session_id: str) -> Optional[Session]:
        """按 session_id 从数据库查询会话。"""
        with self._session_factory() as dbs:
            orm = dbs.get(SessionModel, session_id)
            if orm is None:
                return None
            return self._orm_to_pydantic(dbs, orm)

    def list_rounds(self, session_id: str) -> list[DebateRound]:
        """返回某会话的发言（按轮次与插入顺序排序，US02）。"""
        with self._session_factory() as dbs:
            orm = dbs.get(SessionModel, session_id)
            if orm is None:
                return []
            rounds = sorted(orm.rounds, key=lambda r: (r.round_number, r.id))
            return [self._round_to_pydantic(r) for r in rounds]

    def list_sessions(self) -> list[Session]:
        """返回全部历史会话（按创建时间倒序，用于前端历史侧边栏）。"""
        with self._session_factory() as dbs:
            orms = dbs.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
            return [self._orm_to_pydantic(dbs, o) for o in orms]

    def get_report(self, session_id: str) -> Optional[Recommendation]:
        """返回某会话的战报（US03），无战报返回 None。"""
        with self._session_factory() as dbs:
            orm = dbs.get(SessionModel, session_id)
            if orm is None or orm.recommendation is None:
                return None
            rec = orm.recommendation
            return Recommendation(
                final_choice=rec.final_choice,
                reason=rec.reason,
                pros_cons=ProsCons(pros=rec.pros or [], cons=rec.cons or []),
                score=rec.score,
                winner_agent=rec.winner_agent,
                created_at=rec.created_at,
            )

    # ------------------------------------------------------------------
    # 内部：Agent 与辩论编排
    # ------------------------------------------------------------------
    def _seed_agents(self, dbs: DbSession) -> None:
        """确保预设两位大厨已写入 agents 表（幂等）。"""
        for a in build_default_agents():
            if dbs.get(AgentModel, a.agent_id) is None:
                dbs.add(
                    AgentModel(
                        agent_id=a.agent_id,
                        name=a.name,
                        system_prompt=a.system_prompt,
                        avatar=a.avatar,
                    )
                )

    def _load_default_agents(self, dbs: DbSession) -> list[AgentModel]:
        """加载预设大厨的 ORM 对象。"""
        return [dbs.get(AgentModel, a.agent_id) for a in build_default_agents()]

    def _run_debate(
        self,
        dbs: DbSession,
        session: SessionModel,
        agents: list[AgentModel],
        req: DebateStartRequest,
    ) -> None:
        """轮流调用两位大厨，交替 N 轮，每轮发言即时落库。"""
        context = _build_context_prompt(req)
        pydantic_rounds: list[DebateRound] = []
        for round_no in range(1, self._rounds + 1):
            for agent in agents:
                history = _build_history(pydantic_rounds)
                user_prompt = (
                    f"{context}\n\n当前为第 {round_no} 轮辩论，请针对以下对手发言进行立论或反驳：\n"
                    f"{history}"
                )
                content = self._llm.generate(agent.system_prompt, user_prompt)
                content = _sanitize(content)
                dbs.add(
                    DebateRoundModel(
                        session_id=session.session_id,
                        speaker_id=agent.agent_id,
                        round_number=round_no,
                        speaker_name=agent.name,
                        content=content,
                    )
                )
                dbs.flush()
                pydantic_rounds.append(
                    DebateRound(
                        session_id=session.session_id,
                        round_number=round_no,
                        speaker_id=agent.agent_id,
                        speaker_name=agent.name,
                        content=content,
                    )
                )
        session.current_round = self._rounds
        session.status = SessionStatus.SUCCESS.value

        # 辩论结束，生成结构化战报并持久化（US03）
        report = generate_report(self._llm, pydantic_rounds)
        dbs.add(
            RecommendationModel(
                session_id=session.session_id,
                final_choice=report.final_choice,
                reason=report.reason,
                pros=report.pros_cons.pros,
                cons=report.pros_cons.cons,
                score=report.score,
                winner_agent=report.winner_agent,
            )
        )

    # ------------------------------------------------------------------
    # 内部：ORM <-> Pydantic 转换
    # ------------------------------------------------------------------
    @staticmethod
    def _round_to_pydantic(r: DebateRoundModel) -> DebateRound:
        return DebateRound(
            id=str(r.id),
            session_id=r.session_id,
            round_number=r.round_number,
            speaker_id=r.speaker_id,
            speaker_name=r.speaker_name,
            content=r.content,
            created_at=r.created_at,
        )

    def _orm_to_pydantic(self, dbs: DbSession, orm: SessionModel) -> Session:
        rounds = sorted(orm.rounds, key=lambda r: (r.round_number, r.id))
        speaker_ids = {r.speaker_id for r in rounds}
        agent_orms = (
            dbs.query(AgentModel).filter(AgentModel.agent_id.in_(speaker_ids)).all()
            if speaker_ids
            else []
        )
        agents = [
            Agent(
                agent_id=a.agent_id,
                name=a.name,
                system_prompt=a.system_prompt,
                avatar=a.avatar,
                created_at=a.created_at,
            )
            for a in agent_orms
        ]

        recommendation = None
        if orm.recommendation is not None:
            rec = orm.recommendation
            recommendation = Recommendation(
                final_choice=rec.final_choice,
                reason=rec.reason,
                pros_cons=ProsCons(pros=rec.pros or [], cons=rec.cons or []),
                score=rec.score,
                winner_agent=rec.winner_agent,
                created_at=rec.created_at,
            )

        return Session(
            session_id=orm.session_id,
            taste=TastePreference(orm.taste),
            budget=BudgetLevel(orm.budget),
            weather=WeatherCondition(orm.weather),
            status=SessionStatus(orm.status),
            current_round=orm.current_round,
            agents=agents,
            rounds=[self._round_to_pydantic(r) for r in rounds],
            recommendation=recommendation,
            created_at=orm.created_at,
        )
