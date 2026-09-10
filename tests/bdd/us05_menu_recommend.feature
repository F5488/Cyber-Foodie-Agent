Feature: 结合真实菜单数据（US05）

  Scenario: 导入菜单数据
    Given 我提供一份 JSON 菜单数据
    When 我调用菜单导入接口
    Then 系统存储菜品并可查询

  Scenario: 推荐来自菜单
    Given 菜单列表存在且用户预算为"中"
    When 辩论结束生成推荐
    Then final_choice 来自菜单列表

  Scenario: 筛选候选菜品
    Given 菜单列表存在且用户口味为"辣"
    When 系统筛选候选菜品
    Then 候选菜品包含辣味标签
