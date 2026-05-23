"""
First Glance: The Macro Matrix
==============================
Fetches market data via yfinance, calculates macro indicators,
and renders a WSJ-vintage styled HTML dashboard (index.html).

Run manually:  python generate.py
Auto-run:      GitHub Actions cron @ 06:00 UTC (07:00 CET)
"""

import base64
import os
import warnings
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

LOGO_PATH = Path(__file__).parent / "first_glance.png"
OUTPUT_PATH = Path(__file__).parent / "index.html"

# ETF proxies for top-5 mover sections
TOP5_ETFS = {
    "S&P 500":           "SPY",
    "EuroStoxx 600":     "EXW1.DE",
    "MSCI Emerg. Mkts":  "EEM",
}

TICKERS = {
    "us_rates":    ["^IRX", "^FVX", "^TNX", "^TYX"],
    "eu_sovs":     ["IBGM.L", "IFRB.L", "IITB.L"],
    "credit":      ["LQD", "HYG", "EMB", "IEI", "TLT", "IEAC.L", "IEGA.L"],
    "equity":      ["XLK", "XLF", "XLI", "XLB", "XLY", "XLE", "XLC",
                    "XLP", "XLV", "XLU", "XLRE", "IWF", "IWD"],
    "asia":        ["^N225", "1306.T", "^HSI", "000001.SS", "000300.SS", "^KS11"],
    "fx":          ["DX-Y.NYB", "USDJPY=X", "USDCNH=X", "AUDJPY=X",
                    "USDMXN=X", "USDBRL=X", "EURPLN=X", "USDPLN=X",
                    "^VIX", "^MOVE"],
    "commodities": ["HG=F", "GC=F", "CL=F", "BZ=F"],
}

NAMES = {
    "^IRX": "3M T-Bill", "^FVX": "5Y Note",
    "^TNX": "10Y Note",  "^TYX": "30Y Bond",
    "IBGM.L": "Germany Govt Bond ETF",
    "IFRB.L": "France Govt Bond ETF",
    "IITB.L": "Italy Govt Bond ETF",
    "LQD": "US IG Corporate", "HYG": "US High Yield",
    "EMB": "EM Hard Currency", "IEI": "US Treasury 3-7Y",
    "TLT": "US Treasury 20Y+",
    "IEAC.L": "EUR Corporate Bond", "IEGA.L": "EUR Govt Bond (Core)",
    "XLK": "Technology",   "XLF": "Financials",
    "XLI": "Industrials",  "XLB": "Materials",
    "XLY": "Consumer Disc.", "XLE": "Energy",
    "XLC": "Communication", "XLP": "Consumer Staples",
    "XLV": "Health Care",   "XLU": "Utilities",
    "XLRE": "Real Estate",
    "IWF": "Russell 1000 Growth", "IWD": "Russell 1000 Value",
    "^N225":    "Nikkei 225",
    "1306.T":   "TOPIX (ETF proxy)",
    "^HSI":     "Hang Seng",
    "000001.SS":"Shanghai Comp.",
    "000300.SS":"CSI 300",
    "^KS11":    "KOSPI",
    "DX-Y.NYB": "US Dollar Index",
    "USDJPY=X": "USD/JPY", "USDCNH=X": "USD/CNH",
    "AUDJPY=X": "AUD/JPY",
    "USDMXN=X": "USD/MXN", "USDBRL=X": "USD/BRL",
    "EURPLN=X": "EUR/PLN", "USDPLN=X": "USD/PLN",
    "^VIX": "VIX (Equity Vol)", "^MOVE": "MOVE (Rates Vol)",
    "HG=F": "Copper", "GC=F": "Gold",
    "CL=F": "WTI Crude", "BZ=F": "Brent Crude",
}

SECTOR_ROLE = {
    "XLK": "cyc", "XLF": "cyc", "XLI": "cyc", "XLB": "cyc",
    "XLY": "cyc", "XLE": "cyc", "XLC": "cyc",
    "XLP": "def", "XLV": "def", "XLU": "def", "XLRE": "def",
}

# NewsAPI — set NEWSAPI_KEY env var to enable the news section
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
NEWS_HOURS_BACK = 12
NEWS_SOURCES = "reuters,cnbc,business-insider,bloomberg,the-wall-street-journal,financial-times,marketwatch"

# ---------------------------------------------------------------------------
# NEWS FETCH
# ---------------------------------------------------------------------------

def fetch_news(hours_back=NEWS_HOURS_BACK):
    """Fetch financial market news from the last N hours via NewsAPI."""
    if not NEWSAPI_KEY:
        print("  NEWS: NEWSAPI_KEY not set — skipping news section.")
        return []
    try:
        from newsapi import NewsApiClient
        api   = NewsApiClient(api_key=NEWSAPI_KEY)
        cet   = timezone(timedelta(hours=1))
        from_dt = datetime.now(tz=cet) - timedelta(hours=hours_back)

        resp = api.get_everything(
            q='(markets OR stocks OR bonds OR "interest rates" OR forex OR economy OR "central bank" OR equities)',
            sources=NEWS_SOURCES,
            from_param=from_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            language="en",
            sort_by="publishedAt",
            page_size=12,
        )
        articles = resp.get("articles", [])
        print(f"  NEWS: {len(articles)} articles from last {hours_back}h")
        return articles
    except Exception as e:
        print(f"  NEWS: ERROR - {e}")
        return []


# ---------------------------------------------------------------------------
# DATA FETCH
# ---------------------------------------------------------------------------

def fetch_all():
    all_tickers = []
    for group in TICKERS.values():
        all_tickers.extend(group)

    print(f"Fetching {len(all_tickers)} tickers...")
    raw = yf.download(
        tickers=all_tickers, period="20d", interval="1d",
        auto_adjust=True, progress=False, threads=True,
    )
    closes = raw["Close"] if isinstance(raw.columns, pd.Index) else raw.xs("Close", axis=1, level=0)

    data = {}
    for t in all_tickers:
        try:
            s = closes[t].dropna()
            if len(s) >= 2:
                data[t] = s
        except Exception:
            pass
    print(f"  Got data for {len(data)}/{len(all_tickers)} tickers.")
    return data


