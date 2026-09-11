"""Streamlit 前端：辩论 + Agent 管理 + 菜单管理 + 历史会话。

覆盖 US01/US02/US03/US04/US05。
"""
from __future__ import annotations

import json
import os

import httpx
import streamlit as st

# 兼容两种启动方式：`streamlit run src/frontend.py`（脚本目录在 sys.path）
# 与 `python -m streamlit run src/frontend.py`（项目根在 sys.path）
try:
    from src.agent_templates import AGENT_TEMPLATES
except ModuleNotFoundError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.agent_templates import AGENT_TEMPLATES

# 后端地址：默认用 127.0.0.1（避免 localhost 被系统代理拦截），Docker 内通过环境变量指向 backend 服务
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="Cyber Foodie Agent", page_icon="🍜", layout="wide")

TASTE_OPTIONS = ["辣", "清淡"]
BUDGET_OPTIONS = ["低", "中", "高"]
WEATHER_OPTIONS = ["晴", "雨", "雪"]


def _get(path: str, params: dict | None = None):
    try:
        return httpx.get(f"{API_BASE}{path}", params=params, timeout=15.0)
    except httpx.HTTPError:
        return None


def _post(path: str, json_body: dict | None = None, timeout: float = 60.0):
    try:
        return httpx.post(f"{API_BASE}{path}", json=json_body, timeout=timeout)
    except httpx.HTTPError:
        return None


def _put(path: str, json_body: dict):
    try:
        return httpx.put(f"{API_BASE}{path}", json=json_body, timeout=15.0)
    except httpx.HTTPError:
        return None


def _delete(path: str):
    try:
        return httpx.delete(f"{API_BASE}{path}", timeout=15.0)
    except httpx.HTTPError:
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
        # 顶部：本次辩论的输入摘要
        st.markdown(
            f"🍽️ **口味**：{session.get('taste', '—')}　"
            f"💰 **预算**：{session.get('budget', '—')}　"
            f"☁️ **天气**：{session.get('weather', '—')}"
        )
        st.caption(f"会话 `{session['session_id']}` · 状态 {session['status']}")

        # 聊天式发言记录（st.chat_message 按说话人区分头像）
        agents_list = session.get("agents", [])
        agent_by_id = {a.get("agent_id"): a for a in agents_list}
        for round_item in session.get("rounds", []):
            agent = agent_by_id.get(round_item["speaker_id"], {})
            avatar = agent.get("avatar", "👨‍🍳")
            with st.chat_message(name=round_item["speaker_name"], avatar=avatar):
                st.caption(f"第 {round_item['round_number']} 轮")
                st.write(round_item["content"])

        # 底部：战报卡片（默认折叠）
        recommendation = session.get("recommendation")
        if recommendation:
            rc = recommendation
            with st.expander(
                f"🏆 战报：{rc['final_choice']}　（评分 {rc['score']}/10）", expanded=False
            ):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"### 🍽️ 最终推荐：{rc['final_choice']}")
                    if rc.get("price"):
                        st.caption(f"💰 {rc['price']} 元 · 来源：菜单")
                    st.write(rc["reason"])
                with col_b:
                    st.metric("综合评分", f"{rc['score']}/10")
                    st.markdown(f"**获胜方**：{rc.get('winner_agent', '—')}")

                pros_cons = rc.get("pros_cons", {})
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
def _open_editor(name: str, avatar: str, description: str, system_prompt: str) -> None:
    """打开编辑表单（预填模板/预设内容），并记住当前编辑状态。"""
    st.session_state["editing_agent"] = {
        "name": name,
        "avatar": avatar,
        "description": description,
        "system_prompt": system_prompt,
    }


def _render_editor() -> bool:
    """渲染编辑表单（system_prompt 已预填）。返回是否成功创建。"""
    editing = st.session_state.get("editing_agent")
    if not editing:
        return False

    st.success(f"已载入模板「{editing['name']}」，可修改后保存。")
    with st.form("edit_agent"):
        name = st.text_input("名称（≤50 字符）", value=editing["name"])
        description = st.text_input("描述（可选）", value=editing.get("description", ""))
        avatar = st.text_input("头像 emoji", value=editing.get("avatar", "👨‍🍳"))
        system_prompt = st.text_area(
            "系统提示词（≤2000 字符）", value=editing["system_prompt"], height=180
        )
        c1, c2 = st.columns(2)
        with c1:
            submitted = st.form_submit_button("✅ 保存创建", use_container_width=True)
        with c2:
            cancelled = st.form_submit_button("取消", use_container_width=True)

    if cancelled:
        st.session_state.pop("editing_agent", None)
        st.rerun()

    if submitted:
        if not name or not system_prompt:
            st.error("名称和系统提示词必填")
            return False
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
        if resp is not None and resp.status_code == 201:
            st.session_state.pop("editing_agent", None)
            st.success(f"已创建「{resp.json()['name']}」")
            st.rerun()
        elif resp is not None:
            st.error(f"创建失败（{resp.status_code}）：{resp.text}")
        else:
            st.error("连接后端失败：请确认 uvicorn 已启动")
    return False


