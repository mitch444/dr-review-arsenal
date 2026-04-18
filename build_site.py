"""
DR Review Arsenal — Digital Site Generator.

Reads the master review CSV produced by build_arsenal.py and emits a
self-contained static site:

  DR_Review_Arsenal_Site/
    index.html           ← manager landing, rep grid
    reps/<slug>.html     ← one page per rep (standalone, bookmarkable)
    assets/styles.css
    assets/app.js
    README.md
    .nojekyll

Every rep page embeds its own review data as JSON — no fetch, no CORS, no
external dependencies. Drop the folder straight into GitHub Pages and go.
"""
from __future__ import annotations

import csv
import html
import io
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import qrcode
import qrcode.image.svg


# ── Paths ────────────────────────────────────────────────────────────────────
SITE_DIR = Path("/sessions/amazing-bold-sagan/mnt/Blink Intelligence/DR_Review_Arsenal_Site")
MASTER_CSV = Path(
    "/sessions/amazing-bold-sagan/mnt/Blink Intelligence/DR_Review_Arsenal/data/dr_reviews_master.csv"
)

DEALER_ID = "34932"
DR_DEALER_URL = f"https://www.dealerrater.ca/dealer/Winnipeg-Hyundai-review-{DEALER_ID}/"
DEALERSHIP = "Winnipeg Hyundai"

# ── Scenarios ────────────────────────────────────────────────────────────────
# Mitch's original 7 buyer contexts, then 9 expanded tags (rep qualities +
# product type + loyalty signals). Ordered so the buyer-context pills come
# first on the rep page (matches how a salesperson thinks about a walk-up).
SCENARIOS: list[tuple[str, str, list[str]]] = [
    # (label, emoji, keyword list — lowercased, matched as substrings on review text)

    # ── Buyer-context scenarios (who's in front of the rep) ─────────────────
    ("Trade-In Nervous", "🔁", [
        "trade", "appraisal", "payoff", "negative equity", "trade value",
        "trading in", "my old car", "my old vehicle",
    ]),
    ("First-Time Buyer", "🌱", [
        "first time", "first car", "first vehicle", "never bought",
        "new to", "intimidat", "nervous", "first-time",
    ]),
    ("Credit Story", "💳", [
        "credit", "financing", "approved", "bank", "loan", "budget",
        "payment plan", "affordable payment", "rebuild", "second chance",
    ]),
    ("Family SUV", "👨‍👩‍👧", [
        "family", "kids", "baby", "children", "daughter", "son",
        "growing", "car seat", "tucson", "santa fe", "palisade",
        "family-friendly", "wife", "husband", "spouse",
    ]),
    ("EV-Curious", "⚡", [
        "electric", " ev ", "ev,", "ev.", "ev!", "ioniq", "kona electric",
        "hybrid", "plug-in", "range anxiety", "charging",
    ]),
    ("Switched Brands", "🔀", [
        "toyota", "honda", "ford", "chevy", "chevrolet", "nissan",
        "mazda", "kia", "volkswagen", "vw", "gmc", "dodge", "ram",
        "bmw", "mercedes", "audi", "switched", "used to drive",
        "came from", "upgraded from",
    ]),
    ("Price Shopper", "🏷️", [
        "price", "best deal", "fair", "no haggle", "no-haggle",
        "negotiat", "shopping around", "compared",
        "affordable", "honest price", "best value",
    ]),

    # ── Loyalty / social-proof signals ──────────────────────────────────────
    ("Repeat Customer", "💎", [
        "second car", "second vehicle", "third car", "third vehicle",
        "my second", "my third", "my fourth", "came back", "come back",
        "returning", "returned to", "bought another", "another vehicle from",
        "purchased before", "loyal customer", "fifth", "fourth vehicle",
    ]),
    ("Referral", "📣", [
        "recommend", "recommended", "referred", "referral",
        "my friend", "a friend", "friend of mine", "coworker", "co-worker",
        "told me about", "told us about", "sent me", "sent us",
        "word of mouth", "highly recommend",
    ]),

    # ── Product type ────────────────────────────────────────────────────────
    ("Lease", "📝", [
        "lease", "leasing", "leased", "lease-end", "lease term",
        "lease return", "lease buyout",
    ]),
    ("Pre-Owned", "🚗", [
        "used car", "used vehicle", "pre-owned", "pre owned", "preowned",
        "second hand", "second-hand", "certified pre",
    ]),

    # ── Rep quality signals (what reps want their book to *say* about them) ─
    ("No-Pressure", "🧘", [
        "no pressure", "no-pressure", "zero pressure", "not pushy",
        "never pushy", "didn't pressure", "without pressure",
        "pressure free", "pressure-free", "no sales pitch", "not pushed",
    ]),
    ("Patient Educator", "🎓", [
        "patient", "patience", "walked me through", "walked us through",
        "explained everything", "every detail", "all my questions",
        "all our questions", "took the time", "educated", "taught",
        "showed me how", "showed us how", "never rushed", "not rushed",
        "step by step", "step-by-step",
    ]),
    ("Smooth & Easy", "🪄", [
        "smooth", "seamless", "easy process", "easiest", "effortless",
        "hassle free", "hassle-free", "stress free", "stress-free",
        "painless", "quick and easy", "so easy", "made it easy",
    ]),
    ("Honest & Transparent", "🤝", [
        "honest", "transparent", "no gimmick", "no hidden", "upfront",
        "up front", "straight forward", "straightforward", "trustworthy",
        "integrity", "genuine", "no surprises",
    ]),
    ("Above & Beyond", "🌟", [
        "above and beyond", "above & beyond", "went above", "went the extra",
        "extra mile", "exceeded", "over and above", "out of their way",
        "out of his way", "out of her way", "beyond expectations",
    ]),

    # ── Intensity overlay (handled specially in tag_scenarios) ──────────────
    # Super Fan = the highlight reel. Detected by signal scoring, not direct
    # keyword match — see SUPER_FAN_STRONG / SUPER_FAN_WEAK below.
    ("Super Fan", "🔥", []),
]


