Feature: 自定义 Agent 性格（US04）

  Scenario: 创建自定义 Agent
    Given 我提供一个自定义 Agent 的名称和系统提示词
    When 我调用创建 Agent 接口
    Then 系统创建 Agent 并返回 agent_id
    And 该 Agent 出现在 Agent 列表中

  Scenario: 使用自定义 Agent 辩论
    Given 存在一个自定义 Agent
    When 我启动辩论并指定该 Agent 作为大厨 A
    Then 辩论由该 Agent 参与
    And 发言中包含该 Agent 的名称

  Scenario: 预设 Agent 不可删除
    Given 预设 Agent"川辣派"存在
    When 我尝试删除该预设 Agent
    Then 系统返回 403 错误