def render_agent_page() -> None:
    st.title("🧑‍🍳 Agent 管理")

    # ---------------------------------------------------------------
    # 已有 Agent 列表
    # ---------------------------------------------------------------
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
            cols = st.columns(3)
            with cols[0]:
                # P1：以此为基础创建（预填 system_prompt，可改名字）
                if st.button("✨ 以此为基础创建", key=f"base_{a['agent_id']}"):
                    _open_editor(
                        name=f"{a['name']}（我的版本）",
                        avatar=a.get("avatar", "👨‍🍳"),
                        description=a.get("description", ""),
                        system_prompt=a["system_prompt"],
                    )
                    st.rerun()
            with cols[1]:
                if st.button("📋 克隆", key=f"clone_{a['agent_id']}"):
                    resp = _post(f"/api/agents/{a['agent_id']}/clone", timeout=15.0)
                    if resp is not None and resp.status_code == 201:
                        st.success(f"已克隆为「{resp.json()['name']}」")
                        st.rerun()
            with cols[2]:
                if not a.get("is_preset"):
                    if st.button("🗑️ 删除", key=f"del_{a['agent_id']}"):
                        resp = _delete(f"/api/agents/{a['agent_id']}")
                        if resp is not None and resp.status_code == 204:
                            st.success("已删除")
                            st.rerun()
                        elif resp is not None:
                            st.error(resp.text)

    # ---------------------------------------------------------------
    # 编辑区（点模板或被点「以此为基础创建」后显示）
    # ---------------------------------------------------------------
    st.markdown("---")
    if st.session_state.get("editing_agent"):
        st.subheader("✏️ 编辑 Agent")
        _render_editor()
        return

    # ---------------------------------------------------------------
    # P2：一句话生成 Prompt
    # ---------------------------------------------------------------
    st.subheader("新建 Agent")
    with st.form("gen_prompt"):
        desc = st.text_input(
            "用自然语言描述（可选）",
            placeholder="例如：喜欢日料、追求食材新鲜、不吃辣",
        )
        gen = st.form_submit_button("🪄 生成 Prompt", use_container_width=True)
    if gen:
        if not desc:
            st.warning("请先输入一句描述")
        else:
            resp = _post("/api/agents/generate-prompt", {"description": desc}, timeout=60.0)
            if resp is not None and resp.status_code == 200:
                _open_editor(
                    name=desc[:20],
                    avatar="🤖",
                    description=desc[:50],
                    system_prompt=resp.json()["system_prompt"],
                )
                st.info("已生成 Prompt，可在下方编辑区微调后保存")
                st.rerun()
            elif resp is not None:
                st.error(f"生成失败（{resp.status_code}）：{resp.text}")
            else:
                st.error("连接后端失败：请确认 uvicorn 已启动")

    # ---------------------------------------------------------------
    # P0：风格模板卡片库
    # ---------------------------------------------------------------
    st.markdown("**👉 或直接选一个风格模板一键套用：**")
    # 每行 4 个卡片，共 2 行
    for row_start in range(0, len(AGENT_TEMPLATES), 4):
        row = AGENT_TEMPLATES[row_start : row_start + 4]
        cols = st.columns(4)
        for col, tpl in zip(cols, row):
            with col:
                with st.container(border=True):
                    st.markdown(f"### {tpl.avatar} {tpl.name}")
                    st.caption(tpl.description)
                    if st.button("用这个模板", key=f"tpl_{tpl.name}", use_container_width=True):
                        _open_editor(
                            name=tpl.name,
                            avatar=tpl.avatar,
                            description=tpl.description,
                            system_prompt=tpl.system_prompt,
                        )
                        st.rerun()

    st.caption("💡 选模板后会自动填入系统提示词，你只需改个名字即可保存。")


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
            # 明确读取字节并解析 JSON（对齐后端 {"items": [...]} 结构）
            raw = uploaded.getvalue()
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            st.error(f"JSON 格式错误：{exc}")
        else:
            # 兼容两种结构：顶层 {"items": [...]} 或直接数组 [...]
            if isinstance(data, list):
                data = {"items": data}
            resp = _post("/api/menus/import", data, timeout=30.0)
            if resp is None:
                st.error("连接后端失败：请确认 uvicorn 已启动")
            elif resp.status_code == 201:
                st.success(f"已导入 {len(resp.json())} 道菜")
                st.rerun()
            else:
                st.error(f"后端返回 {resp.status_code}：{resp.text}")
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
    if resp is None:
        st.error("连接后端失败：请确认 uvicorn 已启动")
        return
    if resp.status_code != 200:
        st.error(f"后端返回 {resp.status_code}：{resp.text}")
        return

    menus = resp.json()
    # 服务端过滤
    if params:
        resp2 = _get("/api/menus", params=params)
        if resp2 is not None and resp2.status_code == 200:
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
        st.info("菜单为空，已尝试自动导入，请刷新页面")


# ---------------------------------------------------------------------------
# 侧边栏导航 + 历史会话 + 连接测试
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("🍜 Cyber Foodie")
    page = st.radio("导航", ["💬 辩论", "🧑‍🍳 Agent 管理", "🍽️ 菜单管理"])

    # 显示当前 LLM 配置（来自 /health）
    health = _get("/health")
    if health is not None and health.status_code == 200:
        info = health.json()
        st.caption(
            f"模型：{info.get('model')} | provider：{info.get('llm_provider')} | "
            f"mock：{info.get('is_mock')}"
        )
    else:
        st.caption("⚠️ 未连接后端")

    st.divider()
    if st.button("🔧 测试后端连接", use_container_width=True):
        import time

        url = f"{API_BASE}/health"
        start = time.time()
        try:
            resp = httpx.get(url, timeout=5.0)
            elapsed = (time.time() - start) * 1000
            st.success(f"✅ 后端可达\n\nURL：{url}\n状态码：{resp.status_code}\n耗时：{elapsed:.1f} ms")
        except httpx.HTTPError as exc:
            elapsed = (time.time() - start) * 1000
            st.error(f"❌ 连接失败\n\nURL：{url}\n异常：{type(exc).__name__}\n耗时：{elapsed:.1f} ms")

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
