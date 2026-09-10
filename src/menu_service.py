"""菜单服务（US05）：批量导入、列表查询与候选筛选。"""
from __future__ import annotations

from typing import Optional

from . import db
from .models import Menu, MenuImportRequest
from .orm_models import MenuModel


class MenuService:
    """菜单数据管理。"""

    def __init__(self, session_factory=None) -> None:
        self._session_factory = session_factory or db.SessionLocal

    @staticmethod
    def _to_pydantic(m: MenuModel) -> Menu:
        return Menu(
            id=m.id,
            name=m.name,
            price=m.price,
            category=m.category,
            tags=m.tags or [],
            availability=bool(m.availability),
            source=m.source,
        )

    def import_menus(self, req: MenuImportRequest) -> list[Menu]:
        """批量导入菜品，返回导入后的列表（含自增 id）。"""
        with self._session_factory() as dbs:
            rows = []
            for item in req.items:
                row = MenuModel(
                    name=item.name,
                    price=item.price,
                    category=item.category,
                    tags=item.tags,
                    availability=1 if item.availability else 0,
                    source=item.source,
                )
                dbs.add(row)
                rows.append(row)
            dbs.commit()
            for row in rows:
                dbs.refresh(row)
            return [self._to_pydantic(r) for r in rows]

    def list_menus(
        self,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
    ) -> list[Menu]:
        """列出菜单，支持按分类与价格区间过滤。"""
        with self._session_factory() as dbs:
            q = dbs.query(MenuModel).filter(MenuModel.availability == 1)
            if category:
                q = q.filter(MenuModel.category == category)
            if min_price is not None:
                q = q.filter(MenuModel.price >= min_price)
            if max_price is not None:
                q = q.filter(MenuModel.price <= max_price)
            return [self._to_pydantic(m) for m in q.order_by(MenuModel.id).all()]

    def get_by_id(self, menu_id: int) -> Optional[Menu]:
        with self._session_factory() as dbs:
            row = dbs.get(MenuModel, menu_id)
            return self._to_pydantic(row) if row else None

    def filter_candidates(
        self,
        taste: str,
        budget: str,
    ) -> list[Menu]:
        """按预算与口味标签筛选候选菜品（US05）。

        预算映射：低 ≤15 元，中 ≤30 元，高 不限。
        口味标签映射：辣 → ["辣","麻辣","川"], 清淡 → ["清淡","粤","养生","蒸","汤"]。
        """
        budget_cap = {"低": 15.0, "中": 30.0, "高": float("inf")}[budget]

        with self._session_factory() as dbs:
            q = dbs.query(MenuModel).filter(MenuModel.availability == 1)
            if budget_cap != float("inf"):
                q = q.filter(MenuModel.price <= budget_cap)
            rows = q.order_by(MenuModel.id).all()

        menus = [self._to_pydantic(r) for r in rows]
        return self.filter_candidates_by_rules(menus, taste, budget)

    @staticmethod
    def filter_candidates_by_rules(menus: list[Menu], taste: str, budget: str) -> list[Menu]:
        """纯规则筛选：给定菜单列表，按预算上限与口味标签过滤。"""
        budget_cap = {"低": 15.0, "中": 30.0, "高": float("inf")}[budget]
        taste_keywords = {
            "辣": ["辣", "麻辣", "川", "香辣", "干锅"],
            "清淡": ["清淡", "粤", "养生", "蒸", "汤", "白切", "炖"],
        }.get(taste, [])

        result = [m for m in menus if m.availability and m.price <= budget_cap]
        if taste_keywords:
            result = [
                m for m in result if any(kw in "".join(m.tags) for kw in taste_keywords)
            ]
        return result
