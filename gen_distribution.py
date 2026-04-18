#!/usr/bin/env python3
"""Generate the rep-intake distribution pack:

  1. WH-Team-rep-distribution.html — interactive dashboard with one card
     per rep, copy-to-clipboard SMS button, and a "Preview form" button
     that opens the rep's pre-filled intake link.
  2. WH-Team-rep-distribution.md — plain-text table so the same info is
     readable anywhere (GitHub, a phone, a printout, Notion).

Data is pulled straight out of the patched index.html so this stays in
sync with whatever's actually deployed.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "index.html"
OUT_DIR = Path("/sessions/amazing-bold-sagan/mnt/Blink Intelligence")
OUT_HTML = OUT_DIR / "WH-Team-rep-distribution.html"
OUT_MD   = OUT_DIR / "WH-Team-rep-distribution.md"

SITE_URL = "https://mitch444.github.io/dr-review-arsenal"
FORM_URL_BASE = f"{SITE_URL}/form.html"
MGR_FIRST = "Mitch"
MGR_CELL = "431-276-1044"


# ── Parse rep data from the patched index.html ─────────────────────────────
CARD_RE = re.compile(
    r'<div class="rep-card">\s*'
    r'<a class="rep-card-main" href="reps/([a-z0-9-]+)\.html">.*?'
    r'<div class="rep-name">([^<]+)</div>\s*'
    r'<div class="rep-meta">\s*'
    r'<span class="rep-stars">[★]+</span>\s*'
    r'(\d+) reviews · ([\d.]+)★.*?'
    r'<a class="rep-card-cta" href="form\.html\?([^"]+)"',
    re.DOTALL,
)


def parse_reps():
    html = INDEX.read_text(encoding="utf-8")
    reps = []
    for m in CARD_RE.finditer(html):
        slug, name, count, avg, qs = m.groups()
        params = parse_qs(qs)
        photo = params.get("photo", [""])[0]
        reps.append({
            "slug": slug,
            "name": name,
            "count": int(count),
            "avg": avg,
            "photo": photo,
            "first": name.split()[0],
            "form_url": f"{FORM_URL_BASE}?{qs}",
        })
    return reps


# ── SMS template ───────────────────────────────────────────────────────────
def sms_for(rep):
    """Keep short. The link carries the weight."""
    return (
        f"Hey {rep['first']} — here's the link for your new customer page on the WH site. "
        f"It's mostly filled in already from your DealerRater profile ({rep['count']} reviews, {rep['avg']}★). "
        f"You just add a short bio + a few checkboxes. ~10 min.\n\n"
        f"{rep['form_url']}\n\n"
        f"Reply here if anything's weird. - {MGR_FIRST}"
    )


# ── HTML dashboard ─────────────────────────────────────────────────────────
HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>WH Team Intake — Distribution Dashboard</title>
<style>
  :root {{
    --navy: #002c5F; --teal: #007FA8; --ink: #0b1220;
    --muted: #5a6374; --line: #e5e7ec; --bg: #fbfbfd;
    --bg-soft: #f2f4f8; --success: #16a34a; --star: #f5a524;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: 'Inter', -apple-system, system-ui, sans-serif;
    background: var(--bg); color: var(--ink); line-height: 1.5;
  }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 36px 24px 120px; }}
  h1 {{ font-size: 28px; margin: 0 0 6px; letter-spacing: -.02em; color: var(--navy); }}
  .sub {{ color: var(--muted); font-size: 15px; margin: 0 0 22px; }}
  .steps {{
    background: #fff; border: 1px solid var(--line); border-radius: 14px;
    padding: 18px 22px; margin-bottom: 28px; font-size: 14px;
  }}
  .steps b {{ color: var(--navy); }}
  .steps ol {{ margin: 8px 0 0; padding-left: 22px; }}
  .steps li {{ margin-bottom: 4px; }}
  .counter {{
    display: inline-flex; align-items: center; gap: 8px;
    background: var(--navy); color: #fff;
    padding: 6px 14px; border-radius: 999px;
    font-size: 13px; font-weight: 600; margin-left: 10px;
  }}
  .counter b {{ font-size: 15px; }}

  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 14px;
  }}
  .card {{
    background: #fff; border: 1px solid var(--line); border-radius: 14px;
    padding: 16px 18px; display: flex; flex-direction: column; gap: 12px;
    box-shadow: 0 1px 2px rgba(10,20,50,.04), 0 4px 12px rgba(10,20,50,.04);
    position: relative;
  }}
  .card.done {{ background: #f0fdf4; border-color: #bbf7d0; }}
  .card.done::after {{
    content: "✓ SENT"; position: absolute; top: 14px; right: 16px;
    font-size: 11px; font-weight: 700; color: var(--success);
    letter-spacing: .08em;
  }}
  .who {{ display: flex; align-items: center; gap: 12px; }}
  .avatar {{
    width: 48px; height: 48px; border-radius: 999px;
    background: var(--bg-soft) center/cover no-repeat;
    flex-shrink: 0; border: 2px solid #fff; box-shadow: 0 0 0 1px var(--line);
  }}
  .who-text .name {{ font-weight: 700; font-size: 15px; color: var(--navy); }}
  .who-text .meta {{ font-size: 12px; color: var(--muted); }}
  .who-text .meta .stars {{ color: var(--star); letter-spacing: 1px; }}
  .sms-box {{
    background: var(--bg-soft); border-radius: 10px;
    padding: 10px 12px; font-size: 12.5px; color: var(--ink);
    white-space: pre-wrap; word-break: break-word;
    max-height: 120px; overflow: auto; line-height: 1.4;
  }}
  .url-box {{
    font-family: ui-monospace, Menlo, monospace;
    font-size: 11px; color: var(--muted);
    background: var(--bg-soft); padding: 6px 10px;
    border-radius: 6px; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap;
  }}
  .btns {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
  .btn {{
    padding: 10px 12px; border-radius: 8px; border: none; cursor: pointer;
    font-size: 13px; font-weight: 600; font-family: inherit;
    text-align: center; text-decoration: none;
    transition: all .12s;
  }}
  .btn-primary {{ background: var(--navy); color: #fff; }}
  .btn-primary:hover {{ background: #001a3f; }}
  .btn-primary.copied {{ background: var(--success); }}
  .btn-secondary {{
    background: #fff; color: var(--navy);
    border: 1.5px solid var(--navy);
  }}
  .btn-secondary:hover {{ background: var(--navy); color: #fff; }}
  .btn-sms {{ background: var(--teal); color: #fff; }}
  .btn-sms:hover {{ background: #005f7f; }}
  .sent-toggle {{
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: var(--muted); user-select: none;
    cursor: pointer; padding-top: 4px;
    border-top: 1px dashed var(--line); margin-top: 4px;
  }}
  .sent-toggle input {{ accent-color: var(--success); }}
  @media (max-width: 600px) {{
    .btns {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>WH Team Intake · Distribution Dashboard
    <span class="counter">Sent: <b id="sent-count">0</b> / {n}</span>
  </h1>
  <p class="sub">One card per rep. Every SMS is pre-written with their personalized form link. Tap "Copy SMS", switch to Messages, paste, send. Check the box when done.</p>

  <div class="steps">
    <b>Workflow for each rep:</b>
    <ol>
      <li>Tap <b>Copy SMS</b> — full message + personal link lands on your clipboard.</li>
      <li>Open Messages → tap the rep's thread → paste → send.</li>
      <li>Tick the "Sent" checkbox on this dashboard to keep track.</li>
      <li>(Optional) <b>Preview form</b> shows you exactly what they're about to see.</li>
    </ol>
  </div>

  <div class="grid" id="grid">
    {cards}
  </div>
</div>

<script>
  const KEY = 'wh-team-distribution-sent';
  const sent = JSON.parse(localStorage.getItem(KEY) || '{{}}');

  function refreshCount() {{
    const n = Object.values(sent).filter(Boolean).length;
    document.getElementById('sent-count').textContent = n;
  }}

  document.querySelectorAll('.card').forEach(card => {{
    const slug = card.dataset.slug;
    const toggle = card.querySelector('.sent-check');
    if (sent[slug]) {{ toggle.checked = true; card.classList.add('done'); }}
    toggle.addEventListener('change', () => {{
      sent[slug] = toggle.checked;
      card.classList.toggle('done', toggle.checked);
      localStorage.setItem(KEY, JSON.stringify(sent));
      refreshCount();
    }});
  }});
  refreshCount();

  document.querySelectorAll('.btn-copy').forEach(btn => {{
    btn.addEventListener('click', async () => {{
      const sms = btn.closest('.card').querySelector('.sms-box').textContent;
      try {{
        await navigator.clipboard.writeText(sms);
        btn.textContent = '✓ Copied — paste in Messages';
        btn.classList.add('copied');
        setTimeout(() => {{ btn.textContent = 'Copy SMS'; btn.classList.remove('copied'); }}, 2400);
      }} catch (e) {{ alert('Copy failed — select the text manually.'); }}
    }});
  }});
</script>
</body>
</html>
"""

