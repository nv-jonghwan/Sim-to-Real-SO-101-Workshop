#!/usr/bin/env python3
"""Extract from both English audiences, or check Korean catalog integrity."""
import argparse
from collections import Counter
import json
from pathlib import Path
import pickle
import re
from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po
ROOT = Path(__file__).resolve().parents[3]
LOCALE = ROOT / 'docs/locale/ko/LC_MESSAGES'

def code(text):
    return Counter(re.findall(r'(?<![}`])`([^`]+)`', text))

def links(text):
    return Counter(re.findall(r'\]\(([^)]+)\)', text))

def extract():
    from docutils import nodes
    from sphinx.util.nodes import extract_messages
    catalogs = {}
    for audience in ('learner', 'event', 'instructor'):
        folder = ROOT / 'docs/_build' / audience / 'doctrees'
        if not (folder / 'index.doctree').is_file():
            raise SystemExit('First run build.sh all en')
        for path in folder.glob('*.doctree'):
            # Trusted, locally generated Sphinx artifacts only.
            tree = pickle.loads(path.read_bytes())
            catalog = catalogs.setdefault(path.stem, Catalog(project='SO-101 Sim-to-Real Workshop'))
            for node in tree.findall(nodes.TextElement):
                if node.source or not node.rawsource:
                    continue
                parent = node.parent
                while parent is not None and not parent.source:
                    parent = parent.parent
                if parent is not None:
                    node.source, node.line = parent.source, parent.line
            for node, message in extract_messages(tree):
                # Duplicate implicit headings can include docutils diagnostic children.
                if '(INFO/1) Duplicate implicit target name:' in message:
                    continue
                catalog.add(message, locations=[(str(Path(node.source).relative_to(ROOT)), node.line or 0)])
    output = ROOT / '.local/i18n/messages'
    output.mkdir(parents=True, exist_ok=True)
    for name, catalog in catalogs.items():
        with (output / (name + '.pot')).open('wb') as stream:
            write_po(stream, catalog, width=100)
    print(json.dumps({'catalogs':len(catalogs), 'messages':sum(len(c) for c in catalogs.values()), 'output':str(output)}))

def check():
    errors, total, korean, retained = [], 0, 0, 0
    for path in sorted(LOCALE.glob('*.po')):
        with path.open(encoding='utf-8') as stream:
            catalog = read_po(stream)
        for message in catalog:
            if not message.id:
                continue
            total += 1
            source, target = message.id, message.string
            if not target or 'fuzzy' in message.flags:
                errors.append(f'{path.name}: missing/fuzzy: {source[:80]}')
                continue
            if code(source) != code(target):
                errors.append(f'{path.name}: inline code changed: {source[:80]}')
            if links(source) != links(target):
                errors.append(f'{path.name}: link destination changed: {source[:80]}')
            korean += bool(re.search('[가-힣]', target))
            retained += source == target
    if not total:
        errors.append('No Korean catalogs found')
    print(json.dumps({'messages':total, 'with_korean':korean, 'retained_original':retained, 'errors':errors}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['extract', 'check'])
    args = parser.parse_args()
    globals()[args.action]()
