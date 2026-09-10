"""单元测试：菜单服务（US05）。"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.db import Base
from src.menu_service import MenuService
from src.models import Menu, MenuImportRequest


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    from src import orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    Base.metadata.drop_all(bind=engine)


def _svc(session_factory) -> MenuService:
    return MenuService(session_factory=session_factory)


def _sample_req() -> MenuImportRequest:
    return MenuImportRequest(
        items=[
            Menu(name="麻辣香锅", price=28.0, category="川菜", tags=["辣", "麻辣"], source="食堂"),
            Menu(name="白切鸡", price=20.0, category="粤菜", tags=["清淡", "粤"], source="食堂"),
            Menu(name="老火靓汤", price=12.0, category="粤菜", tags=["清淡", "汤"], source="食堂"),
        ]
    )


def test_import_menus(session_factory):
    svc = _svc(session_factory)
    menus = svc.import_menus(_sample_req())
    assert len(menus) == 3
    assert all(m.id for m in menus)  # 已分配自增 id
    assert menus[0].name == "麻辣香锅"


def test_list_menus_all(session_factory):
    svc = _svc(session_factory)
    svc.import_menus(_sample_req())
    assert len(svc.list_menus()) == 3


def test_list_menus_filter_category(session_factory):
    svc = _svc(session_factory)
    svc.import_menus(_sample_req())
    cantonese = svc.list_menus(category="粤菜")
    assert len(cantonese) == 2
    assert all(m.category == "粤菜" for m in cantonese)


def test_list_menus_filter_price(session_factory):
    svc = _svc(session_factory)
    svc.import_menus(_sample_req())
    cheap = svc.list_menus(max_price=15.0)
    assert len(cheap) == 1
    assert cheap[0].name == "老火靓汤"


def test_filter_candidates_spicy_budget(session_factory):
    svc = _svc(session_factory)
    svc.import_menus(_sample_req())
    candidates = svc.filter_candidates(taste="辣", budget="中")  # ≤30 元
    names = {c.name for c in candidates}
    assert "麻辣香锅" in names
    assert "白切鸡" not in names  # 清淡菜不应入选辣味候选


def test_filter_candidates_light_budget(session_factory):
    svc = _svc(session_factory)
    svc.import_menus(_sample_req())
    candidates = svc.filter_candidates(taste="清淡", budget="低")  # ≤15 元
    names = {c.name for c in candidates}
    assert "老火靓汤" in names
    assert "白切鸡" not in names  # 20 元超出低预算


def test_get_by_id(session_factory):
    svc = _svc(session_factory)
    menus = svc.import_menus(_sample_req())
    m = svc.get_by_id(menus[0].id)
    assert m is not None
    assert m.name == "麻辣香锅"
