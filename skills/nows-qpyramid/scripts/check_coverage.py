#!/usr/bin/env python3
"""Pre-delivery reverse coverage gate for Question Pyramid.

Checks registries, references, artifacts and reviewer decisions, NOT semantic truth.
Exit 0 only when review claims are complete and source scope is full.
A partial source yields exit 3 (limited); blockers or stale review yield exit 1.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

REQUIRED_CHECKS = (
    'forwardCoverage', 'reverseFidelity', 'evidenceAttribution',
    'priorityAndCompleteness', 'renderedHtml',
)
PRIORITIES = {'core', 'major', 'supporting', 'minor'}
KINDS = {'thesis', 'argument', 'method', 'evidence', 'example', 'condition', 'counterexample', 'limitation', 'result', 'other'}
SCOPES = {'full', 'major_part', 'excerpt'}


def load(path):
    return json.loads(Path(path).read_text('utf-8'))


def checksum(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def nonblank(s):
    return isinstance(s, str) and bool(s.strip())


def html_data(path):
    html = Path(path).read_text('utf-8')
    matches = re.findall(r'<script\s+id=["\']qp-data["\']\s+type=["\']application/json["\']>(.*?)</script>', html, re.S)
    if len(matches) != 1:
        raise ValueError('HTML 必须且只能存在一份 qp-data JSON')
    return json.loads(matches[0])


def references_valid(inventory, analysis):
    errors = []
    segments = inventory.get('segments', [])
    points = inventory.get('keyPoints', [])
    if inventory.get('scope') not in SCOPES:
        errors.append('scope 必须标明 full / major_part / excerpt')
    if not nonblank(inventory.get('sourceLabel')):
        errors.append('缺 sourceLabel')
    if inventory.get('scope') == 'full' and not nonblank(inventory.get('sourceExtent')):
        errors.append('全文核对必须注明实际审阅范围 sourceExtent（如页码/视频起止时间）')
    if inventory.get('scope') != 'full' and not nonblank(inventory.get('scopeNotes')):
        errors.append('非全文材料必须说明无法覆盖的范围 scopeNotes')
    seg_ids = set()
    for seg in segments:
        sid = seg.get('id')
        if not nonblank(sid) or sid in seg_ids or not nonblank(seg.get('locator')):
            errors.append('片段 ID 唯一且需包含原文定位 locator')
        seg_ids.add(sid)
    if not segments:
        errors.append('原文覆盖片段 segments 为空')
    nodeids = {n.get('id'): n for n in analysis.get('nodes', [])}
    gapids = {g.get('id'): g for g in analysis.get('criticalGaps', [])}
    evids = {p.get('id'): p for p in analysis.get('paragraphs', [])}
    insight_count = len(analysis.get('insights', []))
    pointids = set()
    for p in points:
        pid = p.get('id')
        if not nonblank(pid) or pid in pointids:
            errors.append('原文要点 ID 缺失或重复'); continue
        pointids.add(pid)
        if p.get('priority') not in PRIORITIES or p.get('kind') not in KINDS or not nonblank(p.get('claim')):
            errors.append(f'{pid}: priority/kind/claim 无效')
        segrefs = p.get('segmentIds', [])
        if not isinstance(segrefs, list) or not segrefs or any(i not in seg_ids for i in segrefs):
            errors.append(f'{pid}: segmentIds 应指向已登记的原始片段')
        if p.get('disposition') not in {'included', 'omitted'}:
            errors.append(f'{pid}: 必须登记 included 或 omitted')
        mappings = p.get('reportRefs', [])
        if not isinstance(mappings, list):
            errors.append(f'{pid}: reportRefs 必须是列表'); mappings = []
        content_mappings = 0
        for ref in mappings:
            typ, rid = ref.get('type'), ref.get('id')
            if typ == 'node' and rid in nodeids:
                content_mappings += 1 if nonblank(nodeids[rid].get('answer')) else 0
            elif typ == 'insight' and isinstance(rid, int) and 0 <= rid < insight_count:
                content_mappings += 1
            elif typ == 'gap' and rid in gapids:
                content_mappings += 1
            elif typ == 'meta' and rid in {'contentRetelling', 'display.thesisHighlight', 'display.heroIntro', 'summary'}:
                content_mappings += 1
            elif typ == 'evidence' and rid in evids:
                pass  # Source snippets alone are never coverage.
            else:
                errors.append(f'{pid}: reportRefs 引用了不存在的 {typ}/{rid}')
        if p.get('priority') in {'core','major'} and p.get('disposition') != 'included':
            errors.append(f'{pid}: 核心/重大要点不可标为遗漏后直接交付')
        if p.get('disposition') == 'included' and content_mappings == 0:
            errors.append(f'{pid}: 未映射到可见的答案/主张/洞见等（仅挂证据不算覆盖）')
        if p.get('disposition') == 'omitted' and not nonblank(p.get('omitReason')):
            errors.append(f'{pid}: 有意省略需有具体理由')
    if not points:
        errors.append('keyPoints 不能为空')
    visited_segments = {sid for p in points for sid in p.get('segmentIds', [])}
    for seg in segments:
        if seg.get('id') not in visited_segments and not nonblank(seg.get('exclusionReason')):
            errors.append(f"原文片段 {seg.get('id')} 无要点且未说明为何可略过")
    return errors, pointids



def expected_claims(analysis):
    """Every authored conclusion in the HTML needs reverse source checking."""
    nodes = {n['id']: n for n in analysis.get('nodes', [])}
    claims = {}
    def add(ref, anchors=(), attribution='author'):
        claims[ref] = {'claimRef': ref, 'verdict': 'pending',
                       'sourceIds': sorted(set(anchors)), 'attribution': attribution, 'reason': ''}
    all_evidence = [eid for n in nodes.values() for eid in n.get('evidence', [])]
    for ref in ('meta:summary', 'meta:display.thesisHighlight', 'meta:contentRetelling'):
        add(ref, all_evidence)
    for n in nodes.values():
        add('node:' + n['id'], n.get('evidence', []))
    for index, item in enumerate(analysis.get('insights', [])):
        ids = [eid for nid in item.get('relatedNodes', []) for eid in nodes.get(nid, {}).get('evidence', [])]
        add(f'insight:{index}', ids)
    for index, p in enumerate(analysis['meta']['display'].get('principles', [])):
        add(f'principle:{index}', nodes.get(p.get('relatedNode'), {}).get('evidence', []))
    for index, rel in enumerate(analysis.get('relations', [])):
        ids = nodes.get(rel.get('from'), {}).get('evidence', []) + nodes.get(rel.get('to'), {}).get('evidence', [])
        add(f'relation:{index}', ids)
    for gap in analysis.get('criticalGaps', []):
        ids = gap.get('evidence', []) + [eid for nid in gap.get('relatedNodes', []) for eid in nodes.get(nid, {}).get('evidence', [])]
        add('gap:' + gap['id'], ids, 'analyst' if gap.get('origin') == 'reader_inferred' else 'author')
    return claims


def template(inventory_path, analysis_path, html_path, output_path):
    inventory, analysis = load(inventory_path), load(analysis_path)
    errors, _ = references_valid(inventory, analysis)
    if errors:
        raise ValueError('台账未通过结构预检:\n- ' + '\n- '.join(errors))
    if html_data(html_path) != analysis:
        raise ValueError('HTML 内部数据不是本轮 analysis.json，请先重新生成 HTML')
    result = {
        'inventorySha256': checksum(inventory_path),
        'htmlSha256': checksum(html_path),
        'reviewBasis': 'pending',
        'reviewSummary': '待对照原文与最终渲染 HTML 填写。不得预先全部标 pass。',
        'claimChecks': list(expected_claims(analysis).values()),
        'items': [
            {'id': p['id'], 'verdict': 'pending', 'reason': ''}
            for p in inventory['keyPoints']
        ],
        'checks': {name: {'status': 'pending', 'reason': ''} for name in REQUIRED_CHECKS},
        'findings': [],
    }
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(f'已生成待审计文件: {output_path}；请实地核对原文和 HTML 后填写，不能直接交付。')


def verify(inventory_path, analysis_path, html_path, review_path):
    inventory, analysis, review = load(inventory_path), load(analysis_path), load(review_path)
    errors, points = references_valid(inventory, analysis)
    if html_data(html_path) != analysis:
        errors.append('HTML 嵌入的内容与本轮 analysis.json 不一致')
    if review.get('inventorySha256') != checksum(inventory_path):
        errors.append('原文台账已更改，原审核失效，请重新 prepare')
    if review.get('htmlSha256') != checksum(html_path):
        errors.append('HTML 已重新生成/更改，原审核失效，请重新 prepare 并复查')
    if review.get('reviewBasis') not in {'original_source', 'source_excerpts', 'secondary_summary'}:
        errors.append('reviewBasis 无效或待审核')
    if not nonblank(review.get('reviewSummary')) or review['reviewSummary'].startswith('待对照'):
        errors.append('reviewSummary 未写实际审查发现')
    items = review.get('items', [])
    itemids = set()
    for it in items:
        pid = it.get('id')
        if pid in itemids:
            errors.append(f'重复审核条目 {pid}')
        itemids.add(pid)
        if pid not in points:
            errors.append(f'审核条目未知 {pid}')
        if it.get('verdict') not in {'pass', 'fix_needed', 'unverifiable'} or not nonblank(it.get('reason')):
            errors.append(f'{pid}: 未做具体的语义核对或未填理由')
        if it.get('verdict') in {'fix_needed', 'unverifiable'}:
            errors.append(f'{pid}: 仍有待修复或无法确认的原文要点')
    if itemids != points:
        errors.append(f'未逐项核对全部要点，缺 {sorted(points - itemids)}')
    expected = expected_claims(analysis)
    claim_checks = review.get('claimChecks', [])
    checked_refs = set()
    evidence_ids = {x['id'] for x in analysis.get('paragraphs', [])}
    for c in claim_checks:
        cref = c.get('claimRef')
        if cref in checked_refs:
            errors.append(f'重复反向审核结论: {cref}')
        checked_refs.add(cref)
        if cref not in expected:
            errors.append(f'未知反向审核结论: {cref}')
        if c.get('verdict') != 'pass' or not nonblank(c.get('reason')):
            errors.append(f'{cref}: 未完成基于原文的反向忠实性复核')
        if c.get('attribution') not in {'author', 'analyst', 'mixed'}:
            errors.append(f'{cref}: 未区分作者主张与分析者推断')
        anchors = c.get('sourceIds')
        if not isinstance(anchors, list) or any(i not in evidence_ids for i in anchors):
            errors.append(f'{cref}: 来源锚点无效')
        elif c.get('attribution') == 'author' and not anchors:
            errors.append(f'{cref}: 作者主张没有任何原文证据锚点')
    if checked_refs != set(expected):
        errors.append(f'部分 HTML 结论未反向核对: {sorted(set(expected) - checked_refs)}')
    checks = review.get('checks', {})
    for name in REQUIRED_CHECKS:
        c = checks.get(name, {})
        if c.get('status') != 'pass' or not nonblank(c.get('reason')):
            errors.append(f'{name}: 未通过复审（或缺少具体说明）')
    for finding in review.get('findings', []):
        if finding.get('status') != 'fixed' and finding.get('severity') in {'blocking','major'}:
            errors.append(f'还有未修复的重要发现: {finding.get("id", "?")}')
    if inventory.get('scope') != 'full':
        print('LIMITED: 已读范围仅为', inventory.get('scope'), '，不能宣称完成全文反向核对。')
        for e in errors:
            print(' -', e)
        return 3 if not errors else 1
    if review.get('reviewBasis') != 'original_source':
        errors.append('全文核对必须实际重新审阅原始材料，而非仅复核旧摘要/摘录')
    if errors:
        print('FAIL: 反向核对尚未完成：')
        for e in errors:
            print(' -', e)
        return 1
    print('PASS: 结构引用、台账覆盖登记、审核结论与本版 HTML 一致。')
    print('注意：语义正确性依赖实际复核记录，程序无法单独证明无遗漏。')
    return 0


def main():
    if len(sys.argv) != 6 or sys.argv[1] not in {'prepare','verify'}:
        print('用法: python scripts/check_coverage.py prepare|verify source-inventory.json analysis.json report.html audit-review.json')
        return 2
    mode, inv, data, html, review = sys.argv[1:]
    try:
        if mode == 'prepare':
            template(inv, data, html, review); return 0
        return verify(inv, data, html, review)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print('ERROR:', exc)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
