"""Render every SVG in a folder to a transparent PNG (600 px wide) with Chromium. Usage: python tools/render_svgs.py <dir>"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

d = Path(sys.argv[1])
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 600, "height": 638}, device_scale_factor=1)
    for f in sorted(d.glob("*.svg")):
        svg = f.read_text().replace('width="320" height="340"', 'width="600" height="638"')
        pg.set_content(f'<body style="margin:0;background:transparent">{svg}</body>')
        pg.wait_for_timeout(100)
        pg.screenshot(path=str(f.with_suffix(".png")), omit_background=True)
    b.close()
