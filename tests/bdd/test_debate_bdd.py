"""BDD 验收测试步骤定义：覆盖 US01 / US02 / US03。

使用 pytest-bdd，每个场景真实走 FastAPI TestClient，不 mock 核心逻辑。
step 之间通过 target_fixture 显式传递值。
"""
from __future__ import annotations

from pytest_bdd import given, parsers, scenario, then, when


@scenario("debate.feature", "成功启动辩论")
def test_start_debate():
    pass


@scenario("debate.feature", "非法口味偏好被拒绝")
def test_invalid_taste():
    pass


@scenario("debate.feature", "查询辩论发言并标明身份")
def test_view_rounds():
    pass


@scenario("debate.feature", "查询不存在的会话")
def test_not_found():
    pass


@scenario("debate.feature", "辩论结束生成战报")
def test_report_generated():
    pass


@scenario("debate.feature", "战报字段完整")
def test_report_fields():
    pass


# ---------------------------------------------------------------------------
# Given
# ---------------------------------------------------------------------------
@given(
    parsers.parse('我提供口味偏好"{taste}"和预算"{budget}"以及天气"{weather}"'),
    target_fixture="preferences",
)
def provide_preferences(taste, budget, weather):
    return {"taste": taste, "budget": budget, "weather": weather}


@given("一个已启动的辩论会话", target_fixture="session_id")
def started_session(client):
    resp = client.post(
        "/api/debate/start", json={"taste": "辣", "budget": "中", "weather": "晴"}
    )
    assert resp.status_code == 201
    return resp.json()["session_id"]


@given("我提供不存在的 session_id", target_fixture="session_id")
def nonexistent_session_id():
    return "nonexistent-session"


# ---------------------------------------------------------------------------
# When
# ---------------------------------------------------------------------------
@when("我提交启动请求", target_fixture="start_response")
def submit_start(preferences, client):
    return client.post("/api/debate/start", json=preferences)


@when("我查询该会话的发言", target_fixture="rounds_response")
def query_rounds(session_id, client):
    return client.get(f"/api/debate/{session_id}/rounds")


@when("我查询其状态", target_fixture="status_response")
def query_status(session_id, client):
    return client.get(f"/api/debate/{session_id}/status")


@when("我查询该会话的战报", target_fixture="report_response")
def query_report(session_id, client):
    return client.get(f"/api/debate/{session_id}/report")


# ---------------------------------------------------------------------------
# Then
# ---------------------------------------------------------------------------
@then("系统创建新会话并返回 session_id")
def assert_session_id(start_response):
    assert start_response.status_code == 201
    assert start_response.json()["session_id"]


@then("系统触发两位 Agent 开始辩论")
def assert_debate_started(start_response):
    data = start_response.json()
    assert data["status"] == "SUCCESS"
    assert len(data["rounds"]) == 6  # 2 大厨 × 3 轮


@then("系统返回 422 校验错误")
def assert_422(start_response):
    assert start_response.status_code == 422


@then("不创建任何会话")
def assert_no_session(client):
    sessions = client.get("/api/debate/sessions")
    assert sessions.json() == []


@then("返回按轮次排序的发言列表")
def assert_sorted_rounds(rounds_response):
    rounds = rounds_response.json()["rounds"]
    round_nums = [r["round_number"] for r in rounds]
    assert round_nums == sorted(round_nums)


@then(parsers.parse('每条发言标明"{a}"或"{b}"'))
def assert_identity(rounds_response, a, b):
    names = {r["speaker_name"] for r in rounds_response.json()["rounds"]}
    assert names == {a, b}


@then("两位 Agent 交替发言")
def assert_alternating(rounds_response):
    speakers = [r["speaker_id"] for r in rounds_response.json()["rounds"]]
    assert speakers[0] != speakers[1]
    assert speakers[2] != speakers[3]


@then("返回 404 错误")
def assert_404(status_response):
    assert status_response.status_code == 404


@then("返回包含 final_choice 和 reason 和 score 的战报")
def assert_report_shape(report_response):
    data = report_response.json()
    assert "final_choice" in data
    assert "reason" in data
    assert "score" in data


@then("战报持久化存储")
def assert_report_persisted(report_response):
    assert report_response.status_code == 200


@then("final_choice 非空")
def assert_final_choice_nonempty(report_response):
    assert report_response.json()["final_choice"]


@then("score 为 0 到 10 之间的数值")
def assert_score_range(report_response):
    score = report_response.json()["score"]
    assert isinstance(score, (int, float))
    assert 0.0 <= score <= 10.0


@then("pros_cons 包含双方观点")
def assert_pros_cons(report_response):
    pros_cons = report_response.json()["pros_cons"]
    assert isinstance(pros_cons.get("pros"), list)
    assert isinstance(pros_cons.get("cons"), list)


@then(parsers.parse('winner_agent 为"{a}"或"{b}"'))
def assert_winner(report_response, a, b):
    assert report_response.json()["winner_agent"] in (a, b)
