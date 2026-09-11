"""辩论服务层：编排两位大厨的多轮自动辩论，并持久化到数据库。

Sprint 2：内存字典替换为 SQLAlchemy 读写，服务重启后可查询历史会话。
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from . import db
from .agents import build_default_agents
from .llm import LLMClient, get_llm_client
from .models import (
    Agent,
    BudgetLevel,
    DebateRound,
    DebateStartRequest,
    Menu,
    ProsCons,
    Recommendation,
    Session,
    SessionStatus,
    TastePreference,
    WeatherCondition,
)
from .menu_service import MenuService
from .orm_models import (
    AgentModel,
    DebateRoundModel,
    MenuModel,
    RecommendationModel,
    SessionModel,
)
from .report import generate_report

logger = logging.getLogger("uvicorn.error")

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
        """创建会话并同步执行完整辩论，返回完整 Pydantic 会话（供 API/测试/评测）。"""
        session_id = self.create_session(req)
        self.run_debate(session_id, req)
        return self.get_status(session_id)

    def create_session(self, req: DebateStartRequest) -> str:
        """仅创建会话（status=RUNNING）并返回 session_id，不执行辩论。

        供异步模式使用：先返回 session_id，再由后台任务跑辩论。
        """
        with self._session_factory() as dbs:
            self._seed_agents(dbs)
            agents = self._load_selected_agents(dbs, req)
            session = SessionModel(
                taste=req.taste.value,
                budget=req.budget.value,
                weather=req.weather.value,
                status=SessionStatus.RUNNING.value,
                current_round=0,
                agent_a_id=agents[0].agent_id,
                agent_b_id=agents[1].agent_id,
            )
            dbs.add(session)
            dbs.commit()
            return session.session_id

    def run_debate(self, session_id: str, req: DebateStartRequest) -> None:
        """执行某个已存在会话的辩论循环（供后台任务调用）。"""
        try:
            with self._session_factory() as dbs:
                session = dbs.get(SessionModel, session_id)
                if session is None:
                    return
                agents = [
                    dbs.get(AgentModel, aid)
                    for aid in (session.agent_a_id, session.agent_b_id)
                ]
                self._run_debate(dbs, session, agents, req)
                dbs.commit()
        except Exception as exc:  # noqa: BLE001
            logger.error("辩论执行失败 session=%s: %s", session_id, exc)
            with self._session_factory() as dbs:
                session = dbs.get(SessionModel, session_id)
                if session is not None:
                    session.status = SessionStatus.FAILED.value
                    dbs.commit()

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
                menu_item_id=rec.menu_item_id,
                price=rec.price,
                created_at=rec.created_at,
            )

    # ------------------------------------------------------------------
    # 内部：Agent 与辩论编排
    # ------------------------------------------------------------------
    def _seed_agents(self, dbs: DbSession) -> None:
        """确保预设两位大厨已写入 agents 表（幂等，并发安全）。

        并发辩论时多个线程可能同时通过存在性检查 → 同时 INSERT 撞
        name 唯一约束。用 savepoint 包裹单条插入，冲突仅回滚该条并忽略。
        """
        for a in build_default_agents():
            try:
                with dbs.begin_nested():  # savepoint：冲突只回滚这一条
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
            except IntegrityError:
                # 其他线程已插入同名 Agent，忽略即可
                continue

    def _load_selected_agents(self, dbs: DbSession, req: DebateStartRequest) -> list[AgentModel]:
        """根据请求选择两位大厨：不传则用默认，传了则从 DB 读取。"""
        default = build_default_agents()
        agent_a_id = req.agent_a_id or default[0].agent_id
        agent_b_id = req.agent_b_id or default[1].agent_id

        a = dbs.get(AgentModel, agent_a_id)
        b = dbs.get(AgentModel, agent_b_id)
        if a is None or b is None:
            raise ValueError("指定的 Agent 不存在")
        return [a, b]

    def _run_debate(
        self,
        dbs: DbSession,
        session: SessionModel,
        agents: list[AgentModel],
        req: DebateStartRequest,
    ) -> None:
        """轮流调用两位大厨，交替 N 轮；每轮结束后提交，供前端轮询实时查看。"""
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
                pydantic_rounds.append(
                    DebateRound(
                        session_id=session.session_id,
                        round_number=round_no,
                        speaker_id=agent.agent_id,
                        speaker_name=agent.name,
                        content=content,
                    )
                )
            # 每完成一轮即提交，前端轮询可看到逐条冒出的发言
            session.current_round = round_no
            dbs.commit()
        session.status = SessionStatus.SUCCESS.value

        # 辩论结束，生成结构化战报并持久化（US03 + US05）
        # 若菜单表非空，先用预算+口味筛选候选，供 LLM 从中定夺
        candidates = self._load_candidates(dbs, req)
        report = generate_report(self._llm, pydantic_rounds, candidates)

        menu_item = self._match_menu_item(report.final_choice, candidates)
        dbs.add(
            RecommendationModel(
                session_id=session.session_id,
                final_choice=report.final_choice,
                reason=report.reason,
                pros=report.pros_cons.pros,
                cons=report.pros_cons.cons,
                score=report.score,
                winner_agent=report.winner_agent,
                menu_item_id=menu_item.id if menu_item else None,
                price=menu_item.price if menu_item else None,
            )
        )

    def _load_candidates(self, dbs: DbSession, req: DebateStartRequest) -> list[Menu]:
        """从菜单表筛选候选菜品（预算 + 口味标签），菜单为空返回空列表。"""
        rows = dbs.query(MenuModel).filter(MenuModel.availability == 1).all()
        if not rows:
            return []
        menus = [
            Menu(
                id=m.id,
                name=m.name,
                price=m.price,
                category=m.category,
                tags=m.tags or [],
                availability=bool(m.availability),
                source=m.source,
            )
            for m in rows
        ]
        return MenuService.filter_candidates_by_rules(menus, req.taste.value, req.budget.value)

    @staticmethod
    def _match_menu_item(final_choice: str, candidates: list[Menu]) -> Optional[Menu]:
        """按名称匹配候选中的菜品，返回对应 Menu（含 id/price）。"""
        for m in candidates:
            if m.name == final_choice or m.name in final_choice or final_choice in m.name:
                return m
        return None

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
        # 优先用 session 记录的大厨 id，回退到发言中出现的 speaker
        agent_ids = {r.speaker_id for r in rounds}
        for aid in (orm.agent_a_id, orm.agent_b_id):
            if aid:
                agent_ids.add(aid)
        agent_orms = (
            dbs.query(AgentModel).filter(AgentModel.agent_id.in_(agent_ids)).all()
            if agent_ids
            else []
        )
        agents = [
            Agent(
                agent_id=a.agent_id,
                name=a.name,
                system_prompt=a.system_prompt,
                avatar=a.avatar,
                description=a.description or "",
                is_preset=bool(a.is_preset),
                created_by=a.created_by,
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
                menu_item_id=rec.menu_item_id,
                price=rec.price,
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
