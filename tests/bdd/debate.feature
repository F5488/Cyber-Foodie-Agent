Feature: Cyber Foodie Agent 辩论与战报

  Scenario: 成功启动辩论
    Given 我提供口味偏好"辣"和预算"中"以及天气"晴"
    When 我提交启动请求
    Then 系统创建新会话并返回 session_id
    And 系统触发两位 Agent 开始辩论

  Scenario: 非法口味偏好被拒绝
    Given 我提供口味偏好"甜"和预算"中"以及天气"晴"
    When 我提交启动请求
    Then 系统返回 422 校验错误
    And 不创建任何会话

  Scenario: 查询辩论发言并标明身份
    Given 一个已启动的辩论会话
    When 我查询该会话的发言
    Then 返回按轮次排序的发言列表
    And 每条发言标明"川辣派"或"粤式养生派"
    And 两位 Agent 交替发言

  Scenario: 查询不存在的会话
    Given 我提供不存在的 session_id
    When 我查询其状态
    Then 返回 404 错误

  Scenario: 辩论结束生成战报
    Given 一个已启动的辩论会话
    When 我查询该会话的战报
    Then 返回包含 final_choice 和 reason 和 score 的战报
    And 战报持久化存储

  Scenario: 战报字段完整
    Given 一个已启动的辩论会话
    When 我查询该会话的战报
    Then final_choice 非空
    And score 为 0 到 10 之间的数值
    And pros_cons 包含双方观点
    And winner_agent 为"川辣派"或"粤式养生派"
