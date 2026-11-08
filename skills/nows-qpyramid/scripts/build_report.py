#!/usr/bin/env python3
"""将 Question Pyramid JSON 嵌入无依赖的 HTML 模板，生成可离线打开的报告。"""
import json
import sys
from pathlib import Path

MARKER = '<script id="qp-data" type="application/json">{}</script>'

def build(data_path: Path, output_path: Path):
    data = json.loads(data_path.read_text(encoding="utf-8"))
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("分析数据必须包含非空 nodes 列表")
    ids = [n.get("id") for n in nodes]
    if len(ids) != len(set(ids)) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("节点 id 必须是非空、不重复的字符串")
    if len([n for n in nodes if n.get("parent") is None]) != 1:
        raise ValueError("必须恰好有一个根节点（parent=null）")
    for n in nodes:
        if not isinstance(n.get("question"), str):
            raise ValueError("节点 question 必须是字符串")
        if n.get("parent") is not None and n["parent"] not in ids:
            raise ValueError(f'父节点缺失: {n["parent"]}')
        if not isinstance(n.get('evidence', []), list):
            raise ValueError("节点 evidence 必须是引用 ID 列表")
    for key in ('paragraphs','relations'):
        if not isinstance(data.get(key, []), list):
            raise ValueError(f'{key} 必须是列表')
    template = (Path(__file__).resolve().parent.parent / 'assets' / 'renderer.html').read_text(encoding='utf-8')
    if template.count(MARKER) != 1:
        raise RuntimeError('模板里未找到唯一数据注入位置')
    # JSON 作为 script type=application/json 的内容，防止意外闭合 HTML script 元素。
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    html = template.replace(MARKER, '<script id="qp-data" type="application/json">' + payload + '</script>')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')
    print('Generated:', output_path)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python scripts/build_report.py analysis.json report.html')
        raise SystemExit(2)
    build(Path(sys.argv[1]), Path(sys.argv[2]))
