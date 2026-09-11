"""数据库层：SQLAlchemy 2.x 引擎、会话工厂与 Base。

开发环境使用 SQLite（文件 `cyber_foodie.db`），连接串通过环境变量
`DATABASE_URL` 配置，生产可切换为 PostgreSQL。

SQLite 并发写入优化（列见下）：
- WAL 模式：读不阻塞写，避免并发辩论时 `database is locked`
- busy_timeout：写冲突时等待 5 秒而非立即报错
- NullPool：每个请求用完即关连接，不长期持有写锁
"""
from __future__ import annotations

import os
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

# 默认使用 SQLite 文件数据库（已加入 .gitignore）
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cyber_foodie.db")

_is_memory_sqlite = DATABASE_URL in ("sqlite://", "sqlite:///:memory:")

if _is_memory_sqlite:
    # 内存库：StaticPool 保证所有连接复用同一内存实例（测试隔离必需）
    _connect_args = {"check_same_thread": False}
    _engine_kwargs = {"poolclass": StaticPool}
elif DATABASE_URL.startswith("sqlite"):
    # 文件库：NullPool 避免连接被长期持有导致写锁竞争
    _connect_args = {"check_same_thread": False}
    _engine_kwargs = {"poolclass": NullPool}
else:
    # PostgreSQL 等：使用默认连接池
    _connect_args = {}
    _engine_kwargs = {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    future=True,
    **_engine_kwargs,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """为每个新 SQLite 连接设置 PRAGMA（WAL + busy_timeout）。

    非 SQLite 连接（如 PostgreSQL）直接跳过，避免 PRAGMA 语法报错。
    """
    if not isinstance(dbapi_connection, sqlite3.Connection):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")  # 读写并发
        cursor.execute("PRAGMA busy_timeout=5000")  # 写冲突等待 5s
        cursor.execute("PRAGMA synchronous=NORMAL")  # WAL 下的推荐安全级别
    finally:
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """所有 ORM 模型的声明式基类。"""


def init_db() -> None:
    """按 ER 图建表（Sprint 2 使用 create_all，暂不引入 Alembic）。"""
    # 导入 ORM 模型以确保注册到 Base.metadata
    from . import orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI 依赖：提供请求级数据库会话。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
