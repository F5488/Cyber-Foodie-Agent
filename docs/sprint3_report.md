# Sprint 3 报告

> 周期：第 5-6 周　目标：US04 自定义 Agent + US05 菜单推荐，系统从「固定两位大厨」升级为「用户可配、菜单可导入」

## 一、Sprint 目标

- 引入 Alembic 数据库迁移，agents 表扩展字段。
- US04：Agent 管理 CRUD + 克隆，辩论支持选 Agent。
- US05：菜单数据模型 + JSON 导入 + 基于菜单的推荐。
- 前端多页面升级，测试覆盖率 ≥75%。

## 二、完成的提交记录

| 提交 | 类型 | 说明 |
| --- | --- | --- |
| `8261b34` | fix | 修正 debate_rounds 主键为 Integer 自增（Sprint 2 遗漏） |
| `93b735b` | feat | 引入 Alembic 数据库迁移 |
| `0f032d2` | feat | 实现 Agent 管理 API（US04） |
| `dd9211b` | feat | 辩论启动支持自定义 Agent |
| `b15f381` | feat | 实现菜单数据模型与导入/查询 API（US05） |
| `661008a` | feat | 基于菜单的推荐 |
| `ea6b6f5` | feat | 前端升级为多页面 |
| `8d34e25` | test | 新增 US04/US05 BDD 测试 |

## 三、完成情况

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| Alembic 迁移 | ✅ | baseline + agents 扩展 migration，从零可跑通 |
| Agent 管理 API | ✅ | CRUD + clone，预设保护，字段校验 |
| 选 Agent 辩论 | ✅ | agent_a_id/agent_b_id，sessions 表记录 |
| 菜单数据模型 | ✅ | menus 表 + 导入/查询，sample_menu 21 道菜 |
| 基于菜单推荐 | ✅ | 规则筛选候选 + LLM 定夺 + menu_item_id/price |
| 前端升级 | ✅ | 辩论/Agent 管理/菜单管理三页 |
| 测试 | ✅ | 单元 + BDD，覆盖率 90% |

## 四、测试与覆盖率

- 总测试：**61 passed**（单元 + 集成 + BDD 12 场景）
- 覆盖率：**90%**（排除纯 UI 层 frontend.py）
- 核心业务逻辑：debate 98%、menu_service 98%、report 93%、agent_service 89%、models/orm_models 100%。

## 五、遇到的困难与解决

1. **Alembic autogenerate 重复建表**
   直接对空库 autogenerate 会生成「建全部表」的 migration，而不是「新增列」。→ 先 `alembic upgrade head` 应用 baseline，再 autogenerate，得到精确的「新增 3 列」diff。

2. **debate_rounds 主键类型不一致（Sprint 2 遗漏）**
   Sprint 2 提交时 `orm_models.py` 有一处未提交，导致本地（Integer 主键）与远程（String 主键）不一致。→ 在 sprint3 首个 commit 补上，保证同轮发言稳定排序。

3. **seed 时机导致 Agent 查不到**
   重构 `start_debate` 后，`_load_selected_agents` 在 `flush()` 前执行，预设 Agent 尚未 INSERT。→ `_seed_agents` 末尾加 `dbs.flush()` 立即落库。

4. **Menu 模型 id 必填冲突**
   导入时数据库才分配自增 id，但 Pydantic 模型要求必填。→ `id` 设默认值 0，数据库 refresh 后返回真实 id。

5. **覆盖率被 frontend.py 拉低**
   Streamlit UI 无法在 pytest 中测试，198 行全算未覆盖。→ pyproject.toml 用 `[tool.coverage.run] omit` 排除纯 UI 层，覆盖率从 70% 回升到 90%。

## 六、Burndown 描述

Sprint 3 共 8 个提交，按 Alembic → US04 后端 → 选 Agent → US05 菜单 → 推荐 → 前端 → 测试 → 文档的顺序推进。主链路（Agent CRUD + 菜单 + 推荐）占比约 60%，前端与测试各 20%。唯一返工点是 debate_rounds 主键的 Sprint 2 遗漏修复，其余按计划推进。

## 七、下一步计划（Sprint 4）

- CI/CD 完善：Docker 镜像推送、Alembic 迁移验证入 CI。
- 评测：eval/ 评分脚本，自动运行生成质量报告。
- 文档完善：演示视频、答辩材料、README 徽章。
- 最终代码审查与合并。
