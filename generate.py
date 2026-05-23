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
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yfinance as yf

# ── CONFIG ─────────────────────────────────────────────────────────────────────

LOGO_PATH = Path(__file__).parent / "first_glance.png"
OUTPUT_PATH = Path(__file__).parent / "index.html"

# All tickers grouped by section
TICKERS = {
    "us_rates":    ["^IRX", "^FVX", "^TNX", "^TYX"],
    "eu_futures":  ["IBGM.L", "IFRB.L", "IITB.L"],
    "credit":      ["LQD", "HYG", "EMB", "IEI", "TLT", "IEAC.L", "IEGA.L"],
    "equity":      ["XLK", "XLF", "XLI", "XLB", "XLY", "XLE", "XLC",
                    "XLP", "XLV", "XLU", "XLRE", "IWD", "IWF"],
    "fx":          ["DX-Y.NYB", "USDJPY=X", "USDCNH=X", "AUDJPY=X",
                    "USDMXN=X", "USDBRL=X", "^VIX", "^MOVE"],
    "commodities": ["HG=F", "GC=F", "CL=F", "BZ=F"],
}

# Display names
NAMES = {
    "^IRX":      "3M T-Bill",
    "^FVX":      "5Y Note",
    "^TNX":      "10Y Note",
    "^TYX":      "30Y Bond",
    "IBGM.L":    "Germany Govt Bond ETF",
    "IFRB.L":    "France Govt Bond ETF",
    "IITB.L":    "Italy Govt Bond ETF",
    "LQD":       "US IG Corporate",
    "HYG":       "US High Yield",
    "EMB":       "EM Hard Currency",
    "IEI":       "US Treasury 3–7Y",
    "TLT":       "US Treasury 20Y+",
    "IEAC.L":    "EUR Corporate Bond",
    "IEGA.L":    "EUR Govt Bond (Core)",
    "XLK":       "Technology",
    "XLF":       "Financials",
    "XLI":       "Industrials",
    "XLB":       "Materials",
    "XLY":       "Consumer Discret.",
    "XLE":       "Energy",
    "XLC":       "Communication",
    "XLP":       "Consumer Staples",
    "XLV":       "Health Care",
    "XLU":       "Utilities",
    "XLRE":      "Real Estate",
    "IWD":       "Russell 1000 Value",
    "IWF":       "Russell 1000 Growth",
    "DX-Y.NYB":  "US Dollar Index",
    "USDJPY=X":  "USD/JPY",
    "USDCNH=X":  "USD/CNH",
    "AUDJPY=X":  "AUD/JPY",
    "USDMXN=X":  "USD/MXN",
    "USDBRL=X":  "USD/BRL",
    "^VIX":      "VIX (Equity Vol)",
    "^MOVE":     "MOVE (Rates Vol)",
    "HG=F":      "Copper",
    "GC=F":      "Gold",
    "CL=F":      "WTI Crude",
    "BZ=F":      "Brent Crude",
}

SECTOR_ROLE = {
    "XLK": "cyc", "XLF": "cyc", "XLI": "cyc", "XLB": "cyc",
    "XLY": "cyc", "XLE": "cyc", "XLC": "cyc",
    "XLP": "def", "XLV": "def", "XLU": "def", "XLRE": "def",
}

# ── DATA FETCH ─────────────────────────────────────────────────────────────────

