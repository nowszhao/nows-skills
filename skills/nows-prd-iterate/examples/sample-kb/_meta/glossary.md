# 术语表

| 术语 | 定义 | 同义词 |
|------|------|--------|
| 数据集 (Dataset) | 系统内可被消费的数据资产单元，对应一张表 / 视图 / 流 | Dataset |
| 数据源 (DataSource) | 数据集的物理来源，如 MySQL 实例、Kafka topic、HDFS 路径 | DataSource、Source |
| 任务 (Task) | 周期性或一次性的数据处理作业 | Job、Task |
| 租户 (Tenant) | 平台隔离的最小资源单位，对应一个业务团队或客户子组织 | Tenant、Workspace |
| 配额 (Quota) | 租户级别的资源上限（数据集数 / 并发任务数 / 存储量） | Quota |
| 元数据 (Metadata) | 描述数据集结构、血缘、统计信息的数据 | Metadata |
