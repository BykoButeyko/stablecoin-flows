# Plan: does a big week of stablecoin issuance predict next week's bitcoin return?

Written and committed 2026-11-13, before any test statistic was computed.
If I change anything below after this commit, the change goes in the "Amendments" section at the end with a date and a reason, and the original text stays.

## Question

When Tether and Circle mint a lot of new USDT and USDC in one week, does bitcoin go up the week after?

The story people tell is simple: new dollars come on chain, they wait on exchanges, then they buy crypto. If that were true and tradable, a weekly supply number that anyone can download would predict returns. The older evidence points the other way. Wei (2018) found Tether grants did not predict bitcoin returns. Griffin and Shams (2020) found Tether flows came after bitcoin declines in 2017-2018. Since then the stablecoin market has grown about tenfold and the issuers changed how they mint, so the question is worth asking again on recent data.

## Hypotheses

**H1 (primary).** Weeks with net USDT+USDC issuance in the top 10% (threshold fixed on the training period) are followed by a higher bitcoin return the next week than all other weeks.

**H2 (secondary).** The effect survives controlling for bitcoin's return in the same week and the week before. If issuance simply follows price and bitcoin returns have some momentum, H1 could pass for that reason alone. H2 separates the two.

My prediction, written down so it can be wrong: H1 is not supported. I expect the difference in next-week return between top-decile weeks and the rest to be between -1 and +1 percentage points in the test period, which is too small to detect here. I also expect issuance to follow price: last week's bitcoin return should explain part of this week's issuance.

I dropped one idea from the brief: comparing mints on Tron and Ethereum. Per-chain supply mixes real issuance with Tether's chain swaps (burn on one chain, mint on another) and with chains that appear in the data on a date long after they launched. See Pitfalls. It would not be cheap to do honestly.

## Data

All free, no key, all checked on 2026-11-13.