def fetch_top5_movers():
    """Use ETF top holdings to find best 1W performers per index."""
    result = {}
    for label, etf in TOP5_ETFS.items():
        try:
            holdings = yf.Ticker(etf).get_funds_data().top_holdings
            if holdings is None or len(holdings) == 0:
                continue
            syms = list(holdings.index)
            names_map = dict(zip(holdings.index, holdings["Name"]))

            raw = yf.download(
                tickers=syms, period="ytd", interval="1d",
                auto_adjust=True, progress=False, threads=True,
            )
            try:
                closes = raw["Close"] if isinstance(raw.columns, pd.Index) else raw.xs("Close", axis=1, level=0)
            except Exception:
                closes = raw["Close"]

            rows = []
            for sym in syms:
                try:
                    s = closes[sym].dropna()
                    if len(s) >= 6:
                        ret_1w  = (s.iloc[-1] - s.iloc[-6]) / s.iloc[-6] * 100
                        ret_1d  = (s.iloc[-1] - s.iloc[-2]) / s.iloc[-2] * 100
                        ret_ytd = (s.iloc[-1] - s.iloc[0])  / s.iloc[0]  * 100
                        rows.append({
                            "symbol":  sym,
                            "name":    names_map.get(sym, sym),
                            "ret_1w":  ret_1w,
                            "ret_1d":  ret_1d,
                            "ret_ytd": ret_ytd,
                        })
                except Exception:
                    pass

            # Sort by 1W return descending; None-safe
            rows.sort(key=lambda x: x["ret_1w"] if x["ret_1w"] is not None else -9999,
                      reverse=True)
            result[label] = rows[:5]
            print(f"  Top5 {label}: OK ({len(rows)} holdings ranked by 1W)")
        except Exception as e:
            print(f"  Top5 {label}: ERROR - {e}")
    return result


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def get_price(data, ticker):
    if ticker not in data:
        return None
    return float(data[ticker].iloc[-1])

def get_delta_1d(data, ticker):
    if ticker not in data or len(data[ticker]) < 2:
        return None
    s = data[ticker]
    return (s.iloc[-1] - s.iloc[-2]) / s.iloc[-2] * 100

def get_delta_1w(data, ticker):
    if ticker not in data or len(data[ticker]) < 6:
        return None
    s = data[ticker]
    return (s.iloc[-1] - s.iloc[-6]) / s.iloc[-6] * 100

def get_yield_1w_ago(data, ticker):
    if ticker not in data or len(data[ticker]) < 6:
        return None
    return float(data[ticker].iloc[-6])

def fmt_price(v, decimals=2):
    if v is None: return "&mdash;"
    if v > 10000: return f"{v:,.0f}"
    if v > 1000: return f"{v:,.2f}"
    return f"{v:.{decimals}f}"

def fmt_pct(v, decimals=2):
    if v is None: return "&mdash;"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"

def fmt_bps(v_pct_points):
    if v_pct_points is None: return "&mdash;"
    bps = v_pct_points * 100
    sign = "+" if bps >= 0 else ""
    return f"{sign}{bps:.0f} bps"

def pct_cls(v):
    if v is None: return "neu"
    return "up" if v > 0 else ("down" if v < 0 else "neu")

def badge(label, cls):
    return f'<span class="badge {cls}">{label}</span>'

def section_head(title, colspan=5):
    return f'<tr class="section-head"><td colspan="{colspan}">{title}</td></tr>'

def tr_row(ticker, label, price_str, d1_str, d1_cls, d1w_str, d1w_cls, extra="", row_cls=""):
    return f"""
      <tr class="{row_cls}">
        <td class="ticker">{ticker}</td><td class="label">{label}</td>
        <td class="r">{price_str}</td>
        <td class="r {d1_cls}">{d1_str}</td>
        <td class="r {d1w_cls}">{d1w_str}</td>
        {extra}
      </tr>"""

def tr_derived(label, val_str, bdg, colspan_l=3, colspan_r=2):
    return f"""
      <tr class="derived">
        <td colspan="{colspan_l}" class="ticker">{label}</td>
        <td class="r" colspan="{colspan_r}">{val_str} {bdg}</td>
      </tr>"""

# ---------------------------------------------------------------------------
# DERIVED INDICATORS (both 1D and 1W)
# ---------------------------------------------------------------------------

def _spread_signal(val, key):
    """Return (val_str, badge_cls, tag) for a given regime key and value."""
    if val is None:
        return "&mdash;", "neutral", "&mdash;"

    if key == "3m10y":
        v_str = fmt_bps(val / 100)
        if val < 0:
            return v_str, "risk-off", "Inverted &middot; Recession Watch"
        return v_str, "risk-on", "Normal &middot; Expansion"

    if key == "5s30s":
        v_str = fmt_bps(val / 100)
        if val > 30:
            return v_str, "risk-on", "Steepening &middot; Reflation"
        if val < 10:
            return v_str, "neutral", "Flat / Inverted Belly"
        return v_str, "neutral", "Moderate Slope"

    if key == "btp_bund":
        v_str = fmt_pct(val)
        if val < 0:
            return v_str, "risk-off", "Spreads Widening &middot; Peripheral Stress"
        return v_str, "risk-on", "Spreads Narrowing &middot; Stable"

    if key == "oat_bund":
        v_str = fmt_pct(val)
        if val < 0:
            return v_str, "risk-off", "OAT&ndash;Bund Widening &middot; France Risk"
        return v_str, "neutral", "OAT&ndash;Bund Stable"

    if key == "hyg_iei":
        v_str = fmt_pct(val)
        if val > 0:
            return v_str, "risk-on", "Spreads Narrowing &middot; Risk Appetite"
        return v_str, "risk-off", "Spreads Widening &middot; De-Risking"

    if key == "emb_tlt":
        v_str = fmt_pct(val)
        if val > 0:
            return v_str, "risk-on", "EM Outperforming &middot; Capital Inflows"
        return v_str, "risk-off", "EM Distress &middot; Capital Flight"

    if key == "xly_xlp":
        v_str = fmt_pct(val)
        if val > 0:
            return v_str, "risk-on", "Cyclicals Leading &middot; Risk-On"
        return v_str, "risk-off", "Defensives Leading &middot; Risk-Off"

    if key == "iwf_iwd":
        v_str = fmt_pct(val)
        if val > 0:
            return v_str, "risk-on", "Growth Leading &middot; Duration Bet"
        return v_str, "neutral", "Value Leading &middot; Rate Sensitive"

    if key == "cu_au":
        v_str = fmt_pct(val)
        if val > 0:
            return v_str, "risk-on", "Growth Signal &middot; Yields Rising"
        return v_str, "risk-off", "Recession Signal &middot; Yields Falling"

    if key == "audjpy":
        v_str = fmt_pct(val)
        if val > 0:
            return v_str, "risk-on", "Carry Trade Alive &middot; Risk Appetite"
        return v_str, "risk-off", "Carry Unwind &middot; Risk-Off"

    return fmt_pct(val), "neutral", "&mdash;"


def _score(v, key):
    """Assign risk-on score: +1 risk-on, -1 risk-off, 0 neutral."""
    if v is None:
        return 0
    if key == "3m10y":
        return 1 if v > 0 else -1
    if key == "5s30s":
        return 0.5 if v > 20 else (-0.5 if v < 0 else 0)
    if key in ("btp_bund", "oat_bund", "hyg_iei", "emb_tlt",
               "xly_xlp", "iwf_iwd", "cu_au", "audjpy"):
        return 1 if v > 0 else -1
    return 0


