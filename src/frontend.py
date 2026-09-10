"""Streamlit 前端：输入表单 + 辩论过程聊天式展示（US01 / US02）。"""
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
        data = resp.json()
        st.session_state["session"] = data
    except httpx.HTTPStatusError as exc:
        st.error(f"请求失败（{exc.response.status_code}）：{exc.response.text}")
    except httpx.ConnectError:
        st.error("无法连接后端，请先启动 FastAPI 服务（uvicorn src.main:app）。")

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

    if session.get("recommendation"):
        rec = session["recommendation"]
        st.subheader("🏆 战报")
        st.success(f"**最终推荐：{rec['final_choice']}**（评分 {rec['score']}/10）")
        st.write(rec["reason"])
