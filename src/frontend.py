"""Streamlit 前端：辩论 + Agent 管理 + 菜单管理 + 历史会话。

覆盖 US01/US02/US03/US04/US05。
"""
from __future__ import annotations

import json

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Cyber Foodie Agent", page_icon="🍜", layout="wide")

TASTE_OPTIONS = ["辣", "清淡"]
BUDGET_OPTIONS = ["低", "中", "高"]
WEATHER_OPTIONS = ["晴", "雨", "雪"]


def _get(path: str):
    try:
        return httpx.get(f"{API_BASE}{path}", timeout=15.0)
    except httpx.ConnectError:
        return None


def _post(path: str, json_body: dict | None = None, timeout: float = 60.0):
    try:
        return httpx.post(f"{API_BASE}{path}", json=json_body, timeout=timeout)
    except httpx.ConnectError:
        return None


def _put(path: str, json_body: dict):
    try:
        return httpx.put(f"{API_BASE}{path}", json=json_body, timeout=15.0)
    except httpx.ConnectError:
        return None


def _delete(path: str):
    try:
        return httpx.delete(f"{API_BASE}{path}", timeout=15.0)
    except httpx.ConnectError:
        return None


def _load_agents() -> list[dict]:
    resp = _get("/api/agents")
    if resp and resp.status_code == 200:
        return resp.json()
    return []


# ---------------------------------------------------------------------------
# 页面：辩论
# ---------------------------------------------------------------------------
def render_debate_page() -> None:
    st.title("🍜 Cyber Foodie Agent")
    st.caption("两位 AI 大厨为你「吵」出一顿好吃的")

    agents = _load_agents()
    agent_options = {f"{a['avatar']} {a['name']}": a["agent_id"] for a in agents}

    with st.form("debate_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            taste = st.selectbox("口味偏好", TASTE_OPTIONS)
        with col2:
            budget = st.selectbox("预算等级", BUDGET_OPTIONS)
        with col3:
            weather = st.selectbox("当前天气", WEATHER_OPTIONS)

        # Agent 选择下拉框（US04）
        col_a, col_b = st.columns(2)
        default_a = next((k for k in agent_options if "川辣派" in k), None)
        default_b = next((k for k in agent_options if "粤式养生派" in k), None)
        agent_keys = list(agent_options.keys())
        with col_a:
            agent_a_label = st.selectbox(
                "大厨 A", agent_keys, index=agent_keys.index(default_a) if default_a else 0
            )
        with col_b:
            agent_b_label = st.selectbox(
                "大厨 B", agent_keys, index=agent_keys.index(default_b) if default_b else 0
            )

        submitted = st.form_submit_button("🚀 开始辩论", use_container_width=True)

    if submitted:
        payload = {
            "taste": taste,
            "budget": budget,
            "weather": weather,
            "agent_a_id": agent_options[agent_a_label],
            "agent_b_id": agent_options[agent_b_label],
        }
        resp = _post("/api/debate/start", payload)
        if resp is None:
            st.error("无法连接后端，请先启动 FastAPI 服务（uvicorn src.main:app）。")
        elif resp.status_code >= 400:
            st.error(f"请求失败（{resp.status_code}）：{resp.text}")
        else:
            st.session_state["session"] = resp.json()

    session = st.session_state.get("session")
    if session:
        st.subheader(f"会话 `{session['session_id']}` · 状态 {session['status']}")

        agents_list = session.get("agents", [])
        for round_item in session.get("rounds", []):
            avatar = next(
                (
                    a.get("avatar", "👨‍🍳")
                    for a in agents_list
                    if a.get("agent_id") == round_item["speaker_id"]
                ),
                "👨‍🍳",
            )
            with st.chat_message(round_item["speaker_name"], avatar=avatar):
                st.write(f"**第 {round_item['round_number']} 轮** — {round_item['speaker_name']}")
                st.write(round_item["content"])

        recommendation = session.get("recommendation")
        if recommendation:
            st.markdown("---")
            st.subheader("🏆 战报")
            with st.container(border=True):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"### 🍽️ 最终推荐：{recommendation['final_choice']}")
                    if recommendation.get("price"):
                        st.caption(f"💰 {recommendation['price']} 元 · 来源：菜单")
                    st.write(recommendation["reason"])
                with col_b:
                    st.metric("综合评分", f"{recommendation['score']}/10")
                    st.markdown(f"**获胜方**：{recommendation.get('winner_agent', '—')}")

                pros_cons = recommendation.get("pros_cons", {})
                pc1, pc2 = st.columns(2)
                with pc1:
                    st.markdown("**✅ 支持观点**")
                    for p in pros_cons.get("pros", []):
                        st.markdown(f"- {p}")
                with pc2:
                    st.markdown("**⚠️ 反对观点**")
                    for c in pros_cons.get("cons", []):
                        st.markdown(f"- {c}")


