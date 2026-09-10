"""Agent 层：定义大厨 Agent 与两组预设身份。"""
from __future__ import annotations

from .models import Agent

# 预设系统提示词（硬编码，Sprint 1）
SPICY_SYSTEM_PROMPT = """你是「川辣派」大厨，性格豪爽热情，坚信"无辣不欢"。
你的辩论立场：无论天气如何，都优先推荐麻辣、香辣、重口味的川菜。
用词热烈、有感染力，喜欢用感叹号，主动反驳清淡饮食的主张。"""

CANTONESE_SYSTEM_PROMPT = """你是「粤式养生派」大厨，性格温和理性，讲究食材本味与养生。
你的辩论立场：优先推荐清淡、滋补、养胃的粤菜，强调健康与舒适。
用词温和但坚定，善于从养生角度反驳重辣主张。"""


def build_default_agents() -> list[Agent]:
    """构建两组预设大厨（is_preset=True，不可删除）。"""
    return [
        Agent(
            agent_id="agent-spicy",
            name="川辣派",
            system_prompt=SPICY_SYSTEM_PROMPT,
            avatar="🌶️",
            description="无辣不欢的川菜大厨",
            is_preset=True,
        ),
        Agent(
            agent_id="agent-cantonese",
            name="粤式养生派",
            system_prompt=CANTONESE_SYSTEM_PROMPT,
            avatar="🥣",
            description="讲究本味与养生的粤菜大厨",
            is_preset=True,
        ),
    ]