REGIME_KEYS = [
    ("3m10y",    "3M&ndash;10Y Spread"),
    ("5s30s",    "5s30s Spread"),
    ("hyg_iei",  "HYG / IEI"),
    ("emb_tlt",  "EMB / TLT"),
    ("xly_xlp",  "XLY / XLP"),
    ("iwf_iwd",  "IWF / IWD"),
    ("cu_au",    "Cu / Au"),
    ("audjpy",   "AUD/JPY"),
]


def calc_derived(data, timeframe="1d"):
    """Calculate regime signals. timeframe = '1d' or '1w'."""
    delta = get_delta_1d if timeframe == "1d" else get_delta_1w
    d = {}

    irx = get_price(data, "^IRX")
    fvx = get_price(data, "^FVX")
    tnx = get_price(data, "^TNX")
    tyx = get_price(data, "^TYX")

    if fvx and tyx:
        d["5s30s"] = tyx - fvx
        if timeframe == "1w":
            prev_fvx = get_yield_1w_ago(data, "^FVX") or fvx
            prev_tyx = get_yield_1w_ago(data, "^TYX") or tyx
            d["5s30s"] = (tyx - fvx)   # current spread
            d["5s30s_delta"] = (tyx - fvx) - (prev_tyx - prev_fvx)
        else:
            prev_fvx = float(data["^FVX"].iloc[-2]) if "^FVX" in data else fvx
            prev_tyx = float(data["^TYX"].iloc[-2]) if "^TYX" in data else tyx
            d["5s30s_delta"] = (tyx - fvx) - (prev_tyx - prev_fvx)

    if irx and tnx:
        d["3m10y"] = tnx - irx

    btp = delta(data, "IITB.L")
    bund = delta(data, "IBGM.L")
    oat  = delta(data, "IFRB.L")
    if btp is not None and bund is not None:
        d["btp_bund"] = btp - bund
    if oat is not None and bund is not None:
        d["oat_bund"] = oat - bund

    hyg = delta(data, "HYG")
    iei = delta(data, "IEI")
    if hyg is not None and iei is not None:
        d["hyg_iei"] = hyg - iei

    emb = delta(data, "EMB")
    tlt = delta(data, "TLT")
    if emb is not None and tlt is not None:
        d["emb_tlt"] = emb - tlt

    xly = delta(data, "XLY")
    xlp = delta(data, "XLP")
    if xly is not None and xlp is not None:
        d["xly_xlp"] = xly - xlp

    # IWF / IWD: Growth vs Value  (positive = growth leading = risk-on)
    iwf = delta(data, "IWF")
    iwd = delta(data, "IWD")
    if iwf is not None and iwd is not None:
        d["iwf_iwd"] = iwf - iwd

    hg = delta(data, "HG=F")
    gc = delta(data, "GC=F")
    if hg is not None and gc is not None:
        d["cu_au"] = hg - gc

    audjpy = delta(data, "AUDJPY=X")
    if audjpy is not None:
        d["audjpy"] = audjpy

    # Composite risk-appetite score [0-100], 50 = neutral
    scores = [_score(d.get(k), k) for k, _ in REGIME_KEYS]
    valid = [s for s in scores if s != 0]
    if valid:
        raw = sum(valid) / len(REGIME_KEYS)   # -1..+1
        d["score"] = round((raw + 1) / 2 * 100)   # 0..100
    else:
        d["score"] = 50

    return d


# ---------------------------------------------------------------------------
# SCORE BAR SVG (replaces speedometer)
# ---------------------------------------------------------------------------

def render_bar(score_1d, score_1w):
    """
    Render two horizontal score bars (1D and 1W).
    score: 0 (full risk-off) to 100 (full risk-on), displayed as 0.0–10.0.
    """
    BAR_X   = 26   # left edge of bar
    BAR_W   = 140  # bar width
    BAR_H   = 10   # bar height
    ROW_H   = 26   # vertical spacing between rows
    W_TOTAL = 195  # total SVG width

    def mood_color(score):
        if score >= 70:  return "#1a5c1a"
        if score <= 30:  return "#8b1a1a"
        return "#666"

    def mood_label(score):
        if score >= 70:  return "Risk-On"
        if score <= 30:  return "Risk-Off"
        return "Neutral"

    def bar_row(score, label, y):
        score = max(0, min(100, score))
        pos   = BAR_X + (score / 100) * BAR_W
        col   = mood_color(score)
        mood  = mood_label(score)
        disp  = f"{score / 10:.1f}"
        return f"""
  <text x="2" y="{y + BAR_H - 0.5:.1f}" font-family="Georgia,serif" font-size="6.5"
        font-weight="700" fill="#999">{label}</text>
  <rect x="{BAR_X}" y="{y}" width="{BAR_W}" height="{BAR_H}" rx="2" fill="url(#bg)"/>
  <circle cx="{pos:.1f}" cy="{y + BAR_H / 2:.1f}" r="5" fill="{col}" stroke="#fff" stroke-width="1.2"/>
  <text x="{BAR_X + BAR_W + 6}" y="{y + BAR_H - 0.5:.1f}" font-family="Georgia,serif"
        font-size="9" font-weight="bold" fill="{col}">{disp}</text>
  <text x="{BAR_X + BAR_W + 6}" y="{y + BAR_H + 8:.1f}" font-family="Georgia,serif"
        font-size="6" fill="{col}" font-style="italic">{mood}</text>"""

    rows = bar_row(score_1d, "1D", 4) + bar_row(score_1w, "1W", 4 + ROW_H)
    h_total = 4 + 2 * ROW_H + 4

    # tick positions
    mid_x = BAR_X + BAR_W / 2
    tick_y = h_total - 1

    return f"""<svg viewBox="0 0 {W_TOTAL} {h_total}" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-width:{W_TOTAL}px;display:block">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="#8b1a1a" stop-opacity="0.80"/>
      <stop offset="30%"  stop-color="#c06060" stop-opacity="0.55"/>
      <stop offset="50%"  stop-color="#cccccc" stop-opacity="0.40"/>
      <stop offset="70%"  stop-color="#60a060" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="#1a5c1a" stop-opacity="0.80"/>
    </linearGradient>
  </defs>
  {rows}
  <text x="{BAR_X}" y="{tick_y}" font-family="Georgia,serif" font-size="5.5"
        fill="#bbb" text-anchor="middle">0</text>
  <text x="{mid_x:.1f}" y="{tick_y}" font-family="Georgia,serif" font-size="5.5"
        fill="#bbb" text-anchor="middle">5</text>
  <text x="{BAR_X + BAR_W}" y="{tick_y}" font-family="Georgia,serif" font-size="5.5"
        fill="#bbb" text-anchor="middle">10</text>
</svg>"""


# ---------------------------------------------------------------------------
# HTML PANELS
# ---------------------------------------------------------------------------

def _table_header(cols):
    ths = "".join(f'<th class="r">{c}</th>' if c not in ("Ticker", "Instrument", "Signal Role", "Company") else f"<th>{c}</th>" for c in cols)
    return f"<tr>{ths}</tr>"


