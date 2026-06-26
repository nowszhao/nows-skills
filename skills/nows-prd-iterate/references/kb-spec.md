# 现有系统知识库（KB）规范

> 本 skill 的所有产出都依赖你提供的 KB。**KB 不准 → 输出不准**。
> 准备 KB 是一次性投入；之后每次迭代都能复用，价值很高。

## 1. 目录结构

```
<your-kb-root>/
├── README.md                          # 系统总览（必填）
├── _meta/
│   ├── glossary.md                    # 术语表（必填）
│   ├── roles.md                       # 角色与权限矩阵（必填）
│   └── sitemap.md                     # 信息架构 / 导航树（必填）
├── modules/                           # 按业务模块分组
│   └── <module-name>/
│       ├── README.md                  # 模块说明（必填）
│       └── pages/
│           ├── <page-slug>.md         # 单页说明（必填，含 frontmatter）
│           └── <page-slug>/           # 该页的截图与附属资源
│               ├── overview.png       # 整页截图
│               ├── <state>.png        # 关键状态截图（如 form-create.png）
│               └── annotations.md     # 截图标注（可选）
└── flows/                             # 跨页业务流程（可选）
    └── <flow-name>.md
```

## 2. 命名规则

- `<module-name>`、`<page-slug>`：**kebab-case**，全英文小写，能成为 URL 片段
- `page_id` = `<module-name>/<page-slug>`，全局唯一（如 `data-management/dataset-list`）
- 截图统一 PNG，文件名小写 + 短横线（如 `form-create.png`）

## 3. 必填文件内容规范

### 3.1 `README.md`（系统总览）

```markdown
# {系统名称}

## 定位
{一段话：是什么系统、给谁用、解决什么问题}

## 部署形态
- 私有化 / SaaS / 混合
- 典型部署环境：…
- 离线 / 内网约束：…

## 核心域
- 模块 1：…
- 模块 2：…

## 用户角色（详见 _meta/roles.md）
- Owner / Admin / Viewer …
```

### 3.2 `_meta/glossary.md`（术语表）

```markdown
# 术语表

| 术语 | 定义 | 同义词 |
|------|------|--------|
| 数据集 | 系统内可被消费的数据资产单元 | Dataset |
| 数据源 | 数据集的物理来源（如 MySQL 表） | DataSource |
```

### 3.3 `_meta/roles.md`（角色权限矩阵）

```markdown
# 角色与权限矩阵

## 角色定义
- **Owner**：租户管理员，全部权限
- **Admin**：模块管理员，限定模块内的管理权限
- **Viewer**：只读用户

## 权限矩阵（模块 × 操作 × 角色）

| 模块 | 操作 | Owner | Admin | Viewer |
|------|------|-------|-------|--------|
| 数据集 | 创建 | ✅ | ✅ | ❌ |
| 数据集 | 查看 | ✅ | ✅ | ✅ |
| 数据集 | 删除 | ✅ | ❌ | ❌ |
```

### 3.4 `_meta/sitemap.md`（信息架构）

```markdown
# 信息架构

## 导航树
- 数据管理 (`data-management`)
  - 数据集列表 (`dataset-list`)
  - 数据集详情 (`dataset-detail`)
  - 数据源列表 (`datasource-list`)
- 任务管理 (`task-management`)
  - …

## 页面索引

| page_id | 标题 | 路径 | 模块 |
|---------|------|------|------|
| data-management/dataset-list | 数据集列表 | /data/datasets | 数据管理 |
| data-management/dataset-detail | 数据集详情 | /data/datasets/:id | 数据管理 |
```

### 3.5 单页 md：`modules/<m>/pages/<p>.md`

**必须含 frontmatter**：

```markdown
---
page_id: data-management/dataset-list
title: 数据集列表
module: data-management
url_path: /data/datasets
roles: [Owner, Admin, Viewer]
screenshots:
  - file: dataset-list/overview.png
    description: 整页默认态
  - file: dataset-list/empty.png
    description: 空数据态
related_pages:
  - data-management/dataset-detail
  - data-management/dataset-create
---

## 页面定位
{一句话：这个页面给谁用、做什么}

## 关键区域

### 顶部操作区
- 「新建数据集」按钮（权限：Owner / Admin）
- 搜索框（按名称模糊匹配）
- 类型筛选下拉：TABLE / VIEW / STREAM

### 列表表格
- 字段：名称、类型、创建人、创建时间、状态、操作
- 排序：按创建时间倒序，可点表头切换
- 分页：每页 20 条
- 行内操作：查看 / 编辑 / 删除（删除需 Owner）

### 状态徽标
- 草稿（灰）/ 已发布（绿）/ 已归档（橙）

## 跳转关系
- 点击「名称」→ `data-management/dataset-detail`
- 点击「新建」→ 弹出新建表单（同页弹窗，非独立页）
- 删除成功 → 留在本页 + toast 提示

## 边界与异常
- 空数据：显示引导插画 + 「立即创建」按钮
- 超过 1 万条：仅展示前 1 万条 + 提示用筛选
- 网络失败：表格区域显示错误态 + 重试按钮

## 关联业务规则
- 数据集名称在租户内唯一
- 同一用户可创建的数据集数量受租户配额限制（默认 100）
```

## 4. 截图建议

- **整页截图必有**（`overview.png`）
- **关键状态分别截**：空态、错误态、典型数据态、超长数据态
- **关键弹窗 / 抽屉单独截**：如 `form-create.png`、`drawer-detail.png`
- 截图尺寸：宽度 1440px 左右；不要太大（单图 < 500KB）
- 可选 `annotations.md` 标注：用文字描述截图里每个区域的位置和说明

## 5. 最小可用 KB（MVP）

如果你的系统很大，不必一次性补全。**最少满足以下条件即可启动 skill**：

- `README.md` 系统总览
- `_meta/roles.md` 至少有角色定义
- `_meta/sitemap.md` 至少列出本次迭代涉及的页面
- 本次迭代**直接涉及的页面**：单页 md + 整页截图

无关页面可以后续按需补。

## 6. 自查清单

准备完 KB 后，对照检查：

- [ ] `README.md` / `_meta/glossary.md` / `_meta/roles.md` / `_meta/sitemap.md` 都存在
- [ ] 本次迭代涉及的每个页面都有 md + 至少 1 张截图
- [ ] 每个页面 md 都有完整 frontmatter（`page_id` / `title` / `module` / `roles` / `related_pages`）
- [ ] `_meta/sitemap.md` 的页面索引表已包含涉及页面的 page_id
- [ ] 截图文件路径与 frontmatter 中 `screenshots.file` 字段对得上

参考实例：见 `../examples/sample-kb/`
