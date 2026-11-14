"""Turn raw files in data/ into the weekly frame defined in PLAN.md.

Timing (all UTC):
- supply S(D) is the DefiLlama value dated D 00:00.
- price P(D) is the daily close at D 00:00, i.e. the close of the candle that opened on D-1.
- for a week starting Monday M:
  g      = log S(M+7) - log S(M)
  r      = log P(M+7) - log P(M)
  r_next = log P(M+15) - log P(M+8)   (one-day gap, Tuesday to Tuesday)
  r_next0 = log P(M+14) - log P(M+7)  (no gap, robustness only)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parent / "data"
FIRST_WEEK = pd.Timestamp("2020-01-06")
TRAIN = (pd.Timestamp("2021-01-04"), pd.Timestamp("2023-12-25"))
TEST_START = pd.Timestamp("2024-01-01")
WINDOW = 52


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def supply(name):
    rows = _load(f"{name}.json")
    return pd.Series({pd.Timestamp(r["date"], unit="s"): r["circulating"] for r in rows},
                     name=name).sort_index()


def prices(name):
    """Price at 00:00 UTC of each day = close of the previous day's candle."""
    unit = "ms" if name.startswith("binance") else "s"
    rows = _load(f"{name}.json")
    s = pd.Series({pd.Timestamp(t, unit=unit) + pd.Timedelta(days=1): float(px) for t, px in rows})
    return s.sort_index()


def robust_z(g, window=WINDOW):
    """(g - trailing median) / (1.4826 * trailing MAD); window ends at t-1."""
    med = g.rolling(window).median().shift(1)
    mad = g.rolling(window).apply(lambda x: np.median(np.abs(x - np.median(x))), raw=True).shift(1)
    return (g - med) / (1.4826 * mad)


def weekly(s_daily, p_daily):
    """Weekly frame indexed by week-start Monday. Missing days stay missing."""
    last = min(s_daily.index.max(), p_daily.index.max())
    mondays = pd.date_range(FIRST_WEEK, last, freq="W-MON")
    S = lambda k: s_daily.reindex(mondays + pd.Timedelta(days=k)).to_numpy()
    P = lambda k: p_daily.reindex(mondays + pd.Timedelta(days=k)).to_numpy()
    w = pd.DataFrame(index=mondays)
    w["supply"] = S(0)
    w["dollar"] = S(7) - S(0)
    w["g"] = np.log(S(7)) - np.log(S(0))
    w["r"] = np.log(P(7)) - np.log(P(0))
    w["r_next"] = np.log(P(15)) - np.log(P(8))
    w["r_next0"] = np.log(P(14)) - np.log(P(7))
    w = w[w["g"].notna()]
    w["z"] = robust_z(w["g"])
    w["r_lag1"] = w["r"].shift(1)
    return w


def combined_supply(smooth=False, which=("usdt", "usdc")):
    s = sum(supply(n) for n in which).dropna()
    if smooth:
        s = s.rolling(3).median()  # trailing, so no day after D is used
    return s


def frame(smooth=False, which=("usdt", "usdc"), price="binance"):
    return weekly(combined_supply(smooth, which), prices(price))


def split(w):
    train = w.loc[TRAIN[0]:TRAIN[1]]
    test = w.loc[TEST_START:]
    return train, test
