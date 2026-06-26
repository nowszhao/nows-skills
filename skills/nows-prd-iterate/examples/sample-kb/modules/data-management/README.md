# 数据管理模块

## 模块定位

数据资产管理的核心模块，让用户能：
- 接入异构数据源（MySQL / PostgreSQL / Kafka / HDFS / S3 / Hive 等）
- 在数据源之上定义数据集（表 / 视图 / 流）
- 维护元数据、血缘、统计信息

## 子页面

- `dataset-list` 数据集列表
- `dataset-detail` 数据集详情
- `datasource-list` 数据源列表
- `datasource-detail` 数据源详情

## 核心业务对象

### Dataset（数据集）
- 类型：`TABLE` / `VIEW` / `STREAM`
- 状态机：`草稿` → `已发布` → `已归档` →（可删除）→ 物理删除
- 唯一性：名称在租户 + 模块内唯一
- 配额：单租户默认上限 1000 个

### DataSource（数据源）
- 类型：MySQL / PostgreSQL / Kafka / HDFS / S3 / Hive
- 状态：`正常` / `连接失败` / `禁用`
- 由 Owner / Admin 管理，Developer 只读使用

## 模块级业务规则

- 删除 Dataset 前，必须先确认无下游 Task 依赖
- 归档的 Dataset 不可被新 Task 引用，但已有 Task 可继续运行
- 数据源被删除前，其上所有 Dataset 必须先归档或迁移
