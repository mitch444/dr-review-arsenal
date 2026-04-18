#!/usr/bin/env python3
"""One-shot patcher: inject GA4 tracking into already-built HTML files.

Adds the gtag snippet to <head> on every page, sets window.REP_NAME on rep
pages, and makes sure index.html pulls in assets/app.js.
"""
import json
import re
from pathlib import Path

GA_TRACKING_ID = "G-118XBY0BED"
ROOT = Path(__file__).resolve().parent


def ga_head_html(rep_name: str | None = None, asset_prefix: str = "") -> str:
    rep_block = ""
    if rep_name:
        rep_js = json.dumps(rep_name)
        rep_block = (
            f"\n    gtag('set', {{'rep_name': {rep_js}}});"
            f"\n    window.REP_NAME = {rep_js};"
        )
    return (
        f"<!-- Google tag (gtag.js) -->\n"
        f'  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_TRACKING_ID}"></script>\n'
        f"  <script>\n"
        f"    window.dataLayer = window.dataLayer || [];\n"
        f"    function gtag(){{dataLayer.push(arguments);}}\n"
        f"    gtag('js', new Date());\n"
        f"    gtag('config', '{GA_TRACKING_ID}');{rep_block}\n"
        f"  </script>"
    )


def patch_file(path: Path, rep_name: str | None, app_js_path: str, is_index: bool):
    html = path.read_text(encoding="utf-8")
    original = html

    # Skip if GA already injected
    if GA_TRACKING_ID in html:
        print(f"  SKIP (already patched): {path.relative_to(ROOT)}")
        return False

    snippet = ga_head_html(rep_name)

    # Inject after the stylesheet <link>
    link_pattern = re.compile(r'(<link\s+rel="stylesheet"\s+href="[^"]+">)')
    m = link_pattern.search(html)
    if not m:
        print(f"  WARN no stylesheet link in {path.relative_to(ROOT)}; injecting before </head>")
        html = html.replace("</head>", f"  {snippet}\n</head>", 1)
    else:
        html = html[:m.end()] + "\n  " + snippet + html[m.end():]

    # Make sure index.html loads app.js so copy-tracking fires on rep-card clicks
    if is_index and 'assets/app.js' not in html:
        html = html.replace(
            "</body>",
            f'  <script src="{app_js_path}"></script>\n</body>',
            1,
        )

    if html != original:
        path.write_text(html, encoding="utf-8")
        print(f"  PATCHED: {path.relative_to(ROOT)}")
        return True
    return False


def extract_rep_name(html: str) -> str | None:
    m = re.search(r'<h1 class="rep-hero-name">([^<]+)</h1>', html)
    return m.group(1).strip() if m else None


def main():
    patched = 0

    # 1) index.html
    idx = ROOT / "index.html"
    if idx.exists():
        if patch_file(idx, rep_name=None, app_js_path="assets/app.js", is_index=True):
            patched += 1

    # 2) reps/*.html
    for rep_file in sorted((ROOT / "reps").glob("*.html")):
        rep_name = extract_rep_name(rep_file.read_text(encoding="utf-8"))
        if patch_file(rep_file, rep_name=rep_name, app_js_path="../assets/app.js", is_index=False):
            patched += 1

    print(f"\nDone. Patched {patched} file(s).")


if __name__ == "__main__":
    main()
