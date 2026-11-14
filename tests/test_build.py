import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis import block_bootstrap_diff  # noqa: E402
from build import robust_z, weekly  # noqa: E402


def test_weekly_timing():
    days = pd.date_range("2020-01-06", periods=40, freq="D")
    s = pd.Series(np.arange(1, 41, dtype=float), index=days)  # S(D) = day number
    p = pd.Series(np.exp(np.arange(40, dtype=float)), index=days)  # log P(D) = day offset
    w = weekly(s, p)
    first = w.iloc[0]
    assert w.index[0] == pd.Timestamp("2020-01-06")
    assert first["dollar"] == 7
    assert np.isclose(first["r"], 7)            # M -> M+7
    assert np.isclose(first["r_next"], 7)       # M+8 -> M+15
    assert np.isnan(w.iloc[-1]["r_next"]) or w.index[-1] + pd.Timedelta(days=15) <= days[-1]


def test_robust_z_uses_only_past():
    g = pd.Series(np.r_[np.zeros(52), 1.0, 100.0])
    g.iloc[:52] = np.tile([-1.0, 1.0], 26)
    z = robust_z(g)
    assert np.isnan(z.iloc[51])
    # week 52 is scaled by weeks 0-51 only: median 0, MAD 1
    assert np.isclose(z.iloc[52], 1 / 1.4826)


def test_bootstrap_sign():
    rng = np.random.default_rng(1)
    top = np.r_[np.ones(10, bool), np.zeros(90, bool)]
    y = rng.normal(0, 1, 100) + 3 * top
    diff, p, lo, hi, dropped = block_bootstrap_diff(top, y, n=2000)
    assert diff > 2 and p < 0.01 and lo < diff < hi


def test_mint_events_declustered():
    from explore import mint_events
    idx = pd.date_range("2024-01-01", periods=30, freq="D")
    usd = pd.Series(0.0, index=idx)
    usd.iloc[[0, 3, 7, 8, 20]] = 2e9   # day 8 is 8 days after day 0, so it is kept
    ev = mint_events(pd.DataFrame({"usd": usd}))
    assert list(ev.day) == [1, 9, 21]