def fetch_all():
    """Fetch 2W of daily data for all tickers. Returns dict ticker -> series."""
    all_tickers = []
    for group in TICKERS.values():
        all_tickers.extend(group)

    print(f"Fetching {len(all_tickers)} tickers...")
    raw = yf.download(
        tickers=all_tickers,
        period="15d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    closes = raw["Close"] if "Close" in raw.columns else raw.xs("Close", axis=1, level=0)

    data = {}
    for ticker in all_tickers:
        try:
            s = closes[ticker].dropna()
            if len(s) >= 2:
                data[ticker] = s
        except Exception:
            pass
    print(f"  Got data for {len(data)}/{len(all_tickers)} tickers.")
    return data


def get_price(data, ticker):
    """Latest close price."""
    if ticker not in data:
        return None
    return float(data[ticker].iloc[-1])


def get_delta_1d(data, ticker):
    """1-day percentage change."""
    if ticker not in data or len(data[ticker]) < 2:
        return None
    s = data[ticker]
    return (s.iloc[-1] - s.iloc[-2]) / s.iloc[-2] * 100


def get_delta_1w(data, ticker):
    """~5-day (1 week) percentage change."""
    if ticker not in data or len(data[ticker]) < 6:
        return None
    s = data[ticker]
    return (s.iloc[-1] - s.iloc[-6]) / s.iloc[-6] * 100


# ── FORMATTERS ─────────────────────────────────────────────────────────────────

def fmt_price(v, decimals=2):
    if v is None:
        return "—"
    if v > 1000:
        return f"{v:,.2f}"
    return f"{v:.{decimals}f}"


def fmt_pct(v, show_sign=True, decimals=2):
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"


def fmt_bps(v):
    if v is None:
        return "—"
    bps = v * 100
    sign = "+" if bps >= 0 else ""
    return f"{sign}{bps:.0f} bps"


def delta_class(v):
    if v is None:
        return "neu"
    return "up" if v > 0.005 else ("down" if v < -0.005 else "neu")


def pct_class(v):
    if v is None:
        return "neu"
    return "up" if v > 0 else ("down" if v < 0 else "neu")


def badge(label, css_class):
    return f'<span class="badge {css_class}">{label}</span>'


# ── DERIVED INDICATORS ─────────────────────────────────────────────────────────

def calc_derived(data):
    """Calculate all macro regime indicators."""
    d = {}

    # US Yield Curve (yields in %, stored as decimal in yfinance for ^IRX etc.)
    # ^IRX, ^FVX, ^TNX, ^TYX are returned as % values (e.g. 5.31 means 5.31%)
    irx = get_price(data, "^IRX")
    fvx = get_price(data, "^FVX")
    tnx = get_price(data, "^TNX")
    tyx = get_price(data, "^TYX")

    if fvx and tyx:
        d["5s30s"] = tyx - fvx
        prev_fvx = float(data["^FVX"].iloc[-2]) if len(data.get("^FVX", [])) >= 2 else fvx
        prev_tyx = float(data["^TYX"].iloc[-2]) if len(data.get("^TYX", [])) >= 2 else tyx
        d["5s30s_delta"] = (tyx - fvx) - (prev_tyx - prev_fvx)

    if irx and tnx:
        d["3m10y"] = tnx - irx
        prev_irx = float(data["^IRX"].iloc[-2]) if len(data.get("^IRX", [])) >= 2 else irx
        prev_tnx = float(data["^TNX"].iloc[-2]) if len(data.get("^TNX", [])) >= 2 else tnx
        d["3m10y_delta"] = (tnx - irx) - (prev_tnx - prev_irx)

    # European sovereign spread proxies via Govt Bond ETFs
    # When Italy (IITB) underperforms Germany (IBGM), spreads widen → risk-off
    btp_d1 = get_delta_1d(data, "IITB.L")
    bund_d1 = get_delta_1d(data, "IBGM.L")
    oat_d1 = get_delta_1d(data, "IFRB.L")
    if btp_d1 is not None and bund_d1 is not None:
        d["btp_bund_proxy"] = btp_d1 - bund_d1
    if oat_d1 is not None and bund_d1 is not None:
        d["oat_bund_proxy"] = oat_d1 - bund_d1

    # Credit ratio: HYG / IEI
    hyg_d1 = get_delta_1d(data, "HYG")
    iei_d1 = get_delta_1d(data, "IEI")
    if hyg_d1 is not None and iei_d1 is not None:
        d["hyg_iei"] = hyg_d1 - iei_d1

    # EM ratio: EMB / TLT
    emb_d1 = get_delta_1d(data, "EMB")
    tlt_d1 = get_delta_1d(data, "TLT")
    if emb_d1 is not None and tlt_d1 is not None:
        d["emb_tlt"] = emb_d1 - tlt_d1

    # Cyclicals vs Defensives: XLY / XLP
    xly_d1 = get_delta_1d(data, "XLY")
    xlp_d1 = get_delta_1d(data, "XLP")
    if xly_d1 is not None and xlp_d1 is not None:
        d["xly_xlp"] = xly_d1 - xlp_d1

    # Value vs Growth: IWD / IWF
    iwd_d1 = get_delta_1d(data, "IWD")
    iwf_d1 = get_delta_1d(data, "IWF")
    if iwd_d1 is not None and iwf_d1 is not None:
        d["iwd_iwf"] = iwd_d1 - iwf_d1

    # Duration play: XLK / XLI
    xlk_d1 = get_delta_1d(data, "XLK")
    xli_d1 = get_delta_1d(data, "XLI")
    if xlk_d1 is not None and xli_d1 is not None:
        d["xlk_xli"] = xlk_d1 - xli_d1

    # Copper / Gold ratio
    hg_d1 = get_delta_1d(data, "HG=F")
    gc_d1 = get_delta_1d(data, "GC=F")
    if hg_d1 is not None and gc_d1 is not None:
        d["cu_au"] = hg_d1 - gc_d1

    return d


def regime_label(key, val):
    """Return (label_text, badge_class, interpretation) for regime signals."""
    if val is None:
        return "N/A", "neutral", "—"

    if key == "3m10y":
        tag = "Curve Inverted · Recession Watch" if val < 0 else "Curve Normal · Expansion"
        cls = "risk-off" if val < 0 else "risk-on"
        return fmt_bps(val / 100), cls, tag

    if key == "5s30s":
        tag = "Steepening · Reflation" if val > 50 else ("Flattening" if val < 10 else "Neutral Slope")
        cls = "risk-on" if val > 30 else "neutral"
        return fmt_bps(val / 100), cls, tag

    if key == "btp_bund_proxy":
        tag = "BTP–Bund Widening · Peripheral Stress" if val < 0 else "BTP–Bund Narrowing · Risk-On"
        cls = "risk-off" if val < 0 else "risk-on"
        return fmt_pct(val), cls, tag

    if key == "oat_bund_proxy":
        tag = "OAT–Bund Widening · France Risk" if val < 0 else "OAT–Bund Stable"
        cls = "risk-off" if val < 0 else "neutral"
        return fmt_pct(val), cls, tag

    if key == "hyg_iei":
        tag = "Spreads Narrowing · Risk Appetite" if val > 0 else "Spreads Widening · De-Risking"
        cls = "risk-on" if val > 0 else "risk-off"
        return fmt_pct(val), cls, tag

    if key == "emb_tlt":
        tag = "EM Outperforming · Capital Inflows" if val > 0 else "EM Distress · Capital Flight"
        cls = "risk-on" if val > 0 else "risk-off"
        return fmt_pct(val), cls, tag

    if key == "xly_xlp":
        tag = "Cyclicals Leading · Risk-On Expansion" if val > 0 else "Defensives Leading · Risk-Off"
        cls = "risk-on" if val > 0 else "risk-off"
        return fmt_pct(val), cls, tag

    if key == "iwd_iwf":
        tag = "Value Leading · Rate Sensitive" if val > 0 else "Growth Leading · Duration Play"
        cls = "neutral"
        return fmt_pct(val), cls, tag

    if key == "xlk_xli":
        tag = "Tech Outperforming · Duration Bet" if val > 0 else "Industrials Leading · CAPEX Cycle"
        cls = "neutral"
        return fmt_pct(val), cls, tag

    if key == "cu_au":
        tag = "Growth Signal · Yields Rising" if val > 0 else "Recession Signal · Yields Falling"
        cls = "risk-on" if val > 0 else "risk-off"
        return fmt_pct(val), cls, tag

    return fmt_pct(val), "neutral", "—"


# ── HTML BUILDING BLOCKS ───────────────────────────────────────────────────────

def tr_data(ticker, label, price_str, d1_str, d1_cls, d1w_str, d1w_cls,
            extra_cols="", row_class=""):
    """Render a standard data row."""
    return f"""
      <tr class="{row_class}">
        <td class="ticker">{ticker}</td>
        <td class="label">{label}</td>
        <td class="r">{price_str}</td>
        <td class="r {d1_cls}">{d1_str}</td>
        <td class="r {d1w_cls}">{d1w_str}</td>
        {extra_cols}
      </tr>"""


def tr_derived(label, val_str, badge_html, colspan_val=5):
    return f"""
      <tr class="derived">
        <td colspan="3" class="ticker">{label}</td>
        <td class="r" colspan="2">{val_str} {badge_html}</td>
      </tr>"""


def section_head(title, colspan=5):
    return f"""
      <tr class="section-head"><td colspan="{colspan}">{title}</td></tr>"""


# ── HTML RENDER ────────────────────────────────────────────────────────────────

def render_html(data, derived, logo_b64, generated_at):
    now_str = generated_at.strftime("%A, %d %B %Y")
    time_str = generated_at.strftime("%H:%M CET")

    # ── REGIME SIGNALS BAR ──────────────────────────────────────────────
    regime_keys = [
        ("3m10y",        "3M–10Y Spread"),
        ("5s30s",        "5s30s Spread"),
        ("hyg_iei",      "HYG / IEI"),
        ("xly_xlp",      "XLY / XLP"),
        ("cu_au",        "Cu / Au Ratio"),
        ("btp_bund_proxy","BTP–Bund"),
    ]
    regime_html = ""
    for key, key_label in regime_keys:
        val = derived.get(key)
        val_str, cls, tag = regime_label(key, val)
        regime_html += f"""
        <div class="regime-item">
          <span class="r-key">{key_label}</span>
          <span class="r-val {pct_class(val) if val else 'neu'}">{val_str}</span>
          <span class="r-tag">{tag}</span>
        </div>"""

    # ── PANEL I: US RATES ───────────────────────────────────────────────
    us_rates_rows = ""
    for ticker in TICKERS["us_rates"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        # Rates tickers return yield in % directly — show as "X.XX%"
        p_str = f"{p:.2f}%" if p else "—"
        d1_str = fmt_bps((d1 / 100) if d1 else None)  # delta in bps
        d1_cls = pct_class(d1)
        d1w_str = fmt_bps((d1w / 100) if d1w else None)
        d1w_cls = pct_class(d1w)
        us_rates_rows += tr_data(ticker, NAMES[ticker], p_str,
                                 d1_str, d1_cls, d1w_str, d1w_cls)

    s30s_val = derived.get("5s30s")
    s30s_d = derived.get("5s30s_delta")
    m10y_val = derived.get("3m10y")
    m10y_d = derived.get("3m10y_delta")

    s30s_str = fmt_bps(s30s_val / 100) if s30s_val is not None else "—"
    s30s_badge_cls = "risk-on" if (s30s_val or 0) > 0 else "neutral"
    s30s_label = "Steepener" if (s30s_val or 0) > 20 else ("Flat" if (s30s_val or 0) > 0 else "Inverted")

    m10y_str = fmt_bps(m10y_val / 100) if m10y_val is not None else "—"
    m10y_badge_cls = "risk-off" if (m10y_val or 0) < 0 else "risk-on"
    m10y_label = "Inverted" if (m10y_val or 0) < 0 else "Normal"

    eu_rows = ""
    for ticker in TICKERS["eu_futures"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        # Show price as-is for ETFs (not as yields)
        eu_rows += tr_data(ticker, NAMES[ticker],
                           fmt_price(p, 2), fmt_pct(d1), pct_class(d1),
                           fmt_pct(d1w), pct_class(d1w))

    btp_val = derived.get("btp_bund_proxy")
    oat_val = derived.get("oat_bund_proxy")
    btp_badge = "risk-off" if (btp_val or 0) < 0 else "risk-on"
    btp_label = "Widening · Stress" if (btp_val or 0) < 0 else "Narrowing · Stable"
    oat_badge = "risk-off" if (oat_val or 0) < 0 else "neutral"
    oat_label = "Widening · France Risk" if (oat_val or 0) < 0 else "Stable"

    panel1 = f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">I.</span>
        <span class="p-title">Sovereign Fixed Income</span>
        <span class="p-sub">Rates &amp; Spread Proxies</span>
      </div>
      <table class="data-table">
        <tr><th>Ticker</th><th>Instrument</th><th class="r">Level</th>
            <th class="r">1D Δ</th><th class="r">1W Δ</th></tr>
        {section_head("US Term Structure")}
        {us_rates_rows}
        {tr_derived("5s30s Slope", s30s_str, badge(s30s_label, s30s_badge_cls))}
        {tr_derived("3M–10Y Slope", m10y_str, badge(m10y_label, m10y_badge_cls))}
        {section_head("Europe — Govt Bond ETFs (Spread Proxies)")}
        {eu_rows}
        {tr_derived("BTP–Bund Proxy (1D)", fmt_pct(btp_val), badge(btp_label, btp_badge))}
        {tr_derived("OAT–Bund Proxy (1D)", fmt_pct(oat_val), badge(oat_label, oat_badge))}
      </table>
    </div>"""

    # ── PANEL II: CREDIT ────────────────────────────────────────────────
    credit_rows = ""
    for ticker in ["LQD", "HYG", "EMB", "IEI", "TLT"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        credit_rows += tr_data(ticker, NAMES[ticker],
                               fmt_price(p), fmt_pct(d1), pct_class(d1),
                               fmt_pct(d1w), pct_class(d1w))

    hyg_iei = derived.get("hyg_iei")
    emb_tlt = derived.get("emb_tlt")
    hyg_badge = "risk-on" if (hyg_iei or 0) > 0 else "risk-off"
    hyg_label = "Spreads ↓ · Risk Appetite" if (hyg_iei or 0) > 0 else "Spreads ↑ · De-Risking"
    emb_badge = "risk-on" if (emb_tlt or 0) > 0 else "risk-off"
    emb_label = "EM Outperforming" if (emb_tlt or 0) > 0 else "EM Distress"

    eu_credit_rows = ""
    for ticker in ["IEAC.L", "IEGA.L"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        eu_credit_rows += tr_data(ticker, NAMES[ticker],
                                  fmt_price(p), fmt_pct(d1), pct_class(d1),
                                  fmt_pct(d1w), pct_class(d1w))

    panel2 = f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">II.</span>
        <span class="p-title">Credit Markets</span>
        <span class="p-sub">Risk Premiums &amp; EM</span>
      </div>
      <table class="data-table">
        <tr><th>Ticker</th><th>Instrument</th><th class="r">Price</th>
            <th class="r">1D Δ</th><th class="r">1W Δ</th></tr>
        {section_head("US Credit ETFs")}
        {credit_rows}
        {tr_derived("HYG / IEI · Pure Credit Appetite", fmt_pct(hyg_iei), badge(hyg_label, hyg_badge))}
        {tr_derived("EMB / TLT · EM Distress Engine", fmt_pct(emb_tlt), badge(emb_label, emb_badge))}
        {section_head("Europe Credit (UCITS)")}
        {eu_credit_rows}
      </table>
    </div>"""

    # ── PANEL III: FX ───────────────────────────────────────────────────
    fx_labels = {
        "DX-Y.NYB": "Dollar Index",
        "USDJPY=X": "Carry Trade Anchor",
        "USDCNH=X": "Offshore Yuan",
        "AUDJPY=X": "Risk Barometer",
        "USDMXN=X": "Mexico (EM Proxy)",
        "USDBRL=X": "Brazil (EM Proxy)",
        "^VIX":     "Equity Volatility",
        "^MOVE":    "Rates Volatility",
    }
    fx_rows = ""
    for ticker in ["DX-Y.NYB", "USDJPY=X", "USDCNH=X", "AUDJPY=X"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        fx_rows += tr_data(ticker, fx_labels[ticker],
                           fmt_price(p, 4 if "CNH" in ticker or "BRL" in ticker else 2),
                           fmt_pct(d1), pct_class(d1), fmt_pct(d1w), pct_class(d1w))

    em_fx_rows = ""
    for ticker in ["USDMXN=X", "USDBRL=X"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        em_fx_rows += tr_data(ticker, fx_labels[ticker],
                              fmt_price(p, 4), fmt_pct(d1), pct_class(d1),
                              fmt_pct(d1w), pct_class(d1w))

    vol_rows = ""
    for ticker in ["^VIX", "^MOVE"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        vol_rows += tr_data(ticker, fx_labels[ticker],
                            fmt_price(p, 2), fmt_pct(d1), pct_class(d1),
                            fmt_pct(d1w), pct_class(d1w))

    panel3 = f"""
    <div class="panel">
      <div class="panel-header">
        <span class="p-num">IV.</span>
        <span class="p-title">FX &amp; Global Liquidity</span>
        <span class="p-sub">Capital Flow Signals</span>
      </div>
      <table class="data-table">
        <tr><th>Ticker</th><th>Instrument</th><th class="r">Rate</th>
            <th class="r">1D Δ</th><th class="r">1W Δ</th></tr>
        {section_head("Key Pairs")}
        {fx_rows}
        {section_head("EM High-Yield FX")}
        {em_fx_rows}
        {section_head("Volatility Gauges")}
        {vol_rows}
      </table>
    </div>"""

    # ── PANEL IV: EQUITY SECTORS ─────────────────────────────────────────
    sectors = ["XLK", "XLF", "XLI", "XLB", "XLY", "XLE", "XLC",
               "XLP", "XLV", "XLU", "XLRE"]
    sector_cells = ""
    for t in sectors:
        p = get_price(data, t)
        d1 = get_delta_1d(data, t)
        role = SECTOR_ROLE.get(t, "cyc")
        d1_str = fmt_pct(d1) if d1 is not None else "—"
        d1_cls = pct_class(d1)
        sector_cells += f"""
        <div class="sector-cell {role}">
          <span class="s-tick">{t}</span>
          <span class="s-name">{NAMES[t]}</span>
          <span class="s-val {d1_cls}">{d1_str}</span>
        </div>"""

    xly_xlp = derived.get("xly_xlp")
    iwd_iwf = derived.get("iwd_iwf")
    xlk_xli = derived.get("xlk_xli")
    xly_xlp_badge = "risk-on" if (xly_xlp or 0) > 0 else "risk-off"
    xly_xlp_label = "Cyclicals Leading · Risk-On" if (xly_xlp or 0) > 0 else "Defensives Leading · Risk-Off"
    iwd_iwf_label = "Value Leading" if (iwd_iwf or 0) > 0 else "Growth Leading"
    xlk_xli_label = "Tech vs Industrial"

    panel4 = f"""
    <div class="panel panel-wide">
      <div class="panel-header">
        <span class="p-num">III.</span>
        <span class="p-title">US Equity Sector &amp; Factor Rotation</span>
        <span class="p-sub">SPDR Sector ETFs · Cyclical vs Defensive</span>
      </div>
      <div class="sectors-grid">
        {sector_cells}
      </div>
      <div class="ratios-row">
        <div class="ratio-cell">
          <div class="rc-label">XLY / XLP · Cyclicals vs Defensives</div>
          <div class="rc-val {pct_class(xly_xlp)}">{fmt_pct(xly_xlp)} {badge(xly_xlp_label, xly_xlp_badge)}</div>
        </div>
        <div class="ratio-cell">
          <div class="rc-label">IWD / IWF · Value vs Growth</div>
          <div class="rc-val {pct_class(iwd_iwf)}">{fmt_pct(iwd_iwf)} {badge(iwd_iwf_label, "neutral")}</div>
        </div>
        <div class="ratio-cell">
          <div class="rc-label">XLK / XLI · Duration Play</div>
          <div class="rc-val {pct_class(xlk_xli)}">{fmt_pct(xlk_xli)} {badge(xlk_xli_label, "neutral")}</div>
        </div>
      </div>
    </div>"""

    # ── PANEL V: COMMODITIES ─────────────────────────────────────────────
    comm_roles = {
        "HG=F": "Global PMI / China Demand Proxy",
        "GC=F": "Real Rate Proxy / Geopolitical Risk",
        "CL=F": "Cost-Push Inflation / OPEC Policy",
        "BZ=F": "Global Benchmark / Brent–WTI Spread",
    }
    comm_rows = ""
    for ticker in TICKERS["commodities"]:
        p = get_price(data, ticker)
        d1 = get_delta_1d(data, ticker)
        d1w = get_delta_1w(data, ticker)
        extra = f'<td style="font-size:9.5px;color:#555;font-style:italic;">{comm_roles[ticker]}</td>'
        comm_rows += tr_data(ticker, NAMES[ticker],
                             fmt_price(p, 2 if ticker == "HG=F" else (2 if "=F" in ticker else 2)),
                             fmt_pct(d1), pct_class(d1), fmt_pct(d1w), pct_class(d1w),
                             extra_cols=extra)

    cu_au = derived.get("cu_au")
    cu_au_badge = "risk-on" if (cu_au or 0) > 0 else "risk-off"
    cu_au_label = "Growth Signal · Yields Rising" if (cu_au or 0) > 0 else "Recession Signal · Yields Falling"

    panel5 = f"""
    <div class="panel panel-wide">
      <div class="panel-header">
        <span class="p-num">V.</span>
        <span class="p-title">Commodities</span>
        <span class="p-sub">Growth vs Inflation Signals</span>
      </div>
      <table class="data-table">
        <tr><th>Ticker</th><th>Instrument</th><th class="r">Price</th>
            <th class="r">1D Δ</th><th class="r">1W Δ</th><th>Signal Role</th></tr>
        {comm_rows}
        <tr class="derived">
          <td colspan="3" class="ticker">
            Copper / Gold Ratio
            <em style="font-size:9px;color:#888;font-style:italic;font-weight:400;">(Gundlach Indicator)</em>
          </td>
          <td class="r" colspan="3">{fmt_pct(cu_au)} {badge(cu_au_label, cu_au_badge)}</td>
        </tr>
      </table>
    </div>"""

    # ── ASSEMBLE ─────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>First Glance · The Macro Matrix · {now_str}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Crimson+Text:ital,wght@0,400;0,600;1,400&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #fff;
    font-family: 'Crimson Text', Georgia, serif;
    font-size: 13px;
    color: #111;
    padding: 20px 24px;
    max-width: 1400px;
    margin: 0 auto;
  }}

  /* ── HEADER ── */
  .header {{
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    border-top: 3px solid #111;
    border-bottom: 1px solid #111;
    padding: 8px 0 6px;
    margin-bottom: 10px;
  }}
  .header-left {{ display: flex; align-items: center; gap: 14px; }}
  .logo-img {{ height: 52px; width: auto; display: block; }}
  .masthead h1 {{
    font-family: 'Playfair Display', Georgia, serif;
    font-size: 24px; font-weight: 900;
    letter-spacing: 0.08em; text-transform: uppercase; line-height: 1;
  }}
  .masthead h2 {{
    font-family: 'Crimson Text', Georgia, serif;
    font-size: 10.5px; font-weight: 400;
    letter-spacing: 0.22em; text-transform: uppercase;
    color: #444; margin-top: 2px;
  }}
  .header-right {{
    text-align: right; font-size: 10.5px;
    letter-spacing: 0.05em; color: #444; line-height: 1.7;
  }}
  .header-right strong {{
    font-family: 'Playfair Display', serif; font-size: 12px; color: #111;
  }}

  /* ── REGIME BAR ── */
  .regime-bar {{
    border: 1px solid #111; display: flex; margin-bottom: 10px;
  }}
  .regime-label {{
    background: #111; color: #fff; padding: 5px 12px;
    font-size: 9.5px; letter-spacing: 0.15em; text-transform: uppercase;
    display: flex; align-items: center; white-space: nowrap;
  }}
  .regime-items {{ display: flex; flex: 1; }}
  .regime-item {{
    flex: 1; padding: 4px 10px; border-left: 1px solid #ccc;
    font-size: 10px; display: flex; flex-direction: column; gap: 1px;
  }}
  .regime-item .r-key {{
    font-size: 8.5px; letter-spacing: 0.12em;
    text-transform: uppercase; color: #777;
  }}
  .regime-item .r-val {{ font-weight: 600; font-size: 11.5px; }}
  .regime-item .r-tag {{
    font-size: 8px; letter-spacing: 0.05em; color: #555; font-style: italic;
  }}

  /* ── GRID ── */
  .grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
  }}
  .panel-wide {{ grid-column: 1 / -1; }}

  /* ── PANEL ── */
  .panel {{ border: 1px solid #111; }}
  .panel-header {{
    background: #111; color: #fff;
    padding: 4px 9px; display: flex; align-items: baseline; gap: 8px;
  }}
  .panel-header .p-num {{ font-size: 9px; opacity: 0.5; letter-spacing: 0.1em; }}
  .panel-header .p-title {{
    font-family: 'Playfair Display', serif; font-size: 11px;
    font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase;
  }}
  .panel-header .p-sub {{
    font-size: 9px; opacity: 0.6; letter-spacing: 0.08em;
    margin-left: auto; font-style: italic; font-family: 'Crimson Text', serif;
  }}

  /* ── TABLE ── */
  .data-table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
  .data-table th {{
    font-size: 8.5px; letter-spacing: 0.12em; text-transform: uppercase;
    color: #777; font-weight: 400; border-bottom: 1px solid #999;
    padding: 3px 7px; text-align: left;
  }}
  .data-table th.r {{ text-align: right; }}
  .data-table td {{ padding: 3px 7px; border-bottom: 1px solid #ebebeb; vertical-align: middle; }}
  .data-table td.r {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .data-table td.ticker {{ font-size: 10px; letter-spacing: 0.04em; color: #444; font-weight: 600; }}
  .data-table td.label {{ font-style: italic; font-size: 10.5px; color: #333; }}
  .data-table tr:last-child td {{ border-bottom: none; }}
  .data-table tr.derived {{ background: #f6f6f6; }}
  .data-table tr.derived td {{ font-size: 10px; border-bottom: 1px solid #ddd; }}
  .data-table tr.section-head td {{
    font-size: 8.5px; letter-spacing: 0.12em; text-transform: uppercase;
    color: #aaa; padding-top: 5px; padding-bottom: 2px;
    border-bottom: 1px solid #d0d0d0; background: none;
  }}

  .up   {{ color: #1a5c1a; }}
  .down {{ color: #8b1a1a; }}
  .neu  {{ color: #333; }}

  .badge {{
    display: inline-block; padding: 1px 5px;
    font-size: 7.5px; letter-spacing: 0.08em; text-transform: uppercase;
    border: 1px solid currentColor; vertical-align: middle; margin-left: 3px;
    font-style: normal;
  }}
  .badge.risk-on  {{ color: #1a5c1a; }}
  .badge.risk-off {{ color: #8b1a1a; }}
  .badge.neutral  {{ color: #666; }}

  /* ── SECTORS ── */
  .sectors-grid {{
    display: grid; grid-template-columns: repeat(11, 1fr);
    border-top: 1px solid #ddd;
  }}
  .sector-cell {{
    padding: 5px 4px; border-right: 1px solid #e8e8e8;
    text-align: center; font-size: 9.5px;
  }}
  .sector-cell:last-child {{ border-right: none; }}
  .sector-cell .s-tick {{ font-weight: 600; font-size: 11px; display: block; letter-spacing: 0.02em; }}
  .sector-cell .s-name {{ display: block; font-size: 7.5px; color: #888; letter-spacing: 0.04em; margin: 1px 0; text-transform: uppercase; font-style: italic; }}
  .sector-cell .s-val  {{ display: block; font-size: 11.5px; font-variant-numeric: tabular-nums; margin-top: 2px; }}
  .sector-cell.cyc {{ background: #fafafa; }}
  .sector-cell.def {{ background: #f2f2f2; }}

  .ratios-row {{ border-top: 1px solid #111; display: grid; grid-template-columns: repeat(3, 1fr); }}
  .ratio-cell {{ padding: 5px 10px; border-right: 1px solid #ccc; }}
  .ratio-cell:last-child {{ border-right: none; }}
  .ratio-cell .rc-label {{ font-size: 8.5px; letter-spacing: 0.1em; text-transform: uppercase; color: #888; }}
  .ratio-cell .rc-val   {{ font-size: 12px; font-weight: 600; }}

  /* ── FOOTER ── */
  .footer {{
    border-top: 1px solid #111; padding-top: 5px;
    display: flex; justify-content: space-between;
    font-size: 9px; letter-spacing: 0.06em; color: #999; font-style: italic;
  }}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-left">
    <img src="data:image/png;base64,{logo_b64}" class="logo-img" alt="First Glance logo">
    <div class="masthead">
      <h1>First Glance</h1>
      <h2>The Macro Matrix</h2>
    </div>
  </div>
  <div class="header-right">
    <strong>{now_str}</strong><br>
    {time_str} &nbsp;·&nbsp; Pre-Market Edition<br>
    Data: Yahoo Finance · yfinance
  </div>
</div>

<!-- REGIME SIGNAL BAR -->
<div class="regime-bar">
  <div class="regime-label">Regime Signals</div>
  <div class="regime-items">
    {regime_html}
  </div>
</div>

<!-- 3-COLUMN GRID -->
<div class="grid">
  {panel1}
  {panel2}
  {panel3}
  {panel4}
  {panel5}
</div>

<!-- FOOTER -->
<div class="footer">
  <span>All prices indicative. Sourced via yfinance. Not investment advice.</span>
  <span>Generated {generated_at.strftime("%Y-%m-%d %H:%M UTC")} · First Glance © {generated_at.year}</span>
</div>

</body>
</html>"""

    return html


# ── MAIN ───────────────────────────────────────────────────────────────────────

def main():
    # Timezone: CET = UTC+1 (winter) / UTC+2 (summer) — approximate with UTC+1
    cet = timezone(timedelta(hours=1))
    now = datetime.now(tz=cet)

    print("=" * 60)
    print("  FIRST GLANCE · THE MACRO MATRIX")
    print(f"  {now.strftime('%A, %d %B %Y  %H:%M CET')}")
    print("=" * 60)

    # Logo
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode()
        print(f"  Logo loaded ({len(logo_b64)//1024} KB base64)")
    else:
        logo_b64 = ""
        print("  WARNING: logo not found — proceeding without it")

    # Fetch
    data = fetch_all()

    # Derive
    derived = calc_derived(data)
    print(f"  Derived indicators: {list(derived.keys())}")

    # Render
    html = render_html(data, derived, logo_b64, now)

    # Save
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n  [OK] Dashboard written to: {OUTPUT_PATH}")
    print(f"    Size: {len(html)//1024} KB")


if __name__ == "__main__":
    main()
ten to: {OUTPUT_PATH}")
    print(f"    Size: {len(html)//1024} KB")


if __name__ == "__main__":
    main()
