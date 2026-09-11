"""并发写入回归测试：验证 SQLite WAL + 种子竞态修复。

对应线上问题：并发启动辩论时报 `database is locked` /
`UNIQUE constraint failed: agents.name`。
"""
from __future__ import annotations

import concurrent.futures as cf

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.db import Base
from src.debate import DebateService
from src.models import BudgetLevel, DebateStartRequest, TastePreference, WeatherCondition


@pytest.fixture()
def file_engine(tmp_path):
    """使用临时文件库（非内存），以便真实复现并发写锁场景。"""
    db_file = tmp_path / "concurrent.db"
    eng = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
        future=True,
    )
    from src import orm_models  # noqa: F401

    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


def test_wal_mode_enabled(file_engine):
    """文件库应启用 WAL 模式。"""
    with file_engine.connect() as c:
        assert c.execute(text("PRAGMA journal_mode")).scalar().lower() == "wal"


def test_concurrent_debates_no_lock(file_engine):
    """并发启动 8 次辩论不应报错（锁冲突 / 种子竞态）。"""
    factory = sessionmaker(bind=file_engine, autoflush=False, autocommit=False, future=True)

    def run_one(_):
        svc = DebateService(session_factory=factory, rounds=1)
        req = DebateStartRequest(
            taste=TastePreference.SPICY,
            budget=BudgetLevel.MEDIUM,
            weather=WeatherCondition.SUNNY,
        )
        return svc.start_debate(req).session_id

    errors = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(run_one, i) for i in range(8)]
        for f in cf.as_completed(futures):
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")

    assert not errors, f"并发辩论出现错误: {errors}"


def test_seed_agents_idempotent_under_concurrency(file_engine):
    """并发 _seed_agents 不应因 name 唯一约束报错。"""
    factory = sessionmaker(bind=file_engine, autoflush=False, autocommit=False, future=True)

    def seed(_):
        with factory() as dbs:
            DebateService(session_factory=factory)._seed_agents(dbs)
            dbs.commit()

    errors = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(seed, i) for i in range(6)]
        for f in cf.as_completed(futures):
            try:
                f.result()
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{type(exc).__name__}: {exc}")

    assert not errors, f"并发 seed 出现错误: {errors}"