def build_panel_fixed_income(data, d1d, d1w):
    # US rates rows (yield display)
    us_rows = ""
    for t in TICKERS["us_rates"]:
        p = get_price(data, t)
        dd = get_delta_1d(data, t)
        dw = get_delta_1w(data, t)
        p_str = f"{p:.2f}%" if p else "&mdash;"
        us_rows += tr_row(t, NAMES[t], p_str,
                          fmt_bps(dd / 100 if dd else None), pct_cls(dd),
                          fmt_bps(dw / 100 if dw else None), pct_cls(dw))

    s30s = d1d.get("5s30s"); m10y = d1d.get("3m10y")
    s30s_str = fmt_bps(s30s / 100) if s30s is not None else "&mdash;"
    m10y_str = fmt_bps(m10y / 100) if m10y is not None else "&mdash;"

    eu_rows = ""
    for t in TICKERS["eu_sovs"]:
        p = get_price(data, t)
        dd = get_delta_1d(data, t); dw = get_delta_1w(data, t)
        eu_rows += tr_row(t, NAMES[t], fmt_price(p),
                          fmt_pct(dd), pct_cls(dd), fmt_pct(dw), pct_cls(dw))

    btp_1d = d1d.get("btp_bund"); oat_1d = d1d.get("oat_bund")
    btp_1w = d1w.get("btp_bund"); oat_1w = d1w.get("oat_bund")
    _, btp_cls, btp_tag = _spread_signal(btp_1d, "btp_bund")
    _, oat_cls, oat_tag = _spread_signal(oat_1d, "oat_bund")

    return f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">I.</span>
        <span class="p-title">Sovereign Fixed Income</span>
        <span class="p-sub">Rates &amp; Spread Proxies</span>
      </div>
      <table class="data-table">
        {_table_header(["Ticker","Instrument","Level","1D","1W"])}
        {section_head("US Term Structure")}
        {us_rows}
        {tr_derived("5s30s Slope", s30s_str, badge("Steepener" if (s30s or 0)>20 else "Flat","risk-on" if (s30s or 0)>20 else "neutral"))}
        {tr_derived("3M-10Y Slope", m10y_str, badge("Inverted","risk-off") if (m10y or 0)<0 else badge("Normal","risk-on"))}
        {section_head("Europe - Govt Bond ETFs")}
        {eu_rows}
        {tr_derived("BTP-Bund Proxy (1D/1W)", f"{fmt_pct(btp_1d)} / {fmt_pct(btp_1w)}", badge(btp_tag, btp_cls))}
        {tr_derived("OAT-Bund Proxy (1D/1W)", f"{fmt_pct(oat_1d)} / {fmt_pct(oat_1w)}", badge(oat_tag, oat_cls))}
      </table>
    </div>"""


def build_panel_credit(data, d1d, d1w):
    rows = ""
    for t in ["LQD", "HYG", "EMB", "IEI", "TLT"]:
        p = get_price(data, t); dd = get_delta_1d(data, t); dw = get_delta_1w(data, t)
        rows += tr_row(t, NAMES[t], fmt_price(p),
                       fmt_pct(dd), pct_cls(dd), fmt_pct(dw), pct_cls(dw))

    hyg_1d = d1d.get("hyg_iei"); hyg_1w = d1w.get("hyg_iei")
    emb_1d = d1d.get("emb_tlt"); emb_1w = d1w.get("emb_tlt")
    _, hyg_cls, hyg_tag = _spread_signal(hyg_1d, "hyg_iei")
    _, emb_cls, emb_tag = _spread_signal(emb_1d, "emb_tlt")

    eu_rows = ""
    for t in ["IEAC.L", "IEGA.L"]:
        p = get_price(data, t); dd = get_delta_1d(data, t); dw = get_delta_1w(data, t)
        eu_rows += tr_row(t, NAMES[t], fmt_price(p),
                          fmt_pct(dd), pct_cls(dd), fmt_pct(dw), pct_cls(dw))

    return f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">II.</span>
        <span class="p-title">Credit Markets</span>
        <span class="p-sub">Risk Premiums &amp; EM</span>
      </div>
      <table class="data-table">
        {_table_header(["Ticker","Instrument","Price","1D","1W"])}
        {section_head("US Credit ETFs")}
        {rows}
        {tr_derived("HYG/IEI - Credit Appetite (1D/1W)", f"{fmt_pct(hyg_1d)} / {fmt_pct(hyg_1w)}", badge(hyg_tag, hyg_cls))}
        {tr_derived("EMB/TLT - EM Distress (1D/1W)",     f"{fmt_pct(emb_1d)} / {fmt_pct(emb_1w)}", badge(emb_tag, emb_cls))}
        {section_head("Europe Credit (UCITS)")}
        {eu_rows}
      </table>
    </div>"""


