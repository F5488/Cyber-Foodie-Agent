"""辩论服务层：编排两位大厨的多轮自动辩论。

MVP（Sprint 1）采用内存存储；Sprint 2 将替换为数据库持久化。
"""
from __future__ import annotations

import re
from typing import Optional

from .agents import build_default_agents
from .llm import LLMClient, get_llm_client
from .models import (
    DebateRound,
    DebateStartRequest,
    Session,
    SessionStatus,
)

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
    lines = []
    for r in rounds:
        lines.append(f"{r.speaker_name}：{r.content}")
    return "\n".join(lines)


class DebateService:
    """辩论控制器，负责 session 生命周期与轮流发言逻辑。"""

    def __init__(self, llm: Optional[LLMClient] = None, rounds: Optional[int] = None) -> None:
        # Sprint 1：内存存储
        self._sessions: dict[str, Session] = {}
        self._llm = llm or get_llm_client()
        import os

        configured = rounds if rounds is not None else int(os.getenv("DEBATE_ROUNDS", "3"))
        # 钳制到上限，防御异常配置
        self._rounds = max(1, min(configured, MAX_ROUNDS))

    def start_debate(self, req: DebateStartRequest) -> Session:
        """创建会话并立即执行辩论。"""
        session = Session(
            taste=req.taste,
            budget=req.budget,
            weather=req.weather,
            status=SessionStatus.RUNNING,
            agents=build_default_agents(),
        )
        self._sessions[session.session_id] = session
        self._run_debate(session)
        return session

    def get_status(self, session_id: str) -> Optional[Session]:
        """按 session_id 查询会话。"""
        return self._sessions.get(session_id)

    def list_rounds(self, session_id: str) -> list[DebateRound]:
        """返回某会话的发言（按轮次排序，US02）。"""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        return sorted(session.rounds, key=lambda r: (r.round_number, r.created_at))

    def _run_debate(self, session: Session) -> None:
        """轮流调用两位大厨，交替 3 轮（共 6 条发言）。"""
        context = _build_context_prompt(
            DebateStartRequest(
                taste=session.taste,
                budget=session.budget,
                weather=session.weather,
            )
        )
        agents = session.agents
        for round_no in range(1, self._rounds + 1):
            for agent in agents:
                history = _build_history(session.rounds)
                user_prompt = (
                    f"{context}\n\n当前为第 {round_no} 轮辩论，请针对以下对手发言进行立论或反驳：\n"
                    f"{history}"
                )
                content = self._llm.generate(agent.system_prompt, user_prompt)
                session.rounds.append(
                    DebateRound(
                        session_id=session.session_id,
                        round_number=round_no,
                        speaker_id=agent.agent_id,
                        speaker_name=agent.name,
                        content=_sanitize(content),
                    )
                )
        session.current_round = self._rounds
        session.status = SessionStatus.SUCCESS
