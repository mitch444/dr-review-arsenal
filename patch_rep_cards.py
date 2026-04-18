#!/usr/bin/env python3
"""Patcher — refactor every rep card in index.html to include a
"Build your customer page" CTA with a pre-filled form URL.

Run once after pulling the latest master CSV-driven rebuild is impractical
(e.g. from a laptop with no access to the source data). Safe to re-run:
it's idempotent. Skips cards that already have the CTA.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
STYLES = ROOT / "assets" / "styles.css"
APP_JS = ROOT / "assets" / "app.js"

SITE_URL = "https://mitch444.github.io/dr-review-arsenal"


# ── 1. index.html — refactor rep cards ─────────────────────────────────────
REP_CARD_RE = re.compile(
    r'<a class="rep-card" href="reps/([a-z0-9-]+)\.html">\s*'
    r'<div class="rep-avatar(?: rep-avatar-photo)?"[^>]*></div>\s*'
    r'<div class="rep-name">([^<]+)</div>\s*'
    r'<div class="rep-meta">\s*'
    r'<span class="rep-stars">([★]+)</span>\s*'
    r'(\d+) reviews · ([\d.]+)★\s*'
    r'</div>\s*'
    r'</a>',
    re.MULTILINE,
)


def build_card(slug: str, name: str, stars: str, count: str, avg: str) -> str:
    photo_path = ROOT / "assets" / "photos" / f"{slug}.jpg"
    if photo_path.exists():
        avatar = (
            f'<div class="rep-avatar rep-avatar-photo" '
            f"style=\"background-image:url('assets/photos/{slug}.jpg')\"></div>"
        )
        photo_full = f"{SITE_URL}/assets/photos/{slug}.jpg"
    else:
        initials = "".join(p[0] for p in name.split()[:2]).upper()
        avatar = f'<div class="rep-avatar">{initials}</div>'
        photo_full = ""

    params = urlencode({
        "name": name,
        "slug": slug,
        "title": "Sales Consultant",
        "reviews": count,
        "rating": avg,
        "photo": photo_full,
    })
    form_url = f"form.html?{params}"

    return (
        f'<div class="rep-card">\n'
        f'        <a class="rep-card-main" href="reps/{slug}.html">\n'
        f'          {avatar}\n'
        f'          <div class="rep-name">{name}</div>\n'
        f'          <div class="rep-meta">\n'
        f'            <span class="rep-stars">{stars}</span>\n'
        f'            {count} reviews · {avg}★\n'
        f'          </div>\n'
        f'        </a>\n'
        f'        <a class="rep-card-cta" href="{form_url}" target="_blank" rel="noopener"\n'
        f'           data-rep="{name}">\n'
        f'          <span class="cta-label">Build your customer page</span>\n'
        f'          <span class="cta-arrow">→</span>\n'
        f'        </a>\n'
        f'      </div>'
    )


def patch_index():
    html = INDEX.read_text(encoding="utf-8")
    if 'class="rep-card-main"' in html:
        print(f"  SKIP index.html (already patched)")
        return False

    def repl(m):
        slug, name, stars, count, avg = m.groups()
        return build_card(slug, name, stars, count, avg)

    new_html, n = REP_CARD_RE.subn(repl, html)
    if n == 0:
        print(f"  WARN no rep-cards matched in index.html — pattern may have drifted")
        return False
    INDEX.write_text(new_html, encoding="utf-8")
    print(f"  PATCHED index.html — {n} rep cards updated")
    return True


# ── 2. styles.css — append new CTA styles ──────────────────────────────────
NEW_CSS = """
/* --- Rep card CTA (intake form link) --- */
.rep-card {
  padding: 0 !important;
  overflow: hidden;
  display: flex !important;
  flex-direction: column;
}
.rep-card-main {
  display: block; color: inherit; padding: 20px 20px 16px;
  flex: 1;
}
.rep-card-main:hover { text-decoration: none; }
.rep-card-cta {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 20px; background: #f3f6fa;
  border-top: 1px solid var(--border);
  font-size: 12.5px; font-weight: 600;
  color: var(--primary); letter-spacing: .01em;
  transition: background .12s ease, color .12s ease;
  text-decoration: none;
}
.rep-card-cta:hover { background: var(--primary); color: #fff; text-decoration: none; }
.rep-card-cta .cta-label { display: flex; align-items: center; gap: 7px; }
.rep-card-cta .cta-label::before { content: "✎"; font-size: 14px; opacity: .85; }
.rep-card-cta .cta-arrow { font-weight: 700; }
.rep-card-cta.done { background: #ecfdf5; color: #065f46; }
.rep-card-cta.done:hover { background: #065f46; color: #fff; }
.rep-card-cta.done .cta-label::before { content: "✓"; }
"""


def patch_css():
    css = STYLES.read_text(encoding="utf-8")
    if ".rep-card-main" in css:
        print(f"  SKIP styles.css (already patched)")
        return False
    STYLES.write_text(css.rstrip() + "\n" + NEW_CSS, encoding="utf-8")
    print(f"  PATCHED styles.css")
    return True


# ── 3. app.js — update click handlers ──────────────────────────────────────
OLD_APP_JS_BLOCK = """    // Rep cards on index page
    var card = e.target.closest("a.rep-card");
    if (card) {
      var nameEl = card.querySelector(".rep-name");
      var rn = nameEl ? nameEl.textContent.trim() : null;
      if (rn) track("rep_card_click", { rep_name: rn });
    }"""

NEW_APP_JS_BLOCK = """    // Rep cards on index page — main link
    var cardMain = e.target.closest("a.rep-card-main");
    if (cardMain) {
      var nameEl = cardMain.querySelector(".rep-name");
      var rn = nameEl ? nameEl.textContent.trim() : null;
      if (rn) track("rep_card_click", { rep_name: rn });
      return;
    }
    // Rep cards — "Build your customer page" CTA
    var ctaBtn = e.target.closest("a.rep-card-cta");
    if (ctaBtn) {
      var rep = ctaBtn.getAttribute("data-rep") || null;
      track("intake_form_open", { rep_name: rep });
      return;
    }"""


def patch_app_js():
    js = APP_JS.read_text(encoding="utf-8")
    if "intake_form_open" in js:
        print(f"  SKIP app.js (already patched)")
        return False
    if OLD_APP_JS_BLOCK not in js:
        print(f"  WARN old app.js block not found — manual check needed")
        return False
    js = js.replace(OLD_APP_JS_BLOCK, NEW_APP_JS_BLOCK)
    APP_JS.write_text(js, encoding="utf-8")
    print(f"  PATCHED app.js")
    return True


def main():
    print("Patching DR Review Arsenal site → add microsite CTAs")
    ok_idx = patch_index()
    ok_css = patch_css()
    ok_js  = patch_app_js()
    if ok_idx or ok_css or ok_js:
        print("\nDone. Commit and push to deploy:")
        print('  git add index.html assets/styles.css assets/app.js form.html patch_rep_cards.py')
        print('  git commit -m "Add rep microsite intake CTA"')
        print('  git push')
    else:
        print("\nNothing changed (already patched).")


if __name__ == "__main__":
    main()
