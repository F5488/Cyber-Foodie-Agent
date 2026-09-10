"""单元测试：LLM 客户端工厂与 Mock 响应。"""
from __future__ import annotations

import pytest

from src.llm import LLMError, MockLLMClient, get_llm_client


def test_get_llm_client_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    client = get_llm_client()
    assert isinstance(client, MockLLMClient)


def test_mock_spicy_response(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    client = get_llm_client()
    out = client.generate("你是川辣派大厨", "预算中，天气晴")
    assert "川辣派" in out
    assert "麻辣香锅" in out


def test_mock_cantonese_response(monkeypatch):
    client = MockLLMClient()
    out = client.generate("你是粤式养生派大厨", "天气晴，预算中")
    assert "粤式养生派" in out
    assert "白切鸡" in out


def test_openai_client_requires_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai_compatible")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        get_llm_client()


def test_azure_client_requires_config(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_KEY", raising=False)
    with pytest.raises(LLMError):
        get_llm_client()
