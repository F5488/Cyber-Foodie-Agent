"""单元测试：战报生成器（US03）。"""
from __future__ import annotations

from src.llm import LLMClient, LLMError
from src.models import DebateRound, Report
from src.report import _build_fallback_report, _extract_json, generate_report


def _round(speaker: str, content: str, n: int = 1) -> DebateRound:
    return DebateRound(
        session_id="s1", round_number=n, speaker_id=speaker, speaker_name=speaker, content=content
    )


class _JsonLLM(LLMClient):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return (
            '{"final_choice": "白切鸡", "reason": "清淡养胃", '
            '"pros_cons": {"pros": ["本味"], "cons": ["清淡"]}, '
            '"score": 7.5, "winner_agent": "粤式养生派"}'
        )


class _BadJsonLLM(LLMClient):
    """始终返回非法 JSON，触发降级。"""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return "抱歉我无法生成 JSON，这里是一段纯文本推荐……"


class _FlakyLLM(LLMClient):
    """第一次抛错，第二次返回合法 JSON，验证重试逻辑。"""

    def __init__(self) -> None:
        self.calls = 0

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls == 1:
            raise LLMError("网络抖动")
        return (
            '{"final_choice": "麻辣香锅", "reason": "热辣", '
            '"pros_cons": {"pros": ["香"], "cons": ["辣"]}, '
            '"score": 8.0, "winner_agent": "川辣派"}'
        )


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_code_fence():
    text = '```json\n{"a": 1}\n```'
    assert _extract_json(text) == {"a": 1}


def test_extract_json_with_noise():
    text = '好的，这是结果：{"a": 1} 谢谢'
    assert _extract_json(text) == {"a": 1}


def test_extract_json_invalid():
    assert _extract_json("没有 JSON") is None


def test_generate_report_valid():
    rounds = [_round("川辣派", "我推荐麻辣香锅"), _round("粤式养生派", "我推荐白切鸡")]
    report = generate_report(_JsonLLM(), rounds)
    assert isinstance(report, Report)
    assert report.final_choice == "白切鸡"
    assert report.score == 7.5
    assert report.winner_agent == "粤式养生派"


def test_generate_report_fallback_on_bad_json():
    rounds = [_round("川辣派", "我推荐麻辣香锅", 1), _round("粤式养生派", "我推荐白切鸡", 1)]
    report = generate_report(_BadJsonLLM(), rounds)
    assert isinstance(report, Report)
    assert report.final_choice  # 规则降级仍产出非空结果
    assert 0.0 <= report.score <= 10.0


def test_generate_report_retry_then_success():
    rounds = [_round("川辣派", "我推荐麻辣香锅", 1)]
    flaky = _FlakyLLM()
    report = generate_report(flaky, rounds)
    assert flaky.calls == 2
    assert report.final_choice == "麻辣香锅"


def test_generate_report_empty_rounds():
    report = generate_report(_JsonLLM(), [])
    assert report.final_choice == "家常小炒"


def test_fallback_report_picks_first_recommendation():
    rounds = [_round("川辣派", "我推荐水煮鱼", 1), _round("粤式养生派", "我推荐炖汤", 1)]
    report = _build_fallback_report(rounds)
    assert report.final_choice == "水煮鱼"