# ── Super Fan detection (intensity, not context) ─────────────────────────────
# A review qualifies as Super Fan if it has ≥1 STRONG signal OR ≥3 WEAK signals.
# Calibrated to land ~6% of the corpus — the highlight-reel reviews you pull
# when a customer needs to be wowed.
SUPER_FAN_STRONG = [
    "best experience", "best dealership", "best salesperson", "best dealer",
    "can't say enough", "cannot say enough", "can not say enough",
    "hands down", "by far the best", "by far the most",
    "won't go anywhere else", "will never go anywhere else",
    "never going anywhere else",
    "100% recommend", "1000%", "10/10", "11/10", "100 stars", "million stars",
    "life changing", "life-changing",
    "tell everyone", "telling everyone", "raving",
    "blown away", "speechless",
    "forever grateful", "can't thank", "cannot thank",
    "best car buying", "best car-buying", "best car purchase",
    "best vehicle purchase",
    "cannot recommend enough", "can't recommend enough",
    "highly highly recommend", "highly, highly recommend",
    "dream car", "above and beyond",
    "exceeded all", "exceeded my expectations", "exceeded our expectations",
    "second to none",
]

SUPER_FAN_WEAK = [
    "amazing", "incredible", "outstanding", "phenomenal", "exceptional",
    "fantastic", "wonderful", "absolutely", "loved", "impressed",
    "!!!", "!!",
]


def is_super_fan(text: str) -> bool:
    """Highlight-reel detector — extreme positive intensity."""
    if not text:
        return False
    low = text.lower()
    for kw in SUPER_FAN_STRONG:
        if kw in low:
            return True
    weak_hits = sum(1 for kw in SUPER_FAN_WEAK if kw in low)
    return weak_hits >= 3


# ── Helpers ──────────────────────────────────────────────────────────────────
def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def mentions_by_name(rep_name: str, review_text: str) -> bool:
    """Does the review text actually name this rep?

    Used to visually elevate reviews where the customer called them out
    personally — but NOT to filter. DR's canonical count includes every
    tagged review (finance managers get tagged on lots of deals they
    helped close without being the narrative's subject).
    """
    parts = rep_name.split()
    first = parts[0].lower() if parts else ""
    last = parts[-1].lower() if len(parts) > 1 else ""
    text = review_text.lower()
    if first and re.search(rf"\b{re.escape(first)}\b", text):
        return True
    if last and len(last) > 3 and re.search(rf"\b{re.escape(last)}\b", text):
        return True
    return False


def tag_scenarios(text: str) -> list[str]:
    """Return scenario labels that match this review. A review can match multiple."""
    if not text:
        return []
    low = text.lower()
    hits = []
    for label, _emoji, keywords in SCENARIOS:
        if not keywords:
            # Special case: label has custom detection (e.g. Super Fan)
            continue
        for kw in keywords:
            if kw in low:
                hits.append(label)
                break
    if is_super_fan(text):
        hits.append("Super Fan")
    return hits


def month_year(date_str: str) -> str:
    """Convert YYYY-MM-DD → 'Mon YYYY'."""
    if not date_str or len(date_str) < 7:
        return ""
    try:
        from datetime import date
        y, m, d = date_str.split("-")[:3]
        return date(int(y), int(m), 1).strftime("%b %Y")
    except Exception:
        return date_str


