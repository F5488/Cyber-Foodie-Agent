"""pytest 全局夹具：为集成/BDD 测试提供隔离的内存数据库与 TestClient。"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# 必须在导入 src.db / src.main 之前设置，确保使用内存 SQLite
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "mock"

from src.db import Base, engine  # noqa: E402


@pytest.fixture()
def db_engine():
    """每个测试一个干净的内存数据库。"""
    from src import orm_models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_engine):
    """基于内存数据库的 TestClient，真实走 API 全链路。"""
    from src.main import app

    with TestClient(app) as c:
        yield c
