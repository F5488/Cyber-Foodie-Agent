# Sprint 1 报告

> 周期：第 1-2 周　目标：核心骨架与基础辩论（US01 + US02）

## 一、计划

- 搭建 FastAPI 后端，定义 Pydantic 模型。
- 实现 LLM 客户端（多 provider + Mock 兜底）。
- 实现 Agent 类（预设「川辣派」与「粤式养生派」）。
- 实现 `DebateService`，含 `start_debate` 与轮流发言逻辑（3 轮交替）。
- 实现 `POST /api/debate/start` 与 `GET /api/debate/{session_id}/status`。
- 编写 Streamlit 前端（输入表单 + 聊天式展示）。
- 编写基础单元测试。

## 二、完成情况

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| 后端项目骨架 + Pydantic 模型 | ✅ | `src/models.py` |
| LLM 客户端（mock/openai_compatible/azure） | ✅ | `src/llm.py`，含超时与指数退避重试 |
| Agent 类与预设大厨 | ✅ | `src/agents.py` |
| DebateService 轮流辩论逻辑 | ✅ | `src/debate.py`，轮次上限钳制 |
| REST API（start/status/rounds） | ✅ | `src/main.py`，含简易频控 |
| Streamlit 前端 | ✅ | `src/frontend.py` |
| 单元测试 + 集成测试 | ✅ | `tests/unit`、`tests/integration` |
| CI（pytest + flake8 + docker build） | ✅ | `.github/workflows/ci.yml` |

## 三、遇到的困难与解决

1. **无 API Key 无法演示** → 引入 `MockLLMClient`，默认 `LLM_PROVIDER=mock`，零配置即可运行与 CI 测试。
2. **LLM 调用不稳定** → 在 `_retry_httpx_post` 中实现 30s 超时 + 3 次指数退避重试。
3. **轮次配置可能异常** → 将 `DEBATE_ROUNDS` 钳制在 `[1, 10]`，防御异常输入。
4. **输入注入风险** → 请求体用 Pydantic 枚举校验 + `_sanitize` 清洗控制字符。

## 四、Sprint 1 演示

```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000   # 终端 1
streamlit run src/frontend.py               # 终端 2
```

访问 http://localhost:8501，选择口味/预算/天气，点击「开始辩论」即可看到两位大厨交替发言。

## 五、下一步（Sprint 2）

- 引入 SQLite 持久化（sessions / debate_rounds / recommendations）。
- 实现战报生成器（US03）。
- 流式输出与前端优化。
- BDD 验收测试（Behave）。
