"""Exploratory analyses E1-E11 from the 2026-11-14 amendment in PLAN.md.

None of these changes the H1 or H2 verdict.

python explore.py > results_explore.txt
"""
import json

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

import build
from analysis import N_BOOT, Z90, block_indices, h1, ols, one_sided, pct
from build import DATA, TEST_START, TRAIN, frame, prices, robust_z, split, weekly
from fetch import hashes

EVENT_USD = 1e9
DAY_BLOCK = 7


def coinmetrics_supply():
    rows = json.loads((DATA / "coinmetrics.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(rows, columns=["asset", "date", "v"])
    df["v"] = df["v"].astype(float)
    s = df.pivot(index="date", columns="asset", values="v")
    s.index = pd.to_datetime(s.index)
    return s.sum(axis=1, min_count=2).dropna()


def all_supply():
    rows = json.loads((DATA / "all_stables.json").read_text(encoding="utf-8"))
    return pd.Series({pd.Timestamp(r["date"], unit="s"): r["circulating"] for r in rows}).sort_index()


def train_p(w, q):
    return split(w)[0]["z"].dropna().quantile(q)


def boot_mean_diff(mask, y, block, sign=1, seed=0):
    """Mean y where mask minus mean y elsewhere; moving block bootstrap. One-sided p for the sign given."""
    mask, y = np.asarray(mask, bool), np.asarray(y, float)
    stat = y[mask].mean() - y[~mask].mean()
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(N_BOOT):
        i = block_indices(len(y), block, rng)
        m, v = mask[i], y[i]
        if m.any() and not m.all():
            out.append(v[m].mean() - v[~m].mean())
    out = np.array(out)
    p = (out <= 0).mean() if sign > 0 else (out >= 0).mean()
    return stat, p, *np.percentile(out, [2.5, 97.5])


def forward_return(p, mondays, start, end):
    return np.log(p.reindex(mondays + pd.Timedelta(days=end)).to_numpy()) - \
        np.log(p.reindex(mondays + pd.Timedelta(days=start)).to_numpy())


def daily_frame(s, p):
    s = s.loc["2020-01-01":]
    days = s.index
    d = pd.DataFrame(index=days)
    d["g"] = np.log(s.shift(-1)) - np.log(s)                     # S(D) -> S(D+1)
    d["usd"] = s.shift(-1) - s
    d["zd"] = robust_z(d["g"], window=365)
    lp = np.log(p)
    at = lambda k: lp.reindex(days + pd.Timedelta(days=k)).to_numpy()
    d["r_next"] = at(3) - at(2)                                   # one-day gap
    d["r_same"] = at(1) - at(0)
    for k in range(1, 8):
        d[f"r_lag{k}"] = d["r_same"].shift(k)
    d["lp"] = lp.reindex(days + pd.Timedelta(days=1)).to_numpy()  # price at end of day D
    return d


def mint_events(d):
    """Days with a >$1bn rise in USDT+USDC, dropping any within 7 days after the last kept event."""
    kept = []
    for t in d.index[d["usd"] > EVENT_USD]:
        if not kept or (t - kept[-1]).days > 7:
            kept.append(t)
    return pd.DatetimeIndex(kept)


def event_paths(lp, events, k=np.arange(-10, 11)):
    """Log price relative to the end of the event day, one row per event."""
    base = lp.reindex(events + pd.Timedelta(days=1)).to_numpy()
    return np.array([lp.reindex(events + pd.Timedelta(days=int(1 + j))).to_numpy() - base for j in k]).T


def main():
    p_btc = prices("binance")
    w = frame()
    train, test = split(w)
    test = test.dropna(subset=["r_next"])
    rows = {}  # name -> (statistic text, p)
    print("data:", {k: v[:8] for k, v in hashes().items()})
    print(f"test weeks {test.index[0].date()} to {test.index[-1].date()} (n={len(test)})")
    print()

    # E1 second source
    wc = weekly(coinmetrics_supply(), p_btc)
    thr = train_p(wc, 0.9)
    tc = split(wc)[1].dropna(subset=["r_next"])
    r = h1(tc, thr)
    both = test.join(tc[["z"]], rsuffix="_cm", how="inner")
    agree = ((both.z > Z90) == (both.z_cm > thr)).mean()
    corr = np.corrcoef(w["g"].loc[TEST_START:].dropna(), wc["g"].reindex(w["g"].loc[TEST_START:].dropna().index))[0, 1]
    rows["E1 CoinMetrics supply"] = (r["diff"], r["p"], f"top={r['n_top']} thr z>{thr:.3f} [{pct(r['lo'])}, {pct(r['hi'])}]")
    print(f"E1 weekly growth corr DefiLlama vs CoinMetrics (test) {corr:.3f}; top-week agreement {agree:.0%}")

    # E2 horizons
    for tag, end in (("E2a next 2 weeks", 22), ("E2b next 4 weeks", 36)):
        y = forward_return(p_btc, test.index, 8, end)
        s = test.assign(y=y).dropna(subset=["y"])
        stat, p, lo, hi = boot_mean_diff(s.z > Z90, s.y, 4)
        rows[tag] = (stat, p, f"n={len(s)} [{pct(lo)}, {pct(hi)}]")

    # E3 continuous slope
    m = ols(test["r_next"], test[["z"]])
    rows["E3 slope r_next ~ z"] = (m.params["z"], one_sided(m.params["z"], m.pvalues["z"]),
                                   f"per unit z, se {m.bse['z'] * 100:.2f}pp, R2 {m.rsquared:.3f}")

    # E4 full sample
    full = w.loc[TRAIN[0]:].dropna(subset=["r_next", "z"])
    r = h1(full, Z90)
    rows["E4 full sample 2021-26"] = (r["diff"], r["p"], f"n={r['n']} top={r['n_top']} [{pct(r['lo'])}, {pct(r['hi'])}]")

    # E5 redemption weeks
    z10 = train_p(w, 0.1)
    stat, p, lo, hi = boot_mean_diff(test.z < z10, test.r_next, 4, sign=-1)
    rows["E5 bottom decile (pred. < 0)"] = (stat, p, f"z<{z10:.3f} n_bottom={(test.z < z10).sum()} [{pct(lo)}, {pct(hi)}]")

    # E6 daily
    s_daily = build.combined_supply()
    d = daily_frame(s_daily, p_btc)
    dt = d.loc[TEST_START:].dropna(subset=["zd", "r_next"])
    m6 = ols(dt["r_next"], dt[["zd"]], lags=7)
    rows["E6 daily r ~ zd"] = (m6.params["zd"], one_sided(m6.params["zd"], m6.pvalues["zd"]),
                               f"n={int(m6.nobs)} se {m6.bse['zd'] * 100:.3f}pp")
    lags = [f"r_lag{k}" for k in range(1, 8)]
    dd = dt.dropna(subset=lags)
    m6b = ols(dd["zd"], dd[lags], lags=7)
    wald = m6b.wald_test(", ".join(f"{c} = 0" for c in lags), scalar=True)
    print("E6b daily zd ~ 7 lagged returns (description): "
          + ", ".join(f"{k[-1]}:{m6b.params[k]:+.1f}" for k in lags)
          + f"  joint Wald p={float(wald.pvalue):.4f}, R2 {m6b.rsquared:.3f}")

    # E7 all stablecoins
    wa = weekly(all_supply(), p_btc)
    thr = train_p(wa, 0.9)
    ta = split(wa)[1].dropna(subset=["r_next"])
    r = h1(ta, thr)
    rows["E7 all stablecoins"] = (r["diff"], r["p"], f"top={r['n_top']} thr z>{thr:.3f} [{pct(r['lo'])}, {pct(r['hi'])}]")

    # E8 event study
    ev = mint_events(d)
    lp = np.log(p_btc)
    post = lambda days: lp.reindex(days + pd.Timedelta(days=9)).to_numpy() - lp.reindex(days + pd.Timedelta(days=2)).to_numpy()
    dtest = d.loc[TEST_START:].copy()
    dtest["post"] = post(dtest.index)
    dtest = dtest.dropna(subset=["post"])
    is_ev = dtest.index.isin(ev)
    stat, p, lo, hi = boot_mean_diff(is_ev, dtest["post"], DAY_BLOCK)
    rows["E8 >$1bn mint days, 7d after"] = (stat, p, f"events={is_ev.sum()} (test), [{pct(lo)}, {pct(hi)}]")
    path = {}
    for name, sel in (("test", ev[ev >= TEST_START]), ("2021-23", ev[(ev >= TRAIN[0]) & (ev < TEST_START)])):
        path[name] = pd.Series(np.nanmean(event_paths(lp, sel), axis=0), index=np.arange(-10, 11))
        print(f"E8 path {name} ({len(sel)} events): " + " ".join(f"{j:+d}:{100 * v:+.1f}" for j, v in path[name].items() if j % 2 == 0))
    pd.DataFrame(path).to_csv("event_path.csv", float_format="%.5f")

    # E9 trend regime
    trend = np.log(p_btc.reindex(test.index + pd.Timedelta(days=7)).to_numpy()) - \
        np.log(p_btc.reindex(test.index - pd.Timedelta(days=21)).to_numpy())
    up = trend > 0
    top = (test.z > Z90).to_numpy()
    y = test.r_next.to_numpy()

    def inter(t, u, v):
        a = v[u & t].mean() - v[u & ~t].mean()
        b = v[~u & t].mean() - v[~u & ~t].mean()
        return a - b, a, b
    stat, a, b = inter(top, up, y)
    rng = np.random.default_rng(0)
    out = []
    for _ in range(N_BOOT):
        i = block_indices(len(y), 4, rng)
        t2, u2 = top[i], up[i]
        if all(x.any() for x in (u2 & t2, u2 & ~t2, ~u2 & t2, ~u2 & ~t2)):
            out.append(inter(t2, u2, y[i])[0])
    out = np.array(out)
    p = 2 * min((out <= 0).mean(), (out >= 0).mean())
    rows["E9 up-trend minus down-trend"] = (stat, min(p, 1.0), f"up: {pct(a)} (top {int((up & top).sum())}), down: {pct(b)} (top {int((~up & top).sum())}); two-sided")

    # E10 ether
    we = weekly(build.combined_supply(), prices("binance_eth"))
    te = split(we)[1].dropna(subset=["r_next"])
    r = h1(te, Z90)
    rows["E10 ETH next week"] = (r["diff"], r["p"], f"top={r['n_top']} [{pct(r['lo'])}, {pct(r['hi'])}]")

    # Holm
    names = list(rows)
    ps = [rows[n][1] for n in names]
    adj = multipletests(ps, method="holm")[1]
    print()
    print("=== Exploratory family, Holm-adjusted across 11 ===")
    for n, pa in zip(names, adj):
        stat, p, note = rows[n]
        val = f"{stat * 100:+.3f}pp" if "slope" in n or "daily" in n else pct(stat)
        print(f"{n:32s} {val:>10s}  p={p:.3f}  Holm p={pa:.3f}  {note}")
    print()

    # E11 by year
    print("=== E11 H1 difference by calendar year (description) ===")
    for yr in ("2024", "2025", "2026"):
        s = test.loc[yr]
        t = s.z > Z90
        print(f"  {yr}: weeks {len(s)}, top {t.sum()}, top {pct(s.r_next[t].mean())}, rest {pct(s.r_next[~t].mean())}, "
              f"diff {pct(s.r_next[t].mean() - s.r_next[~t].mean())}")


if __name__ == "__main__":
    main()
