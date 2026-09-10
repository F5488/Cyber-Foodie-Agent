"""战报生成器（US03）：将辩论发言聚合为结构化战报。

流程：
  1. 调用一次 LLM，要求返回 JSON 结构。
  2. 用 Pydantic Report 校验。
  3. 非法 JSON / 校验失败时：重试一次，仍失败则降级为规则摘要。

规则降级保证系统在 LLM 异常时仍能产出可读战报，满足防御性编程要求。
"""
from __future__ import annotations

import json
import re
from typing import Optional

from .llm import LLMClient, LLMError
from .models import DebateRound, ProsCons, Report

_REPORT_SYSTEM_PROMPT = """你是一位美食裁判，需要根据两位大厨的辩论发言，输出一份结构化战报。
严格只返回 JSON，不要输出任何额外文字。JSON 结构如下：
{
  "final_choice": "最终推荐菜品名",
  "reason": "推荐理由摘要（一句话）",
  "pros_cons": {"pros": ["支持观点1"], "cons": ["反对观点1"]},
  "score": 8.5,
  "winner_agent": "川辣派 或 粤式养生派"
}
score 为 0~10 的数值，保留一位小数。winner_agent 必须从两位大厨名字中二选一。"""


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 输出中提取 JSON 对象，容忍 ```json 代码块等噪声。"""
    if not text:
        return None
    # 去掉 markdown 代码块围栏
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    # 尝试直接解析
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 提取首个 { ... } 子串
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _build_fallback_report(rounds: list[DebateRound]) -> Report:
    """规则降级：基于发言的关键词与发言顺序构造战报。

    - 若发言中出现「推荐」，则取第一个被推荐菜品名。
    - 否则按发言人划分正反观点。
    - 获胜方取发言更多的 Agent。
    """
    pros: list[str] = []
    cons: list[str] = []
    final_choice = "家常小炒"
    reason = "根据两位大厨的辩论综合权衡，为您推荐家常小炒，荤素搭配、口味适中。"

    by_speaker: dict[str, list[str]] = {}
    for r in rounds:
        by_speaker.setdefault(r.speaker_name, []).append(r.content)
        m = re.search(r"推荐([一-龥A-Za-z]+)", r.content)
        if m and final_choice == "家常小炒":
            final_choice = m.group(1)

    names = list(by_speaker.keys())
    if names:
        pros = [f"{names[0]}：{by_speaker[names[0]][0][:50]}"]
    if len(names) > 1:
        cons = [f"{names[1]}：{by_speaker[names[1]][0][:50]}"]

    # 获胜方 = 发言更多者；持平取第一位
    winner = names[0] if names else "川辣派"
    if len(names) > 1 and len(by_speaker[names[1]]) > len(by_speaker[names[0]]):
        winner = names[1]

    return Report(
        final_choice=final_choice,
        reason=reason,
        pros_cons=ProsCons(pros=pros, cons=cons),
        score=7.0,
        winner_agent=winner,
    )


def generate_report(llm: LLMClient, rounds: list[DebateRound]) -> Report:
    """调用 LLM 生成战报；失败重试一次，仍失败则规则降级。"""
    if not rounds:
        return _build_fallback_report(rounds)

    transcript = "\n".join(f"{r.speaker_name}：{r.content}" for r in rounds)
    user_prompt = f"以下是辩论完整记录：\n\n{transcript}\n\n请输出战报 JSON。"

    for attempt in range(2):  # 原始 + 重试 1 次
        try:
            raw = llm.generate(_REPORT_SYSTEM_PROMPT, user_prompt)
            data = _extract_json(raw)
            if data is not None:
                # 兼容 LLM 未返回 pros_cons 字段的情况
                data.setdefault("pros_cons", {"pros": [], "cons": []})
                return Report.model_validate(data)
        except (LLMError, ValueError, TypeError):
            continue

    # 兜底降级
    return _build_fallback_report(rounds)
