# Cyber Foodie Agent — 答辩材料

## 1. 项目背景

大学生「今天吃什么」是高频决策难题：口味、预算、天气多重约束叠加，众口难调。
Cyber Foodie Agent 用「AI 大厨辩论」的方式把选择过程变得有趣——两位预设大厨（川辣派 vs 粤式养生派）围绕你的需求多轮辩论，最终输出结构化战报与菜品推荐。

## 2. 技术架构

| 层 | 选型 |
| --- | --- |
| 后端 | Python + FastAPI |
| 前端 | Streamlit（MVP） |
| 数据库 | SQLite（开发）→ PostgreSQL（生产） |
| LLM | 硅基流动 / Azure OpenAI / DeepSeek（环境变量切换，Mock 兜底） |
| 容器 | Docker 多阶段构建 + Compose |
| CI/CD | GitHub Actions（flake8 + pytest + coverage + alembic + docker） |

## 3. 六图精华

- **用例图**：用户（学生）驱动 5 个用例（启动辩论/查看过程/获取战报/自定义 Agent/查询菜单），依赖 LLM API 与外部菜单源。
- **数据流图**：用户输入 → 构造 Prompt → 调 LLM → 解析 → 存会话 → 返回前端。
- **领域类图**：Session（聚合根）、Agent、DebateRound、Recommendation、Menu、UserPreference。
- **ER 图**：sessions、agents、debate_rounds、recommendations、menus 五表。
- **时序图**：前端 → 后端 → LLM（两次调用/两位大厨）×3 轮 → 聚合 → 返回。
- **状态机图**：PENDING → RUNNING → VALIDATING → SUCCESS/FAILED。

详见 [system_design.md](system_design.md)。

## 4. 四个 Sprint 成果

| Sprint | 成果 |
| --- | --- |
| 1 | FastAPI + Mock LLM + 3 轮自动辩论 + Streamlit 前端 |
| 2 | SQLAlchemy 持久化 + 结构化战报（US03） |
| 3 | Agent CRUD + 菜单导入与推荐（US04/05） |
| 4 | Docker 优化 + CI + 评测 + 文档 |

## 5. 创新点

1. **辩论式推荐**：不是单一 LLM 推荐，而是两位风格化大厨对抗，推荐更有解释性。
2. **可配置 Agent 性格**：用户可创建/克隆自定义大厨，辩论风格随人而变。
3. **基于真实菜单**：推荐必须来自可购买菜品，价格与口味标签约束。
4. **LLM 降级兜底**：非法 JSON 自动重试 + 规则摘要，系统永不宕机。

## 6. 演示截图占位

<!-- 录完视频后，在此插入关键截图 -->
- [ ] 辩论过程截图
- [ ] 战报卡片截图
- [ ] Agent 管理截图
- [ ] 菜单管理截图

## 7. Q&A 准备

**Q1：为什么用 Mock LLM？**
A：确保零配置可演示、CI 稳定；真实 provider 通过环境变量一键切换，接口已实现。

**Q2：如何保证推荐菜品可购买？**
A：菜单模式下先用预算+口味标签规则筛选候选，再把候选列表喂给 LLM，要求 final_choice 必须来自候选；战报存 menu_item_id 与 price 关联到具体菜品。

**Q3：频控为什么设 5 次/分钟？**
A：LLM 调用有成本，5 次/分钟足够个人演示，同时防止 API 滥用与费用失控。

**Q4：数据库迁移如何管理？**
A：Sprint 3 引入 Alembic，baseline + 扩展字段 migration，CI 中 `alembic upgrade head` 空库验证。

**Q5：测试覆盖如何？**
A：61 测试通过，覆盖率 90%，核心业务逻辑（debate/report/menu/agent）≥89%，BDD 覆盖 US01~US05。
