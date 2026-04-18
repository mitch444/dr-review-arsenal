#!/usr/bin/env python3
"""Patcher — refactor every rep card in index.html.

Idempotent, re-runnable. Two conversion passes run on every invocation:

  1. UNPATCHED → PENDING: converts original `<a class="rep-card">` cards into
     the new `<div class="rep-card">` structure.

  2. PATCHED card resync: for each card, check whether `team/{slug}.html`
     exists and render in the correct mode:

        PENDING (page not yet live)
          - greyed-out "Not live" pill button top-right (visual placeholder)
          - footer CTA "Build your customer page" → intake form

        LIVE (page exists)
          - active emerald "View page" pill button top-right → microsite
          - footer CTA removed

CSS (styles.css) and JS (app.js) blocks are appended once; also idempotent.

Workflow when a rep goes live:
  1. Drop `team/{slug}.html` into the repo.
  2. Run `python patch_rep_cards.py`.
  3. git add -A && git commit -m "..." && git push.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
STYLES = ROOT / "assets" / "styles.css"
APP_JS = ROOT / "assets" / "app.js"
TEAM_DIR = ROOT / "team"

SITE_URL = "https://mitch444.github.io/dr-review-arsenal"


def is_live(slug: str) -> bool:
    """A rep is 'live' when their customer microsite file exists."""
    return (TEAM_DIR / f"{slug}.html").exists()


def avatar_html(slug: str, name: str) -> tuple[str, str]:
    """Return (avatar_html, full_photo_url_or_empty)."""
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
    return avatar, photo_full


def form_url(slug: str, name: str, count: str, avg: str, photo_full: str) -> str:
    params = urlencode({
        "name": name,
        "slug": slug,
        "title": "Sales Consultant",
        "reviews": count,
        "rating": avg,
        "photo": photo_full,
    })
    return f"form.html?{params}"


def build_card(slug: str, name: str, stars: str, count: str, avg: str) -> str:
    """Render a rep card in PENDING or LIVE mode based on team/{slug}.html."""
    avatar, photo_full = avatar_html(slug, name)

    if is_live(slug):
        microsite = f"team/{slug}.html"
        live_btn = (
            f'<a class="rep-card-live-btn" href="{microsite}" target="_blank" rel="noopener"\n'
            f'           data-rep="{name}" data-slug="{slug}">\n'
            f'          <span class="rep-live-dot"></span>\n'
            f'          <span class="rep-live-label">View page</span>\n'
            f'          <span class="rep-live-arrow">↗</span>\n'
            f'        </a>'
        )
        return (
            f'<div class="rep-card rep-card-live">\n'
            f'        {live_btn}\n'
            f'        <a class="rep-card-main" href="reps/{slug}.html">\n'
            f'          {avatar}\n'
            f'          <div class="rep-name">{name}</div>\n'
            f'          <div class="rep-meta">\n'
            f'            <span class="rep-stars">{stars}</span>\n'
            f'            {count} reviews · {avg}★\n'
            f'          </div>\n'
            f'        </a>\n'
            f'      </div>'
        )

    # PENDING mode
    fu = form_url(slug, name, count, avg, photo_full)
    pending_btn = (
        f'<span class="rep-card-live-btn rep-card-live-btn-pending"\n'
        f'           aria-disabled="true" title="Page not live yet"\n'
        f'           data-rep="{name}" data-slug="{slug}">\n'
        f'          <span class="rep-live-dot"></span>\n'
        f'          <span class="rep-live-label">Not live</span>\n'
        f'        </span>'
    )
    return (
        f'<div class="rep-card">\n'
        f'        {pending_btn}\n'
        f'        <a class="rep-card-main" href="reps/{slug}.html">\n'
        f'          {avatar}\n'
        f'          <div class="rep-name">{name}</div>\n'
        f'          <div class="rep-meta">\n'
        f'            <span class="rep-stars">{stars}</span>\n'
        f'            {count} reviews · {avg}★\n'
        f'          </div>\n'
        f'        </a>\n'
        f'        <a class="rep-card-cta" href="{fu}" target="_blank" rel="noopener"\n'
        f'           data-rep="{name}">\n'
        f'          <span class="cta-label">Build your customer page</span>\n'
        f'          <span class="cta-arrow">→</span>\n'
        f'        </a>\n'
        f'      </div>'
    )


# ── Regexes ────────────────────────────────────────────────────────────────

# Original (unpatched) structure — matches on first-ever run.
OLD_REP_CARD_RE = re.compile(
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

# Patched structure — matches all states (pending w/ or w/o placeholder, live).
# Captures: slug, name, stars, count, avg. Re-render decides live vs. pending.
PATCHED_CARD_RE = re.compile(
    r'<div class="rep-card(?: rep-card-live)?">\s*'
    r'(?:<(?:a|span) class="rep-card-live-btn[^"]*"[^>]*>[\s\S]*?</(?:a|span)>\s*)?'
    r'<a class="rep-card-main" href="reps/([a-z0-9-]+)\.html">\s*'
    r'<div class="rep-avatar[^"]*"[^>]*>[^<]*</div>\s*'
    r'<div class="rep-name">([^<]+)</div>\s*'
    r'<div class="rep-meta">\s*'
    r'<span class="rep-stars">([★]+)</span>\s*'
    r'(\d+) reviews · ([\d.]+)★\s*'
    r'</div>\s*'
    r'</a>\s*'
    r'(?:<a class="rep-card-cta"[^>]*>[\s\S]*?</a>\s*)?'
    r'</div>',
    re.MULTILINE,
)


def patch_index():
    html = INDEX.read_text(encoding="utf-8")
    original = html

    def repl(m):
        slug, name, stars, count, avg = m.groups()
        return build_card(slug, name, stars, count, avg)

    # Pass 1 — first-time conversion of original unpatched cards.
    html, n1 = OLD_REP_CARD_RE.subn(repl, html)

    # Pass 2 — resync every patched card to current live/pending state.
    html, n2 = PATCHED_CARD_RE.subn(repl, html)

    if html == original:
        if n1 == 0 and n2 == 0:
            print("  WARN no rep-cards matched — pattern may have drifted")
            return False
        print("  SKIP index.html (no content change needed)")
        return False

    INDEX.write_text(html, encoding="utf-8")
    live_total = len(re.findall(r'<div class="rep-card rep-card-live">', html))
    pending_total = len(re.findall(r'<div class="rep-card">', html))
    print(f"  PATCHED index.html — {n1} first-time, {n2} re-synced · "
          f"{live_total} live / {pending_total} pending")
    return True


# ── styles.css additions ───────────────────────────────────────────────────

PENDING_CSS_BLOCK = """
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

