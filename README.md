# First Glance · The Macro Matrix

Morning macro dashboard — regenerated every weekday at 07:00 CET via GitHub Actions.  
Live view → **GitHub Pages** at `https://<your-username>.github.io/<repo-name>/`

---

## What it shows

| Section | Tickers | Derived signals |
|---|---|---|
| I. Sovereign Fixed Income | ^IRX ^FVX ^TNX ^TYX + EU futures | 5s30s slope, 3M–10Y slope, BTP/OAT–Bund proxies |
| II. Credit Markets | LQD HYG EMB IEI TLT + EU UCITS | HYG/IEI credit appetite, EMB/TLT EM distress |
| III. Equity Sectors | 11 SPDR sectors + IWD/IWF | XLY/XLP cyclicals, Value/Growth, Duration play |
| IV. FX & Liquidity | DXY USDJPY USDCNH AUDJPY + EM FX + VIX/MOVE | — |
| V. Commodities | HG GC CL BZ | Copper/Gold ratio (Gundlach) |

---

## Local setup

```bash
pip install -r requirements.txt
python generate.py
# opens index.html in the same folder
```

---

## GitHub Pages setup (one-time)

1. Push this repo to GitHub
2. Go to **Settings → Pages → Source** → set to `main` branch, root `/`
3. The workflow runs automatically Mon–Fri at 06:00 UTC, commits `index.html`, and Pages refreshes within ~1 min

To trigger manually: **Actions → First Glance · Daily Refresh → Run workflow**