# ---------------------------------------------------------------------------
# 页面：Agent 管理
# ---------------------------------------------------------------------------
def render_agent_page() -> None:
    st.title("🧑‍🍳 Agent 管理")

    agents = _load_agents()
    st.subheader("已有 Agent")
    for a in agents:
        badge = "🔒 预设" if a.get("is_preset") else "✏️ 自定义"
        with st.expander(f"{a['avatar']} {a['name']}  [{badge}]"):
            st.write(f"**描述**：{a.get('description', '—')}")
            st.text_area(
                "系统提示词",
                a["system_prompt"],
                height=120,
                key=f"sp_{a['agent_id']}",
                disabled=True,
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📋 克隆", key=f"clone_{a['agent_id']}"):
                    resp = _post(f"/api/agents/{a['agent_id']}/clone", timeout=15.0)
                    if resp and resp.status_code == 201:
                        st.success(f"已克隆为「{resp.json()['name']}」")
                        st.rerun()
            with col2:
                if not a.get("is_preset"):
                    if st.button("🗑️ 删除", key=f"del_{a['agent_id']}"):
                        resp = _delete(f"/api/agents/{a['agent_id']}")
                        if resp and resp.status_code == 204:
                            st.success("已删除")
                            st.rerun()
                        elif resp:
                            st.error(resp.text)

    st.markdown("---")
    st.subheader("新建 Agent")
    with st.form("new_agent"):
        name = st.text_input("名称（≤50 字符）")
        description = st.text_input("描述（可选）")
        avatar = st.text_input("头像 emoji", value="👨‍🍳")
        system_prompt = st.text_area("系统提示词（≤2000 字符）", height=150)
        submitted = st.form_submit_button("创建", use_container_width=True)
    if submitted:
        if not name or not system_prompt:
            st.error("名称和系统提示词必填")
        else:
            resp = _post(
                "/api/agents",
                {
                    "name": name,
                    "system_prompt": system_prompt,
                    "avatar": avatar,
                    "description": description,
                },
                timeout=15.0,
            )
            if resp and resp.status_code == 201:
                st.success(f"已创建「{resp.json()['name']}」")
                st.rerun()
            elif resp:
                st.error(resp.text)


# ---------------------------------------------------------------------------
# 页面：菜单管理
# ---------------------------------------------------------------------------
def render_menu_page() -> None:
    st.title("🍽️ 菜单管理")

    # 导入
    st.subheader("导入菜单")
    with st.form("import_menu"):
        uploaded = st.file_uploader("上传 JSON 菜单文件", type=["json"])
        submitted = st.form_submit_button("导入", use_container_width=True)
    if submitted and uploaded is not None:
        try:
            data = json.load(uploaded)
            resp = _post("/api/menus/import", data, timeout=30.0)
            if resp and resp.status_code == 201:
                st.success(f"成功导入 {len(resp.json())} 道菜")
                st.rerun()
            elif resp:
                st.error(resp.text)
        except json.JSONDecodeError:
            st.error("JSON 格式错误")
    elif submitted:
        st.warning("请先上传 JSON 文件（可参考 eval/sample_menu.json）")

    # 列表
    st.subheader("菜单列表")
    col1, col2, col3 = st.columns(3)
    with col1:
        category = st.text_input("按分类过滤（留空=全部）")
    with col2:
        max_price = st.number_input(
            "最高价格（0=不限）", min_value=0.0, value=0.0, step=1.0
        )

    params = {}
    if category:
        params["category"] = category
    if max_price > 0:
        params["max_price"] = max_price

    resp = _get("/api/menus")
    if resp and resp.status_code == 200:
        menus = resp.json()
        # 客户端二次过滤（简单处理，也可用后端参数）
        if params:
            resp2 = httpx.get(f"{API_BASE}/api/menus", params=params, timeout=15.0)
            if resp2.status_code == 200:
                menus = resp2.json()

        if menus:
            st.dataframe(
                [
                    {
                        "ID": m["id"],
                        "名称": m["name"],
                        "价格": m["price"],
                        "分类": m["category"],
                        "标签": "/".join(m.get("tags", [])),
                        "来源": m.get("source", "食堂"),
                    }
                    for m in menus
                ],
                use_container_width=True,
            )
        else:
            st.info("暂无菜单数据，请先导入")
    else:
        st.info("无法连接后端或暂无菜单")


# ---------------------------------------------------------------------------
# 侧边栏导航 + 历史会话
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🍜 Cyber Foodie")
    page = st.radio("导航", ["💬 辩论", "🧑‍🍳 Agent 管理", "🍽️ 菜单管理"])

    st.divider()
    st.header("📚 历史会话")
    resp = _get("/api/debate/sessions")
    sessions = resp.json() if resp and resp.status_code == 200 else []
    if sessions:
        for s in sessions[:10]:
            label = f"{s['created_at'][:16]} · {s['taste']}/{s['budget']}/{s['weather']}"
            if st.button(label, key=s["session_id"], use_container_width=True):
                st.session_state["session"] = s
    else:
        st.caption("暂无历史会话")

# ---------------------------------------------------------------------------
# 主区域渲染
# ---------------------------------------------------------------------------
if page == "💬 辩论":
    render_debate_page()
elif page == "🧑‍🍳 Agent 管理":
    render_agent_page()
else:
    render_menu_page()
