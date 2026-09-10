# AGENTS.md — 团队 AI 规则注入

本文件为仓库内的 AI 辅助开发规则，任何在此仓库工作的 AI 工具（Claude Code、Copilot 等）都应遵循。

## 语言规范

- 所有代码注释、文档、Commit Message、PR 描述使用**简体中文**。
- 代码标识符（变量名、函数名、类名）使用英文，保持可读性。

## 提交规范（Angular 语义）

每次提交必须使用以下前缀之一：

| 前缀 | 用途 |
| --- | --- |
| `feat:` | 新功能 |
| `fix:` | 修复缺陷 |
| `docs:` | 文档变更 |
| `style:` | 代码格式（不影响逻辑） |
| `refactor:` | 重构 |
| `test:` | 测试相关 |
| `chore:` | 构建/工具/依赖 |

示例：`feat: 实现川辣派 Agent 的 Prompt 模板`

## PR 流程

1. 从 `main` 拉取新分支，命名建议：`feature/us01-start-debate`、`fix/debate-round-counter`。
2. 完成后发起 Pull Request，描述必须填写：变更摘要、测试情况、截图（如 UI 变更）。
3. 至少 1 人 Review 并 Approve，且 CI 通过后方可合并。

## 测试要求

- 单元测试使用 pytest，覆盖率目标 ≥ 70%（核心业务逻辑 ≥ 90%）。
- BDD 验收测试使用 Behave，覆盖所有 User Story 的 Given-When-Then 场景。
- CI 失败阻断合并。

## 防御性编程要求

- 所有外部 API 调用设置超时与重试（指数退避）。
- 使用 Pydantic 校验请求体，拒绝非法字段。
- 对用户输入进行清洗，避免 Prompt 注入。
- 使用频控限制单 IP 每分钟请求数。

## 环境变量

- 严禁将真实 API Key 提交到仓库。
- 所有密钥通过 `.env`（已加入 `.gitignore`）注入，模板见 `.env.example`。

## 关键约束

- 主分支 `main` 禁止直接 push，必须通过 PR。
- 数据模型以 `src/models.py` 中的 Pydantic 契约为准。
