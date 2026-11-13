"""Run the H1 and H2 tests from PLAN.md and the listed robustness checks.

python analysis.py > results.txt
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

from build import frame, split
from fetch import hashes

# fixed in PLAN.md amendments, 2026-11-13
Z90 = 1.708
Z80 = 0.803
Z90_SMOOTH = 1.660
Z90_USDT = 1.876
Z90_USDC = 1.368
DOLLAR90 = 2.276e9
DECILE_EDGES = [-1.134, -0.955, -0.694, -0.393, -0.232, 0.020, 0.417, 0.803, 1.708]
BLOCK = 4
N_BOOT = 10_000


def block_indices(n, block, rng):
    starts = rng.integers(0, n - block + 1, size=int(np.ceil(n / block)))
    return np.concatenate([np.arange(s, s + block) for s in starts])[:n]


def block_bootstrap_diff(top, y, n=N_BOOT, block=BLOCK, seed=0):
    """Mean y in top weeks minus mean y in the rest, moving block bootstrap.

    Returns (diff, one-sided p = share of resampled diffs <= 0, 2.5%, 97.5%, dropped).
    """
    top, y = np.asarray(top, bool), np.asarray(y, float)
    diff = y[top].mean() - y[~top].mean()
    rng = np.random.default_rng(seed)
    out, dropped = [], 0
    for _ in range(n):
        i = block_indices(len(y), block, rng)
        t, v = top[i], y[i]
        if t.all() or not t.any():
            dropped += 1
            continue
        out.append(v[t].mean() - v[~t].mean())
    out = np.array(out)
    return diff, (out <= 0).mean(), *np.percentile(out, [2.5, 97.5]), dropped


def block_bootstrap_mean(y, n=N_BOOT, block=BLOCK, seed=0):
    y = np.asarray(y, float)
    rng = np.random.default_rng(seed)
    means = [y[block_indices(len(y), block, rng)].mean() for _ in range(n)]
    return np.percentile(means, [2.5, 97.5])


def one_sided(coef, p_two):
    return p_two / 2 if coef > 0 else 1 - p_two / 2


def ols(y, X, lags=4):
    X = sm.add_constant(X)
    return sm.OLS(y, X, missing="drop").fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def h1(sample, thr, ret="r_next"):
    s = sample.dropna(subset=["z", ret])
    top = (s["z"] > thr).to_numpy()
    diff, p, lo, hi, dropped = block_bootstrap_diff(top, s[ret].to_numpy())
    return dict(n=len(s), n_top=int(top.sum()), mean_top=s[ret][top].mean(),
                mean_rest=s[ret][~top].mean(), diff=diff, p=p, lo=lo, hi=hi, dropped=dropped,
                welch_p=one_sided(diff, stats.ttest_ind(s[ret][top], s[ret][~top], equal_var=False).pvalue))


def h1_dollar(sample, ret="r_next"):
    s = sample.dropna(subset=["dollar", ret])
    top = (s["dollar"] > DOLLAR90).to_numpy()
    diff, p, lo, hi, dropped = block_bootstrap_diff(top, s[ret].to_numpy())
    return dict(n=len(s), n_top=int(top.sum()), diff=diff, p=p, lo=lo, hi=hi)


def h2(sample):
    s = sample.dropna(subset=["z", "r", "r_lag1", "r_next"])
    m = ols(s["r_next"], s[["z", "r", "r_lag1"]])
    return m, one_sided(m.params["z"], m.pvalues["z"])


def follows_price(w):
    s = w.copy()
    for k in (1, 2, 3):
        s[f"r_lag{k}"] = w["r"].shift(k)
    s = s.dropna(subset=["z", "r_lag1", "r_lag2", "r_lag3"])
    return ols(s["z"], s[["r_lag1", "r_lag2", "r_lag3"]])


def pct(x):
    return f"{100 * x:+.2f}%"


def fmt_h1(name, d):
    return (f"{name:34s} n={d['n']:3d} top={d['n_top']:3d}  diff {pct(d['diff'])} "
            f"[{pct(d['lo'])}, {pct(d['hi'])}]  p={d['p']:.3f}")


def main():
    w = frame()
    train, test = split(w)
    test = test.dropna(subset=["r_next"])
    print("data:", {k: v[:8] for k, v in hashes().items()})
    print(f"test weeks {test.index[0].date()} to {test.index[-1].date()}")
    print()

    print("=== H1 (primary): next-week return, z above 1.708 vs rest ===")
    r = h1(test, Z90)
    print(f"test: n={r['n']} top weeks={r['n_top']}")
    print(f"  mean next-week log return top {pct(r['mean_top'])}, rest {pct(r['mean_rest'])}")
    print(f"  diff {pct(r['diff'])}, 95% block bootstrap [{pct(r['lo'])}, {pct(r['hi'])}], "
          f"one-sided p={r['p']:.3f} (dropped resamples {r['dropped']}), Welch one-sided p={r['welch_p']:.3f}")
    print(f"  H1 {'SUPPORTED' if r['diff'] > 0 and r['p'] < 0.05 else 'NOT SUPPORTED'}")
    print(f"  test top weeks: {[d.strftime('%Y-%m-%d') for d in test.index[test['z'] > Z90]]}")
    rt = h1(train.dropna(subset=['r_next']), Z90)
    print(f"training (threshold set here, not a test): top={rt['n_top']} diff {pct(rt['diff'])} "
          f"[{pct(rt['lo'])}, {pct(rt['hi'])}] p={rt['p']:.3f}")
    print()

    print("=== H2 (secondary): r_next ~ z + r + r_lag1, test, Newey-West 4 lags ===")
    m, p1 = h2(test)
    print(m.summary().tables[1])
    print(f"  b(z) = {m.params['z']:+.5f} per unit z, one-sided p={p1:.3f}, n={int(m.nobs)}")
    print(f"  H2 {'SUPPORTED' if m.params['z'] > 0 and p1 < 0.05 else 'NOT SUPPORTED'}")
    print()

    print("=== Description: does issuance follow price? z ~ r(t-1..t-3), Newey-West 4 lags ===")
    for name, s in (("training", train), ("test", test)):
        mm = follows_price(w.loc[s.index[0]:s.index[-1]])
        coefs = ", ".join(f"{k} {mm.params[k]:+.2f} (p {mm.pvalues[k]:.3f})" for k in ("r_lag1", "r_lag2", "r_lag3"))
        print(f"  {name}: {coefs}, R2 {mm.rsquared:.3f}, n={int(mm.nobs)}")
    print("  (z units per 1.0 log return, so +1.0 means a 10% week adds 0.1 to z)")
    print()

    print("=== Robustness (reported, never changes a verdict) ===")
    print(fmt_h1("no one-day gap", h1(test.dropna(subset=['r_next0']), Z90, ret="r_next0")))
    print(fmt_h1("3-day median supply", h1(split(frame(smooth=True))[1].dropna(subset=['r_next']), Z90_SMOOTH)))
    print(fmt_h1("USDT only", h1(split(frame(which=('usdt',)))[1].dropna(subset=['r_next']), Z90_USDT)))
    print(fmt_h1("USDC only", h1(split(frame(which=('usdc',)))[1].dropna(subset=['r_next']), Z90_USDC)))
    print(fmt_h1("top 20%", h1(test, Z80)))
    print(fmt_h1("raw dollar threshold $2.276bn", h1_dollar(test)))
    wc = frame(price="coinbase")
    print(fmt_h1("Coinbase BTC-USD returns", h1(split(wc)[1].dropna(subset=['r_next']), Z90)))
    print()

    print("=== Chart data: mean r_next by training-z decile ===")
    for name, s in (("training", train.dropna(subset=["r_next"])), ("test", test)):
        dec = np.digitize(s["z"], DECILE_EDGES) + 1
        row = []
        for k in range(1, 11):
            y = s["r_next"][dec == k]
            row.append(f"d{k} n={len(y)} {pct(y.mean())}")
        print(f"  {name}: " + " | ".join(row))


if __name__ == "__main__":
    pd.set_option("display.width", 140)
    main()