LIVE_CSS_BLOCK = """
/* --- Rep card live/pending pill button (top-right of card) --- */
.rep-card { position: relative; }
.rep-card-live-btn {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 2;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 6px 11px 6px 10px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  text-decoration: none;
  transition: transform .14s ease, box-shadow .14s ease, background .14s ease, color .14s ease;
}
.rep-card-live-btn .rep-live-dot {
  width: 7px; height: 7px; border-radius: 50%;
  display: inline-block;
}
.rep-card-live-btn .rep-live-arrow { font-weight: 700; opacity: .9; }

/* LIVE — emerald gradient, pulsing dot, lifts on hover */
.rep-card-live-btn:not(.rep-card-live-btn-pending) {
  color: #fff;
  background: linear-gradient(135deg, #10b981 0%, #047857 55%, #064e3b 100%);
  box-shadow: 0 2px 8px rgba(4, 120, 87, .35),
              inset 0 0 0 1px rgba(255, 255, 255, .12);
}
.rep-card-live-btn:not(.rep-card-live-btn-pending):hover {
  transform: translateY(-1px);
  color: #fff;
  text-decoration: none;
  box-shadow: 0 6px 14px rgba(4, 120, 87, .45),
              inset 0 0 0 1px rgba(255, 255, 255, .22);
}
.rep-card-live-btn:not(.rep-card-live-btn-pending) .rep-live-dot {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, .35);
  animation: rep-live-pulse 1.8s ease-in-out infinite;
}
@keyframes rep-live-pulse {
  0%, 100% { opacity: 1;   box-shadow: 0 0 0 2px rgba(255,255,255,.35); }
  50%      { opacity: .55; box-shadow: 0 0 0 5px rgba(255,255,255,.10); }
}

/* PENDING — greyed-out placeholder, not clickable */
.rep-card-live-btn-pending {
  background: #eef1f5;
  color: #8a95a5;
  box-shadow: inset 0 0 0 1px var(--border);
  cursor: not-allowed;
  pointer-events: none;
  user-select: none;
}
.rep-card-live-btn-pending .rep-live-dot {
  background: #c5ccd6;
}

/* Live mode hides the footer intake CTA */
.rep-card-live .rep-card-cta { display: none; }
"""


