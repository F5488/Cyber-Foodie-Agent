"""Streamlit 前端：输入表单 + 辩论过程聊天式展示 + 战报卡片 + 历史会话（US01/02/03）。"""
from __future__ import annotations

import httpx
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Cyber Foodie Agent", page_icon="🍜", layout="wide")

st.title("🍜 Cyber Foodie Agent")
st.caption("两位 AI 大厨为你「吵」出一顿好吃的")

TASTE_OPTIONS = ["辣", "清淡"]
BUDGET_OPTIONS = ["低", "中", "高"]
WEATHER_OPTIONS = ["晴", "雨", "雪"]


def _api_get(path: str):
    try:
        return httpx.get(f"{API_BASE}{path}", timeout=15.0)
    except httpx.ConnectError:
        return None


# ---------------------------------------------------------------------------
# 侧边栏：历史会话
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📚 历史会话")
    try:
        resp = httpx.get(f"{API_BASE}/api/debate/sessions", timeout=15.0)
        resp.raise_for_status()
        sessions = resp.json()
    except Exception:  # noqa: BLE001
        sessions = []

    if sessions:
        for s in sessions:
            label = f"{s['created_at'][:16]} · {s['taste']}/{s['budget']}/{s['weather']}"
            if st.button(label, key=s["session_id"], use_container_width=True):
                st.session_state["session"] = s
    else:
        st.caption("暂无历史会话")

# ---------------------------------------------------------------------------
# 主区域：输入表单
# ---------------------------------------------------------------------------
with st.form("debate_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        taste = st.selectbox("口味偏好", TASTE_OPTIONS)
    with col2:
        budget = st.selectbox("预算等级", BUDGET_OPTIONS)
    with col3:
        weather = st.selectbox("当前天气", WEATHER_OPTIONS)
    submitted = st.form_submit_button("🚀 开始辩论", use_container_width=True)

if submitted:
    payload = {"taste": taste, "budget": budget, "weather": weather}
    try:
        resp = httpx.post(f"{API_BASE}/api/debate/start", json=payload, timeout=60.0)
        resp.raise_for_status()
        st.session_state["session"] = resp.json()
    except httpx.HTTPStatusError as exc:
        st.error(f"请求失败（{exc.response.status_code}）：{exc.response.text}")
    except httpx.ConnectError:
        st.error("无法连接后端，请先启动 FastAPI 服务（uvicorn src.main:app）。")

# ---------------------------------------------------------------------------
# 会话展示
# ---------------------------------------------------------------------------
session = st.session_state.get("session")
if session:
    st.subheader(f"会话 `{session['session_id']}` · 状态 {session['status']}")

    agents = session.get("agents", [])
    for round_item in session.get("rounds", []):
        avatar = next(
            (
                a.get("avatar", "👨‍🍳")
                for a in agents
                if a.get("agent_id") == round_item["speaker_id"]
            ),
            "👨‍🍳",
        )
        with st.chat_message(round_item["speaker_name"], avatar=avatar):
            st.write(f"**第 {round_item['round_number']} 轮** — {round_item['speaker_name']}")
            st.write(round_item["content"])

    # 战报卡片
    recommendation = session.get("recommendation")
    if recommendation:
        st.markdown("---")
        st.subheader("🏆 战报")
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"### 🍽️ 最终推荐：{recommendation['final_choice']}")
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
