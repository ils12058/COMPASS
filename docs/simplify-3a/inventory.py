#!/usr/bin/env python3
"""Inventory page entry points and shared UI imports; not a substitute for an audit."""
import csv
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
app = root / 'fe/src/app'
src = root / 'fe/src'
out = Path(__file__).resolve().parent
imports = re.compile(r'from\s+[\'"](@/[^\'"]+)[\'"]')

def resolve(spec):
    base = src / spec.removeprefix('@/')
    return next((p for p in (base.with_suffix('.tsx'), base.with_suffix('.ts'), base / 'index.tsx', base / 'index.ts') if p.is_file()), None)

def relative(path):
    return path.relative_to(root).as_posix()

def route(path):
    parts = path.relative_to(app).parts[:-1]
    return '/' + '/'.join(p for p in parts if not (p.startswith('(') and p.endswith(')')) and not p.startswith('@'))

def workspace(path):
    parts = path.relative_to(app).parts
    return next((p[1:-1] for p in parts if p.startswith('(') and p.endswith(')')), 'root')

pages = sorted(app.rglob('page.tsx'))
with (out / 'routes.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['route', 'entry_file', 'workspace', 'direct_feature_modules', 'entry_layout_hint', 'direct_ui_imports', 'roles_and_capabilities', 'primary_task', 'states', 'visual_evidence', 'disposition'])
    for page in pages:
        text = page.read_text()
        specs = imports.findall(text)
        features = sorted(s for s in specs if s.startswith('@/features/'))
        ui = sorted(s for s in specs if s.startswith('@/components/ui/'))
        layout = 'redirect' if re.search(r'\bredirect\(', text) else ('pageSheetWidth' if 'pageSheetWidth' in text else 'inspect feature/layout')
        writer.writerow([route(page), relative(page), workspace(page), '; '.join(features), layout, '; '.join(ui), 'not assessed', 'not assessed', 'not assessed', 'not assessed', 'pending audit'])

ui_files = sorted((src / 'components/ui').glob('*'))
source_files = list(src.rglob('*.ts')) + list(src.rglob('*.tsx'))
consumers = {}
for source in source_files:
    for spec in set(imports.findall(source.read_text())):
        target = resolve(spec)
        if target and target.parent == src / 'components/ui':
            consumers.setdefault(target, []).append(relative(source))
with (out / 'components.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, lineterminator='\n')
    writer.writerow(['shared_ui_file', 'direct_consumer_count', 'direct_consumers', 'audit_disposition'])
    for ui in ui_files:
        if ui.suffix not in ('.ts', '.tsx'): continue
        uses = sorted(consumers.get(ui, []))
        writer.writerow([relative(ui), len(uses), '; '.join(uses), 'pending audit'])
print(f'{len(pages)} page entries; {sum(p.suffix in (".ts", ".tsx") for p in ui_files)} shared UI files')
