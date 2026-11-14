"""Post-hoc checks of E6 (daily issuance -> return two days later), decided after seeing E6.

Not pre-registered. Reported as such in the README.
python posthoc_e6.py >> results_explore.txt
"""
import numpy as np

import build
from analysis import ols, one_sided
from build import TEST_START, TRAIN, prices
from explore import daily_frame


def fit(df, y, xs, label):
    s = df.dropna(subset=[y, *xs])
    m = ols(s[y], s[xs], lags=7)
    print(f"  {label:44s} b={m.params['zd'] * 100:+.3f}pp se {m.bse['zd'] * 100:.3f}  "
          f"one-sided p={one_sided(m.params['zd'], m.pvalues['zd']):.3f}  n={int(m.nobs)}")


def main():
    p = prices("binance")
    d = daily_frame(build.combined_supply(), p)
    lp = np.log(p)
    at = lambda k: lp.reindex(d.index + np.timedelta64(k, "D")).to_numpy()
    d["r_gap2"] = at(4) - at(3)
    d["r_nogap"] = at(2) - at(1)
    lags = [f"r_lag{k}" for k in range(1, 8)]
    test = d.loc[TEST_START:]
    print("=== Post-hoc checks of E6 (decided after seeing E6, not pre-registered) ===")
    fit(test, "r_next", ["zd"], "as E6")
    fit(test, "r_next", ["zd", "r_same", *lags], "control same-day and 7 lagged returns")
    fit(test, "r_gap2", ["zd"], "two-day gap")
    fit(test, "r_nogap", ["zd"], "no gap")
    fit(d.loc[TRAIN[0]:"2023-12-31"], "r_next", ["zd"], "training years 2021-23")
    for yr in ("2024", "2025", "2026"):
        fit(test.loc[yr], "r_next", ["zd"], f"test, {yr} only")
    w = test.dropna(subset=["zd", "r_next"]).copy()
    w["zd"] = w["zd"].clip(-5, 5)
    fit(w, "r_next", ["zd"], "zd winsorised at +-5")
    print(f"  daily return autocorrelation lag 1 (test): {test['r_same'].autocorr():.3f}")


if __name__ == "__main__":
    main()