def build_panel_fx(data):
    def fx_rows_block(tickers, decimals_map=None):
        out = ""
        for t in tickers:
            p = get_price(data, t); dd = get_delta_1d(data, t); dw = get_delta_1w(data, t)
            dec = (decimals_map or {}).get(t, 4)
            out += tr_row(t, NAMES[t], fmt_price(p, dec),
                          fmt_pct(dd), pct_cls(dd), fmt_pct(dw), pct_cls(dw))
        return out

    dec = {"DX-Y.NYB": 2, "USDJPY=X": 2, "AUDJPY=X": 2,
           "USDMXN=X": 4, "USDBRL=X": 4, "EURPLN=X": 4, "USDPLN=X": 4,
           "^VIX": 2, "^MOVE": 2}

    return f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">IV.</span>
        <span class="p-title">FX &amp; Global Liquidity</span>
        <span class="p-sub">Capital Flow Signals</span>
      </div>
      <table class="data-table">
        {_table_header(["Ticker","Instrument","Rate","1D","1W"])}
        {section_head("Key Pairs")}
        {fx_rows_block(["DX-Y.NYB","USDJPY=X","USDCNH=X","AUDJPY=X"], dec)}
        {section_head("EM / CEE FX")}
        {fx_rows_block(["USDMXN=X","USDBRL=X","EURPLN=X","USDPLN=X"], dec)}
        {section_head("Volatility")}
        {fx_rows_block(["^VIX","^MOVE"], dec)}
      </table>
    </div>"""


def build_panel_asia(data):
    rows = ""
    for t in TICKERS["asia"]:
        p = get_price(data, t); dd = get_delta_1d(data, t); dw = get_delta_1w(data, t)
        rows += tr_row(t, NAMES[t], fmt_price(p, 2),
                       fmt_pct(dd), pct_cls(dd), fmt_pct(dw), pct_cls(dw))
    return f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">V.</span>
        <span class="p-title">Asian Equity Markets</span>
        <span class="p-sub">Japan &middot; China/HK &middot; Korea</span>
      </div>
      <table class="data-table">
        {_table_header(["Ticker","Index","Level","1D","1W"])}
        {section_head("Japan")}
        {tr_row("^N225",    NAMES["^N225"],    fmt_price(get_price(data,"^N225"),2), fmt_pct(get_delta_1d(data,"^N225")), pct_cls(get_delta_1d(data,"^N225")), fmt_pct(get_delta_1w(data,"^N225")), pct_cls(get_delta_1w(data,"^N225")))}
        {tr_row("1306.T",   NAMES["1306.T"],   fmt_price(get_price(data,"1306.T"),2), fmt_pct(get_delta_1d(data,"1306.T")), pct_cls(get_delta_1d(data,"1306.T")), fmt_pct(get_delta_1w(data,"1306.T")), pct_cls(get_delta_1w(data,"1306.T")))}
        {section_head("China / Hong Kong")}
        {tr_row("000001.SS", NAMES["000001.SS"], fmt_price(get_price(data,"000001.SS"),2), fmt_pct(get_delta_1d(data,"000001.SS")), pct_cls(get_delta_1d(data,"000001.SS")), fmt_pct(get_delta_1w(data,"000001.SS")), pct_cls(get_delta_1w(data,"000001.SS")))}
        {tr_row("000300.SS", NAMES["000300.SS"], fmt_price(get_price(data,"000300.SS"),2), fmt_pct(get_delta_1d(data,"000300.SS")), pct_cls(get_delta_1d(data,"000300.SS")), fmt_pct(get_delta_1w(data,"000300.SS")), pct_cls(get_delta_1w(data,"000300.SS")))}
        {tr_row("^HSI",     NAMES["^HSI"],     fmt_price(get_price(data,"^HSI"),2), fmt_pct(get_delta_1d(data,"^HSI")), pct_cls(get_delta_1d(data,"^HSI")), fmt_pct(get_delta_1w(data,"^HSI")), pct_cls(get_delta_1w(data,"^HSI")))}
        {section_head("Korea")}
        {tr_row("^KS11",    NAMES["^KS11"],    fmt_price(get_price(data,"^KS11"),2), fmt_pct(get_delta_1d(data,"^KS11")), pct_cls(get_delta_1d(data,"^KS11")), fmt_pct(get_delta_1w(data,"^KS11")), pct_cls(get_delta_1w(data,"^KS11")))}
      </table>
    </div>"""


def build_panel_equity(data, d1d, d1w):
    # Sector cells — 1D row + 1W row
    sectors = ["XLK","XLF","XLI","XLB","XLY","XLE","XLC",
               "XLP","XLV","XLU","XLRE"]

    def sector_cells(delta_fn):
        out = ""
        for t in sectors:
            v = delta_fn(data, t)
            role = SECTOR_ROLE.get(t, "cyc")
            cls = pct_cls(v)
            out += f"""
        <div class="sector-cell {role}">
          <span class="s-tick">{t}</span>
          <span class="s-name">{NAMES[t]}</span>
          <span class="s-val {cls}">{fmt_pct(v)}</span>
        </div>"""
        return out

    xly_1d = d1d.get("xly_xlp"); xly_1w = d1w.get("xly_xlp")
    iwf_1d = d1d.get("iwf_iwd"); iwf_1w = d1w.get("iwf_iwd")
    xlk_1d = get_delta_1d(data,"XLK"); xli_1d = get_delta_1d(data,"XLI")
    xlk_1w = get_delta_1w(data,"XLK"); xli_1w = get_delta_1w(data,"XLI")
    dur_1d = (xlk_1d - xli_1d) if xlk_1d is not None and xli_1d is not None else None
    dur_1w = (xlk_1w - xli_1w) if xlk_1w is not None and xli_1w is not None else None

    _, xly_cls, xly_tag = _spread_signal(xly_1d, "xly_xlp")
    _, iwf_cls, iwf_tag = _spread_signal(iwf_1d, "iwf_iwd")

    return f"""
    <div class="panel panel-wide">
      <div class="panel-header">
        <span class="p-num">III.</span>
        <span class="p-title">US Equity Sector &amp; Factor Rotation</span>
        <span class="p-sub">SPDR Sectors &middot; Cyclical vs Defensive</span>
      </div>
      <div class="sector-label-row">
        <span class="sector-timeframe-label">1D</span>
      </div>
      <div class="sectors-grid">
        {sector_cells(get_delta_1d)}
      </div>
      <div class="sector-label-row">
        <span class="sector-timeframe-label">1W</span>
      </div>
      <div class="sectors-grid sectors-grid-1w">
        {sector_cells(get_delta_1w)}
      </div>
      <div class="ratios-row">
        <div class="ratio-cell">
          <div class="rc-label">XLY / XLP &middot; Cyclicals vs Defensives</div>
          <div class="rc-val {pct_cls(xly_1d)}">
            1D: {fmt_pct(xly_1d)} &nbsp; 1W: {fmt_pct(xly_1w)}
            {badge(xly_tag, xly_cls)}
          </div>
        </div>
        <div class="ratio-cell">
          <div class="rc-label">IWF / IWD &middot; Growth vs Value</div>
          <div class="rc-val {pct_cls(iwf_1d)}">
            1D: {fmt_pct(iwf_1d)} &nbsp; 1W: {fmt_pct(iwf_1w)}
            {badge(iwf_tag, iwf_cls)}
          </div>
        </div>
        <div class="ratio-cell">
          <div class="rc-label">XLK / XLI &middot; Duration Play</div>
          <div class="rc-val {pct_cls(dur_1d)}">
            1D: {fmt_pct(dur_1d)} &nbsp; 1W: {fmt_pct(dur_1w)}
            {badge("Tech vs Industrial","neutral")}
          </div>
        </div>
      </div>
    </div>"""


