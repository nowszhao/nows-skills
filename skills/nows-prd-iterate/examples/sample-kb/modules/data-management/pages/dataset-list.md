---
page_id: data-management/dataset-list
title: 数据集列表
module: data-management
url_path: /data/datasets
roles: [Owner, Admin, Developer, Viewer]
screenshots:
  - file: dataset-list/overview.png
    description: 整页默认态（已有数据）
  - file: dataset-list/empty.png
    description: 空数据态
  - file: dataset-list/form-create.png
    description: 新建数据集弹窗
related_pages:
  - data-management/dataset-detail
  - data-management/datasource-list
  - task-management/task-list
---

## 页面定位

展示当前租户下所有数据集的列表，支持搜索、筛选、分页，并提供创建入口。
所有角色都可查看，但操作按钮根据角色不同显示/隐藏。

## 关键区域

### 顶部操作区

布局：左侧搜索 + 筛选；右侧主操作。

- **搜索框**：按数据集名称模糊匹配，输入即触发（debounce 300ms）
- **类型筛选**：下拉多选 `TABLE` / `VIEW` / `STREAM`，默认全选
- **状态筛选**：下拉多选 `草稿` / `已发布` / `已归档`，默认仅选「已发布」
- **「新建数据集」按钮**：仅 Owner / Admin / Developer 可见，点击后弹窗（非跳转）

### 列表表格

| 字段 | 排序 | 说明 |
|------|------|------|
| 名称 | 可点击进详情 | 长名截断 + tooltip |
| 类型 | 可排序 | TABLE / VIEW / STREAM 徽标 |
| 数据源 | 不可排序 | 点击跳数据源详情 |
| 创建人 | 可排序 | 显示昵称 |
| 创建时间 | 默认倒序 | YYYY-MM-DD HH:mm |
| 状态 | 可排序 | 草稿（灰）/ 已发布（绿）/ 已归档（橙）|
| 操作 | — | 查看 / 编辑 / 删除（按权限） |

分页：每页 20 条，分页器在表格下方。

### 状态徽标
- 草稿：灰底白字
- 已发布：绿底白字
- 已归档：橙底白字

## 跳转关系

- 点击「名称」→ `data-management/dataset-detail`
- 点击「数据源」列 → `data-management/datasource-detail`
- 点击「新建数据集」→ 弹出新建表单（弹窗在本页内）
- 行内「查看」→ `data-management/dataset-detail`
- 行内「编辑」→ `data-management/dataset-detail`（详情页编辑态）
- 行内「删除」→ 二次确认弹窗 → 留在本页 + toast

## 边界与异常

- **空数据态**：显示引导插画 + 「立即创建」按钮（仅 Owner/Admin/Developer 可见）
- **超过 1 万条**：仅返回前 1 万条 + 顶部提示「结果较多，请用筛选缩小范围」
- **网络失败**：表格区域显示错误态 + 「重试」按钮
- **权限不足看不到任何数据**：显示「当前角色暂无可查看的数据集，请联系管理员」

## 关联业务规则

- 数据集名称在租户内唯一（同租户跨模块不冲突）
- Viewer 角色不显示「新建」「编辑」「删除」按钮
- Developer 仅能看到「编辑」「删除」自己创建的数据集
- 删除前如果有下游 Task 依赖，弹窗提示并列出依赖任务，不允许直接删
- 单租户数据集总数上限 1000，到达上限时「新建」按钮置灰 + tooltip 提示

## 审计

- 新建数据集：写审计日志（操作人 / 时间 / 数据集名 / 类型）
- 删除数据集：写审计日志（操作人 / 时间 / 数据集名 / 删除原因可选）

## 截图说明（占位）

> 真实 KB 应放对应 PNG 文件。本示例 KB 用文字描述代替。

- `dataset-list/overview.png`：整页默认态，10 行示例数据
- `dataset-list/empty.png`：空数据引导态
- `dataset-list/form-create.png`：新建数据集弹窗
