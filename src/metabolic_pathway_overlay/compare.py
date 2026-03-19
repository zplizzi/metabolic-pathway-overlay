#!/usr/bin/env python3
"""
Screenshot comparison tool for pathway viewer.
Takes high-res screenshots of both renderers, then generates
1000x1000 crop comparisons of various regions.

Usage: python compare.py [pathway_name]
  Default: b3_nad
"""

import asyncio
import sys
from pathlib import Path

from PIL import Image
from playwright.async_api import async_playwright

HERE = Path(__file__).parent
OUT_DIR = HERE / "screenshots"


async def screenshot_html_renderer(pw, pathway: str, out_path: Path):
    """High-res screenshot of our custom HTML renderer."""
    browser = await pw.chromium.launch()
    page = await browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=2)
    await page.goto(f"http://127.0.0.1:5555/#{pathway}", wait_until="networkidle")
    await page.wait_for_timeout(1500)

    dims = await page.evaluate("""() => {
        const svg = document.getElementById('pathway');
        return { w: +svg.getAttribute('width'), h: +svg.getAttribute('height') };
    }""")
    w = min(int(dims["w"]) + 60, 8000)
    h = min(int(dims["h"]) + 100, 8000)

    await page.evaluate("""() => {
        document.getElementById('viewer-container').style.overflow = 'visible';
        document.getElementById('viewer-container').style.height = 'auto';
        document.querySelector('.diagram-wrap').style.position = 'relative';
        document.querySelector('.diagram-wrap').style.transform = 'none';
        document.querySelector('.layout').style.height = 'auto';
    }""")
    await page.set_viewport_size({"width": max(w, 1200), "height": max(h, 900)})
    await page.wait_for_timeout(500)

    svg = page.locator("svg#pathway")
    await svg.screenshot(path=str(out_path))
    size = Image.open(out_path).size
    print(f"HTML screenshot: {out_path} ({size[0]}x{size[1]})")
    await browser.close()


async def screenshot_drawio_viewer(pw, pathway: str, out_path: Path):
    """High-res screenshot of the draw.io viewer rendering."""
    browser = await pw.chromium.launch()
    page = await browser.new_page(viewport={"width": 4000, "height": 4000}, device_scale_factor=2)
    await page.goto(
        f"http://127.0.0.1:5555/drawio-viewer?pathway={pathway}",
        wait_until="networkidle",
    )
    await page.wait_for_timeout(5000)
    svg = page.locator(".mxgraph svg").first
    try:
        await svg.wait_for(timeout=10000)
        box = await svg.bounding_box()
        if box:
            vw = max(int(box["width"]) + 40, 4000)
            vh = max(int(box["height"]) + 40, 4000)
            await page.set_viewport_size({"width": min(vw, 8000), "height": min(vh, 8000)})
            await page.wait_for_timeout(2000)
        svg = page.locator(".mxgraph svg").first
        await svg.screenshot(path=str(out_path))
    except Exception:
        await page.screenshot(path=str(out_path))
    size = Image.open(out_path).size
    print(f"draw.io screenshot: {out_path} ({size[0]}x{size[1]})")
    await browser.close()


REGIONS = {
    "tl": (0.0, 0.0, 0.3, 0.3),
    "tc": (0.35, 0.0, 0.65, 0.3),
    "tr": (0.55, 0.0, 0.85, 0.3),
    "cl": (0.0, 0.3, 0.3, 0.6),
    "center": (0.3, 0.3, 0.6, 0.6),
    "cr": (0.55, 0.3, 0.85, 0.6),
    "bl": (0.0, 0.65, 0.3, 0.95),
    "bc": (0.3, 0.65, 0.6, 0.95),
    "br": (0.55, 0.65, 0.85, 0.95),
}


def generate_crops(pathway: str):
    """Crop both full screenshots into 1000x1000 region comparisons."""
    html_path = OUT_DIR / f"{pathway}_html.png"
    drawio_path = OUT_DIR / f"{pathway}_drawio.png"

    html_img = Image.open(html_path)
    drawio_img = Image.open(drawio_path)

    for region_name, (x1f, y1f, x2f, y2f) in REGIONS.items():
        for label, img in [("html", html_img), ("drawio", drawio_img)]:
            w, h = img.size
            box = (int(x1f * w), int(y1f * h), int(x2f * w), int(y2f * h))
            crop = img.crop(box).resize((1000, 1000), Image.LANCZOS)
            out = OUT_DIR / f"{pathway}_{label}_{region_name}.png"
            crop.save(out)

    print(f"Generated {len(REGIONS)} region crops for each renderer")


async def main():
    pathway = sys.argv[1] if len(sys.argv) > 1 else "full_figure_1"
    OUT_DIR.mkdir(exist_ok=True)

    html_out = OUT_DIR / f"{pathway}_html.png"
    drawio_out = OUT_DIR / f"{pathway}_drawio.png"

    async with async_playwright() as pw:
        await screenshot_html_renderer(pw, pathway, html_out)
        await screenshot_drawio_viewer(pw, pathway, drawio_out)

    generate_crops(pathway)
    print(f"\nAll screenshots saved to {OUT_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
