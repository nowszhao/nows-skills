# 用法示例

本目录提供一个示例知识库 `sample-kb/`，模拟一个**数据平台**的「数据管理」模块。
你可以拿它直接试跑 skill，了解输入和输出长什么样。

## 示例知识库说明

`sample-kb/` 模拟系统：「Lakehouse 数据平台 v2.4（私有化部署版）」

包含：
- `README.md` —— 系统总览
- `_meta/glossary.md` —— 术语表
- `_meta/roles.md` —— 角色权限矩阵
- `_meta/sitemap.md` —— 信息架构 + 页面索引
- `modules/data-management/README.md` —— 数据管理模块说明
- `modules/data-management/pages/dataset-list.md` —— 数据集列表页
- `modules/data-management/pages/dataset-detail.md` —— 数据集详情页
- 截图：以占位说明文件代替（真实场景应放 PNG）

## 试跑示例

把整段需求贴给 skill：

```
KB 路径：./skills/nows-prd-iterate/examples/sample-kb
迭代需求：客户希望在数据集列表里加批量导出功能，可一次性导出多个数据集为 CSV
```

Skill 会按以下流程响应：

1. **加载 KB** → 读取 `_meta/*`、`dataset-list.md`、相关截图占位
2. **澄清需求**（分批提问）：
   - 「单次导出最多多少条？是否限制并发数？」
   - 「导出格式只 CSV 还是支持 Excel/JSON？」
   - 「Viewer 角色能不能用？」
   - 「导出文件存哪？租户私有存储还是临时下载链接？」
3. **生成影响面清单**让你确认
4. **生成 PRD**：`dataset-batch-export-prd.md`
5. **生成 HTML 原型**：`dataset-batch-export-prototype.html`

## 自己准备 KB 时

参考 `sample-kb/` 的结构，按 `../references/kb-spec.md` 规范准备即可。

最小可用 KB 只需：
- `README.md` + `_meta/roles.md` + `_meta/sitemap.md`
- 本次迭代涉及的页面 md + 至少 1 张整页截图
