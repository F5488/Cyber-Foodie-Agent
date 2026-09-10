"""FastAPI 入口：暴露辩论相关 REST API。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .db import init_db
from .debate import DebateService
from .models import DebateStartRequest, Session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库表。"""
    init_db()
    yield


app = FastAPI(
    title="Cyber Foodie Agent",
    description="AI 大厨辩论系统 — 多轮自动辩论，产出结构化战报",
    version="0.2.0",
    lifespan=lifespan,
)


service = DebateService()

# 简单内存频控：单 IP 每分钟请求上限
_rate_limit: dict[str, list[float]] = {}
_RATE_LIMIT = int(__import__("os").getenv("RATE_LIMIT", "60"))


def _is_rate_limited(client_ip: str) -> bool:
    """简易滑动窗口频控。"""
    import time

    now = time.time()
    window = _rate_limit.setdefault(client_ip, [])
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= _RATE_LIMIT:
        return True
    window.append(now)
    return False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/debate/start", response_model=Session, status_code=201)
def start_debate(req: DebateStartRequest, request: Request) -> Session:
    """启动辩论（US01）。"""
    client_ip = request.client.host if request.client else "unknown"
    if _is_rate_limited(client_ip):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    try:
        session = service.start_debate(req)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"辩论执行失败: {exc}") from exc
    return session


@app.get("/api/debate/{session_id}/status", response_model=Session)
def get_status(session_id: str) -> Session:
    """查询会话状态与全部发言（US02）。"""
    session = service.get_status(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@app.get("/api/debate/{session_id}/rounds")
def get_rounds(session_id: str) -> dict:
    """按轮次返回发言列表（US02）。"""
    session = service.get_status(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    rounds = service.list_rounds(session_id)
    return {"session_id": session_id, "status": session.status, "rounds": rounds}


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:  # noqa: B008
    """统一兜底错误处理。"""
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
