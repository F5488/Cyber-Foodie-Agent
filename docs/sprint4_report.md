# Sprint 4 报告

> 周期：第 7-8 周　目标：工程化完善 + 评测 + 文档 + 演示，项目达到「可交付、可展示、可复现」

## 一、Sprint 目标

- Docker 多阶段构建优化，一键起后端 + 前端 + 数据卷持久化。
- CI/CD 完善（Alembic 验证、Docker 构建、评测脚本）。
- 评测数据集与评分脚本（11 场景 + 4 维度评分）。
- README 工业级完善、演示视频、答辩材料。
- 最终交付物检查。

## 二、完成的提交记录

| 提交 | 类型 | 说明 |
| --- | --- | --- |
| `09d27c7` | feat | Docker 多阶段构建优化与数据卷持久化 |
| `7c94e16` | feat | 评测数据集与评分脚本（11 场景） |
| `21f6cf9` | docs | README 工业级完善 + 演示视频分镜脚本 |

## 三、完成情况

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| Docker 优化 | ✅ | 多阶段构建、前端独立镜像、SQLite 数据卷 |
| CI/CD 完善 | ✅ | alembic + docker compose build + eval 脚本 |
| 评测脚本 | ✅ | 11 场景全通过，输出 JSON + Markdown 报告 |
| README 完善 | ✅ | 徽章/结构/贡献者/视频占位 |
| 演示视频脚本 | ✅ | 分镜脚本（实际录制需组员完成） |
| Sprint 4 报告 | ✅ | 本文 |
| 答辩材料 | ✅ | docs/presentation.md |

## 四、评测结果

```
场景总数：11　通过：11　失败：0　通过率：100%
平均响应时间：23.5 ms（Mock LLM）
平均 LLM 调用次数：7（3 轮 × 2 大厨 + 1 战报）
```

## 五、遇到的困难与解决

1. **评测脚本触发频控 429**
   slowapi 全局限频器跨场景累积，第 6 个场景起被限流。→ 每个场景前 `limiter.reset()`。

2. **Mock LLM 固定返回「麻辣香锅」**
   菜单模式下清淡/低预算场景的候选不含麻辣香锅，导致 price 缺失。→ Mock 战报分支从 user_prompt 解析候选列表，取第一个候选菜品。

3. **Windows GBK 控制台无法输出 emoji**
   评测报告打印 `✅/❌` 报 UnicodeEncodeError。→ 改用 ASCII 的 `PASS/FAIL`，跨平台稳定。

4. **本机无 Docker**
   无法本地实测 `docker compose up`。→ 在 CI 中加入 `docker compose build` 验证双镜像可构建，实测交给 CI。

## 六、4 个 Sprint 复盘总结

| Sprint | 目标 | 关键产出 | 状态 |
| --- | --- | --- | --- |
| 1 | 核心骨架 + 基础辩论 | FastAPI + Mock LLM + 3 轮辩论 + Streamlit | ✅ |
| 2 | 持久化 + 战报 | SQLAlchemy 4 表 + 结构化战报（US03） | ✅ |
| 3 | 自定义 Agent + 菜单 | Agent CRUD + 菜单推荐（US04/05） | ✅ |
| 4 | 工程化 + 评测 + 演示 | Docker + CI + 评测 + 文档 | ✅ |

## 七、项目亮点

1. **完整工程实践**：4 个 Sprint 每项功能独立 commit、走 PR、CI 门禁（flake8 + pytest + 覆盖率 + Alembic + Docker）。
2. **防御性编程**：频控、输入截断、Prompt 注入防护、LLM 超时重试 + 规则降级。
3. **可复现**：Docker 多阶段构建 + 数据卷持久化，一键启动。
4. **评测体系**：11 场景自动评测，4 维度评分，输出 JSON/Markdown 报告。
5. **测试覆盖**：61 测试通过，覆盖率 90%，核心逻辑 ≥89%。

## 八、不足与改进

1. **演示视频**：尚未实际录制，需组员出镜/旁白完成。
2. **ghcr 推送**：因需 GitHub secrets 配置，暂未启用。
3. **真实 LLM 未实测**：默认 Mock，真实 DeepSeek/Azure 需 API Key 验证。
4. **前端为 MVP**：Streamlit 适合快速演示，正式版可迁移 React/Vue。
5. **菜单爬虫未实现**：当前用 JSON 导入，真实食堂/外卖爬虫留待拓展。

## 九、下一步（如继续）

- 录制演示视频并上传。
- 配置 ghcr secrets 推送镜像。
- 真实 LLM 接入联调。
- 前端 React 化。
