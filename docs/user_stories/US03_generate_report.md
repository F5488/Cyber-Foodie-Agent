# US03 — 生成结构化战报与推荐

> 状态：MVP（Sprint 2）　故事点：8

## 用户故事

**As a** 学生
**I want to** 在辩论结束后获得一份包含最终推荐菜品、理由摘要、双方观点总结的战报
**So that** 我能快速决策

## 验收条件

- [x] 输出为 JSON 结构，包含 `final_choice`、`reason`、`pros_cons`、`score` 等字段
- [x] 前端以友好卡片形式展示
- [x] 战报在辩论结束后自动生成（或通过 finalize 接口触发）
- [x] 战报结果持久化存储

## Gherkin 场景

```gherkin
Feature: 生成结构化战报

  Scenario: 辩论结束生成战报
    Given 会话已完成 3 轮辩论
    When 系统触发战报生成
    Then 返回包含 final_choice / reason / pros_cons / score 的 JSON
    And 战报持久化到 recommendations 表

  Scenario: 战报字段完整
    Given 战报已生成
    When 我读取战报
    Then final_choice 非空
    And score 为 0 到 10 之间的数值
    And pros_cons 包含双方观点

  Scenario: 未完成辩论时请求战报
    Given 会话仍在辩论中
    When 我请求战报
    Then 返回 409 或提示"辩论尚未结束"
```

## 故事级 Mermaid 图

### 1. 用例图

```mermaid
flowchart LR
    U((学生)) --> UC3["获取战报"]
    UC3 -.->|聚合| L((LLM API))
    UC3 --> DB[("recommendations 表")]
```

### 2. 数据流图

```mermaid
flowchart LR
    T["全部发言"] --> A["聚合总结(LLM)"]
    A --> S["结构化解析"]
    S --> DB[("recommendations")]
    S --> O["战报 JSON"]
```

### 3. 领域类图

```mermaid
classDiagram
    class Recommendation {
        +str final_choice
        +str reason
        +list pros_cons
        +float score
    }
    class DebateService {
        +finalize(session_id) Recommendation
    }
    DebateService --> Recommendation : 产出
```

### 4. 时序图

```mermaid
sequenceDiagram
    participant B as 后端
    participant L as LLM
    participant DB as 数据库
    B->>B: 收集全部发言
    B->>L: summarize(发言)
    L-->>B: 结构化结论
    B->>B: 校验字段/评分范围
    B->>DB: 保存 Recommendation
    B-->>B: 状态 → SUCCESS
```

### 5. 状态机图

```mermaid
stateDiagram-v2
    RUNNING --> VALIDATING : 辩论结束
    VALIDATING --> SUCCESS : 校验通过
    VALIDATING --> FAILED : 校验失败
```

### 6. 活动图

```mermaid
flowchart TD
    A[开始] --> B{辩论结束?}
    B -- 否 --> C[返回 409]
    B -- 是 --> D[聚合发言]
    D --> E[调用 LLM 总结]
    E --> F{字段校验}
    F -- 失败 --> G[FAILED + 重试]
    F -- 通过 --> H[保存并返回战报]
    C --> I[结束]
    G --> I
    H --> I
```