def build_panel_commodities(data, d1d, d1w):
    comm_roles = {
        "HG=F": "Global PMI / China Demand Proxy",
        "GC=F": "Real Rate Proxy / Geopolitical Risk",
        "CL=F": "Cost-Push Inflation / OPEC Policy",
        "BZ=F": "Global Benchmark",
    }
    rows = ""
    for t in TICKERS["commodities"]:
        p = get_price(data, t); dd = get_delta_1d(data, t); dw = get_delta_1w(data, t)
        extra = f'<td class="role-col">{comm_roles[t]}</td>'
        rows += tr_row(t, NAMES[t], fmt_price(p, 2),
                       fmt_pct(dd), pct_cls(dd), fmt_pct(dw), pct_cls(dw), extra)

    # Brent-WTI spread
    bz = get_price(data, "BZ=F"); cl = get_price(data, "CL=F")
    bz_prev = float(data["BZ=F"].iloc[-2]) if "BZ=F" in data and len(data["BZ=F"]) >= 2 else bz
    cl_prev = float(data["CL=F"].iloc[-2]) if "CL=F" in data and len(data["CL=F"]) >= 2 else cl
    bz_6 = float(data["BZ=F"].iloc[-6]) if "BZ=F" in data and len(data["BZ=F"]) >= 6 else bz
    cl_6 = float(data["CL=F"].iloc[-6]) if "CL=F" in data and len(data["CL=F"]) >= 6 else cl

    spread = (bz - cl) if bz and cl else None
    spread_1d_chg = ((bz - cl) - (bz_prev - cl_prev)) if bz and cl else None
    spread_1w_chg = ((bz - cl) - (bz_6 - cl_6)) if bz and cl else None
    spread_str = f"${spread:.2f}" if spread else "&mdash;"
    spread_d1 = f"{fmt_pct(spread_1d_chg / cl * 100 if spread_1d_chg and cl else None)}"
    spread_d1_str = f"+${spread_1d_chg:.2f}" if spread_1d_chg and spread_1d_chg >= 0 else (f"${spread_1d_chg:.2f}" if spread_1d_chg else "&mdash;")
    spread_d1w_str = f"+${spread_1w_chg:.2f}" if spread_1w_chg and spread_1w_chg >= 0 else (f"${spread_1w_chg:.2f}" if spread_1w_chg else "&mdash;")

    cu_au_1d = d1d.get("cu_au"); cu_au_1w = d1w.get("cu_au")
    _, cu_cls, cu_tag = _spread_signal(cu_au_1d, "cu_au")

    return f"""
    <div class="panel panel-2col">
      <div class="panel-header">
        <span class="p-num">VI.</span>
        <span class="p-title">Commodities</span>
        <span class="p-sub">Growth vs Inflation Signals</span>
      </div>
      <table class="data-table">
        <tr>{_table_header(["Ticker","Instrument","Price","1D","1W","Signal Role"]).replace("<tr>","").replace("</tr>","")}</tr>
        {rows}
        <tr class="derived">
          <td colspan="2" class="ticker">Brent &minus; WTI Spread</td>
          <td class="r"><strong>{spread_str}</strong></td>
          <td class="r {pct_cls(spread_1d_chg)}">{spread_d1_str}</td>
          <td class="r {pct_cls(spread_1w_chg)}">{spread_d1w_str}</td>
          <td class="role-col" style="font-style:italic;">Quality/Transport premium</td>
        </tr>
        <tr class="derived">
          <td colspan="2" class="ticker">
            Cu / Au Ratio
            <em style="font-size:9px;color:#aaa;font-style:italic;"> (Gundlach)</em>
          </td>
          <td class="r" colspan="2"><strong>1D: {fmt_pct(cu_au_1d)}</strong></td>
          <td class="r" colspan="2"><strong>1W: {fmt_pct(cu_au_1w)}</strong> {badge(cu_tag, cu_cls)}</td>
        </tr>
      </table>
    </div>"""


def build_panel_top5(top5):
    if not top5:
        return ""

    def sub_table(label, rows):
        if not rows:
            return ""
        trs = ""
        for i, r in enumerate(rows):
            trs += f"""
          <tr>
            <td class="rank">{i+1}</td>
            <td class="ticker">{r['symbol']}</td>
            <td class="label" style="max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{r['name']}</td>
            <td class="r {pct_cls(r['ret_1d'])}">{fmt_pct(r['ret_1d'])}</td>
            <td class="r {pct_cls(r['ret_1w'])}">{fmt_pct(r['ret_1w'])}</td>
            <td class="r {pct_cls(r.get('ret_ytd'))}">{fmt_pct(r.get('ret_ytd'))}</td>
          </tr>"""
        return f"""
        <div class="top5-block">
          <div class="top5-index-label">{label}</div>
          <table class="data-table">
            <tr><th class="rank">#</th><th>Ticker</th><th>Company</th>
                <th class="r">1D</th><th class="r">1W</th><th class="r">YTD</th></tr>
            {trs}
          </table>
        </div>"""

    blocks = ""
    for label in ["S&P 500", "EuroStoxx 600", "MSCI Emerg. Mkts"]:
        rows = top5.get(label, [])
        blocks += sub_table(label, rows)

    return f"""
    <div class="panel panel-wide">
      <div class="panel-header">
        <span class="p-num">VII.</span>
        <span class="p-title">Top 5 Movers &mdash; Last Week</span>
        <span class="p-sub">From ETF top holdings &middot; SPY &middot; EXW1.DE &middot; EEM</span>
      </div>
      <div class="top5-grid">
        {blocks}
      </div>
    </div>"""


# ---------------------------------------------------------------------------
# NEWS PANEL
# ---------------------------------------------------------------------------

def build_panel_news(articles, hours_back=NEWS_HOURS_BACK):
    if not articles:
        return ""

    def time_ago(published_at):
        try:
            pub   = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            now   = datetime.now(tz=timezone.utc)
            mins  = int((now - pub).total_seconds() / 60)
            if mins < 60:
                return f"{mins}m ago"
            return f"{mins // 60}h ago"
        except Exception:
            return ""

    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    cards = ""
    for art in articles[:12]:
        source = esc(art.get("source", {}).get("name", ""))
        title  = esc(art.get("title") or "")
        desc   = esc(art.get("description") or "")
        url    = art.get("url", "#")
        t_ago  = time_ago(art.get("publishedAt", ""))
        if len(desc) > 170:
            desc = desc[:167] + "…"

        cards += f"""
        <div class="news-card">
          <div class="news-meta">
            <span class="news-source">{source}</span>
            <span class="news-time">{t_ago}</span>
          </div>
          <div class="news-title">{title}</div>
          <div class="news-desc">{desc}</div>
          <a class="news-link" href="{url}" target="_blank" rel="noopener noreferrer">Read &rarr;</a>
        </div>"""

    return f"""
    <div class="panel panel-wide">
      <div class="panel-header">
        <span class="p-num">VIII.</span>
        <span class="p-title">Market News</span>
        <span class="p-sub">Last {hours_back}h &middot; Reuters &middot; CNBC &middot; Bloomberg &middot; More</span>
      </div>
      <div class="news-grid">
        {cards}
      </div>
    </div>"""


# ---------------------------------------------------------------------------
# REGIME BAR
# ---------------------------------------------------------------------------

def build_regime_bar(d1d, d1w):
    def row_html(d, timeframe_label):
        cells = ""
        for key, label in REGIME_KEYS:
            val = d.get(key)
            v_str, cls, tag = _spread_signal(val, key)
            cells += f"""
        <div class="regime-item">
          <span class="r-tf">{timeframe_label}</span>
          <span class="r-key">{label}</span>
          <span class="r-val {pct_cls(val)}">{v_str}</span>
          <span class="r-tag">{tag}</span>
        </div>"""
        return cells

    score_1d = d1d.get("score", 50)
    score_1w = d1w.get("score", 50)
    bar_svg  = render_bar(score_1d, score_1w)

    return f"""
    <div class="regime-outer">
      <div class="regime-bar">
        <div class="regime-label-col">
          <div class="regime-label-text">Regime<br>Signals</div>
        </div>
        <div class="regime-rows">
          <div class="regime-row">
            {row_html(d1d, "1D")}
          </div>
          <div class="regime-row regime-row-2w">
            {row_html(d1w, "1W")}
          </div>
        </div>
        <div class="gauge-col">
          <div class="gauge-wrap">
            {bar_svg}
          </div>
        </div>
      </div>
    </div>"""


