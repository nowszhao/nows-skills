#!/usr/bin/env python3
"""Build a Question Pyramid standalone HTML report from a validated JSON analysis.

No external JavaScript, CSS, or network dependency is required to open the result.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

MARKER = '<script id="qp-data" type="application/json">{}</script>'
STATUS = {'full', 'partial', 'assertion', 'unanswered', 'contradiction', 'unaudited'}
PRIORITY = {'critical', 'high', 'medium', 'low'}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def check_list(value, label):
    if not isinstance(value, list):
        raise ValueError(f'{label} 必须是列表')
    return value


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('顶层必须是 JSON 对象')
    meta = data.get('meta')
    if not isinstance(meta, dict):
        raise ValueError('meta 必须是对象')
    for field in ('title', 'summary', 'analysisBasis', 'contentScope', 'sourceLabel'):
        if not nonempty(meta.get(field)):
            raise ValueError(f'meta.{field} 必须说明真实且具体的材料范围或内容')
    recap = meta.get('contentRetelling')
    if not nonempty(recap):
        raise ValueError('meta.contentRetelling 必须提供约 300 字、基于原文且突出内容重点的连贯中文复述')
    han_count = len(re.findall(r'[\u4e00-\u9fff]', recap))
    if not 280 <= han_count <= 320:
        raise ValueError(f'meta.contentRetelling 需约 300 个汉字，当前 {han_count} 个；请控制在 280–320 个汉字')
    if '\n\n' in recap:
        raise ValueError('内容复述必须是自然连续段落，不是列表或分节')
    disp = meta.get('display')
    if not isinstance(disp, dict):
        raise ValueError('meta.display 必须包含对应当前材料的首页显示文案')
    for field in ('heroLead', 'heroIntro', 'thesisLead', 'thesisHighlight', 'thesisCaveat'):
        if not nonempty(disp.get(field)):
            raise ValueError(f'meta.display.{field} 必须由本篇内容生成；不能使用示例作者的固定文案')
    nodes = check_list(data.get('nodes'), 'nodes')
    if not nodes:
        raise ValueError('nodes 不能为空')
    ids = set()
    for n in nodes:
        if not isinstance(n, dict) or not nonempty(n.get('id')) or n['id'] in ids:
            raise ValueError('nodes 的 id 必须唯一且非空')
        i = n['id']; ids.add(i)
        if not nonempty(n.get('question')):
            raise ValueError(f'{i} 缺 question')
        if n.get('answerStatus') not in STATUS:
            raise ValueError(f'{i} 的 answerStatus 非法或缺失')
        if not isinstance(n.get('answer'), str):
            raise ValueError(f'{i} 的 answer 应为字符串（找不到时请注明材料范围）')
        if not isinstance(n.get('argument', ''), str):
            raise ValueError(f'{i} 的 argument 应为字符串')
        check_list(n.get('evidence', []), f'{i}.evidence')
    roots = [x for x in nodes if x.get('parent') is None]
    if len(roots) != 1:
        raise ValueError('必须恰好有一个根问题')
    parents = {x['id']: x.get('parent') for x in nodes}
    for nid in ids:
        visited = set()
        cursor = nid
        while cursor is not None:
            if cursor in visited:
                raise ValueError('节点树有环：' + nid)
            if cursor not in parents:
                raise ValueError('父节点不存在：' + cursor)
            visited.add(cursor)
            cursor = parents[cursor]
    # This renderer supports an explicit three-level layout (root / branch / question).
    rootid = roots[0]['id']
    for n in nodes:
        pid = n.get('parent')
        if pid is not None and pid != rootid and parents[pid] != rootid:
            raise ValueError(f'{n["id"]} 的树深度超过 3 层；请将更细的追问合并为第三层节点，或修改渲染器')
    principles = check_list(disp.get('principles'), 'meta.display.principles')
    if not 1 <= len(principles) <= 6:
        raise ValueError('作者主张下的实践要点需要 1–6 条，不能固定套用样例内容')
    for p in principles:
        if not isinstance(p, dict) or any(not nonempty(p.get(f)) for f in ('title', 'description', 'relatedNode')):
            raise ValueError('princples 每项需有 title、description、relatedNode')
        if p['relatedNode'] not in ids:
            raise ValueError('实践要点引用不存在的节点：' + p['relatedNode'])
    gaps = check_list(data.get('criticalGaps'), 'criticalGaps')
    if not gaps and not nonempty(meta.get('gapAuditConclusion')):
        raise ValueError('没有关键追问时必须说明审查范围及原因 meta.gapAuditConclusion')
    gap_ids = set()
    for g in gaps:
        if not isinstance(g, dict) or not nonempty(g.get('id')) or g['id'] in gap_ids:
            raise ValueError('关键追问 ID 无效或重复')
        gap_ids.add(g['id'])
        for field in ('question', 'sourceProvides', 'impact', 'basis'):
            if not nonempty(g.get(field)):
                raise ValueError(f'{g["id"]} 缺少 {field}')
        for field in ('missing', 'sufficiencyCriteria', 'evidence', 'relatedNodes'):
            check_list(g.get(field), f'{g["id"]}.{field}')
        if g.get('priority') not in PRIORITY or g.get('answerStatus') not in STATUS:
            raise ValueError(f'{g["id"]} 的优先级或回答状态错误')
        if g.get('origin') not in {'reader_inferred', 'source_explicit'}:
            raise ValueError(f'{g["id"]} 须区分原文问题和读者追问')
        for nid in g['relatedNodes']:
            if nid not in ids:
                raise ValueError(f'{g["id"]} 引用了未知节点 {nid}')
    pars = check_list(data.get('paragraphs'), 'paragraphs')
    pids = [x.get('id') if isinstance(x, dict) else None for x in pars]
    if any(not nonempty(x) for x in pids) or len(pids) != len(set(pids)):
        raise ValueError('paragraphs 中的依据 ID 重复或无效')
    source_ids = set(pids)
    for p in pars:
        if not nonempty(p.get('text')):
            raise ValueError('每条证据必须有可定位的摘录或忠实转述')
    for obj in [*nodes, *gaps]:
        for eid in obj.get('evidence', []):
            if eid not in source_ids:
                raise ValueError(f'{obj["id"]} 引用了未知依据 {eid}')
    relations = check_list(data.get('relations'), 'relations')
    for edge in relations:
        if not isinstance(edge, dict) or edge.get('from') not in ids or edge.get('to') not in ids:
            raise ValueError('论证关系引用了未知节点')
    insights = check_list(data.get('insights'), 'insights')
    for ins in insights:
        if not isinstance(ins, dict) or any(not nonempty(ins.get(f)) for f in ('claim', 'whyItMatters', 'whyDifferent', 'certainty')):
            raise ValueError('认知增量必须有观点、价值、不同之处和证据/核验状态')
        for nid in check_list(ins.get('relatedNodes'), 'insight.relatedNodes'):
            if nid not in ids:
                raise ValueError('认知增量关联了不存在的问题节点')
    return len(nodes), len(insights), len(gaps), len(pars)


def build(input_json: Path, output_html: Path):
    data = json.loads(input_json.read_text('utf-8'))
    counts = validate(data)
    template = (Path(__file__).resolve().parent.parent / 'assets' / 'renderer.html').read_text('utf-8')
    if template.count(MARKER) != 1:
        raise RuntimeError('模板 JSON 注入标记不存在或出现多次')
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    escaped = raw.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    output = template.replace(MARKER, '<script id="qp-data" type="application/json">'+escaped+'</script>')
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(output, 'utf-8')
    print(f'Created {output_html}\n  questions={counts[0]}, insights={counts[1]}, open_questions={counts[2]}, sources={counts[3]}')

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python scripts/build_report.py analysis.json report.html')
        raise SystemExit(2)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
