"""集成测试：通过 FastAPI TestClient 验证 REST API 全链路。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_start_debate_returns_session():
    resp = client.post(
        "/api/debate/start",
        json={"taste": "辣", "budget": "中", "weather": "晴"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["session_id"]
    assert data["status"] == "SUCCESS"
    assert len(data["rounds"]) == 6  # 2 大厨 × 3 轮


def test_start_debate_invalid_input():
    resp = client.post(
        "/api/debate/start",
        json={"taste": "甜", "budget": "中", "weather": "晴"},
    )
    assert resp.status_code == 422


def test_get_status_and_rounds():
    start = client.post(
        "/api/debate/start",
        json={"taste": "清淡", "budget": "低", "weather": "雨"},
    )
    session_id = start.json()["session_id"]

    resp = client.get(f"/api/debate/{session_id}/status")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == session_id

    rounds = client.get(f"/api/debate/{session_id}/rounds")
    assert rounds.status_code == 200
    assert len(rounds.json()["rounds"]) == 6


def test_get_status_not_found():
    resp = client.get("/api/debate/nonexistent/status")
    assert resp.status_code == 404
