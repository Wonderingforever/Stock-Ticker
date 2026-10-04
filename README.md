# Market Dashboard Setup

Files:
- `index.html` — GitHub Pages dashboard
- `scripts/update_market_data.py` — fetches current/day + historical returns
- `.github/workflows/update-market-data.yml` — scheduled GitHub Action
- `data/market-data.json` — generated data file

## Setup

1. Put these files in your GitHub repository, preserving the folders.
2. Rotate the Finnhub API key that was previously exposed.
3. In GitHub, go to:
   Settings -> Secrets and variables -> Actions -> New repository secret
4. Create a secret named:
   FINNHUB_KEY
5. Paste your new Finnhub key as the secret value.
6. Go to:
   Actions -> Update market dashboard -> Run workflow
7. Wait for the workflow to finish. It will populate `data/market-data.json`.
8. Enable GitHub Pages:
   Settings -> Pages -> Deploy from a branch -> main -> /(root)

The scheduled workflow runs on weekdays after the regular US market close.

Historical returns are calculated from server-side daily market history. The browser does not call the historical provider, which avoids the CORS problem you hit before.