# ---------------------------------------------------------------------------
# FULL HTML
# ---------------------------------------------------------------------------

CSS = """
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: #fff;
    font-family: 'Crimson Text', Georgia, serif;
    font-size: 13px; color: #111;
    padding: 18px 22px;
    max-width: 1440px; margin: 0 auto;
  }

  /* HEADER */
  .header {
    display: flex; align-items: flex-end; justify-content: space-between;
    border-top: 3px solid #111; border-bottom: 1px solid #111;
    padding: 8px 0 6px; margin-bottom: 10px;
  }
  .header-left { display: flex; align-items: center; gap: 14px; }
  .logo-img { height: 52px; width: auto; display: block; }
  .masthead h1 {
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 24px; font-weight: 900; letter-spacing: .08em;
    text-transform: uppercase; line-height: 1;
  }
  .masthead h2 {
    font-size: 10.5px; font-weight: 400; letter-spacing: .22em;
    text-transform: uppercase; color: #444; margin-top: 2px;
  }
  .header-right {
    text-align: right; font-size: 10.5px;
    letter-spacing: .05em; color: #444; line-height: 1.7;
  }
  .header-right strong { font-family: 'Playfair Display', serif; font-size: 12px; color: #111; }

  /* REGIME BAR */
  .regime-outer { margin-bottom: 10px; }
  .regime-bar {
    border: 1px solid #111; display: flex; align-items: stretch;
  }
  .regime-label-col {
    background: #111; color: #fff; padding: 6px 10px;
    display: flex; align-items: center; justify-content: center;
    min-width: 58px;
  }
  .regime-label-text {
    font-size: 9px; letter-spacing: .15em; text-transform: uppercase;
    text-align: center; line-height: 1.4;
  }
  .regime-rows { flex: 1; display: flex; flex-direction: column; }
  .regime-row {
    display: flex; flex: 1; border-bottom: 1px solid #ddd;
  }
  .regime-row:last-child { border-bottom: none; }
  .regime-row-2w { background: #fafafa; }
  .regime-item {
    flex: 1; padding: 3px 8px; border-left: 1px solid #ddd;
    display: grid;
    grid-template-rows: auto auto auto;
    grid-template-columns: auto 1fr;
    column-gap: 4px;
  }
  .regime-item:first-child { border-left: none; }
  .r-tf {
    font-size: 7.5px; font-weight: 600; letter-spacing: .1em;
    text-transform: uppercase; color: #999;
    grid-column: 1; grid-row: 1 / 4; align-self: center;
    padding-right: 4px; border-right: 1px solid #e0e0e0; margin-right: 0;
    writing-mode: vertical-rl; transform: rotate(180deg);
    padding: 2px 2px;
  }
  .r-key {
    font-size: 8px; letter-spacing: .1em; text-transform: uppercase;
    color: #888; grid-column: 2; grid-row: 1;
  }
  .r-val { font-weight: 600; font-size: 11px; grid-column: 2; grid-row: 2; }
  .r-tag { font-size: 7.5px; color: #666; font-style: italic; grid-column: 2; grid-row: 3; }
  .gauge-col {
    background: #fafafa; border-left: 1px solid #ccc;
    padding: 8px 12px; display: flex; align-items: center;
    min-width: 210px;
  }
  .gauge-wrap { width: 100%; }

  /* MAIN GRID */
  .grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 10px; margin-bottom: 10px;
  }
  .panel-wide { grid-column: 1 / -1; }
  .panel-2col { grid-column: span 2; }

  /* PANEL */
  .panel { border: 1px solid #111; }
  .panel-header {
    background: #111; color: #fff; padding: 4px 9px;
    display: flex; align-items: baseline; gap: 8px;
  }
  .p-num { font-size: 9px; opacity: .5; letter-spacing: .1em; }
  .p-title {
    font-family: 'Playfair Display', serif; font-size: 11px;
    font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  }
  .p-sub {
    font-size: 9px; opacity: .6; letter-spacing: .08em;
    margin-left: auto; font-style: italic;
  }

  /* TABLE */
  .data-table { width: 100%; border-collapse: collapse; font-size: 11px; }
  .data-table th {
    font-size: 8px; letter-spacing: .12em; text-transform: uppercase;
    color: #888; font-weight: 400; border-bottom: 1px solid #999;
    padding: 3px 6px; text-align: left;
  }
  .data-table th.r { text-align: right; }
  .data-table td { padding: 3px 6px; border-bottom: 1px solid #ebebeb; vertical-align: middle; }
  .data-table td.r { text-align: right; font-variant-numeric: tabular-nums; }
  .data-table td.ticker { font-size: 9.5px; letter-spacing: .04em; color: #444; font-weight: 600; }
  .data-table td.label { font-style: italic; font-size: 10px; color: #333; }
  .data-table td.rank { text-align: center; font-size: 10px; color: #aaa; width: 18px; }
  .data-table td.role-col { font-size: 9px; color: #777; font-style: italic; }
  .data-table tr:last-child td { border-bottom: none; }
  .data-table tr.derived { background: #f6f6f6; }
  .data-table tr.derived td { font-size: 10px; border-bottom: 1px solid #ddd; }
  .data-table tr.section-head td {
    font-size: 8px; letter-spacing: .12em; text-transform: uppercase;
    color: #aaa; padding-top: 5px; padding-bottom: 2px;
    border-bottom: 1px solid #d0d0d0;
  }

  .up   { color: #1a5c1a; }
  .down { color: #8b1a1a; }
  .neu  { color: #333; }

  .badge {
    display: inline-block; padding: 1px 5px; font-size: 7.5px;
    letter-spacing: .07em; text-transform: uppercase;
    border: 1px solid currentColor; vertical-align: middle; margin-left: 3px;
    font-style: normal;
  }
  .badge.risk-on  { color: #1a5c1a; }
  .badge.risk-off { color: #8b1a1a; }
  .badge.neutral  { color: #777; }

  /* EQUITY SECTORS */
  .sector-label-row {
    background: #f0f0f0; border-top: 1px solid #ccc; padding: 2px 8px;
  }
  .sector-timeframe-label {
    font-size: 8px; font-weight: 600; letter-spacing: .15em;
    text-transform: uppercase; color: #888;
  }
  .sectors-grid {
    display: grid; grid-template-columns: repeat(11, 1fr);
    border-top: 1px solid #ddd;
  }
  .sector-cell {
    padding: 4px 3px; border-right: 1px solid #e8e8e8;
    text-align: center;
  }
  .sector-cell:last-child { border-right: none; }
  .sector-cell .s-tick { font-weight: 600; font-size: 10.5px; display: block; }
  .sector-cell .s-name { display: block; font-size: 7px; color: #999; text-transform: uppercase; font-style: italic; margin: 1px 0; }
  .sector-cell .s-val  { display: block; font-size: 11px; font-variant-numeric: tabular-nums; }
  .sector-cell.cyc { background: #fafafa; }
  .sector-cell.def { background: #f2f2f2; }
  .sectors-grid-1w .sector-cell.cyc { background: #f5f5f5; }
  .sectors-grid-1w .sector-cell.def { background: #eeeeee; }
  .ratios-row {
    border-top: 1px solid #111; display: grid; grid-template-columns: repeat(3,1fr);
  }
  .ratio-cell { padding: 5px 9px; border-right: 1px solid #ccc; }
  .ratio-cell:last-child { border-right: none; }
  .rc-label { font-size: 8px; letter-spacing: .1em; text-transform: uppercase; color: #999; }
  .rc-val { font-size: 11.5px; font-weight: 600; }

  /* TOP 5 */
  .top5-grid {
    display: grid; grid-template-columns: repeat(3,1fr); border-top: 1px solid #ddd;
  }
  .top5-block { border-right: 1px solid #ddd; }
  .top5-block:last-child { border-right: none; }
  .top5-index-label {
    background: #f5f5f5; padding: 4px 9px; font-size: 9px;
    letter-spacing: .1em; text-transform: uppercase; color: #666;
    border-bottom: 1px solid #ddd; font-style: italic;
  }

  /* NEWS */
  .news-grid {
    display: grid; grid-template-columns: repeat(3, 1fr);
    border-top: 1px solid #ddd;
  }
  .news-card {
    padding: 9px 12px; border-right: 1px solid #eee; border-bottom: 1px solid #eee;
  }
  .news-card:nth-child(3n) { border-right: none; }
  .news-meta { display: flex; justify-content: space-between; margin-bottom: 3px; }
  .news-source {
    font-size: 8px; letter-spacing: .12em; text-transform: uppercase;
    color: #888; font-weight: 600;
  }
  .news-time { font-size: 8px; color: #bbb; font-style: italic; }
  .news-title {
    font-family: 'Playfair Display', serif; font-size: 12px; font-weight: 700;
    line-height: 1.35; margin-bottom: 4px; color: #111;
  }
  .news-desc { font-size: 10.5px; color: #555; line-height: 1.45; margin-bottom: 6px; font-style: italic; }
  .news-link {
    font-size: 9px; letter-spacing: .08em; text-transform: uppercase;
    color: #888; text-decoration: none; border-bottom: 1px solid #ccc;
  }
  .news-link:hover { color: #111; border-color: #111; }

  /* FOOTER */
  .footer {
    border-top: 1px solid #111; padding-top: 5px;
    display: flex; justify-content: space-between;
    font-size: 9px; letter-spacing: .06em; color: #aaa; font-style: italic;
  }

  /* MOBILE */
  @media (max-width: 768px) {
    body { padding: 10px 12px; font-size: 12px; }
    .grid { grid-template-columns: 1fr; }
    .panel-wide { grid-column: 1; }
    .panel-2col { grid-column: 1; }
    .sectors-grid { grid-template-columns: repeat(4, 1fr); }
    .ratios-row { grid-template-columns: 1fr; }
    .ratio-cell { border-right: none; border-bottom: 1px solid #ccc; }
    .ratio-cell:last-child { border-bottom: none; }
    .top5-grid { grid-template-columns: 1fr; }
    .top5-block { border-right: none; border-bottom: 1px solid #ddd; }
    .regime-rows { overflow-x: auto; }
    .regime-row { min-width: 600px; }
    .gauge-col { display: none; }
    .header { flex-direction: column; gap: 6px; align-items: flex-start; }
    .header-right { text-align: left; }
    .masthead h1 { font-size: 20px; }
    .news-grid { grid-template-columns: 1fr; }
    .news-card { border-right: none; }
  }
"""


