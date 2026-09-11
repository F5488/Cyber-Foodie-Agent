"""FastAPI 入口：暴露辩论相关 REST API。

注意：
1. 本模块不使用 `from __future__ import annotations`，
   因为 slowapi 的 @limiter.limit 装饰器会替换函数对象，导致字符串注解
   无法在 FastAPI 中解析。
2. 必须在导入任何业务模块（llm/debate/db 等）之前加载 .env，
   因为 LLMClient 等对象在模块导入时即按环境变量初始化。
"""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# 加载 .env：显式 UTF-8（避免 Windows GBK 读取含中文注释的 .env 报错），
# override=True 让 .env 优先于手动 set 的环境变量。
# 测试/评测场景通过 CYBER_FOODIE_SKIP_DOTENV=1 跳过，避免覆盖其内存数据库与 Mock 设置。
if not os.getenv("CYBER_FOODIE_SKIP_DOTENV"):
    load_dotenv(encoding="utf-8", override=True)

from .agent_service import (  # noqa: E402
    AgentNameConflictError,
    AgentNotFoundError,
    AgentService,
    PresetAgentProtectedError,
)
from .db import init_db  # noqa: E402
from .debate import DebateService  # noqa: E402
from .llm import get_llm_info  # noqa: E402
from .menu_service import MenuService  # noqa: E402
from .models import (  # noqa: E402
    Agent,
    AgentCreateRequest,
    AgentUpdateRequest,
    DebateStartRequest,
    Menu,
    MenuImportRequest,
    Session,
)

logger = logging.getLogger("uvicorn.error")

# slowapi 频控：按客户端 IP 识别
limiter = Limiter(key_func=get_remote_address)


def _auto_import_sample_menu() -> None:
    """若菜单表为空，自动导入 eval/sample_menu.json（兜底，保证开箱可用）。"""
    svc = MenuService()
    if svc.list_menus():
        return  # 已有菜单，跳过

    sample = Path(__file__).resolve().parent.parent / "eval" / "sample_menu.json"
    if not sample.exists():
        logger.warning("未找到示例菜单文件 %s，跳过自动导入", sample)
        return

    try:
        data = json.loads(sample.read_text(encoding="utf-8"))
        items = [Menu(**item) for item in data.get("items", [])]
        if not items:
            return
        svc.import_menus(MenuImportRequest(items=items))
        logger.info("自动导入 %d 道菜", len(items))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.warning("自动导入示例菜单失败：%s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库表，并自动导入示例菜单（若为空）。"""
    init_db()
    _auto_import_sample_menu()
    yield


app = FastAPI(
    title="Cyber Foodie Agent",
    description="AI 大厨辩论系统 — 多轮自动辩论，产出结构化战报",
    version="0.3.0",
    lifespan=lifespan,
)

# 注册频控状态与处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


service = DebateService()
agent_service = AgentService()
menu_service = MenuService()


@app.get("/health")
def health() -> dict:
    """健康检查，附带 LLM 配置摘要（不含 api_key）。"""
    return {"status": "ok", **get_llm_info()}


# ---------------------------------------------------------------------------
# Agent 管理（US04）
# ---------------------------------------------------------------------------
@app.get("/api/agents", response_model=list[Agent])
def list_agents() -> list[Agent]:
    """列出全部 Agent（预设 + 自定义）。"""
    return agent_service.list_agents()


@app.post("/api/agents", response_model=Agent, status_code=201)
def create_agent(req: AgentCreateRequest) -> Agent:
    """创建自定义 Agent。"""
    try:
        return agent_service.create_agent(req)
    except AgentNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.put("/api/agents/{agent_id}", response_model=Agent)
def update_agent(agent_id: str, req: AgentUpdateRequest) -> Agent:
    """更新 Agent（仅更新提供的字段）。"""
    try:
        return agent_service.update_agent(agent_id, req)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AgentNameConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.delete("/api/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str) -> None:
    """删除 Agent（预设不可删）。"""
    try:
        agent_service.delete_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PresetAgentProtectedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/api/agents/{agent_id}/clone", response_model=Agent, status_code=201)
def clone_agent(agent_id: str) -> Agent:
    """克隆 Agent（含预设），返回可编辑副本。"""
    try:
        return agent_service.clone_agent(agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/debate/start", response_model=Session, status_code=201)
@limiter.limit("5/minute")
def start_debate(req: DebateStartRequest, request: Request) -> Session:
    """启动辩论（US01），每 IP 每分钟限 5 次。"""
    try:
        session = service.start_debate(req)
    except ValueError as exc:
        # 指定的 Agent 不存在
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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


# ---------------------------------------------------------------------------
# 菜单管理（US05）
# ---------------------------------------------------------------------------
@app.post("/api/menus/import", response_model=list[Menu], status_code=201)
def import_menus(req: MenuImportRequest) -> list[Menu]:
    """批量导入菜品。"""
    return menu_service.import_menus(req)


@app.get("/api/menus", response_model=list[Menu])
def list_menus(
    category: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> list[Menu]:
    """列出菜单，支持按分类与价格区间过滤。"""
    return menu_service.list_menus(category=category, min_price=min_price, max_price=max_price)


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:  # noqa: B008
    """统一兜底错误处理。"""
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})