def qr_svg(url: str, box_size: int = 3, border: int = 2) -> str:
    """Generate an inline SVG QR code (self-contained, no external deps)."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode("utf-8")
    # Strip XML prolog so it inlines cleanly in HTML
    svg = re.sub(r"<\?xml[^>]+\?>", "", svg).strip()
    # Ensure width/height are responsive
    svg = svg.replace("<svg ", '<svg style="width:100%;height:auto;display:block" ', 1)
    return svg


# ── Verified DR employee profile URLs ────────────────────────────────────────
# Scraped from DealerRater dealer + tagged-employee pages. Keyed by full name
# exactly as it appears in the review CSV's `employee_mentioned` field.
# To add a rep: find their "View N Reviews" button on
# https://www.dealerrater.ca/dealer/Winnipeg-Hyundai-review-34932/ and grab
# the URL from the href — it looks like /sales/First-Last-review-NNNNNN/.
DR_EMPLOYEE_URLS: dict[str, str] = {
    "Bill Turnbull":        "https://www.dealerrater.ca/sales/Bill-Turnbull-review-440324/",
    "Bob McGregor":         "https://www.dealerrater.ca/sales/Bob-McGregor-review-705626/",
    "Brady Hrymak":         "https://www.dealerrater.ca/sales/Brady-Hrymak-review-715258/",
    "Chris Martin":         "https://www.dealerrater.ca/sales/Chris-Martin-review-546431/",
    "Doug McCartney":       "https://www.dealerrater.ca/sales/Doug-McCartney-review-580670/",
    "Eric Anderson":        "https://www.dealerrater.ca/sales/Eric-Anderson-review-631283/",
    "Greg Renner":          "https://www.dealerrater.ca/sales/Greg-Renner-review-777695/",
    "Kaelen Honke":         "https://www.dealerrater.ca/sales/Kaelen-Honke-review-440332/",
    "Kevin Dodge":          "https://www.dealerrater.ca/sales/Kevin-Dodge-review-803478/",
    "Leo Caronte":          "https://www.dealerrater.ca/sales/Leo-Caronte-review-878893/",
    "Les Friesen":          "https://www.dealerrater.ca/sales/Les-Friesen-review-441262/",
    "Mitch Gallant":        "https://www.dealerrater.ca/sales/Mitch-Gallant-review-978656/",
    "Pat Guenette":         "https://www.dealerrater.ca/sales/Pat-Guenette-review-495564/",
    "Ralph Wasserberg":     "https://www.dealerrater.ca/sales/Ralph-Wasserberg-review-441258/",
    "Samantha Swaikoski":   "https://www.dealerrater.ca/sales/Samantha-Swaikoski-review-895625/",
    "Sonny Dela Cruz":      "https://www.dealerrater.ca/sales/Sonny-Dela-Cruz-review-978698/",
    "Sumit Thapar":         "https://www.dealerrater.ca/sales/Sumit-Thapar-review-777697/",
    "Trent Yellowega":      "https://www.dealerrater.ca/sales/Trent-Yellowega-review-441276/",
    "Vladyslav Ihnatov":    "https://www.dealerrater.ca/sales/Vladyslav-Ihnatov-review-870233/",
}


def dr_employee_url(rep_name: str) -> str:
    """Return the verified DR profile URL for this rep, or the dealer page as
    a safe fallback when the rep doesn't have a verified profile yet.

    Never guess a URL — a broken link is worse than the generic dealer page,
    which at least drops the customer onto a real Winnipeg Hyundai DR page.
    """
    url = DR_EMPLOYEE_URLS.get(rep_name.strip())
    if url:
        return url
    # Fallback: send them to the dealership's main DR page
    return DR_DEALER_URL


def ensure_clean(site_dir: Path) -> None:
    """Ensure output dirs exist. Skip cleanup — overwrite is fine and works
    across sandbox mounts that don't allow unlinking."""
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "reps").mkdir(exist_ok=True)
    (site_dir / "assets").mkdir(exist_ok=True)


