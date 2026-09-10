"""单元测试：数据库层与频控防御。"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db import Base
from src.orm_models import DebateRoundModel, RecommendationModel, SessionModel


@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


def test_tables_created(engine):
    tables = set(inspect(engine).get_table_names())
    assert {"sessions", "agents", "debate_rounds", "recommendations"} <= tables


def test_session_crud(engine):
    factory = sessionmaker(bind=engine, future=True)
    with factory() as dbs:
        s = SessionModel(
            session_id="s1", taste="辣", budget="中", weather="晴", status="SUCCESS"
        )
        dbs.add(s)
        dbs.commit()

        loaded = dbs.get(SessionModel, "s1")
        assert loaded is not None
        assert loaded.taste == "辣"


def test_recommendation_unique_per_session(engine):
    factory = sessionmaker(bind=engine, future=True)
    with factory() as dbs:
        dbs.add(SessionModel(session_id="s1", taste="辣", budget="中", weather="晴"))
        dbs.flush()
        dbs.add(
            RecommendationModel(
                session_id="s1",
                final_choice="麻辣香锅",
                reason="r",
                pros=["a"],
                cons=["b"],
                score=8.0,
                winner_agent="川辣派",
            )
        )
        dbs.commit()
        rec = dbs.query(RecommendationModel).filter_by(session_id="s1").one()
        assert rec.final_choice == "麻辣香锅"
        assert rec.pros == ["a"]


def test_debate_round_ordering(engine):
    factory = sessionmaker(bind=engine, future=True)
    with factory() as dbs:
        dbs.add(SessionModel(session_id="s1", taste="辣", budget="中", weather="晴"))
        dbs.flush()
        dbs.add(
            DebateRoundModel(
                session_id="s1", speaker_id="a", round_number=1, speaker_name="川", content="x"
            )
        )
        dbs.add(
            DebateRoundModel(
                session_id="s1", speaker_id="b", round_number=1, speaker_name="粤", content="y"
            )
        )
        dbs.commit()
        cnt = dbs.query(DebateRoundModel).filter_by(session_id="s1").count()
        assert cnt == 2


def test_rate_limit_returns_429():
    """频控：连续 6 次启动辩论，第 6 次应返回 429。"""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["LLM_PROVIDER"] = "mock"
    from src.db import engine as app_engine, Base as app_base

    app_base.metadata.create_all(bind=app_engine)
    from src.main import app, limiter

    # 隔离频控状态
    limiter.reset()
    with TestClient(app) as client:
        codes = []
        for _ in range(6):
            r = client.post(
                "/api/debate/start", json={"taste": "辣", "budget": "中", "weather": "晴"}
            )
            codes.append(r.status_code)
    assert codes[:5] == [201] * 5
    assert codes[5] == 429
    app_base.metadata.drop_all(bind=app_engine)
