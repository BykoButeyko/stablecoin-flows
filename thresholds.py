"""Thresholds from the training period only (weeks starting 2021-01-04 to 2023-12-25).

Reads no return and no test-period week. Run before analysis.py; the printed
numbers go into the PLAN.md amendments.
"""
from build import TRAIN, combined_supply, frame, split
from fetch import hashes


def main():
    out = {}
    for label, kw in [("main", {}),
                      ("smooth3", {"smooth": True}),
                      ("usdt", {"which": ("usdt",)}),
                      ("usdc", {"which": ("usdc",)})]:
        train, _ = split(frame(**kw))
        z = train["z"].dropna()
        out[label] = (z.quantile(0.9), z.quantile(0.8), len(z))
    d = frame()["dollar"]
    dollar = d.loc["2020-01-06":TRAIN[1]]
    deciles = split(frame())[0]["z"].dropna().quantile([i / 10 for i in range(1, 10)])

    for k, v in hashes().items():
        print(k, v[:8])
    for k, (p90, p80, n) in out.items():
        print(f"{k:8s} z p90 {p90:.3f}  p80 {p80:.3f}  (n={n})")
    print(f"dollar p90 {dollar.quantile(0.9) / 1e9:.3f} bn (n={dollar.notna().sum()})")
    print("decile edges", [round(x, 3) for x in deciles])


if __name__ == "__main__":
    main()