CARD_TEMPLATE = """    <div class="card" data-slug="{slug}">
      <div class="who">
        <div class="avatar" style="background-image:url('{photo}');"></div>
        <div class="who-text">
          <div class="name">{name}</div>
          <div class="meta"><span class="stars">★★★★★</span> {count} reviews · {avg}★</div>
        </div>
      </div>
      <div class="sms-box">{sms}</div>
      <div class="url-box">{form_url}</div>
      <div class="btns">
        <button class="btn btn-primary btn-copy" type="button">Copy SMS</button>
        <a class="btn btn-secondary" href="{form_url}" target="_blank" rel="noopener">Preview form</a>
      </div>
      <a class="btn btn-sms" href="sms:&body={sms_urlenc}" style="text-align:center;">
        📱 Open Messages with text pre-filled
      </a>
      <label class="sent-toggle">
        <input type="checkbox" class="sent-check"> Mark as sent
      </label>
    </div>"""


def html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


def main():
    reps = parse_reps()
    if not reps:
        print("ERROR — no reps parsed. Has index.html been patched yet?")
        return

    # HTML dashboard
    cards_html = []
    for r in reps:
        sms = sms_for(r)
        card = CARD_TEMPLATE.format(
            slug=r["slug"],
            name=html_escape(r["name"]),
            photo=r["photo"],
            count=r["count"],
            avg=r["avg"],
            sms=html_escape(sms),
            form_url=r["form_url"],
            sms_urlenc=urlencode({"_": sms})[2:],
        )
        cards_html.append(card)

    html_out = HTML_TEMPLATE.format(cards="\n".join(cards_html), n=len(reps))
    OUT_HTML.write_text(html_out, encoding="utf-8")
    print(f"WROTE {OUT_HTML} — {len(reps)} cards")

    # Markdown table
    lines = [
        "# WH Team Intake · Distribution Pack",
        "",
        f"**Reps:** {len(reps)} · **Manager cell:** {MGR_CELL} · **Form URL base:** {FORM_URL_BASE}",
        "",
        "Sorted by review count (most social proof first → best early wins).",
        "",
        "## The rollout in one paragraph",
        "",
        "Send the personalized SMS below to each rep. The link inside carries their name, title, review count, rating, and photo as URL params — when they tap it, their intake form is already half-filled. Text works better than email for this; reps read texts. Keep the dashboard HTML open and tick each rep off as you send.",
        "",
        "## The 19 reps",
        "",
    ]
    for i, r in enumerate(reps, 1):
        sms = sms_for(r)
        lines.extend([
            f"### {i}. {r['name']} · {r['count']} reviews · {r['avg']}★",
            "",
            f"**Pre-filled form URL:**",
            f"```",
            f"{r['form_url']}",
            f"```",
            "",
            f"**SMS to send:**",
            f"```",
            sms,
            f"```",
            "",
            "---",
            "",
        ])

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"WROTE {OUT_MD}")


if __name__ == "__main__":
    main()
