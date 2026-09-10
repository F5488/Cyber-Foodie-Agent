"""数据库层：SQLAlchemy 2.x 引擎、会话工厂与 Base。

开发环境使用 SQLite（文件 `cyber_foodie.db`），连接串通过环境变量
`DATABASE_URL` 配置，生产可切换为 PostgreSQL。
"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

# 默认使用 SQLite 文件数据库（已加入 .gitignore）
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cyber_foodie.db")

# 连接参数：SQLite 需关闭同线程检查；内存库使用 StaticPool 保证连接复用
_is_memory_sqlite = DATABASE_URL in ("sqlite://", "sqlite:///:memory:")
if _is_memory_sqlite:
    _connect_args = {"check_same_thread": False}
    _engine_kwargs = {"poolclass": StaticPool}
elif DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    _engine_kwargs = {}
else:
    _connect_args = {}
    _engine_kwargs = {}

engine = create_engine(
    DATABASE_URL,
    connect_args=_connect_args,
    future=True,
    **_engine_kwargs,
)

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
