"""Key chart: next-week bitcoin return by decile of the issuance signal, training band and test points."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis import DECILE_EDGES, block_bootstrap_mean
from build import Path, frame, split

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, BAND = "#2a78d6", "#eb6834", "#d6e5f7"


def by_decile(s):
    dec = np.digitize(s["z"], DECILE_EDGES) + 1
    means, los, his = [], [], []
    for k in range(1, 11):
        y = s["r_next"][dec == k].to_numpy()
        lo, hi = block_bootstrap_mean(y)
        means.append(y.mean())
        los.append(lo)
        his.append(hi)
    return 100 * np.array(means), 100 * np.array(los), 100 * np.array(his)


def main():
    train, test = split(frame())
    train, test = train.dropna(subset=["r_next"]), test.dropna(subset=["r_next"])
    x = np.arange(1, 11)
    m_tr, lo_tr, hi_tr = by_decile(train)
    m_te, lo_te, hi_te = by_decile(test)

    fig, ax = plt.subplots(figsize=(10, 5.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.fill_between(x, lo_tr, hi_tr, color=BAND, linewidth=0, label="2021-23 training, 95% band")
    ax.plot(x, m_tr, color=BLUE, marker="o", markersize=5, linewidth=1.6, label="2021-23 training, mean")
    ax.plot(x, m_te, color=ORANGE, marker="D", markersize=5, linewidth=0, label="2024-26 test, mean")
    ax.errorbar([10], [m_te[-1]], yerr=[[m_te[-1] - lo_te[-1]], [hi_te[-1] - m_te[-1]]],
                color=ORANGE, capsize=4, linewidth=1.4)
    ax.annotate(f"Test top decile: {m_te[-1]:+.1f}%\n(training {m_tr[-1]:+.1f}%)",
                xy=(10.45, lo_te[-1] - 2.6), ha="right", va="top", fontsize=9, color=ORANGE)
    ax.axhline(0, color=INK2, linewidth=0.8)
    ax.axvspan(9.5, 10.5, color="#f0efec", zorder=0)
    ax.set_xticks(x, ["1\nlowest"] + [str(i) for i in range(2, 10)] + ["10\nhighest"])
    ax.set_xlim(0.5, 10.5)
    ax.set_xlabel("Decile of weekly USDT+USDC issuance, relative to the previous 52 weeks", color=INK2, fontsize=9.5)
    ax.set_title("Bitcoin return the week after, by how much new stablecoin supply was issued (%)",
                 loc="left", fontsize=10.5, color=INK, pad=8)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", labelcolor=INK2)
    fig.text(0.125, -0.04,
             "Decile edges fixed on 2021-23. Return is the log change in BTC from the Tuesday after the issuance week "
             "to the next Tuesday.\nBands and the test interval: 4-week moving block bootstrap. "
             "Sources: DefiLlama stablecoin supply, Binance BTCUSDT.",
             fontsize=8, color=INK2)
    fig.savefig(Path(__file__).with_name("chart.png"), dpi=160, bbox_inches="tight", facecolor=SURFACE)


if __name__ == "__main__":
    main()
