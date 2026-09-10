"""FastAPI 入口：暴露辩论相关 REST API。

注意：本模块不使用 `from __future__ import annotations`，
因为 slowapi 的 @limiter.limit 装饰器会替换函数对象，导致字符串注解
无法在 FastAPI 中解析。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from .db import init_db
from .debate import DebateService
from .models import DebateStartRequest, Session

# slowapi 频控：按客户端 IP 识别
limiter = Limiter(key_func=get_remote_address)


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

# 注册频控状态与处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


service = DebateService()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/debate/start", response_model=Session, status_code=201)
@limiter.limit("5/minute")
def start_debate(req: DebateStartRequest, request: Request) -> Session:
    """启动辩论（US01），每 IP 每分钟限 5 次。"""
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


@app.get("/api/debate/{session_id}/report")
def get_report(session_id: str) -> dict:
    """返回会话的结构化战报（US03）。"""
    report = service.get_report(session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="战报不存在")
    return report.model_dump(mode="json")


@app.get("/api/debate/sessions")
def list_sessions() -> list[Session]:
    """返回全部历史会话（按创建时间倒序）。"""
    return service.list_sessions()


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:  # noqa: B008
    """统一兜底错误处理。"""
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
