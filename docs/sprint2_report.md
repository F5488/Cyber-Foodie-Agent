# Sprint 2 报告

> 周期：第 3-4 周　目标：数据库持久化 + 结构化战报（US03），系统从「能跑」到「能用」

## 一、Sprint 目标

- 引入 SQLAlchemy 2.x + SQLite，按 ER 图建 4 张表。
- `DebateService` 从内存改为数据库读写，重启后历史可查。
- 实现结构化战报生成（US03），含 LLM 聚合 + 规则降级。
- 前端战报卡片 + 历史会话侧边栏。
- 防御性编程：slowapi 频控、输入截断、注入防护。
- BDD 验收测试 + 单元测试，覆盖率达标。

## 二、完成的 Issue / 提交记录

| 提交 | 类型 | 说明 |
| --- | --- | --- |
| `7f48d49` | feat | 引入 SQLAlchemy 数据库层与 ORM 映射 |
| `3501ef5` | feat | DebateService 改为数据库持久化 |
| `fee8fe5` | feat | 实现结构化战报生成与 report API（US03） |
| `c047c4e` | feat | 前端战报卡片与历史会话侧边栏 |
| `75e630d` | feat | 防御性编程（slowapi 频控、输入截断、测试隔离） |
| `a263517` | test | 新增 BDD 验收测试（pytest-bdd） |

## 三、完成情况

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| 数据库层 | ✅ | `src/db.py` + `src/orm_models.py`，4 表对齐 ER 图 |
| 持久化改造 | ✅ | 辩论/发言/战报全部落库，重启可查 |
| 战报生成 | ✅ | LLM 聚合 + JSON 提取 + 重试一次 + 规则降级 |
| report API | ✅ | `GET /api/debate/{session_id}/report` |
| 前端 | ✅ | 战报卡片 + 历史会话侧边栏 |
| 防御性编程 | ✅ | slowapi 5/min、长度截断、超时重试 |
| BDD 测试 | ✅ | 6 个场景覆盖 US01~US03 |
| 单元测试 | ✅ | test_db.py + test_report.py |

## 四、测试与覆盖率

- 总测试：**39 passed**（单元 24 + 集成 5 + BDD 6 + 其他）
- 覆盖率：**76%**（总），核心业务逻辑 `debate.py` 98%、`report.py` 93%、`models.py`/`orm_models.py` 100%。
- flake8 静态检查通过。

## 五、遇到的困难与解决

1. **slowapi 与 `from __future__ import annotations` 冲突**
   slowapi 的 `@limiter.limit` 装饰器替换函数对象，导致字符串注解无法被 FastAPI 解析。→ 移除 `main.py` 的 future annotations，改用真实类型引用。

2. **pytest-bdd 7.x 的 step 间传值**
   早期版本函数返回值会自动成为 fixture，7.x 需要显式 `target_fixture`。→ 所有 step 定义改用 `target_fixture` 显式传递。

3. **测试间频控污染**
   slowapi 的 limiter 是全局单例，TestClient 共享同一 IP，跨测试累积触发 429。→ 在 conftest 增加 autouse fixture，每个测试前 `limiter.reset()`。

4. **LLM 返回非法 JSON**
   真实 LLM 可能返回 markdown 代码块或纯文本。→ `_extract_json` 容错解析 + 失败重试 + 规则降级兜底，保证始终产出可读战报。

5. **战报字段需要获胜方**
   US03 要求 `winner_agent` 字段，原 Pydantic `Recommendation` 未定义。→ 新增 `Report` 模型 + `Recommendation.winner_agent`，ORM 表同步加列。

## 六、Burndown 描述

Sprint 2 共 6 个功能提交，按数据库 → 持久化 → 战报 → 前端 → 防御 → 测试的依赖顺序推进。前 4 个任务（数据库、持久化、战报、前端）构成主链路，占比约 60%；防御性编程与测试各占 20%。整体无返工，唯一超出预期的调试来自 slowapi 注解冲突与 pytest-bdd 传值机制，均在当天解决。

## 七、下一步计划（Sprint 3）

- 引入 Alembic 数据库迁移。
- 实现 Agent 管理 CRUD（US04），支持自定义 Agent 性格。
- 设计菜单数据模型与导入接口（US05），推荐基于真实菜单。
- 前端 Agent 列表与编辑界面。
