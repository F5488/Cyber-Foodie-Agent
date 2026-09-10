"""BDD 步骤定义：US04 自定义 Agent 与 US05 菜单推荐。

每个场景真实走 FastAPI TestClient，不 mock 核心逻辑。
"""
from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when


@scenario("us04_custom_agent.feature", "创建自定义 Agent")
def test_create_agent():
    pass


@scenario("us04_custom_agent.feature", "使用自定义 Agent 辩论")
def test_use_custom_agent():
    pass


@scenario("us04_custom_agent.feature", "预设 Agent 不可删除")
def test_preset_protected():
    pass


@scenario("us05_menu_recommend.feature", "导入菜单数据")
def test_import_menu():
    pass


@scenario("us05_menu_recommend.feature", "推荐来自菜单")
def test_recommend_from_menu():
    pass


@scenario("us05_menu_recommend.feature", "筛选候选菜品")
def test_filter_candidates():
    pass


# ---------------------------------------------------------------------------
# US04 Given
# ---------------------------------------------------------------------------
@given("我提供一个自定义 Agent 的名称和系统提示词", target_fixture="agent_payload")
def agent_payload():
    return {"name": "日式轻食", "system_prompt": "你是日式料理大厨", "avatar": "🍣"}


@given("存在一个自定义 Agent", target_fixture="custom_agent_id")
def create_custom_agent(client):
    resp = client.post(
        "/api/agents", json={"name": "日式轻食", "system_prompt": "你是日式料理大厨"}
    )
    assert resp.status_code == 201
    return resp.json()["agent_id"]


@given(parsers.parse('预设 Agent"{name}"存在'))
def preset_exists(name):
    pass


# ---------------------------------------------------------------------------
# US04 When
# ---------------------------------------------------------------------------
@when("我调用创建 Agent 接口", target_fixture="create_response")
def create_agent_call(agent_payload, client):
    return client.post("/api/agents", json=agent_payload)


@when("我启动辩论并指定该 Agent 作为大厨 A", target_fixture="debate_response")
def start_debate_with_custom(custom_agent_id, client):
    return client.post(
        "/api/debate/start",
        json={
            "taste": "辣",
            "budget": "中",
            "weather": "晴",
            "agent_a_id": custom_agent_id,
            "agent_b_id": "agent-cantonese",
        },
    )


@when("我尝试删除该预设 Agent", target_fixture="delete_response")
def delete_preset(client):
    return client.delete("/api/agents/agent-spicy")


# ---------------------------------------------------------------------------
# US04 Then
# ---------------------------------------------------------------------------
@then("系统创建 Agent 并返回 agent_id")
def assert_agent_id(create_response):
    assert create_response.status_code == 201
    assert create_response.json()["agent_id"]


@then("该 Agent 出现在 Agent 列表中")
def assert_agent_listed(create_response, client):
    agents = client.get("/api/agents").json()
    names = {a["name"] for a in agents}
    assert create_response.json()["name"] in names


@then("辩论由该 Agent 参与")
def assert_custom_agent_used(debate_response):
    assert debate_response.status_code == 201


@then("发言中包含该 Agent 的名称")
def assert_speaker_name(debate_response):
    speakers = {r["speaker_name"] for r in debate_response.json()["rounds"]}
    assert "日式轻食" in speakers


@then("系统返回 403 错误")
def assert_403(delete_response):
    assert delete_response.status_code == 403


# ---------------------------------------------------------------------------
# US05 Given
# ---------------------------------------------------------------------------
@given("我提供一份 JSON 菜单数据", target_fixture="menu_payload")
def menu_payload():
    return {
        "items": [
            {"name": "麻辣香锅", "price": 28.0, "category": "川菜", "tags": ["辣"], "source": "食堂"},
            {"name": "白切鸡", "price": 20.0, "category": "粤菜", "tags": ["清淡"], "source": "食堂"},
        ]
    }


@given("菜单列表存在且用户预算为\"中\"", target_fixture="imported_menus")
def import_for_budget(client):
    resp = client.post(
        "/api/menus/import",
        json={
            "items": [
                {"name": "麻辣香锅", "price": 28.0, "category": "川菜", "tags": ["辣"], "source": "食堂"},
                {"name": "白切鸡", "price": 20.0, "category": "粤菜", "tags": ["清淡"], "source": "食堂"},
            ]
        },
    )
    assert resp.status_code == 201
    return resp.json()


@given("菜单列表存在且用户口味为\"辣\"", target_fixture="spicy_menus")
def import_for_taste(client):
    resp = client.post(
        "/api/menus/import",
        json={
            "items": [
                {"name": "麻辣香锅", "price": 28.0, "category": "川菜", "tags": ["辣"], "source": "食堂"},
                {"name": "白切鸡", "price": 20.0, "category": "粤菜", "tags": ["清淡"], "source": "食堂"},
            ]
        },
    )
    assert resp.status_code == 201
    return resp.json()


# ---------------------------------------------------------------------------
# US05 When
# ---------------------------------------------------------------------------
@when("我调用菜单导入接口", target_fixture="import_response")
def import_menu_call(menu_payload, client):
    return client.post("/api/menus/import", json=menu_payload)


@when("辩论结束生成推荐", target_fixture="report")
def debate_then_report(imported_menus, client):
    resp = client.post("/api/debate/start", json={"taste": "辣", "budget": "中", "weather": "晴"})
    assert resp.status_code == 201
    return resp.json()["recommendation"]


@when("系统筛选候选菜品", target_fixture="candidates")
def filter_candidates(spicy_menus):
    # 直接复用 MenuService 纯规则筛选验证
    from src.menu_service import MenuService
    from src.models import Menu

    menus = [
        Menu(
            id=m["id"],
            name=m["name"],
            price=m["price"],
            category=m["category"],
            tags=m["tags"],
            source=m["source"],
        )
        for m in spicy_menus
    ]
    return MenuService.filter_candidates_by_rules(menus, "辣", "中")


# ---------------------------------------------------------------------------
# US05 Then
# ---------------------------------------------------------------------------
@then("系统存储菜品并可查询")
def assert_menus_queried(import_response, client):
    assert import_response.status_code == 201
    menus = client.get("/api/menus").json()
    assert len(menus) >= 2


@then("final_choice 来自菜单列表")
def assert_final_choice_in_menu(report, client):
    menus = client.get("/api/menus").json()
    names = {m["name"] for m in menus}
    fc = report["final_choice"]
    assert fc in names or any(fc in n or n in fc for n in names)


@then("候选菜品包含辣味标签")
def assert_spicy_tags(candidates):
    assert candidates
    assert all(any("辣" in t for t in c.tags) for c in candidates)