| Source | What | Coverage | Notes |
|---|---|---|---|
| DefiLlama stablecoins API, `stablecoins.llama.fi/stablecoin/1` (USDT) and `/stablecoin/2` (USDC) | Daily circulating supply per asset (`tokens`) and per chain (`chainBalances`), US$ | USDT from 2017-11-29, USDC from 2018-09-11, to today. One row per day at 00:00 UTC, no missing days, no duplicates. | `circulating` excludes `unreleased` (authorized but not yet issued, held in the issuer's treasury). Check on Tron today: minted 94.21bn minus unreleased 2.13bn equals circulating 92.07bn. History can be revised, so every run saves the raw JSON and its sha256. |
| Binance spot klines, `api.binance.com/api/v3/klines`, BTCUSDT 1d | Daily close at 24:00 UTC | From 2017-08-17. No missing day from 2019-12-22 to today (2,519 days). | Priced in USDT, not USD. |
| Coinbase Exchange candles, BTC-USD 1d | Daily close, USD | Back to at least 2017 | Cross-check of the Binance series only. |

Not usable: CoinGecko's free API now refuses history older than 365 days (HTTP 401, checked today).

## Pitfalls found while checking the data

1. **USDT before 2020 is incomplete.** DefiLlama shows USDT circulating at $0.03bn on 2019-01-01, when the real figure was around $2bn. The Omni chain series starts only on 2022-05-12. The asset total looks close to right from mid-2020 ($9.1bn on 2020-06-01). The sample starts in January 2020, and the first year only feeds the trailing window (see Variables), so no test or threshold relies on 2020 levels.
2. **Per-chain series have birth jumps.** Several chains enter the per-chain data on 2022-05-12 with large balances already on them (USDC on Solana $3.9bn, USDT on Solana $1.8bn, USDT on Omni $0.9bn). The asset total does not jump on that day, so it was built separately. I use the asset total only. Summing chains would create fake mints of several billion dollars.
3. **Chain swaps.** Since 2020 there are 21 days where USDT on Tron and USDT on Ethereum moved more than $0.5bn in opposite directions by nearly the same amount. These cancel in the asset total, and they are another reason for not splitting by chain.
4. **Tether's authorized but unissued supply.** Tether mints in large round blocks into its treasury and releases them later. DefiLlama reports that stock as `unreleased` (USDT about $2bn to $11bn over 2022-2026), separately from circulating. I use circulating, so a treasury mint counts as issuance only when it leaves the treasury.
5. **One-day reversals.** There are 30 USDT days and 10 USDC days since 2019 where a move of more than $0.3bn reversed by at least 70% the next day (for example USDC -$2.07bn on 2024-04-18, then +$2.56bn). Most are treasury moves or data glitches. Weekly sums cancel them unless they straddle the week boundary. As a robustness check I rebuild the weekly series from a 3-day rolling median of daily supply.
6. **USDC depeg, March 2023.** USDC supply fell by about $7bn between 10 and 18 March 2023 after SVB failed, and bitcoin rallied in the same weeks. These are bottom-tail weeks in the training period. They do not set the top-10% threshold, but they would inflate a trailing standard deviation for a year, which is one reason the scale below is a median absolute deviation.
7. **Terra collapse, May 2022.** USDT supply fell by more than $3bn on single days. Same treatment as point 6.
8. **Issuance growth slowed a lot.** This is the biggest design problem. The 90th percentile of weekly log supply change in 2020-2023 is 4.8%. No week in 2024-2026 reaches it, because combined supply went from about $4bn to about $117bn between January 2020 and January 2022. A threshold on raw percentage change fixed on training would select zero test weeks. A threshold in dollars has the opposite drift (supply is bigger now). So the signal is measured against its own recent history; see Variables.

I looked at the distribution of the issuance variable in the test period while choosing the scaling (point 8). I have not looked at any bitcoin return in relation to issuance, in either period.

## Variables

- **Week.** Monday 00:00 UTC to the next Monday 00:00 UTC.
- **Supply.** USDT circulating plus USDC circulating from the DefiLlama asset totals, value dated Monday 00:00 UTC.
- **Weekly issuance, g(t).** Log change of supply over week t.
- **Issuance signal, z(t).** (g(t) minus the median of g over the previous 52 weeks) divided by 1.4826 times the median absolute deviation over the same 52 weeks. The window ends at week t-1, so a week never scales itself. With data from January 2020, z is defined from January 2021.
- **Next-week return, r_next(t).** Log change in the BTCUSDT daily close from Tuesday 00:00 UTC of week t+1 to the following Tuesday 00:00 UTC. The one-day gap is there because I don't know at what hour DefiLlama actually takes the snapshot it labels 00:00. If it is taken later in the day, a no-gap return would overlap with issuance I count in week t.
- **Same-week return, r(t).** Log change in the BTCUSDT close over week t (Monday 00:00 to Monday 00:00).

## Samples

- **Training:** weeks starting 2021-01-04 to 2023-12-25 (156 weeks with a defined z). Used only to fix the threshold and debug the code.
- **Test:** weeks starting 2024-01-01 up to the last week whose next-week return is complete when I run the test (about 150 weeks).

The test period is not blind to the market. I know roughly what bitcoin did in 2024-2026, and I have seen the issuance series. What this plan fixes in advance is the variable definitions, the threshold, and the pass lines.

## Tests and pass lines

All tests are one-sided at 5%.

**H1.**
- Top week: z(t) above the 90th percentile of z in the training sample. The number goes into the Amendments before the test runs.
- Statistic: mean r_next in top weeks minus mean r_next in all other test weeks.
- p-value: moving block bootstrap of the test-period weeks, 4-week blocks, 10,000 resamples, seed 0, resampling (z, r_next) pairs together and recomputing the difference. The p-value is the share of resampled differences at or below zero. Top weeks cluster in bull runs, which is why blocks are used.
- H1 passes if the difference is positive and p < 0.05.
- Also reported: the same statistic on the training period (where the threshold was fixed, so not a test), and Welch's t-test.

**H2.**
- OLS on the test period: r_next(t) = a + b z(t) + c r(t) + d r(t-1) + e. Newey-West standard errors, 4 lags.
- H2 passes if b > 0 and its one-sided p < 0.05.
- Also reported, as description and not as a test: OLS of z(t) on r(t-1), r(t-2), r(t-3), to show how much issuance follows price.

**Robustness, reported whatever the main results are, never used to change a verdict:**
- No one-day gap (return starts Monday 00:00 UTC).
- Weekly supply from the 3-day rolling median of daily supply.
- USDT only and USDC only.
- Top 20% instead of top 10%.
- Threshold on raw weekly dollar change instead of z (90th percentile of 2020-2023 weekly change).
- Bitcoin returns from Coinbase BTC-USD instead of Binance BTCUSDT.

## Sample size and what it can detect

- Weekly bitcoin log return standard deviation: 9.0% in 2020-2023, 6.1% in 2024-2026 so far.
- In the exploration that settled the scaling, about 14% of test weeks were above the training 90th percentile of z, so roughly 20 top weeks against about 130 others. The standard error of the difference in means is then about 6.1% × sqrt(1/20 + 1/130) ≈ 1.5 percentage points. With 80% power at one-sided 5%, the smallest difference I can reliably detect is about 3.5 to 4 percentage points per week.
- That is a very large effect. Average weekly return in 2024-2026 is about 0.3%. A pass on H1 would mean something unusual; a fail means only that any effect is smaller than about 3.5 points a week, not that there is none.
- For H2, with about 150 weeks, the slope has to correspond to a partial correlation of roughly 0.2 or more to be detected with 80% power.

## Output

- One chart: mean next-week bitcoin return by decile of z, deciles fixed on the training period, with a 95% bootstrap band (same 4-week blocks) for the training period. The test-period mean for each decile is drawn on top, and the test top-decile result is marked with its interval.
- A README with the two verdicts, the effect sizes with intervals, and the null results stated as plainly as any positive one.
- I publish whatever comes out.

## Amendments

(none yet)
