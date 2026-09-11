"""集成测试：异步辩论端点（实时可见功能）。"""
from __future__ import annotations

import time


def test_start_async_returns_session_id(client):
    """异步启动应返回 202 + session_id + is_complete=False。"""
    resp = client.post(
        "/api/debate/start-async",
        json={"taste": "辣", "budget": "中", "weather": "晴"},
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["session_id"]
    assert data["status"] == "RUNNING"
    assert data["is_complete"] is False


def test_async_then_poll_until_complete(client):
    """轮询直到 is_complete=True，最终应有 6 条发言与战报。"""
    resp = client.post(
        "/api/debate/start-async",
        json={"taste": "清淡", "budget": "低", "weather": "雨"},
    )
    session_id = resp.json()["session_id"]

    final = None
    for _ in range(30):
        status = client.get(f"/api/debate/{session_id}/status").json()
        if status.get("is_complete"):
            final = status
            break
        time.sleep(0.2)

    assert final is not None, "辩论未在预期时间内完成"
    assert final["status"] == "SUCCESS"
    assert len(final["rounds"]) == 6
    assert final["recommendation"] is not None


def test_status_includes_is_complete_field(client):
    """status 响应必须含 is_complete 字段（前端轮询依赖）。"""
    resp = client.post(
        "/api/debate/start",
        json={"taste": "辣", "budget": "中", "weather": "晴"},
    )
    data = resp.json()
    assert "is_complete" in data
    assert data["is_complete"] is True
