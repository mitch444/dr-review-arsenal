# DealerRater Review Arsenal — Digital Site

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
cd "/sessions/amazing-bold-sagan/mnt/Blink Intelligence/DR_Review_Arsenal_Site"
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
cd "/sessions/amazing-bold-sagan/mnt/Blink Intelligence/DR_Review_Arsenal_Site"
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
