# Deploying vik-isit

Split deployment: **frontend on Vercel**, **backend + database on Render**.
Both have permanent free tiers with this setup — no credit card required for
either. Total time: ~10 minutes of clicking through two dashboards.

Order matters: deploy the backend first (you need its URL for the frontend's
build-time env var), then the frontend, then go back and give the backend the
frontend's URL for CORS.

## 1. Backend + database — Render

1. Push this repo to GitHub (see the main [README](README.md) if you haven't).
2. On [render.com](https://render.com): **New > Blueprint**, pick this repo.
   Render reads [`render.yaml`](render.yaml) and provisions a free web service
   *and* a free Postgres database together, wired to each other automatically.
3. It'll prompt for one secret: **`ANTHROPIC_API_KEY`** — paste your Anthropic
   API key (get one at [console.anthropic.com](https://console.anthropic.com)).
   Leave `CORS_ORIGINS` blank for now, you'll set it in step 4.
4. Deploy. Once it's live, note the service URL — something like
   `https://vik-isit-api.onrender.com`.
5. Seed the database once, from your machine, pointed at the new Postgres —
   copy the **External Database URL** from the Render Postgres dashboard, then:

   ```bash
   DATABASE_URL="<external connection string from Render>" venv/Scripts/python -m app.seed_dashboard
   DATABASE_URL="<same>" venv/Scripts/python -m app.tier_a_pipeline
   DATABASE_URL="<same>" venv/Scripts/python -m app.tier_b_pipeline
   ```

   (Render's free web service can't run one-off shell commands, so this runs
   locally against the remote DB — a few seconds either way.)

**Free-tier note:** Render's free web service spins down after 15 minutes of
inactivity and takes ~30–60s to wake on the next request. Fine for a
portfolio/showcase link; if that first-load delay bothers you, Render's
Starter plan (~$7/mo) keeps it always-on.

## 2. Frontend — Vercel

1. On [vercel.com](https://vercel.com): **Add New > Project**, import this
   same GitHub repo.
2. Set **Root Directory** to `frontend` (Vercel auto-detects Vite once you do).
3. Add an environment variable: **`VITE_API_BASE_URL`** = your Render backend
   URL from step 1 (e.g. `https://vik-isit-api.onrender.com`, no trailing slash).
   This is baked in at *build* time, so it must be set before you deploy.
4. Deploy. Note the resulting URL — something like `https://vik-isit.vercel.app`.

`frontend/vercel.json` already handles client-side routing (React Router), so
deep links like `/summary` won't 404 on refresh.

## 3. Close the loop — CORS

Back on Render: open the `vik-isit-api` service → **Environment** → set
`CORS_ORIGINS` to your Vercel URL from step 2 (e.g.
`https://vik-isit.vercel.app`), save. Render redeploys automatically. Without
this step the frontend loads but every API call fails with a CORS error.

## Keeping data current after deploying

The [scheduled GitHub Actions workflow](.github/workflows/check-data-freshness.yml)
runs against the repo's curated CSVs, not the deployed database — it tells you
*what* to update. After editing a CSV and pushing, either:

- click **Sync Live Data** on the deployed frontend (calls `POST /sync` on
  the live backend, recomputes from the CSVs now baked into the latest
  deploy), or
- Render auto-redeploys on push to `main` by default, which picks up the new
  CSVs; then hit Sync once it's live.

## Custom domain (optional)

Both Render and Vercel support attaching your own domain for free (you pay
only the registrar for the domain itself) — Vercel: Project → Settings →
Domains; Render: service → Settings → Custom Domains.