# ── Data loading ─────────────────────────────────────────────────────────────
def load_reviews() -> list[dict]:
    with MASTER_CSV.open(encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def explode_by_rep(reviews: list[dict]) -> dict[str, list[dict]]:
    """Distribute each review to every tagged rep — matches DR's own count.

    A review tagged with three reps shows up on all three pages. That's
    intentional: DR's "View N reviews" button uses the same logic, and we
    want our public counts to match.
    """
    by_rep: dict[str, list[dict]] = defaultdict(list)
    for r in reviews:
        emps = (r.get("employee_mentioned") or "").strip()
        if not emps:
            continue
        tagged = [e.strip() for e in emps.split(",") if e.strip()]
        for name in tagged:
            by_rep[name].append(r)
    return by_rep


def rep_summary(rep: str, reviews: list[dict]) -> dict:
    ratings = [float(r.get("overall_rating") or 0) for r in reviews if r.get("overall_rating")]
    avg = round(sum(ratings) / len(ratings), 2) if ratings else 0
    # Distinct tag counts per scenario
    counts = Counter()
    for r in reviews:
        for s in tag_scenarios(r.get("review_text", "")):
            counts[s] += 1
    return {
        "name": rep,
        "slug": slugify(rep),
        "count": len(reviews),
        "avg": avg,
        "scenario_counts": dict(counts),
        "dr_url": dr_employee_url(rep),
        "dr_url_verified": rep.strip() in DR_EMPLOYEE_URLS,
    }


# ── HTML rendering ───────────────────────────────────────────────────────────
COMMON_CSS = """
:root {
  --bg: #f5f6f8;
  --surface: #ffffff;
  --text: #1a2b42;
  --muted: #6b7a8f;
  --primary: #002c5f;
  --primary-soft: #e8eef5;
  --accent: #c89d56;
  --star: #f4b400;
  --border: #e1e5ec;
  --shadow: 0 1px 2px rgba(20,30,60,.06), 0 4px 20px rgba(20,30,60,.05);
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text);
  -webkit-font-smoothing: antialiased;
}
a { color: var(--primary); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 1100px; margin: 0 auto; padding: 24px; }
.brand {
  display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
}
.brand-logo {
  width: 44px; height: 44px; border-radius: 50%;
  background: var(--primary); color: white;
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 18px;
}
.brand-name { font-size: 20px; font-weight: 700; letter-spacing: -0.01em; }
.brand-sub { color: var(--muted); font-size: 13px; }
h1 { font-size: 34px; margin: 20px 0 8px; letter-spacing: -0.02em; }
h2 { font-size: 22px; margin: 28px 0 12px; letter-spacing: -0.01em; }
.lead { color: var(--muted); font-size: 16px; margin-bottom: 28px; }

/* --- Rep grid (index) --- */
.grid {
  display: grid; gap: 16px;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
}
.rep-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 20px; box-shadow: var(--shadow);
  transition: transform .08s ease, box-shadow .08s ease;
  display: block; color: inherit;
}
.rep-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 4px rgba(20,30,60,.08), 0 10px 30px rgba(20,30,60,.08);
  text-decoration: none;
}
.rep-avatar {
  width: 56px; height: 56px; border-radius: 50%;
  background: linear-gradient(135deg, var(--primary), #1e4a80);
  color: white; display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 20px; margin-bottom: 14px;
}
.rep-avatar-photo {
  background-size: cover; background-position: center top;
  background-repeat: no-repeat;
}
.rep-name { font-size: 18px; font-weight: 700; letter-spacing: -0.01em; }
.rep-meta { color: var(--muted); font-size: 14px; margin-top: 4px; }
.rep-stars { color: var(--star); font-size: 15px; }

/* --- Rep page header --- */
.rep-hero {
  background: linear-gradient(135deg, var(--primary) 0%, #063e82 100%);
  color: white; border-radius: 18px; padding: 28px;
  margin-bottom: 20px; box-shadow: var(--shadow);
  display: flex; align-items: center; gap: 22px; flex-wrap: wrap;
}
.rep-hero-avatar {
  width: 84px; height: 84px; border-radius: 50%;
  background: white; color: var(--primary);
  display: flex; align-items: center; justify-content: center;
  font-weight: 700; font-size: 30px; flex-shrink: 0;
}
.rep-hero-avatar-photo {
  background-size: cover; background-position: center top;
  background-repeat: no-repeat;
  border: 3px solid white; box-shadow: 0 2px 8px rgba(0,0,0,.15);
}
.rep-hero-name { font-size: 30px; font-weight: 700; letter-spacing: -0.02em; margin: 0; }
.rep-hero-sub { opacity: .9; font-size: 14px; margin-top: 4px; }
.rep-hero-stats {
  display: flex; gap: 22px; margin-top: 12px; flex-wrap: wrap;
}
.stat-pill {
  background: rgba(255,255,255,.14);
  border-radius: 20px; padding: 6px 14px; font-size: 13px;
}
.rep-hero-qr {
  margin-left: auto; background: white; padding: 10px;
  border-radius: 12px; width: 120px; text-align: center;
}
.rep-hero-qr-label {
  font-size: 10px; color: var(--primary); text-transform: uppercase;
  letter-spacing: 0.08em; margin-top: 4px; font-weight: 600;
}

/* --- Scenario pills --- */
.pills {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 22px;
}
.pill {
  background: var(--surface); border: 1px solid var(--border);
  padding: 8px 14px; border-radius: 20px; font-size: 13px;
  cursor: pointer; user-select: none; transition: all .12s ease;
  color: var(--text);
}
.pill:hover { border-color: var(--primary); }
.pill.active {
  background: var(--primary); color: white; border-color: var(--primary);
}
.pill .count {
  margin-left: 6px; font-size: 11px; opacity: .7; font-weight: 600;
}

/* --- Review cards --- */
.reviews {
  display: grid; gap: 16px;
  grid-template-columns: 1fr;
}
.review {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 14px; padding: 20px; box-shadow: var(--shadow);
}
.review-head {
  display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px;
  flex-wrap: wrap;
}
.review-stars { color: var(--star); font-size: 15px; letter-spacing: 2px; }
.review-reviewer { font-weight: 600; font-size: 14px; }
.review-date { color: var(--muted); font-size: 13px; }
.review-scenarios {
  display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px;
}
.scenario-tag {
  background: var(--primary-soft); color: var(--primary);
  padding: 3px 9px; border-radius: 12px; font-size: 11px;
  font-weight: 600; letter-spacing: 0.01em;
}
.scenario-tag-named {
  background: linear-gradient(135deg, #fff4d6, #ffe7a6);
  color: #8a5a0b; border: 1px solid #e0b85a;
}
.pill-named {
  background: linear-gradient(135deg, #fff4d6, #ffe7a6);
  border-color: #e0b85a; color: #8a5a0b; font-weight: 600;
}
.pill-named.active {
  background: var(--accent); border-color: var(--accent); color: white;
}
.review-named {
  border-left: 3px solid var(--accent);
}
.review-text {
  font-size: 15px; line-height: 1.55; color: var(--text);
  margin: 12px 0 16px; white-space: pre-wrap;
}
.actions {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;
}
.btn {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 9px 14px; border-radius: 10px; font-size: 13px;
  font-weight: 600; cursor: pointer; border: 1px solid var(--border);
  background: var(--surface); color: var(--text);
  transition: all .1s ease; text-decoration: none;
}
.btn:hover { border-color: var(--primary); text-decoration: none; }
.btn.primary { background: var(--primary); color: white; border-color: var(--primary); }
.btn.primary:hover { background: #063e82; }
.btn.accent { background: var(--accent); color: white; border-color: var(--accent); }
.btn.accent:hover { background: #b68746; }
.btn.copied {
  background: #0c7a3e !important; color: white !important; border-color: #0c7a3e !important;
}
.btn .ico { font-size: 14px; }

/* --- Empty state --- */
.empty {
  background: var(--surface); border: 1px dashed var(--border);
  border-radius: 14px; padding: 40px; text-align: center;
  color: var(--muted);
}
.empty h3 { margin: 0 0 8px; color: var(--text); }

/* --- Footer --- */
.footer {
  margin-top: 40px; padding-top: 24px; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 12px; text-align: center;
}

/* --- Mobile --- */
@media (max-width: 640px) {
  .container { padding: 16px; }
  h1 { font-size: 26px; }
  .rep-hero { padding: 22px; }
  .rep-hero-avatar { width: 64px; height: 64px; font-size: 24px; }
  .rep-hero-name { font-size: 24px; }
  .rep-hero-qr { margin-left: 0; margin-top: 16px; width: 100%; max-width: 180px; }
}
"""


COMMON_JS = r"""
(function () {
  // --- Click-to-copy with visual feedback ---
  function copyToClipboard(text, btn) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(
        () => flashCopied(btn),
        () => fallback(text, btn)
      );
    } else {
      fallback(text, btn);
    }
  }
  function fallback(text, btn) {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.left = "-9999px";
    document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); flashCopied(btn); } catch (e) {}
    document.body.removeChild(ta);
  }
  function flashCopied(btn) {
    const orig = btn.innerHTML;
    btn.classList.add("copied");
    btn.innerHTML = '<span class="ico">✓</span> Copied';
    setTimeout(() => {
      btn.classList.remove("copied");
      btn.innerHTML = orig;
    }, 1400);
  }
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    e.preventDefault();
    copyToClipboard(btn.getAttribute("data-copy"), btn);
  });

  // --- Scenario filter pills ---
  const pills = document.querySelectorAll(".pill[data-scenario]");
  const cards = document.querySelectorAll(".review[data-scenarios]");
  function applyFilter(scenario) {
    pills.forEach((p) => p.classList.toggle("active", p.dataset.scenario === scenario));
    let visible = 0;
    cards.forEach((c) => {
      let show;
      if (scenario === "all") {
        show = true;
      } else if (scenario === "__named__") {
        show = c.dataset.named === "1";
      } else {
        const s = (c.dataset.scenarios || "").split("|");
        show = s.indexOf(scenario) !== -1;
      }
      c.style.display = show ? "" : "none";
      if (show) visible++;
    });
    const empty = document.getElementById("empty-state");
    if (empty) empty.style.display = visible === 0 ? "" : "none";
  }
  pills.forEach((p) => {
    p.addEventListener("click", () => applyFilter(p.dataset.scenario));
  });
})();
"""


def render_index(reps: list[dict]) -> str:
    reps_sorted = sorted(reps, key=lambda r: -r["count"])
    cards = []
    for r in reps_sorted:
        initials = "".join(p[0] for p in r["name"].split()[:2]).upper()
        photo_path = SITE_DIR / "assets" / "photos" / f"{r['slug']}.jpg"
        if photo_path.exists():
            photo_url = f"assets/photos/{r['slug']}.jpg"
            avatar_html = (
                '<div class="rep-avatar rep-avatar-photo" '
                f'style="background-image:url({photo_url!r})"></div>'
            )
        else:
            avatar_html = f'<div class="rep-avatar">{html.escape(initials)}</div>'
        cards.append(f"""
      <a class="rep-card" href="reps/{r["slug"]}.html">
        {avatar_html}
        <div class="rep-name">{html.escape(r["name"])}</div>
        <div class="rep-meta">
          <span class="rep-stars">{"★" * int(round(r["avg"]))}</span>
          {r["count"]} reviews · {r["avg"]:.2f}★
        </div>
      </a>""")

    stats_total = sum(r["count"] for r in reps)
    top = reps_sorted[0] if reps_sorted else None

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Review Arsenal · {DEALERSHIP}</title>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body>
  <div class="container">
    <div class="brand">
      <div class="brand-logo">WH</div>
      <div>
        <div class="brand-name">{DEALERSHIP} · Review Arsenal</div>
        <div class="brand-sub">Manager view · {len(reps_sorted)} reps · {stats_total:,} reviews</div>
      </div>
    </div>
    <h1>Pick a rep.</h1>
    <p class="lead">
      Every card opens a rep's personal review library — tagged by scenario,
      ready to text or email in one tap. Reps bookmark their own page.
    </p>
    <div class="grid">
      {"".join(cards)}
    </div>
    <div class="footer">
      Built from {stats_total:,} DealerRater reviews · regenerate via <code>python3 build_site.py</code>
    </div>
  </div>
</body>
</html>"""


def render_rep_page(rep: dict, reviews: list[dict]) -> str:
    """Per-rep page. Standalone — no link back to index, bookmarkable."""
    initials = "".join(p[0] for p in rep["name"].split()[:2]).upper()
    avg_stars = "★" * int(round(rep["avg"]))
    photo_path = SITE_DIR / "assets" / "photos" / f"{rep['slug']}.jpg"
    if photo_path.exists():
        hero_avatar_html = (
            '<div class="rep-hero-avatar rep-hero-avatar-photo" '
            f'style="background-image:url(\'../assets/photos/{rep["slug"]}.jpg\')"></div>'
        )
    else:
        hero_avatar_html = f'<div class="rep-hero-avatar">{html.escape(initials)}</div>'

    # Sort reviews: most recent first
    reviews_sorted = sorted(
        reviews, key=lambda r: r.get("review_date", ""), reverse=True
    )

    # Build scenario counts in Mitch's declared order
    scenario_order = [s[0] for s in SCENARIOS]
    scenario_emoji = {s[0]: s[1] for s in SCENARIOS}
    scenario_counts = Counter()
    named_count = 0
    review_payloads: list[dict] = []
    for r in reviews_sorted:
        text = r.get("review_text", "") or ""
        scs = tag_scenarios(text)
        for s in scs:
            scenario_counts[s] += 1
        by_name = mentions_by_name(rep["name"], text)
        if by_name:
            named_count += 1
        review_payloads.append({
            "text": text,
            "reviewer": r.get("reviewer_name", "").strip() or "DealerRater customer",
            "date": r.get("review_date", ""),
            "month_year": month_year(r.get("review_date", "")),
            "rating": r.get("overall_rating", "5"),
            "scenarios": scs,
            "by_name": by_name,
        })

    # Pills: All + Mentions-me (special) + each scenario that has ≥1 match
    pills_html = [
        f'<div class="pill active" data-scenario="all">All <span class="count">{len(review_payloads)}</span></div>'
    ]
    if named_count > 0:
        pills_html.append(
            f'<div class="pill pill-named" data-scenario="__named__">'
            f'✨ Mentions me by name <span class="count">{named_count}</span></div>'
        )
    for label in scenario_order:
        c = scenario_counts.get(label, 0)
        if c == 0:
            continue
        extra_cls = " pill-fan" if label == "Super Fan" else ""
        pills_html.append(
            f'<div class="pill{extra_cls}" data-scenario="{html.escape(label)}">'
            f'{scenario_emoji[label]} {html.escape(label)} <span class="count">{c}</span></div>'
        )

    # Review cards
    card_html = []
    for rp in review_payloads:
        stars = "★" * int(round(float(rp["rating"] or 5)))
        reviewer = html.escape(rp["reviewer"])
        my = html.escape(rp["month_year"])
        text = html.escape(rp["text"])
        scs = rp["scenarios"]
        scs_attr = html.escape("|".join(scs))

        scenario_tags_inner = "".join(
            f'<span class="scenario-tag">{scenario_emoji[s]} {html.escape(s)}</span>'
            for s in scs
        )
        if rp["by_name"]:
            scenario_tags = (
                '<span class="scenario-tag scenario-tag-named">✨ Mentions you</span>'
                + scenario_tags_inner
            )
        else:
            scenario_tags = scenario_tags_inner

        # Pre-format SMS snippet (short — target ~300 chars)
        excerpt = rp["text"].strip()
        if len(excerpt) > 220:
            excerpt = excerpt[:215].rstrip() + "…"
        sms_blurb = (
            f"Here's a real review of {rep['name']} at {DEALERSHIP}: "
            f'"{excerpt}" — {rp["reviewer"]}, {rp["month_year"]}. '
            f"More: {rep['dr_url']}"
        )
        email_body = (
            f"Hi,\n\n"
            f"Wanted to share a recent review from another {DEALERSHIP} customer "
            f"who was in a similar spot to you:\n\n"
            f'"{rp["text"].strip()}"\n'
            f'— {rp["reviewer"]}, {rp["month_year"]} (via DealerRater)\n\n'
            f"Happy to answer any questions or set up a time to chat.\n\n"
            f"{rep['name']}\n"
            f"{DEALERSHIP}\n"
            f"DealerRater profile: {rep['dr_url']}\n"
        )
        email_subject = f"A review from a recent {DEALERSHIP} customer"

        sms_url = "sms:?&body=" + _pct_encode(sms_blurb)
        mailto_url = (
            "mailto:?subject=" + _pct_encode(email_subject)
            + "&body=" + _pct_encode(email_body)
        )

        card_html.append(f"""
      <div class="review{' review-named' if rp['by_name'] else ''}" data-scenarios="{scs_attr}" data-named="{'1' if rp['by_name'] else '0'}">
        <div class="review-head">
          <span class="review-stars">{stars}</span>
          <span class="review-reviewer">{reviewer}</span>
          <span class="review-date">· {my}</span>
        </div>
        <div class="review-scenarios">{scenario_tags}</div>
        <div class="review-text">{text}</div>
        <div class="actions">
          <a class="btn primary" href="{html.escape(sms_url)}">
            <span class="ico">💬</span> Text
          </a>
          <a class="btn accent" href="{html.escape(mailto_url)}">
            <span class="ico">📧</span> Email
          </a>
          <button class="btn" data-copy="{html.escape(sms_blurb, quote=True)}">
            <span class="ico">📋</span> Copy text blurb
          </button>
          <button class="btn" data-copy="{html.escape(email_body, quote=True)}">
            <span class="ico">📋</span> Copy email body
          </button>
        </div>
      </div>""")

    qr = qr_svg(rep["dr_url"], box_size=3, border=1)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(rep["name"])} · Review Arsenal</title>
  <link rel="stylesheet" href="../assets/styles.css">
</head>
<body>
  <div class="container">
    <div class="rep-hero">
      {hero_avatar_html}
      <div>
        <h1 class="rep-hero-name">{html.escape(rep["name"])}</h1>
        <div class="rep-hero-sub">{DEALERSHIP} · DealerRater Reviews</div>
        <div class="rep-hero-stats">
          <span class="stat-pill"><span style="color:var(--star)">{avg_stars}</span> {rep["avg"]:.2f}★ avg</span>
          <span class="stat-pill">{rep["count"]} DR reviews</span>
          {f'<span class="stat-pill">✨ {named_count} mention you by name</span>' if named_count else ''}
        </div>
      </div>
      <div class="rep-hero-qr" title="Scan to open {html.escape(rep["name"])}'s DealerRater profile">
        {qr}
        <div class="rep-hero-qr-label">My DR Profile</div>
      </div>
    </div>

    <div class="pills">
      {"".join(pills_html)}
    </div>

    <div class="reviews">
      {"".join(card_html)}
    </div>

    <div class="empty" id="empty-state" style="display:none">
      <h3>Nothing matches that scenario yet.</h3>
      <p>Try a different filter, or use "All" to see every review.</p>
    </div>

    <div class="footer">
      Tap a scenario pill to filter · Tap <strong>Text</strong> or <strong>Email</strong> to send · Tap <strong>Copy</strong> to paste anywhere
    </div>
  </div>
  <script src="../assets/app.js"></script>
</body>
</html>"""


def _pct_encode(s: str) -> str:
    """URL-encode for sms: and mailto: body params."""
    from urllib.parse import quote
    return quote(s, safe="")


# ── README ───────────────────────────────────────────────────────────────────
README = f"""# DealerRater Review Arsenal — Digital Site

Static companion to the printed flipbook system. Every rep gets a standalone page with their reviews tagged by customer scenario and pre-formatted snippets they can fire off in one tap.

## What it is

- `index.html` — manager landing, grid of all reps.
- `reps/<slug>.html` — one per rep. **Bookmarkable** — no link back to home, so it can stand on its own as the rep's daily tool.
- `assets/styles.css`, `assets/app.js` — shared.
- Fully static. No backend. No external CDN.

## How reps use it

1. Bookmark their page on their phone's home screen.
2. During or after a customer appointment, filter by the scenario that matches (Trade-in, First-time, Credit, Family, EV, Switched, Price).
3. Tap **Text** → opens Messages pre-filled. Tap **Email** → opens Mail pre-filled. Tap **Copy** → pastes anywhere (CRM, DealerSocket, whatever).

## Deploy to GitHub Pages

### Option 1: Brand-new repo (simplest)

```bash
cd "{SITE_DIR.parent}/DR_Review_Arsenal_Site"
git init
git add .
git commit -m "Initial Review Arsenal site"
# Create a repo on github.com (e.g. winnipeg-hyundai/review-arsenal)
git remote add origin git@github.com:winnipeg-hyundai/review-arsenal.git
git push -u origin main
```

Then on GitHub: **Settings → Pages → Source: `main` / root → Save**. Site goes live at `https://<org>.github.io/review-arsenal/` in a minute or two.

### Option 2: Subfolder of an existing repo

Drop the folder into your repo under `/docs` (GitHub Pages can serve from `/docs` on main). Same settings path as above, but select `/docs`.

### Option 3: Custom domain

In **Settings → Pages**, add your domain and create a CNAME record pointing to `<org>.github.io`. Optionally add a `CNAME` file to this folder with the bare domain (e.g. `reviews.winnipeghyundai.ca`).

## Regenerate

Whenever the master CSV updates (after every DealerRater scrape + `build_arsenal.py` run):

```bash
cd "{SITE_DIR}"
python3 build_site.py
```

It reads `../DR_Review_Arsenal/data/dr_reviews_master.csv` and regenerates every page. Then commit + push to trigger a GH Pages redeploy.

## Customize

- **Scenarios and keywords** — edit `SCENARIOS` in `build_site.py` (top of file). Keep the 7 Mitch defined, or add more (e.g. "Luxury Trade", "Military", "Tech-first").
- **Rep QR URLs** — the `dr_employee_url()` function currently best-guesses the DR profile slug. Replace with real URLs once scraped (same TODO as the flipbook).
- **Brand colors** — CSS variables at the top of `assets/styles.css`.

## What's not in v1

- **Rep photos** — placeholder initials for now. Drop PNG files into `assets/photos/<slug>.png` and wire in later.
- **Share analytics** — no tracking of which blurbs get used. Could wire a click endpoint (Plausible, Umami) later.
- **Customer-facing pages** — this is for internal use. Public review pages live on DealerRater itself.
"""


# ── Main ─────────────────────────────────────────────────────────────────────
def main() -> None:
    ensure_clean(SITE_DIR)
    (SITE_DIR / ".nojekyll").touch()
    (SITE_DIR / "README.md").write_text(README, encoding="utf-8")
    (SITE_DIR / "assets" / "styles.css").write_text(COMMON_CSS, encoding="utf-8")
    (SITE_DIR / "assets" / "app.js").write_text(COMMON_JS, encoding="utf-8")

    reviews = load_reviews()
    print(f"  Loaded {len(reviews):,} reviews from master CSV.")

    by_rep = explode_by_rep(reviews)
    # Only publish reps with ≥3 reviews to keep quality high
    reps = [rep_summary(name, rs) for name, rs in by_rep.items() if len(rs) >= 3]
    reps.sort(key=lambda r: -r["count"])

    for rep_info in reps:
        rep_reviews = by_rep[rep_info["name"]]
        html_out = render_rep_page(rep_info, rep_reviews)
        (SITE_DIR / "reps" / f"{rep_info['slug']}.html").write_text(html_out, encoding="utf-8")
        vmark = "✓" if rep_info["dr_url_verified"] else "⚠"
        print(f"  → reps/{rep_info['slug']}.html  "
              f"({rep_info['count']} reviews, {rep_info['avg']:.2f}★)  [{vmark} DR url]")

    (SITE_DIR / "index.html").write_text(render_index(reps), encoding="utf-8")
    print(f"  → index.html  ({len(reps)} reps)")

    # Call out reps still using the fallback dealer URL for their QR
    missing = [r["name"] for r in reps if not r["dr_url_verified"]]
    if missing:
        print(f"\n  ⚠  {len(missing)} reps using dealer-page fallback for QR "
              f"(no verified DR profile URL):")
        for name in missing:
            print(f"       · {name}")
        print(f"     Add their URLs to DR_EMPLOYEE_URLS in build_site.py "
              f"when you have them.")

    print(f"\n✓ Site built at: {SITE_DIR}")


if __name__ == "__main__":
    main()
