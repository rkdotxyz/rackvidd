"""Inline the data, the router and the map base into one self-contained index.html.

    python3 scripts/build.py
"""
from pathlib import Path

root = Path(__file__).resolve().parent.parent
page = (root / 'src/app.html').read_text(encoding='utf-8')
page = (page
        .replace('/*@@DATA@@*/', (root / 'data/stockholm.js').read_text(encoding='utf-8'))
        .replace('/*@@ENGINE@@*/', (root / 'src/engine.js').read_text(encoding='utf-8'))
        .replace('/*@@BASE@@*/', (root / 'src/base.js').read_text(encoding='utf-8')))
(root / 'index.html').write_text(page, encoding='utf-8')
print(f'index.html  {len(page) / 1e6:.2f} MB')
