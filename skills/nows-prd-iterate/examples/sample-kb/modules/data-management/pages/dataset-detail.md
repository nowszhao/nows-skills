---
page_id: data-management/dataset-detail
title: 数据集详情
module: data-management
url_path: /data/datasets/:id
roles: [Owner, Admin, Developer, Viewer]
screenshots:
  - file: dataset-detail/overview.png
    description: 详情默认态（已发布数据集）
  - file: dataset-detail/edit-mode.png
    description: 编辑态
related_pages:
  - data-management/dataset-list
  - data-management/datasource-detail
  - task-management/task-list
---

## 页面定位

展示单个数据集的完整信息（基础信息 / 字段结构 / 血缘 / 任务依赖 / 元数据 / 操作历史），支持编辑、发布、归档、删除等操作。

## 关键区域

### 1. 页面顶部
- 面包屑：数据管理 / 数据集列表 / {数据集名}
- 数据集名 + 状态徽标 + 类型徽标
- 右侧操作：编辑 / 发布 / 归档 / 删除（按权限和当前状态显示）

### 2. Tab 区
- **基础信息**（默认）：名称、描述、类型、所属数据源、创建人、创建时间、更新时间、标签
- **字段结构**：表格展示字段名、类型、可空、注释、是否主键
- **血缘**：上下游图（mermaid 渲染）
- **任务依赖**：依赖本数据集的所有 Task 列表
- **操作历史**：本数据集的所有审计日志

### 3. 编辑态
点击「编辑」后，基础信息变为可编辑表单：
- 描述：可改
- 标签：可改
- 名称、类型、数据源：**只读，创建后不可改**

## 状态机

| 当前状态 | 可执行操作 | 目标状态 |
|---------|-----------|---------|
| 草稿 | 编辑 / 发布 / 删除 | 草稿 / 已发布 / 物理删除 |
| 已发布 | 编辑（限元数据）/ 归档 | 已发布 / 已归档 |
| 已归档 | 重新发布 / 删除 | 已发布 / 物理删除 |

## 跳转关系

- 面包屑「数据集列表」→ `data-management/dataset-list`
- 「所属数据源」→ `data-management/datasource-detail`
- 「任务依赖」Tab 内任务名 → `task-management/task-detail`

## 边界与异常

- 数据集不存在：显示 404 页
- 无权限查看：显示 403 页
- 数据集已被他人删除（刷新前是详情，刷新后已删）：显示「该数据集已被删除」+ 返回列表按钮

## 关联业务规则

- 已发布的数据集不可改名 / 改类型 / 改数据源（避免破坏下游）
- 已归档的数据集不可被新 Task 引用
- 删除前如果有任务依赖，弹窗提示
- 重新发布要求当前归档状态 ≤ 90 天，超期需重新创建

## 审计

- 编辑：写审计日志（操作人 / 时间 / 变更字段 / 旧值 / 新值）
- 发布 / 归档 / 删除：写审计日志（操作人 / 时间 / 动作 / 数据集名）

## 截图说明（占位）

- `dataset-detail/overview.png`：默认详情态，已发布的 TABLE 类型数据集
- `dataset-detail/edit-mode.png`：编辑态展开