def patch_css():
    css = STYLES.read_text(encoding="utf-8")
    changed = False

    if ".rep-card-main" not in css:
        css = css.rstrip() + "\n" + PENDING_CSS_BLOCK
        changed = True
        print("  APPENDED styles.css (pending CTA block)")

    if ".rep-card-live-btn" not in css:
        css = css.rstrip() + "\n" + LIVE_CSS_BLOCK
        changed = True
        print("  APPENDED styles.css (live/pending button block)")

    if changed:
        STYLES.write_text(css, encoding="utf-8")
    else:
        print("  SKIP styles.css (already patched)")
    return changed


# ── app.js additions ───────────────────────────────────────────────────────

OLD_APP_JS_BLOCK = """    // Rep cards on index page
    var card = e.target.closest("a.rep-card");
    if (card) {
      var nameEl = card.querySelector(".rep-name");
      var rn = nameEl ? nameEl.textContent.trim() : null;
      if (rn) track("rep_card_click", { rep_name: rn });
    }"""

PENDING_PLUS_LIVE_APP_JS_BLOCK = """    // Rep cards on index page — main link
    var cardMain = e.target.closest("a.rep-card-main");
    if (cardMain) {
      var nameEl = cardMain.querySelector(".rep-name");
      var rn = nameEl ? nameEl.textContent.trim() : null;
      if (rn) track("rep_card_click", { rep_name: rn });
      return;
    }
    // Rep cards — "Build your customer page" footer CTA
    var ctaBtn = e.target.closest("a.rep-card-cta");
    if (ctaBtn) {
      var rep = ctaBtn.getAttribute("data-rep") || null;
      track("intake_form_open", { rep_name: rep });
      return;
    }
    // Rep cards — live microsite pill button (top-right)
    var liveBtn = e.target.closest("a.rep-card-live-btn");
    if (liveBtn && !liveBtn.classList.contains("rep-card-live-btn-pending")) {
      var rep2 = liveBtn.getAttribute("data-rep") || null;
      var slug = liveBtn.getAttribute("data-slug") || null;
      track("live_page_open", { rep_name: rep2, rep_slug: slug });
      return;
    }"""

LIVE_EXTRA_APP_JS_BLOCK = """
    // Rep cards — live microsite pill button (top-right)
    var liveBtn = e.target.closest("a.rep-card-live-btn");
    if (liveBtn && !liveBtn.classList.contains("rep-card-live-btn-pending")) {
      var rep2 = liveBtn.getAttribute("data-rep") || null;
      var slug = liveBtn.getAttribute("data-slug") || null;
      track("live_page_open", { rep_name: rep2, rep_slug: slug });
      return;
    }"""

EXISTING_INTAKE_BLOCK = """    // Rep cards — "Build your customer page" CTA
    var ctaBtn = e.target.closest("a.rep-card-cta");
    if (ctaBtn) {
      var rep = ctaBtn.getAttribute("data-rep") || null;
      track("intake_form_open", { rep_name: rep });
      return;
    }"""


def patch_app_js():
    js = APP_JS.read_text(encoding="utf-8")

    if "live_page_open" in js:
        print("  SKIP app.js (already has live_page_open handler)")
        return False

    if OLD_APP_JS_BLOCK in js:
        js = js.replace(OLD_APP_JS_BLOCK, PENDING_PLUS_LIVE_APP_JS_BLOCK)
        APP_JS.write_text(js, encoding="utf-8")
        print("  PATCHED app.js (intake + live handlers)")
        return True

    if EXISTING_INTAKE_BLOCK in js:
        js = js.replace(EXISTING_INTAKE_BLOCK, EXISTING_INTAKE_BLOCK + LIVE_EXTRA_APP_JS_BLOCK)
        APP_JS.write_text(js, encoding="utf-8")
        print("  PATCHED app.js (live handler appended)")
        return True

    print("  WARN app.js — neither old nor intake block found; manual check needed")
    return False


def main():
    print("Patching DR Review Arsenal site → rep card button (live/pending) + CTAs")
    ok_idx = patch_index()
    ok_css = patch_css()
    ok_js  = patch_app_js()
    if ok_idx or ok_css or ok_js:
        print("\nDone. Commit and push to deploy:")
        print('  git add index.html assets/styles.css assets/app.js team/ patch_rep_cards.py')
        print('  git commit -m "Rep cards: greyed pending / emerald live microsite button"')
        print('  git push')
    else:
        print("\nNothing changed.")


if __name__ == "__main__":
    main()