def render_html(data, d1d, d1w, top5, logo_b64, generated_at, articles=None):
    now_str  = generated_at.strftime("%A, %d %B %Y")
    time_str = generated_at.strftime("%H:%M CET")

    regime_html  = build_regime_bar(d1d, d1w)
    panel_fi     = build_panel_fixed_income(data, d1d, d1w)
    panel_credit = build_panel_credit(data, d1d, d1w)
    panel_fx     = build_panel_fx(data)
    panel_equity = build_panel_equity(data, d1d, d1w)
    panel_asia   = build_panel_asia(data)
    panel_comm   = build_panel_commodities(data, d1d, d1w)
    panel_top5   = build_panel_top5(top5)
    panel_news   = build_panel_news(articles or [])

    logo_tag = f'<img src="data:image/png;base64,{logo_b64}" class="logo-img" alt="First Glance">' if logo_b64 else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>First Glance - The Macro Matrix - {now_str}</title>
<style>{CSS}</style>
</head>
<body>

<div class="header">
  <div class="header-left">
    {logo_tag}
    <div class="masthead">
      <h1>First Glance</h1>
      <h2>The Macro Matrix</h2>
    </div>
  </div>
  <div class="header-right">
    <strong>{now_str}</strong><br>
    {time_str} &nbsp;&middot;&nbsp; Pre-Market Edition<br>
    Data: Yahoo Finance &middot; yfinance
  </div>
</div>

{regime_html}

<div class="grid">
  {panel_fi}
  {panel_credit}
  {panel_fx}
  {panel_equity}
  {panel_asia}
  {panel_comm}
  {panel_top5}
  {panel_news}
</div>

<div class="footer">
  <span>All prices indicative. Not investment advice. Sourced via yfinance.</span>
  <span>Generated {generated_at.strftime("%Y-%m-%d %H:%M UTC")} &middot; First Glance &copy; {generated_at.year}</span>
</div>

</body>
</html>"""


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    cet = timezone(timedelta(hours=1))
    now = datetime.now(tz=cet)

    print("=" * 60)
    print("  FIRST GLANCE - THE MACRO MATRIX")
    print(f"  {now.strftime('%A, %d %B %Y  %H:%M CET')}")
    print("=" * 60)

    logo_b64 = ""
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        print(f"  Logo: {len(logo_b64)//1024} KB base64")
    else:
        print("  WARNING: logo not found")

    data = fetch_all()

    print("Calculating derived indicators...")
    d1d = calc_derived(data, "1d")
    d1w = calc_derived(data, "1w")
    print(f"  1D signals: {list(d1d.keys())}")
    print(f"  1W score:   {d1w.get('score')}")

    print("Fetching top-5 movers from ETF holdings...")
    top5 = fetch_top5_movers()

    print("Fetching market news...")
    articles = fetch_news()

    print("Rendering HTML...")
    html = render_html(data, d1d, d1w, top5, logo_b64, now, articles=articles)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  [OK] {OUTPUT_PATH}")
    print(f"  Size: {len(html)//1024} KB")


if __name__ == "__main__":
    main()
