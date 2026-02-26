#!/usr/bin/env python3
"""Global stock market + quantitative analysis engine (free-first)."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import ssl
import statistics
import tomllib
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "stock_quant.toml"


@dataclass
class Bar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def parse_symbols(csv_text: str) -> List[str]:
    return [x.strip() for x in csv_text.split(",") if x.strip()]


def get_universe(cfg: Dict[str, Any], name: str) -> List[str]:
    uni = cfg.get("universes", {}).get(name, {})
    syms = uni.get("symbols", [])
    return [str(s).strip() for s in syms if str(s).strip()]


def normalize_symbol_for_stooq(symbol: str) -> str:
    s = symbol.strip().lower()
    if "." in s:
        return s
    return f"{s}.us"


def _open_with_ssl_strategy(req: urllib.request.Request, timeout: int, verify_ssl: bool, insecure_fallback: bool):
    if not str(req.full_url).lower().startswith("https://"):
        return urllib.request.urlopen(req, timeout=timeout), "plain_http"

    if not verify_ssl:
        ctx = ssl._create_unverified_context()
        return urllib.request.urlopen(req, timeout=timeout, context=ctx), "insecure"

    try:
        return urllib.request.urlopen(req, timeout=timeout), "verified"
    except Exception as first_err:
        err_msg = str(first_err).lower()
        cert_issue = ("certificate verify failed" in err_msg) or ("ssl" in err_msg and "certificate" in err_msg)
        if cert_issue:
            try:
                import certifi  # type: ignore

                ctx = ssl.create_default_context(cafile=certifi.where())
                return urllib.request.urlopen(req, timeout=timeout, context=ctx), "verified_certifi"
            except Exception:
                pass
        if insecure_fallback and cert_issue:
            ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=timeout, context=ctx), "insecure_fallback"
        raise


def fetch_stooq(symbol: str, timeout: int, verify_ssl: bool, insecure_fallback: bool) -> List[Bar]:
    sid = normalize_symbol_for_stooq(symbol)
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(sid)}&i=d"
    req = urllib.request.Request(url=url, headers={"User-Agent": "AgentSystem-StockQuant/1.0"}, method="GET")
    resp_obj, _ssl_mode = _open_with_ssl_strategy(req, timeout=timeout, verify_ssl=verify_ssl, insecure_fallback=insecure_fallback)
    with resp_obj as resp:
        raw = resp.read(800_000).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(raw.splitlines()))
    bars: List[Bar] = []
    for r in rows:
        if not r.get("Date"):
            continue
        try:
            bars.append(
                Bar(
                    date=r["Date"],
                    open=float(r.get("Open", 0) or 0),
                    high=float(r.get("High", 0) or 0),
                    low=float(r.get("Low", 0) or 0),
                    close=float(r.get("Close", 0) or 0),
                    volume=float(r.get("Volume", 0) or 0),
                )
            )
        except ValueError:
            continue
    return [b for b in bars if b.close > 0]


def fetch_yahoo(symbol: str, timeout: int, verify_ssl: bool, insecure_fallback: bool) -> List[Bar]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5y&interval=1d"
    req = urllib.request.Request(url=url, headers={"User-Agent": "AgentSystem-StockQuant/1.0"}, method="GET")
    resp_obj, _ssl_mode = _open_with_ssl_strategy(req, timeout=timeout, verify_ssl=verify_ssl, insecure_fallback=insecure_fallback)
    with resp_obj as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))

    result = (((payload.get("chart") or {}).get("result") or [None])[0]) or {}
    ts = result.get("timestamp") or []
    quote = ((((result.get("indicators") or {}).get("quote") or [None])[0]) or {})
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    vols = quote.get("volume") or []

    bars: List[Bar] = []
    for i, t in enumerate(ts):
        try:
            c = float(closes[i]) if closes[i] is not None else 0.0
            if c <= 0:
                continue
            o = float(opens[i]) if opens[i] is not None else c
            h = float(highs[i]) if highs[i] is not None else c
            l = float(lows[i]) if lows[i] is not None else c
            v = float(vols[i]) if vols[i] is not None else 0.0
            d = dt.datetime.utcfromtimestamp(int(t)).strftime("%Y-%m-%d")
            bars.append(Bar(date=d, open=o, high=h, low=l, close=c, volume=v))
        except Exception:
            continue
    return bars


def cache_path(cache_dir: Path, symbol: str) -> Path:
    safe = symbol.replace("/", "_").replace(".", "_")
    return cache_dir / f"{safe}.json"


def save_cache(path: Path, symbol: str, provider: str, bars: List[Bar]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "symbol": symbol,
        "provider": provider,
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "bars": [b.__dict__ for b in bars],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_cache(path: Path) -> List[Bar]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    bars = []
    for r in data.get("bars", []):
        try:
            bars.append(
                Bar(
                    date=str(r["date"]),
                    open=float(r["open"]),
                    high=float(r["high"]),
                    low=float(r["low"]),
                    close=float(r["close"]),
                    volume=float(r.get("volume", 0) or 0),
                )
            )
        except Exception:
            continue
    return bars


def sma(vals: List[float], n: int) -> Optional[float]:
    if len(vals) < n or n <= 0:
        return None
    return sum(vals[-n:]) / n


def rsi(vals: List[float], n: int = 14) -> Optional[float]:
    if len(vals) < n + 1:
        return None
    gains = []
    losses = []
    for i in range(-n, 0):
        diff = vals[i] - vals[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))
    avg_gain = sum(gains) / n
    avg_loss = sum(losses) / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(bars: List[Bar], n: int = 14) -> Optional[float]:
    if len(bars) < n + 1:
        return None
    trs = []
    for i in range(-n, 0):
        cur = bars[i]
        prev = bars[i - 1]
        tr = max(cur.high - cur.low, abs(cur.high - prev.close), abs(cur.low - prev.close))
        trs.append(tr)
    return sum(trs) / n


def annualized_volatility(closes: List[float], n: int = 20) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    rets = []
    for i in range(-n, 0):
        prev = closes[i - 1]
        cur = closes[i]
        if prev <= 0:
            continue
        rets.append((cur / prev) - 1.0)
    if len(rets) < 2:
        return None
    sd = statistics.pstdev(rets)
    return sd * math.sqrt(252) * 100.0


def mean(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    return sum(vals) / len(vals)


def percentile_rank(values: List[float], value: float, reverse: bool = False) -> float:
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return 0.5
    lte = sum(1 for v in vals if v <= value)
    p = lte / len(vals)
    return 1.0 - p if reverse else p


def cap_and_normalize(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    if not weights:
        return {}
    cap = max(0.01, min(cap, 1.0))
    out = dict(weights)
    for _ in range(10):
        total = sum(out.values())
        if total <= 0:
            break
        out = {k: v / total for k, v in out.items()}
        capped = {k for k, v in out.items() if v > cap}
        if not capped:
            return out
        fixed = {k: min(out[k], cap) for k in out}
        used = sum(fixed.values())
        if used >= 1.0:
            break
        free = [k for k in out if k not in capped]
        free_sum = sum(out[k] for k in free)
        if free_sum <= 0:
            out = fixed
            break
        rem = 1.0 - sum(fixed[k] for k in capped)
        for k in free:
            fixed[k] = out[k] / free_sum * rem
        out = fixed
    total = sum(out.values())
    return {k: (v / total if total > 0 else 0.0) for k, v in out.items()}


def market_of_symbol(symbol: str) -> str:
    s = symbol.upper()
    if s.endswith(".HK"):
        return "HK"
    if s.endswith(".SS") or s.endswith(".SZ"):
        return "CN"
    if s.endswith(".T"):
        return "JP"
    if s.endswith(".NS"):
        return "IN"
    if s.endswith(".L"):
        return "UK"
    if s.endswith(".DE") or s.endswith(".PA") or s.endswith(".MI"):
        return "EU"
    if s.endswith(".TO"):
        return "CA"
    if s.endswith(".AX"):
        return "AU"
    if s.endswith(".SA"):
        return "BR"
    if s.endswith(".KS"):
        return "KR"
    if s.endswith(".SI"):
        return "SG"
    return "US"


def region_of_market(market: str) -> str:
    m = market.upper()
    if m in {"US", "CA", "BR"}:
        return "AMER"
    if m in {"UK", "EU"}:
        return "EMEA"
    if m in {"CN", "HK", "JP", "IN", "AU", "KR", "SG"}:
        return "APAC"
    return "OTHER"


def _norm_cap(v: Any, default_pct: float) -> float:
    try:
        x = float(v)
    except Exception:
        x = default_pct
    if x > 1.0:
        x = x / 100.0
    return max(0.01, min(1.0, x))


def sector_of_symbol(symbol: str, cfg: Dict[str, Any]) -> str:
    sec_cfg = cfg.get("sectors", {})
    smap = sec_cfg.get("map", {})
    key = symbol.upper()
    if key in smap:
        return str(smap[key])
    k = key.replace("^", "")
    etf_keys = ("ETF", "SPY", "QQQ", "IWM", "VTI", "EEM", "EWJ", "EWZ", "FXI", "KWEB", "GLD", "SLV", "USO", "TLT", "IEF", "HYG", "LQD")
    if any(x in k for x in etf_keys) or k.startswith("51") or k.startswith("15") or k.startswith("28") or k.startswith("30"):
        return "DiversifiedETF"
    return str(sec_cfg.get("default", "Other"))


def constrained_allocate(
    raw: Dict[str, float],
    sector_map: Dict[str, str],
    sym_cap: float,
    market_cap: float,
    region_cap: float,
    sector_cap: float,
) -> Dict[str, float]:
    valid = {k: max(0.0, float(v)) for k, v in raw.items() if float(v) > 0}
    if not valid:
        return {}
    out = {k: 0.0 for k in valid}
    remaining = 1.0
    m_used: Dict[str, float] = {}
    r_used: Dict[str, float] = {}
    s_used: Dict[str, float] = {}

    for _ in range(50):
        if remaining <= 1e-8:
            break
        active = []
        for s, base in valid.items():
            if base <= 0:
                continue
            m = market_of_symbol(s)
            r = region_of_market(m)
            sec = sector_map.get(s, "Other")
            sym_left = sym_cap - out[s]
            m_left = market_cap - m_used.get(m, 0.0)
            r_left = region_cap - r_used.get(r, 0.0)
            s_left = sector_cap - s_used.get(sec, 0.0)
            cap_left = min(sym_left, m_left, r_left, s_left)
            if cap_left > 1e-8:
                active.append((s, base, m, r, sec, cap_left))
        if not active:
            break

        total_base = sum(x[1] for x in active)
        if total_base <= 0:
            break
        moved = 0.0
        for s, base, m, r, sec, cap_left in active:
            target = remaining * (base / total_base)
            add = min(target, cap_left)
            if add <= 1e-12:
                continue
            out[s] += add
            m_used[m] = m_used.get(m, 0.0) + add
            r_used[r] = r_used.get(r, 0.0) + add
            s_used[sec] = s_used.get(sec, 0.0) + add
            moved += add
        if moved <= 1e-10:
            break
        remaining = max(0.0, 1.0 - sum(out.values()))
    return out


def analyze_symbol(symbol: str, bars: List[Bar]) -> Dict[str, Any]:
    closes = [b.close for b in bars]
    if len(closes) < 80:
        return {"symbol": symbol, "ok": False, "reason": "insufficient_data"}

    last = bars[-1]
    sma20 = sma(closes, 20)
    sma60 = sma(closes, 60)
    rsi14 = rsi(closes, 14)
    atr14 = atr(bars, 14)
    mom20 = ((closes[-1] / closes[-21]) - 1.0) * 100 if len(closes) >= 21 else None
    vol20 = annualized_volatility(closes, 20)
    atr_pct = (atr14 / closes[-1] * 100.0) if (atr14 is not None and closes[-1] > 0) else None

    trend_up = bool(sma20 and sma60 and closes[-1] > sma20 > sma60)
    trend_down = bool(sma20 and sma60 and closes[-1] < sma20 < sma60)

    signal = "HOLD"
    if trend_up and (rsi14 is not None and rsi14 < 68):
        signal = "BUY"
    elif trend_down or (rsi14 is not None and rsi14 > 78):
        signal = "SELL"

    highs20 = [b.high for b in bars[-20:]]
    lows20 = [b.low for b in bars[-20:]]
    vols20 = [b.volume for b in bars[-20:]]
    vols60 = [b.volume for b in bars[-60:]]
    v20 = mean(vols20)
    v60 = mean(vols60)
    volume_ratio = (v20 / v60) if (v20 is not None and v60 and v60 > 0) else None
    trend_gap = ((closes[-1] / sma60) - 1.0) * 100 if sma60 else None

    return {
        "symbol": symbol,
        "ok": True,
        "date": last.date,
        "close": round(last.close, 6),
        "sma20": round(sma20, 6) if sma20 else None,
        "sma60": round(sma60, 6) if sma60 else None,
        "rsi14": round(rsi14, 2) if rsi14 is not None else None,
        "atr14": round(atr14, 6) if atr14 is not None else None,
        "atr_pct": round(atr_pct, 3) if atr_pct is not None else None,
        "vol20_pct": round(vol20, 3) if vol20 is not None else None,
        "trend_gap_pct": round(trend_gap, 3) if trend_gap is not None else None,
        "volume_ratio_20_60": round(volume_ratio, 3) if volume_ratio is not None else None,
        "mom20_pct": round(mom20, 2) if mom20 is not None else None,
        "signal": signal,
        "support_20d": round(min(lows20), 6) if lows20 else None,
        "resistance_20d": round(max(highs20), 6) if highs20 else None,
        "risk_tags": [
            "trend_following",
            "non_realtime_data",
            "free_data_sources",
        ],
    }


def max_drawdown(equity: List[float]) -> float:
    if not equity:
        return 0.0
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        dd = (v / peak) - 1.0
        mdd = min(mdd, dd)
    return mdd * 100


def backtest_symbol(symbol: str, bars: List[Bar]) -> Dict[str, Any]:
    closes = [b.close for b in bars]
    if len(closes) < 120:
        return {"symbol": symbol, "ok": False, "reason": "insufficient_data"}

    position = 0
    entry = 0.0
    trade_pnls: List[float] = []
    equity = [1.0]

    for i in range(61, len(bars)):
        window = closes[: i + 1]
        c = closes[i]
        prev = closes[i - 1]
        s20 = sma(window, 20)
        s60 = sma(window, 60)
        rs = rsi(window, 14)

        if position == 0 and s20 and s60 and c > s20 > s60 and (rs is None or rs < 70):
            position = 1
            entry = c
        elif position == 1 and ((s20 and c < s20) or (rs is not None and rs > 78)):
            pnl = (c / entry) - 1.0
            trade_pnls.append(pnl)
            position = 0

        eq = equity[-1]
        if position == 1:
            eq = eq * (c / prev)
        equity.append(eq)

    if position == 1:
        pnl = (closes[-1] / entry) - 1.0
        trade_pnls.append(pnl)

    total_ret = (equity[-1] - 1.0) * 100
    years = max(1.0, len(closes) / 252.0)
    cagr = ((equity[-1]) ** (1.0 / years) - 1.0) * 100

    daily_rets = []
    for i in range(1, len(equity)):
        if equity[i - 1] > 0:
            daily_rets.append((equity[i] / equity[i - 1]) - 1.0)
    sharpe = 0.0
    if len(daily_rets) > 2 and statistics.pstdev(daily_rets) > 0:
        sharpe = (statistics.mean(daily_rets) / statistics.pstdev(daily_rets)) * math.sqrt(252)

    wins = sum(1 for p in trade_pnls if p > 0)
    total = len(trade_pnls)

    return {
        "symbol": symbol,
        "ok": True,
        "trades": total,
        "win_rate": round((wins / total) * 100, 2) if total else 0.0,
        "total_return_pct": round(total_ret, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(max_drawdown(equity), 2),
        "sharpe": round(sharpe, 3),
    }


def score_factors(rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> None:
    fac_cfg = cfg.get("factors", {})
    weights = fac_cfg.get("weights", {})
    w_mom = float(weights.get("momentum", 0.3))
    w_trend = float(weights.get("trend", 0.25))
    w_vol = float(weights.get("volatility", 0.2))
    w_rsi = float(weights.get("rsi_regime", 0.15))
    w_liq = float(weights.get("liquidity", 0.1))
    w_sum = w_mom + w_trend + w_vol + w_rsi + w_liq
    if w_sum <= 0:
        w_sum = 1.0

    ok_rows = [r for r in rows if r.get("ok")]
    moms = [float(r.get("mom20_pct")) for r in ok_rows if r.get("mom20_pct") is not None]
    trends = [float(r.get("trend_gap_pct")) for r in ok_rows if r.get("trend_gap_pct") is not None]
    vols = [float(r.get("vol20_pct")) for r in ok_rows if r.get("vol20_pct") is not None]
    liqs = [float(r.get("volume_ratio_20_60")) for r in ok_rows if r.get("volume_ratio_20_60") is not None]

    for r in ok_rows:
        mom = float(r.get("mom20_pct") or 0.0)
        trend = float(r.get("trend_gap_pct") or 0.0)
        vol = float(r.get("vol20_pct") or 99.0)
        rsi14 = float(r.get("rsi14") or 50.0)
        liq = float(r.get("volume_ratio_20_60") or 1.0)

        mom_s = percentile_rank(moms, mom, reverse=False)
        trend_s = percentile_rank(trends, trend, reverse=False)
        vol_s = percentile_rank(vols, vol, reverse=True)
        rsi_pref = max(0.0, 1.0 - abs(rsi14 - 55.0) / 55.0)
        liq_s = percentile_rank(liqs, liq, reverse=False)

        raw = (w_mom * mom_s + w_trend * trend_s + w_vol * vol_s + w_rsi * rsi_pref + w_liq * liq_s) / w_sum
        score = max(0.0, min(100.0, raw * 100.0))

        bucket = "C"
        if score >= 75:
            bucket = "A"
        elif score >= 60:
            bucket = "B"
        elif score >= 45:
            bucket = "B-"

        r["factor_score"] = round(score, 2)
        r["factor_bucket"] = bucket
        r["factor_breakdown"] = {
            "momentum": round(mom_s, 3),
            "trend": round(trend_s, 3),
            "volatility": round(vol_s, 3),
            "rsi_regime": round(rsi_pref, 3),
            "liquidity": round(liq_s, 3),
        }


def build_portfolio(analyze_rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    p_cfg = cfg.get("portfolio", {})
    target_vol_pct = float(p_cfg.get("target_vol_pct", 12.0))
    max_leverage = float(p_cfg.get("max_leverage", 1.5))
    max_single = _norm_cap(p_cfg.get("max_single_weight_pct", 18.0), 18.0)
    max_market = _norm_cap(p_cfg.get("max_market_weight_pct", 45.0), 45.0)
    max_region = _norm_cap(p_cfg.get("max_region_weight_pct", 70.0), 70.0)
    max_sector = _norm_cap(p_cfg.get("max_sector_weight_pct", 35.0), 35.0)
    min_score = float(p_cfg.get("min_factor_score", 60.0))

    candidates = [
        r
        for r in analyze_rows
        if r.get("ok")
        and r.get("signal") != "SELL"
        and float(r.get("factor_score", 0.0)) >= min_score
        and r.get("vol20_pct") is not None
    ]
    if not candidates:
        return {
            "ok": False,
            "reason": "no_candidates",
            "target_vol_pct": target_vol_pct,
            "items": [],
        }

    raw = {}
    sector_map: Dict[str, str] = {}
    for r in candidates:
        vol = max(float(r.get("vol20_pct") or 0.0) / 100.0, 0.05)
        raw[r["symbol"]] = 1.0 / vol
        sector_map[r["symbol"]] = sector_of_symbol(r["symbol"], cfg)
    base = constrained_allocate(raw, sector_map, max_single, max_market, max_region, max_sector)
    if not base:
        return {
            "ok": False,
            "reason": "capacity_constraints_exhausted",
            "target_vol_pct": target_vol_pct,
            "items": [],
        }

    vol_map = {r["symbol"]: max(float(r.get("vol20_pct") or 0.0) / 100.0, 0.05) for r in candidates}
    port_vol = math.sqrt(sum((w * vol_map.get(s, 0.2)) ** 2 for s, w in base.items())) * 100.0

    base_market_exp: Dict[str, float] = {}
    base_region_exp: Dict[str, float] = {}
    base_sector_exp: Dict[str, float] = {}
    for sym, w in base.items():
        mkt = market_of_symbol(sym)
        reg = region_of_market(mkt)
        sec = sector_map.get(sym, "Other")
        base_market_exp[mkt] = base_market_exp.get(mkt, 0.0) + w
        base_region_exp[reg] = base_region_exp.get(reg, 0.0) + w
        base_sector_exp[sec] = base_sector_exp.get(sec, 0.0) + w

    lev_cap_single = (max_single / max(base.values())) if base else 1.0
    lev_cap_market = min((max_market / v) for v in base_market_exp.values()) if base_market_exp else 1.0
    lev_cap_region = min((max_region / v) for v in base_region_exp.values()) if base_region_exp else 1.0
    lev_cap_sector = min((max_sector / v) for v in base_sector_exp.values()) if base_sector_exp else 1.0
    lev_cap = min(lev_cap_single, lev_cap_market, lev_cap_region, lev_cap_sector)
    lev = 1.0
    if port_vol > 0:
        lev = min(max_leverage, target_vol_pct / port_vol, lev_cap)
    final = {k: v * lev for k, v in base.items()}
    gross = sum(final.values())
    cash = max(0.0, 1.0 - gross)

    score_map = {r["symbol"]: float(r.get("factor_score") or 0.0) for r in candidates}
    out_items = []
    for sym, w in sorted(final.items(), key=lambda x: x[1], reverse=True):
        mkt = market_of_symbol(sym)
        sec = sector_map.get(sym, "Other")
        out_items.append(
            {
                "symbol": sym,
                "market": mkt,
                "region": region_of_market(mkt),
                "sector": sec,
                "weight_pct": round(w * 100.0, 2),
                "factor_score": round(score_map.get(sym, 0.0), 2),
            }
        )

    market_exp: Dict[str, float] = {}
    region_exp: Dict[str, float] = {}
    sector_exp: Dict[str, float] = {}
    for sym, w in final.items():
        mkt = market_of_symbol(sym)
        reg = region_of_market(mkt)
        sec = sector_map.get(sym, "Other")
        market_exp[mkt] = market_exp.get(mkt, 0.0) + w * 100.0
        region_exp[reg] = region_exp.get(reg, 0.0) + w * 100.0
        sector_exp[sec] = sector_exp.get(sec, 0.0) + w * 100.0

    return {
        "ok": True,
        "method": "risk_parity_with_target_vol",
        "target_vol_pct": round(target_vol_pct, 2),
        "estimated_portfolio_vol_pct": round(port_vol * lev, 2),
        "base_vol_pct": round(port_vol, 2),
        "leverage": round(lev, 3),
        "gross_exposure_pct": round(gross * 100.0, 2),
        "cash_weight_pct": round(cash * 100.0, 2),
        "constraints": {
            "max_single_weight_pct": round(max_single * 100.0, 2),
            "max_market_weight_pct": round(max_market * 100.0, 2),
            "max_region_weight_pct": round(max_region * 100.0, 2),
            "max_sector_weight_pct": round(max_sector * 100.0, 2),
        },
        "exposure": {
            "market_pct": {k: round(v, 2) for k, v in sorted(market_exp.items())},
            "region_pct": {k: round(v, 2) for k, v in sorted(region_exp.items())},
            "sector_pct": {k: round(v, 2) for k, v in sorted(sector_exp.items())},
        },
        "items": out_items,
    }


def _series_metrics(nav: List[float]) -> Dict[str, float]:
    if len(nav) < 2:
        return {"total_return_pct": 0.0, "cagr_pct": 0.0, "max_drawdown_pct": 0.0, "sharpe": 0.0}
    total_ret = (nav[-1] - 1.0) * 100.0
    years = max(1.0 / 252.0, len(nav) / 252.0)
    cagr = ((nav[-1]) ** (1.0 / years) - 1.0) * 100.0 if nav[-1] > 0 else -100.0
    mdd = max_drawdown(nav)
    rets = []
    for i in range(1, len(nav)):
        if nav[i - 1] > 0:
            rets.append((nav[i] / nav[i - 1]) - 1.0)
    sharpe = 0.0
    if len(rets) > 2 and statistics.pstdev(rets) > 0:
        sharpe = (statistics.mean(rets) / statistics.pstdev(rets)) * math.sqrt(252)
    return {
        "total_return_pct": round(total_ret, 2),
        "cagr_pct": round(cagr, 2),
        "max_drawdown_pct": round(mdd, 2),
        "sharpe": round(sharpe, 3),
    }


def _window_candidates(data: Dict[str, List[Bar]], end_idx: int, cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sym, bars in data.items():
        if end_idx >= len(bars):
            continue
        sub = bars[: end_idx + 1]
        row = analyze_symbol(sym, sub)
        rows.append(row)
    score_factors(rows, cfg)
    return rows


def backtest_portfolio(data: Dict[str, List[Bar]], cfg: Dict[str, Any], requested_symbols: List[str]) -> Dict[str, Any]:
    pbt = cfg.get("portfolio_backtest", {})
    rebalance_days = max(5, int(pbt.get("rebalance_days", 20)))
    transaction_cost_bps = max(0.0, float(pbt.get("transaction_cost_bps", 4.0)))
    slippage_bps = max(0.0, float(pbt.get("slippage_bps", 3.0)))
    warmup_bars = max(80, int(pbt.get("warmup_bars", 120)))
    benchmark_symbol = str(pbt.get("benchmark_symbol", "SPY"))
    drawdown_circuit_pct = max(1.0, float(pbt.get("drawdown_circuit_pct", 12.0)))
    recovery_drawdown_pct = max(0.5, float(pbt.get("recovery_drawdown_pct", 6.0)))
    delever_to = max(0.05, min(1.0, float(pbt.get("delever_to", 0.35))))

    # Keep symbols that have enough data and align by truncating to the shortest history.
    symbols = [s for s in requested_symbols if s in data and len(data[s]) >= warmup_bars + 2]
    if len(symbols) < 2:
        return {"ok": False, "reason": "insufficient_symbols", "symbols": symbols}

    min_len = min(len(data[s]) for s in symbols)
    symbols = [s for s in symbols if len(data[s]) >= min_len]
    closes = {s: [b.close for b in data[s][-min_len:]] for s in symbols}
    dates = [b.date for b in data[symbols[0]][-min_len:]]

    bench = benchmark_symbol if benchmark_symbol in data and len(data[benchmark_symbol]) >= min_len else symbols[0]
    bench_closes = [b.close for b in data[bench][-min_len:]]

    nav = [1.0]
    nav_bench = [1.0]
    cur_w: Dict[str, float] = {}
    turnover_sum = 0.0
    rebalance_count = 0
    last_portfolio: Dict[str, Any] = {"ok": False}
    peak_nav = 1.0
    risk_off = False
    risk_off_days = 0
    circuit_triggers = 0

    cost_rate = (transaction_cost_bps + slippage_bps) / 10000.0

    for i in range(1, min_len):
        # Drift on daily returns with previous weights.
        day_ret = 0.0
        for s, w in cur_w.items():
            prev = closes[s][i - 1]
            cur = closes[s][i]
            if prev > 0:
                day_ret += w * ((cur / prev) - 1.0)
        nav.append(nav[-1] * (1.0 + day_ret))

        bp = bench_closes[i - 1]
        bc = bench_closes[i]
        bret = ((bc / bp) - 1.0) if bp > 0 else 0.0
        nav_bench.append(nav_bench[-1] * (1.0 + bret))

        peak_nav = max(peak_nav, nav[-1])
        dd = ((nav[-1] / peak_nav) - 1.0) * 100.0 if peak_nav > 0 else 0.0
        if (not risk_off) and dd <= -drawdown_circuit_pct:
            risk_off = True
            circuit_triggers += 1
            if cur_w:
                reduced = {k: v * delever_to for k, v in cur_w.items()}
                cut_turnover = sum(abs(reduced.get(k, 0.0) - cur_w.get(k, 0.0)) for k in set(cur_w) | set(reduced))
                nav[-1] = nav[-1] * max(0.0, 1.0 - cut_turnover * cost_rate)
                turnover_sum += cut_turnover
                cur_w = reduced
        if risk_off:
            risk_off_days += 1
            if dd >= -recovery_drawdown_pct:
                risk_off = False

        need_rebalance = i >= warmup_bars and ((i - warmup_bars) % rebalance_days == 0)
        if not need_rebalance:
            continue

        window_data = {s: data[s][-min_len:][: i + 1] for s in symbols}
        rows = _window_candidates(window_data, i, cfg)
        port = build_portfolio(rows, cfg)
        if not port.get("ok"):
            continue
        target = {x["symbol"]: float(x["weight_pct"]) / 100.0 for x in port.get("items", [])}
        if not target:
            continue
        if risk_off:
            target = {k: v * delever_to for k, v in target.items()}

        keys = set(cur_w) | set(target)
        turnover = sum(abs(target.get(k, 0.0) - cur_w.get(k, 0.0)) for k in keys)
        nav[-1] = nav[-1] * max(0.0, 1.0 - turnover * cost_rate)
        cur_w = target
        turnover_sum += turnover
        rebalance_count += 1
        last_portfolio = port

    strat = _series_metrics(nav)
    bench_m = _series_metrics(nav_bench)
    excess = round(strat["total_return_pct"] - bench_m["total_return_pct"], 2)

    return {
        "ok": True,
        "method": "dynamic_factor_risk_parity",
        "symbols": symbols,
        "benchmark_symbol": bench,
        "rebalance_days": rebalance_days,
        "rebalance_count": rebalance_count,
        "transaction_cost_bps": transaction_cost_bps,
        "slippage_bps": slippage_bps,
        "avg_turnover_pct": round((turnover_sum / rebalance_count) * 100.0, 2) if rebalance_count > 0 else 0.0,
        "drawdown_circuit_pct": drawdown_circuit_pct,
        "recovery_drawdown_pct": recovery_drawdown_pct,
        "delever_to": round(delever_to, 3),
        "circuit_triggers": circuit_triggers,
        "risk_off_days": risk_off_days,
        "strategy": strat,
        "benchmark": bench_m,
        "excess_total_return_pct": excess,
        "last_portfolio": last_portfolio,
        "nav_tail": [round(x, 6) for x in nav[-20:]],
        "bench_nav_tail": [round(x, 6) for x in nav_bench[-20:]],
        "start_date": dates[0],
        "end_date": dates[-1],
        "days": len(dates),
    }


def resolve_symbols(cfg: Dict[str, Any], args: argparse.Namespace) -> List[str]:
    if args.symbols:
        return parse_symbols(args.symbols)
    return get_universe(cfg, args.universe)


def cmd_sync(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    timeout = int(defaults.get("request_timeout_sec", 15))
    providers = list(defaults.get("providers", ["stooq", "yahoo"]))
    verify_ssl = bool(defaults.get("ssl_verify", True))
    insecure_fallback = bool(defaults.get("ssl_insecure_fallback", True))
    cache_dir = Path(str(defaults.get("cache_dir", ROOT / "日志/stock_quant/cache")))
    if not cache_dir.is_absolute():
        cache_dir = ROOT / cache_dir

    symbols = resolve_symbols(cfg, args)
    if args.limit > 0:
        symbols = symbols[: args.limit]

    synced = []
    failed = []

    for sym in symbols:
        bars = []
        used = ""
        err = ""
        for p in providers:
            try:
                if p == "stooq":
                    bars = fetch_stooq(sym, timeout, verify_ssl=verify_ssl, insecure_fallback=insecure_fallback)
                elif p == "yahoo":
                    bars = fetch_yahoo(sym, timeout, verify_ssl=verify_ssl, insecure_fallback=insecure_fallback)
                else:
                    continue
                if bars:
                    used = p
                    break
            except Exception as e:
                err = str(e)
                continue
        if bars:
            save_cache(cache_path(cache_dir, sym), sym, used, bars)
            synced.append({"symbol": sym, "provider": used, "bars": len(bars)})
        else:
            failed.append({"symbol": sym, "error": err or "no_data"})

    return {
        "synced": len(synced),
        "failed": len(failed),
        "synced_items": synced,
        "failed_items": failed,
    }


def load_symbols_from_cache(cfg: Dict[str, Any], symbols: List[str]) -> Dict[str, List[Bar]]:
    cache_dir = Path(str(cfg.get("defaults", {}).get("cache_dir", ROOT / "日志/stock_quant/cache")))
    if not cache_dir.is_absolute():
        cache_dir = ROOT / cache_dir
    out = {}
    for s in symbols:
        bars = load_cache(cache_path(cache_dir, s))
        if bars:
            out[s] = bars
    return out


def cmd_analyze(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    symbols = resolve_symbols(cfg, args)
    if args.limit > 0:
        symbols = symbols[: args.limit]
    data = load_symbols_from_cache(cfg, symbols)
    rows = [analyze_symbol(s, b) for s, b in data.items()]
    score_factors(rows, cfg)
    rows.sort(key=lambda x: (x.get("signal") != "BUY", -(x.get("factor_score") or 0.0), -(x.get("mom20_pct") or -9999)))
    return {"count": len(rows), "items": rows}


def cmd_backtest(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    symbols = resolve_symbols(cfg, args)
    if args.limit > 0:
        symbols = symbols[: args.limit]
    data = load_symbols_from_cache(cfg, symbols)
    rows = [backtest_symbol(s, b) for s, b in data.items()]
    rows = [r for r in rows if r.get("ok")]
    rows.sort(key=lambda x: (x.get("sharpe", -999), x.get("total_return_pct", -999)), reverse=True)
    return {"count": len(rows), "items": rows}


def cmd_portfolio(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    analyze = cmd_analyze(cfg, args)
    port = build_portfolio(analyze.get("items", []), cfg)
    symbols = resolve_symbols(cfg, args)
    if args.limit > 0:
        symbols = symbols[: args.limit]
    data = load_symbols_from_cache(cfg, symbols)
    pbt = backtest_portfolio(data, cfg, symbols)
    return {"analyze_count": analyze.get("count", 0), "portfolio": port, "portfolio_backtest": pbt}


def cmd_portfolio_backtest(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    symbols = resolve_symbols(cfg, args)
    if args.limit > 0:
        symbols = symbols[: args.limit]
    data = load_symbols_from_cache(cfg, symbols)
    return {"portfolio_backtest": backtest_portfolio(data, cfg, symbols)}


def render_report(
    analyze: Dict[str, Any],
    backtest: Dict[str, Any],
    portfolio: Dict[str, Any],
    portfolio_backtest: Dict[str, Any],
    universe: str,
) -> str:
    buys = [x for x in analyze.get("items", []) if x.get("signal") == "BUY"]
    sells = [x for x in analyze.get("items", []) if x.get("signal") == "SELL"]
    lines = [
        "# 全球股票市场 + 量化分析报告",
        "",
        f"- Universe: {universe}",
        f"- 分析标的数: {analyze.get('count', 0)}",
        f"- BUY数: {len(buys)} | SELL数: {len(sells)}",
        "",
        "## 优先关注（BUY Top10）",
        "",
        "| Symbol | Close | Factor | Mom20% | RSI14 | Support(20D) | Resistance(20D) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in buys[:10]:
        lines.append(
            f"| {r['symbol']} | {r.get('close')} | {r.get('factor_score')} | {r.get('mom20_pct')} | {r.get('rsi14')} | {r.get('support_20d')} | {r.get('resistance_20d')} |"
        )

    lines.extend([
        "",
        "## 回测表现（Top10 by Sharpe）",
        "",
        "| Symbol | Trades | WinRate% | TotalRet% | CAGR% | MaxDD% | Sharpe |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for r in backtest.get("items", [])[:10]:
        lines.append(
            f"| {r['symbol']} | {r.get('trades')} | {r.get('win_rate')} | {r.get('total_return_pct')} | {r.get('cagr_pct')} | {r.get('max_drawdown_pct')} | {r.get('sharpe')} |"
        )

    lines.extend([
        "",
        "## 组合建议（风险平价 + 目标波动）",
        "",
    ])
    if portfolio.get("ok"):
        lines.extend([
            f"- 目标波动率: {portfolio.get('target_vol_pct')}%",
            f"- 组合预估波动率: {portfolio.get('estimated_portfolio_vol_pct')}%",
            f"- 杠杆: {portfolio.get('leverage')}",
            f"- 总敞口: {portfolio.get('gross_exposure_pct')}% | 现金: {portfolio.get('cash_weight_pct')}%",
            f"- 约束: 单票<= {portfolio.get('constraints',{}).get('max_single_weight_pct')}% | 单市场<= {portfolio.get('constraints',{}).get('max_market_weight_pct')}% | 单地区<= {portfolio.get('constraints',{}).get('max_region_weight_pct')}% | 单行业<= {portfolio.get('constraints',{}).get('max_sector_weight_pct')}%",
            "",
            "| Symbol | Mkt | Region | Sector | Weight% | FactorScore |",
            "|---|---|---|---|---:|---:|",
        ])
        for x in portfolio.get("items", [])[:12]:
            lines.append(f"| {x.get('symbol')} | {x.get('market')} | {x.get('region')} | {x.get('sector')} | {x.get('weight_pct')} | {x.get('factor_score')} |")
        mexp = portfolio.get("exposure", {}).get("market_pct", {})
        rexp = portfolio.get("exposure", {}).get("region_pct", {})
        sexp = portfolio.get("exposure", {}).get("sector_pct", {})
        if mexp:
            lines.append("")
            lines.append(f"- 市场暴露: {mexp}")
        if rexp:
            lines.append(f"- 地区暴露: {rexp}")
        if sexp:
            lines.append(f"- 行业暴露: {sexp}")
    else:
        lines.append("- 候选不足，未生成组合建议。")

    lines.extend([
        "",
        "## 组合级回测",
        "",
    ])
    if portfolio_backtest.get("ok"):
        s = portfolio_backtest.get("strategy", {})
        b = portfolio_backtest.get("benchmark", {})
        lines.extend([
            f"- 区间: {portfolio_backtest.get('start_date')} ~ {portfolio_backtest.get('end_date')}",
            f"- 再平衡: 每 {portfolio_backtest.get('rebalance_days')} 个交易日 | 次数 {portfolio_backtest.get('rebalance_count')}",
            f"- 成本: 交易 {portfolio_backtest.get('transaction_cost_bps')} bps + 滑点 {portfolio_backtest.get('slippage_bps')} bps",
            f"- 平均换手: {portfolio_backtest.get('avg_turnover_pct')}%",
            f"- 熔断: 回撤触发 {portfolio_backtest.get('drawdown_circuit_pct')}% | 恢复阈值 {portfolio_backtest.get('recovery_drawdown_pct')}% | 风险仓位 {portfolio_backtest.get('delever_to')}",
            f"- 熔断统计: 触发 {portfolio_backtest.get('circuit_triggers')} 次 | 风险关闭天数 {portfolio_backtest.get('risk_off_days')}",
            "",
            "| 维度 | 策略 | 基准 |",
            "|---|---:|---:|",
            f"| TotalRet% | {s.get('total_return_pct')} | {b.get('total_return_pct')} |",
            f"| CAGR% | {s.get('cagr_pct')} | {b.get('cagr_pct')} |",
            f"| MaxDD% | {s.get('max_drawdown_pct')} | {b.get('max_drawdown_pct')} |",
            f"| Sharpe | {s.get('sharpe')} | {b.get('sharpe')} |",
            "",
            f"- 超额收益(策略-基准): {portfolio_backtest.get('excess_total_return_pct')}%",
        ])
    else:
        lines.append("- 数据不足，未生成组合级回测。")

    lines.extend([
        "",
        "## 风险提示",
        "",
        "- 本模块基于免费公开数据源，存在非实时与补丁延迟。",
        "- 信号仅作研究用途，不构成投资建议。",
        "- 建议叠加基本面、流动性与事件风险做二次确认。",
        "",
    ])
    return "\n".join(lines)


def cmd_report(cfg: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
    analyze = cmd_analyze(cfg, args)
    backtest = cmd_backtest(cfg, args)
    portfolio = build_portfolio(analyze.get("items", []), cfg)
    portfolio_backtest = cmd_portfolio_backtest(cfg, args).get("portfolio_backtest", {})

    report_dir = Path(str(cfg.get("defaults", {}).get("report_dir", ROOT / "日志/stock_quant/reports")))
    if not report_dir.is_absolute():
        report_dir = ROOT / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    md_file = report_dir / f"stock_quant_{args.universe}_{ts}.md"
    payload = {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "universe": args.universe,
        "analyze": analyze,
        "backtest": backtest,
        "portfolio": portfolio,
        "portfolio_backtest": portfolio_backtest,
        "report_md": str(md_file),
    }
    md_file.write_text(render_report(analyze, backtest, portfolio, portfolio_backtest, args.universe), encoding="utf-8")

    latest = report_dir / "latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Global stock quant engine")
    p.add_argument("--config", default=str(CFG_DEFAULT))

    sub = p.add_subparsers(dest="cmd")

    uv = sub.add_parser("universe", help="show universe symbols")
    uv.add_argument("--config", default=str(CFG_DEFAULT))
    uv.add_argument("--universe", default="global_core")

    for name in ["sync", "analyze", "backtest", "portfolio", "portfolio-backtest", "report", "run"]:
        s = sub.add_parser(name)
        s.add_argument("--config", default=str(CFG_DEFAULT))
        s.add_argument("--universe", default="global_core")
        s.add_argument("--symbols", default="")
        s.add_argument("--limit", type=int, default=0)

    return p


def main() -> int:
    parser = build_cli()
    args = parser.parse_args()

    if not args.cmd:
        parser.print_help()
        return 2

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)

    if args.cmd == "universe":
        out = {"universe": args.universe, "symbols": get_universe(cfg, args.universe)}
    elif args.cmd == "sync":
        out = cmd_sync(cfg, args)
    elif args.cmd == "analyze":
        out = cmd_analyze(cfg, args)
    elif args.cmd == "backtest":
        out = cmd_backtest(cfg, args)
    elif args.cmd == "report":
        out = cmd_report(cfg, args)
    elif args.cmd == "portfolio":
        out = cmd_portfolio(cfg, args)
    elif args.cmd == "portfolio-backtest":
        out = cmd_portfolio_backtest(cfg, args)
    elif args.cmd == "run":
        _ = cmd_sync(cfg, args)
        out = cmd_report(cfg, args)
    else:
        out = {"ok": False, "error": f"unknown cmd: {args.cmd}"}

    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
