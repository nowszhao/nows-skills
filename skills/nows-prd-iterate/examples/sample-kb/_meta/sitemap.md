# 信息架构

## 导航树

- 数据管理 (`data-management`)
  - 数据集列表 (`dataset-list`) ⭐
  - 数据集详情 (`dataset-detail`) ⭐
  - 数据源列表 (`datasource-list`)
  - 数据源详情 (`datasource-detail`)
- 任务管理 (`task-management`)
  - 任务列表 (`task-list`)
  - 任务详情 (`task-detail`)
  - 任务编排 (`task-flow`)
- 查询分析 (`query-analytics`)
  - SQL 工作台 (`sql-workbench`)
  - 查询历史 (`query-history`)
- 平台管理 (`platform-admin`)
  - 用户管理 (`user-list`)
  - 配额管理 (`quota-config`)
  - 审计日志 (`audit-log`)

> ⭐ 表示本示例 KB 提供了详细页面 md。其他页面在真实 KB 中也应有详细 md。

## 页面索引

| page_id | 标题 | 路径 | 模块 |
|---------|------|------|------|
| data-management/dataset-list | 数据集列表 | /data/datasets | 数据管理 |
| data-management/dataset-detail | 数据集详情 | /data/datasets/:id | 数据管理 |
| data-management/datasource-list | 数据源列表 | /data/sources | 数据管理 |
| task-management/task-list | 任务列表 | /tasks | 任务管理 |
| task-management/task-detail | 任务详情 | /tasks/:id | 任务管理 |
| query-analytics/sql-workbench | SQL 工作台 | /query | 查询分析 |
| platform-admin/audit-log | 审计日志 | /admin/audit | 平台管理 |
