"""LLM 客户端抽象层：支持多 provider 切换与 Mock 兜底。

通过环境变量 LLM_PROVIDER 选择实现：
  - mock               : 内置大厨响应（零配置，用于演示与 CI）
  - openai_compatible  : DeepSeek / 硅基流动 等 OpenAI 兼容协议
  - azure_openai       : 微软 Azure OpenAI

模型名解析（openai_compatible）：OPENAI_MODEL → DEFAULT_MODEL → deepseek-chat。
所有外部调用均设置超时与重试（指数退避），满足防御性编程要求。
"""
from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx

# 使用 uvicorn.error 通道，保证日志出现在 uvicorn 启动终端
logger = logging.getLogger("uvicorn.error")


class LLMError(RuntimeError):
    """LLM 调用失败时抛出。"""


class LLMClient(ABC):
    """LLM 客户端统一接口。"""

    provider: str = "unknown"

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """根据系统提示词与用户输入，生成一段文本响应。"""
        raise NotImplementedError


def _resolve_openai_model() -> str:
    """解析 OpenAI 兼容协议的模型名：OPENAI_MODEL → DEFAULT_MODEL → 兜底。"""
    return os.getenv("OPENAI_MODEL") or os.getenv("DEFAULT_MODEL") or "deepseek-chat"


def _resolve_openai_base_url() -> str:
    return os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com").rstrip("/")


def get_llm_info() -> dict:
    """返回当前 LLM 配置摘要（绝不含 api_key），供 /health 使用。"""
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    if provider == "openai_compatible":
        return {
            "llm_provider": "openai_compatible",
            "is_mock": False,
            "model": _resolve_openai_model(),
            "base_url": _resolve_openai_base_url(),
        }
    if provider == "azure_openai":
        return {
            "llm_provider": "azure_openai",
            "is_mock": False,
            "model": os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
            "base_url": os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/"),
        }
    return {
        "llm_provider": "mock",
        "is_mock": True,
        "model": "mock",
        "base_url": "",
    }


def _retry_httpx_post(url: str, **kwargs) -> httpx.Response:
    """带指数退避重试的 POST 请求。

    超时 30s，最多重试 3 次，退避间隔 1s / 2s / 4s。
    """
    last_err: Optional[Exception] = None
    for attempt in range(4):  # 1 次原始 + 3 次重试
        try:
            resp = httpx.post(url, timeout=30.0, **kwargs)
            resp.raise_for_status()
            return resp
        except (httpx.HTTPError, httpx.TimeoutException) as exc:  # noqa: B014
            last_err = exc
            if attempt < 3:
                time.sleep(2**attempt)
    raise LLMError(f"LLM 调用失败（已重试 3 次）: {last_err}")


class MockLLMClient(LLMClient):
    """Mock 客户端：无需 API Key，按大厨身份返回预设风格发言。"""

    provider = "mock"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # 战报请求：返回结构化 JSON
        if "美食裁判" in system_prompt or "结构化战报" in system_prompt:
            # 若 user_prompt 含候选列表，取第一个候选作为 final_choice
            choice = self._extract_candidate(user_prompt) or "麻辣香锅"
            return (
                f'{{"final_choice": "{choice}", '
                '"reason": "综合辩论与候选菜品，此方案最契合口味与预算。", '
                '"pros_cons": {"pros": ["口味契合、价格合理"], "cons": ["口味单一"]}, '
                '"score": 8.5, "winner_agent": "川辣派"}'
            )
        name = "大厨"
        if "川辣派" in system_prompt:
            name = "川辣派"
            return (
                f"{name}：这位同学，天气这么{self._extract_weather(user_prompt)}，"
                f"当然要吃点热辣的！我推荐麻辣香锅，预算{self._extract_budget(user_prompt)}完全够，"
                "花椒的麻与辣椒的香，一筷子下去浑身通透！"
            )
        if "粤式养生派" in system_prompt:
            name = "粤式养生派"
            return (
                f"{name}：还是听我一句劝，{self._extract_weather(user_prompt)}天宜清淡养胃。"
                "我推荐白切鸡配老火靓汤，食材本味，温和滋补，"
                f"同样的预算{self._extract_budget(user_prompt)}，吃得更舒服不上火。"
            )
        return f"{name}：收到，我的建议是均衡饮食，荤素搭配。"

    @staticmethod
    def _extract_weather(user_prompt: str) -> str:
        for w in ("晴", "雨", "雪"):
            if w in user_prompt:
                return w
        return "今天"

    @staticmethod
    def _extract_candidate(user_prompt: str) -> str:
        """从候选列表文本中提取第一个菜品名（格式：id=N 名称=XX 价格=...）。"""
        import re

        m = re.search(r"名称=([^\s]+)", user_prompt)
        return m.group(1) if m else ""

    @staticmethod
    def _extract_budget(user_prompt: str) -> str:
        for b in ("低", "中", "高"):
            if f"预算{b}" in user_prompt or b in user_prompt:
                return b
        return ""


class OpenAICompatibleClient(LLMClient):
    """OpenAI 兼容协议客户端（DeepSeek / 硅基流动）。"""

    provider = "openai_compatible"

    def __init__(self) -> None:
        self.base_url = _resolve_openai_base_url()
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.model = _resolve_openai_model()
        if not self.api_key:
            raise LLMError("缺少 OPENAI_API_KEY，无法使用 openai_compatible provider")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        logger.info(
            "LLM 调用: provider=%s model=%s url=%s", self.provider, self.model, url
        )
        start = time.time()
        try:
            resp = _retry_httpx_post(
                url,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                },
            )
        except LLMError as exc:
            logger.error("LLM 调用失败: %s", exc)
            raise
        elapsed = (time.time() - start) * 1000
        logger.info(
            "LLM 响应: status=%s 耗时=%.1fms", resp.status_code, elapsed
        )
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("LLM 响应解析失败: %s", data)
            raise LLMError(f"解析 LLM 响应失败: {data}") from exc


class AzureOpenAIClient(LLMClient):
    """Azure OpenAI 客户端。"""

    provider = "azure_openai"

    def __init__(self) -> None:
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.api_key = os.getenv("AZURE_OPENAI_KEY", "")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        if not (self.endpoint and self.api_key and self.deployment):
            raise LLMError("Azure OpenAI 配置不完整（endpoint/key/deployment）")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )
        logger.info(
            "LLM 调用: provider=%s model=%s url=%s", self.provider, self.deployment, url
        )
        start = time.time()
        try:
            resp = _retry_httpx_post(
                url,
                headers={"api-key": self.api_key},
                json={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.7,
                },
            )
        except LLMError as exc:
            logger.error("LLM 调用失败: %s", exc)
            raise
        elapsed = (time.time() - start) * 1000
        logger.info("LLM 响应: status=%s 耗时=%.1fms", resp.status_code, elapsed)
        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("LLM 响应解析失败: %s", data)
            raise LLMError(f"解析 LLM 响应失败: {data}") from exc


def get_llm_client() -> LLMClient:
    """根据环境变量创建 LLM 客户端实例。"""
    provider = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    if provider == "openai_compatible":
        return OpenAICompatibleClient()
    if provider == "azure_openai":
        return AzureOpenAIClient()
    if provider != "mock":
        logger.warning(
            "未知的 LLM_PROVIDER=%r，回退到 Mock 大厨（可选：mock/openai_compatible/azure_openai）",
            provider,
        )
    else:
        logger.warning("LLM key 未配置或 provider=mock，使用 Mock 大厨")
    return MockLLMClient()
