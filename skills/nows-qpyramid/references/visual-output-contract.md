# Question Pyramid Visual｜HTML 输出规范

## 默认输出

如果运行环境支持文件读写和 Python：

1. 完成原文分析，记录每个 FAQ 的证据位置、推理、争议、共识核验状态。保持 `references/output-contract.md` 的全部内容要求。
2. 生成 `analysis.json`，必须符合下面的数据契约。
3. 在本 Skill 根目录执行 `python scripts/build_report.py /path/to/analysis.json /path/to/report.html`。
4. 输出报告 HTML 与 JSON 两份正式文件。HTML 可以双击离线运行，默认包含问题金字塔、论证关系、原文溯源、证据面板、搜索及差异过滤。不得在真实报告中保留虚构演示数据。
5. 正式回答只给分析结果的精炼导读以及文件链接，不要重复整份 FAQ。

没有文件写入/运行能力时，输出规范 Markdown，明确说明无法生成 HTML 文件；不得声称自动下载了素材、访问了完整媒体或核验了外部事实。

## JSON 数据契约

顶层格式：

```json
{
  "meta": {
    "title": "内容核心问题/来源标题",
    "summary": "30秒速读：结论及最大盲区",
    "sourceLabel": "来源URL/标题；覆盖范围：完整字幕或节选；外部核验状态"
  },
  "nodes": [
    {
      "id": "Q0", "parent": null, "kind": "root",
      "question": "核心问题？", "answer": "作者归纳结论",
      "argument": "前提 → 机制 → 结论",
      "evidence": ["P01"],
      "type": "作者明确断言 / 综合归纳 / 作者建议 / 未回答",
      "consensus": "已核验共识 / 争议 / 待外部核验",
      "novelty": "差异化 / 一般论点 / 待证实",
      "strength": "原文证据评级，不含模型捏造的分数",
      "limits": "适用边界、反例或尚待澄清之处"
    }
  ],
  "relations": [
    {"from":"Q1.1", "to":"Q1", "type":"support", "label":"支持", "why":"关系的原文依据与推理说明"}
  ],
  "paragraphs": [
    {"id":"P01", "text":"所引用的原文短摘录或忠实转述；需标明章节/段落/时间戳"}
  ]
}
```

### 树结构约束

- `nodes` 里的 `id` 唯一，`parent` 除根节点 `null` 外必须引用存在的 ID。恰好一个根节点。
- 推荐 Q0 → 一级问题 Q1…Qn → 二级问题 Q1.1…；渲染器为三列深度设计。更深层问题需要扁平化为二级展示，并在问题描述中保留原编号，或者升级可视化实现。
- `answer` 简明，`argument` 含前提与推理，`evidence` 通过 ID 关联 `paragraphs`；原文没有证据，空数组即可，不可编造引用。
- `paragraphs[].text` 是保留原位置的合理短摘录/转述，不能未经授权复制整篇长文；缺少素材不要构造虚假的原文。
- `relations[].type` 可用 `support` 支持、`conflict` 反驳/限定、`premise` 前提，`why` 交代证据归属；对未能核验的争议不暗示已得出外部事实结论。
- `consensus` 与 `novelty` 绝不能混合；“作者不同寻常的观点”不自动意味着真的新颖或正确。
- 对大型素材必须先使用 `long-form-workflow.md` 做分片与覆盖审计；图谱可以只显示核心层级，但 JSON 应包含完整重要 FAQ。

## 视觉策略

- **首屏：** 3 条最值得关注的增量卡。差异与不确定性同时可见。
- **中间：** 左侧金字塔，右侧证据检查器；点击节点更新答案、论证、依据、边界及四维标签。
- **关联：** 单独的论证关系视图，避免把树结构与跨层因果边同时画得过于拥挤。
- **溯源：** 可在原文视图中查到被引用的段落/时间戳，不能只显示抽象可信度分数。
- **交互：** 搜索、差异筛选、节点展开、JSON 导入导出；长内容按需钻取。

## 进阶选型（不是内置依赖）

- React Flow（MIT）：用于自定义节点/证据卡及大型交互图谱。
- AntV Infographic（MIT）：用于首页高质量可视化摘要或静态导出。
- Argdown（MIT）：可参考其支持/反驳/前提论证模型。
- Markmap（MIT）：极简 Markdown → 层级思维导图快速路径。

内置模板只使用原生 HTML/CSS/JS 以确保离线打开；不是声称已经使用上述四种库。
