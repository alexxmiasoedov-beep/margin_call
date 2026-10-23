# US / English-language crypto quant literature: strategies relevant to the MarginData bot

Compiled 2026-10-23. Scope: the American (English-language, US-based) academic, Fed and practitioner ecosystem. A few
non-US English sources are included when they are the closest evidence; they are tagged **[non-US]**.

**How this was gathered and what was not reachable**
- About 30 sources were opened and read (full text, key sections, or at minimum the abstract page). 11 were read in depth:
  He–Manela–Ross–von Wachter, Borri–Liu–Tsyvinski–Wu, Schmeling–Schrimpf–Todorov (BIS), Christin et al. (CMU),
  Liu–Tsyvinski–Wu, Cong–Karolyi–Tang–Zhao, Hong et al. (days-to-cover), Da et al. (SSP), FRBSF 2018-12,
  Robot Wealth, The Tie (listings).
- Blocked: SSRN (Cloudflare 403 on every abstract), Wiley (JFM), CEPR/VoxEU, the Edinburgh and ICM (Poland)
  repositories, and Robot Wealth Pro (paywall). The Kaiko/Amberdata research index is mostly product pages.
- The **web-search budget ran out partway through** (a 200-call limit shared by all agents). After that, sources were
  opened by direct URL only. Not covered as a result: Fed FEDS Notes, Coinbase Institutional, Glassnode, Paradigm,
  Messari, Block Scholes, CME basis research, Two Sigma/AQR, Velo/Laevitas/CryptoQuant, Hummingbot, and r/quant threads.
- Items seen only as search snippets are listed separately at the end (section F). They are **not** used as evidence.

**Main finding about this ecosystem.** US academic work on crypto leverage does not look at margin borrowing per coin.
It looks at **perp/futures basis and funding as a measure of leveraged-long demand** and at the limits of arbitrage
(He–Manela, CMU, BIS, Fed/Gorton). I found **no US paper that uses CEX margin borrow or short interest per coin as a
cross-sectional return signal.** Our MarginData factor looks new relative to this literature. The most useful guidance
for improving it comes from the US **equity short-interest** literature: days-to-cover, short-selling profitability,
and the aggregate short-interest index.

---

## Summary table

| # | Source (org, country) | Date / sample | Theme | Testability with our data | Novelty vs. our lists |
|---|---|---|---|---|---|
| A1 | Hong, Li, Ni, Scheinkman, Yan, *Days to Cover* (Princeton/Columbia/HKUST, NBER) | 2015; US stocks 1988–2012 | short interest ÷ turnover | High | New twist on borrow basket |
| A2 | Da, Fu, Lin, Lu, *Short-Selling Profitability* (Notre Dame et al.) | Feb 2026; US stocks 2005–2021 | when short interest is informative | Medium | New twist (conditioning) |
| A3 | Rapach, Ringgenberg, Zhou, *Short Interest and Aggregate Returns* (WashU/SLU, JFE) | 2016; 1973–2012 | aggregate SI predicts market | Medium | New (time-series use) |
| A4 | Gorton, Klee, Ross, Ross, Vardoulakis, *Leverage and Stablecoin Pegs* (Yale/Fed/OFR, NBER) | Dec 2022; Dec 2020–Nov 2022 | funding drives stablecoin lending rates | High | New (USDT margin rate as leverage gauge) |
| A5 | Schmeling, Schrimpf, Todorov, *Crypto Carry* (BIS WP 1087) | Apr 2023; Mar 2019–Jan 2022 | basis predicts crashes and short liquidations | High | New (crash-timing angle) |
| A6 | Christin, Routledge, Soska, Zetlin-Jones, *The Crypto Carry Trade* (CMU/UIUC) | Aug 2022; Binance 2020-08 to 2022-06 | carry = demand for leverage | High | Known; decayed |
| A7 | Dunbar & Owusu-Amoako (WPI/Fayetteville State) | Sep 2023 | retail net-short in futures predicts returns | Low | Abstract only |
| B1 | He, Manela, Ross, von Wachter, *Fundamentals of Perpetual Futures* (WashU/Copenhagen) | v7 Sep 2026; Binance 2020-01 to 2024-03 | perp-spot deviation arbitrage | High data, low fit | Partly new |
| B2 | Borri, Liu, Tsyvinski, Wu, *Coming of Age* (LUISS/Rochester/Yale/Berkeley) | Oct 2025; 2013–2025 | carry decay; factor update | High | Context; CMOM evidence |
| B3 | Robot Wealth, *Quantifying and Combining Crypto Alphas* (+ strategy index) | Feb 2024; Binance perps 2019–2024 | carry, momentum, breakout | High | Partly new |
| B4 | dima_quant, *Trading Crypto Funding Rates, Part 1* (Substack) | Sep 2026; Binance 2023–2025 | funding cross-section, net of costs | High | Confirms our rejection |
| B5 | Kaiko/Amberdata, *How $3.21B vanished in 60 seconds* | Oct 10 2025 event | anatomy of a liquidation cascade | Medium | New (OI-flush proxy) |
| B6 | Galaxy Research, *State of Crypto Leverage Q2 2026* | Aug 2026 | leverage aggregates | Low | Context |
| B7 | Kim & Hansen, *The Quarter-Hour Effect* (UNC; KISDI) | Jul 2026; Binance 2021–2024 | clock-time order-flow predictability | Low | Not tradable for us |
| B8 | Gornall, Rinaldi, Xiao **[non-US, UBC/CUHK]** | May 2025 | perps vs quarterly basis risk | Low | Context |
| B9 | Giagkiozis & Said (*Ledger* 2024) | 2023 tick data | OI misreported by some exchanges | Caveat | Caveat |
| C1 | Liu, Tsyvinski, Wu, *Common Risk Factors* (Yale, JF 2022) | 2014–2018 | market, size, momentum | High | Standard |
| C2 | Cong, Karolyi, Tang, Zhao (Cornell/Tsinghua; Mgmt Sci 2025) | 2014–2021 | momentum in large caps, reversal in small | High | Size-conditional sign |
| C3 | Artemis (NYC), *Crypto Factor Model, Mar 2026 update* | Mar 2026 | live factor returns | Medium | Context |
| C4 | Quantpedia summary of Babayeva & Aliyev Q-7 **[non-US]** | Jul 2026; 2020–May 2026 | reversal, funding sentiment | Medium | Partly new |
| C5 | tradingstrategy.ai summaries of Cao et al. / Chi et al. / Fan et al. **[non-US; secondary]** | 2023–2026 | basis spans perp anomalies | High | New (basis sort) |
| C6 | Kogan, Makarov, Niessner, Schoar (NBER/JFE 2024); Liu & Tsyvinski (RFS 2021) | 2018–2024 | retail trend-chasing; TS momentum | — | Mechanism |
| D1 | Hale, Krishnamurthy, Kudlyak, Shultz, FRBSF Economic Letter 2018-12 | May 2018 | futures launch lets pessimists in, price falls | High | New event type |
| D2 | The Block, *"Death-trap" perps listings* | Feb 2025 | ai16z −84%, VVV −67% after Binance perps | High | New event type |
| D3 | The Tie (NYC), *What Does an Exchange Listing Deliver in 2026?* | Jul 2026; 1,844 listings 2023–2026 | listing pop fades within 2 weeks | High | New |
| D4 | The Tie, *Binance listing for already-listed tokens* | Jul/Aug 2026; 14 tokens | +7% to D+9, decline after D+21 | High | New |
| D5 | The Tie, *Most Token Unlocks Don't Move the Market* | Aug/Sep 2026; 12,350 events in 2026 | unlock size vs ADV | Medium | New |
| D6 | Pantera (L. Stephanian), *Optimal vesting structure* | Aug 2022 | cliff vs linear unlock impact | Low–Medium | New |
| D7 | Cointelegraph Magazine, *Market maker deals are quietly killing crypto projects* | Apr 2025 | loan + call option, dump-and-rebuy | Medium (proxy) | New mechanism |
| D8 | Öget (2022) **[non-US]** | — | listing/delisting events | Medium | Weak |
| E1 | Bertomeu, Martin, Sall, *Measuring DeFi Risk* (WashU) | Sep 2026 | DeFi fragility metric | Low | — |
| E2 | Heimbach et al. **[non-US, ETH Zurich]** | 2023 | CRV borrow-and-dump on Aave | Low | Borrow-to-dump example |

---

## A. Margin borrowing, short interest and leverage demand

### A1. Days to Cover and Stock Returns
- **URL:** https://www.nber.org/papers/w21166 (PDF read: https://www.nber.org/papers/w21166.pdf)
- **Authors / org:** Harrison Hong (Princeton), Weikai Li, Sophie X. Ni (HKUST), Jose Scheinkman (Columbia), Philip Yan (GSAM). NBER WP 21166, May 2015.
- **Sample:** NYSE/AMEX/NASDAQ, 1988–2012, monthly.
- **Finding and rules.**
  - The short ratio (SR = shares shorted ÷ shares outstanding) is the wrong measure of arbitrageurs' view when trading costs vary across stocks.
  - **Days-to-cover (DTC) = SR ÷ average daily turnover** is roughly the marginal cost of the short position. At the optimum it equals the shorts' estimate of overvaluation.
  - Shorts naturally crowd into liquid names, so a high SR may only mean a stock is easy to trade. A high DTC means shorts accept a high cost to unwind, so they are more convinced.
  - Baseline DTC = short-interest ratio in month t ÷ average daily turnover in month t. The mean is 5.5 days (sd 8). SR and turnover correlate at about 0.4.
- **Evidence.** DTC predicts poor returns better than SR. A monthly-rebalanced long-short on DTC earns **about 1.2% per month**, gross of costs.
- **Relation to margin borrowing.** Direct. Our persistence or borrowed-$ ranking is the analog of SR. Dividing by the coin's daily volume gives a crypto DTC. Coins borrowed heavily *relative to their liquidity* should carry the strongest negative signal.
- **Data needed / testability:** MarginData borrowed $ (24h flow; cumulative net borrow as a stock proxy), spot and futures quote volume. **High.**
- **Novelty:** a materially new twist on our confirmed borrow basket. It normalises the signal rather than replacing it.

### A2. Short-Selling Profitability, Market Power, and Asset Pricing Anomalies
- **URL:** https://www3.nd.edu/~zda/SSP.pdf
- **Authors / org:** Zhi Da (Notre Dame), Chengbo Fu (UNBC), Nanying Lin (Arkansas State), Lei Lu (Manitoba). Draft dated Feb 16, 2026.
- **Sample:** CRSP stocks, SSP plotted 2005–2021; lending-fee data from 2007.
- **Finding and rules.**
  - **Abnormal short interest (abnSIR)** = a stock's SIR minus its own trailing 12-month average, standardised cross-sectionally.
  - **SSP** = −β from a **rolling 36-month regression** (at least 24 observations) of the stock's monthly excess return on lagged abnSIR. It measures how reliably that stock's shorts have been right.
  - SSP is persistent out of sample. Each month: split stocks into high- and low-SSP, then sort by lagged abnSIR within each group.
  - Lenders with market power charge higher fees on high-SSP stocks, capturing part of the shorts' profit.
- **Evidence.**
  - Full sample: low-minus-high abnSIR quintile spread **0.59%/month (t = 2.54)**.
  - High-SSP group: **0.82%/month (t = 3.40)**.
  - Low-SSP group: 0.35% (t = 1.14), not significant.
  - Short-selling costs cut anomaly profits by about half on average. Anomalies stay significant among high-SSP stocks, especially where lenders lack market power.
- **Relation to margin borrowing.** Direct. This explains *when* borrowing signals survive borrow costs, which is the question behind our rejected borrow-rate factor. The answer is in coins where borrowers are historically informed. Binance is a monopoly lender, so fees can absorb the edge. That is consistent with our finding that negative funding offsets the decline in hard-to-borrow coins.
- **Data needed / testability:** MarginData (2025-02 onward), klines, Binance margin rates. **Medium**: a rolling coin-level beta needs history. With about 20 months of MarginData, use daily observations and a 120-day window.
- **Novelty:** new conditioning layer for the borrow basket.

### A3. Short Interest and Aggregate Stock Returns
- **URLs:** abstract via search, published as JFE 2016, doi 10.1016/j.jfineco.2016.03.004; summary read at https://source.washu.edu/2015/05/why-investors-should-listen-to-short-sellers-yes-short-sellers/
- **Authors / org:** David Rapach (Saint Louis U.), Matthew Ringgenberg and Guofu Zhou (Washington University in St. Louis). JFE 2016.
- **Sample:** US stocks 1973–2012.
- **Finding and rules.** Short Interest Index (SII) = equal-weighted average short interest (% of shares outstanding), with a linear trend removed and standardised. It predicts market excess returns negatively.
- **Evidence.**
  - Annual R² **12.89% in sample and 13.24% out of sample**, beating 14 popular predictors.
  - Utility gain above 300 bp/year for a mean-variance investor. Works mainly through a cash-flow channel.
  - Caveat: a later replication reportedly finds a weaker effect. I saw this only in a snippet and did not read it.
- **Relation to margin borrowing.** The aggregate version of our signal: total MarginData borrowing across coins, detrended, as a market-timing variable.
- **Testability:** **Medium.** About 85 weekly observations since 2025-02 gives low power. Combine with longer-history leverage gauges (A4, A5).
- **Novelty:** new. We have only used borrow data cross-sectionally.

### A4. Leverage and Stablecoin Pegs
- **URL:** https://www.nber.org/system/files/working_papers/w30796/w30796.pdf
- **Authors / org:** Gary Gorton (Yale), Elizabeth Klee, Chase Ross, Alexandros Vardoulakis (Federal Reserve Board), Sharon Ross (OFR). NBER WP 30796, Dec 2022.
- **Sample:** Daily, Dec 1, 2020 to Nov 5, 2022. FTX USDT/DAI margin lending rates; Binance BTC/ETH USDT-perp funding.
- **Finding.**
  - Stablecoin holders are paid indirectly because levered speculators borrow stablecoins at high rates when speculative demand is strong.
  - Average lending rate is about 8% for USDT, often above 20%.
  - Funding (the proxy for speculative demand) and the USDT lending rate are tightly linked: binscatter coefficient **0.24, R² 0.56**. A 1 pp rise in annualised funding goes with a **0.11–0.24 pp** rise in the USDT lending rate, depending on controls.
  - Funding rates are highly correlated across BTC/ETH and across exchanges, so they reflect market-wide demand.
- **Evidence:** regressions only. No return-prediction test.
- **Relation to margin borrowing.** Direct. The **Binance cross-margin USDT (and USDC/FDUSD) borrow rate** measures aggregate levered-*long* demand: borrowing stablecoins to buy coins. Our 625-asset hourly rate history contains it.
- **Testability:** **High** (margin rates 2024-09 onward, funding history).
- **Novelty:** new. We tested coin borrow rates per coin, not the stablecoin rate as a market-wide gauge.

### A5. Crypto Carry (BIS Working Paper 1087)
- **URLs:** https://www.bis.org/publ/work1087.htm; full PDF read from https://www.bis.org/publications/working-paper-1087-crypto-carry.pdf
- **Authors / org:** Maik Schmeling (Goethe), Andreas Schrimpf and Karamfil Todorov (BIS). April 2023; later also CEPR DP20719.
- **Sample:** Daily, Mar 2019 to Jan 2022. 1- and 3-month constant-maturity BTC and ETH basis on Binance, OKEx, FTX, Huobi, BitMEX, Deribit and CME (Skew data). Also uses Aave and Binance VIP borrow rates and CFTC COT.
- **Findings.**
  - Carry averages above 10% p.a. and reaches 40–60%. Time fixed effects explain 88% of variation, exchange fixed effects 1%.
  - Interest-rate differentials, including Binance borrow rates, are far too stable to explain carry. It is a volatile "convenience yield" of levered futures.
  - Carry rises with retail attention (Reddit subscribers: R² 23% for OKEx), past 1-week and 1-month BTC returns (trend-chasing) and open interest.
  - **Fama regressions:** a $1 rise in the 1-month BTC basis predicts about a **$5 fall in spot** and $6 fall in futures by maturity. For the 3-month basis, about $10 and $11.
  - **A 10% rise in carry predicts a 44% rise in short-side (sell) liquidations** relative to open interest over the next month. It does not predict long liquidations.
  - Higher carry predicts more negative implied and realised skew and lower 3-month spot returns.
  - CME cash-and-carry Sharpe is only about 0.6 before costs and financing spreads (2018–2022). At 10× leverage, the futures leg would have been liquidated in more than half of the months.
- **Relation to margin borrowing.** Basis and funding capture leverage demand from the *long* side. Combined with USDT margin rates (A4), this gives a time-series "leverage froth" index.
- **Testability:** **High.** Perp premium from 15-minute perp and spot klines, plus funding. No quarterly futures are needed, though Binance quarterlies could be added.
- **Novelty:** we rejected funding-group regimes and funding-level sorts. This is a *time-series crash and skew predictor at the market level*, which we have not tested.

### A6. The Crypto Carry Trade
- **URL:** https://www.andrew.cmu.edu/user/azj/files/CarryTrade.v1.0.pdf
- **Authors / org:** Nicolas Christin, Bryan Routledge, Ariel Zetlin-Jones (Carnegie Mellon), Kyle Soska (UIUC). Aug 1, 2022.
- **Sample:** Binance, 2020-08-11 to 2022-06-20, 8-hour funding periods. 18 coins, USDT- and coin-margined perps.
- **Rules:** long 1 unit of spot, short an equal perp notional, collect funding every 8 hours. No costs or margin modelled.
- **Evidence.**
  - BTC USDT-carry: **21.8% mean, 1.9% sd, Sharpe 11.5**. Coin-margined: 16.7%, Sharpe 6.4.
  - Altcoins: Sharpe mostly 4–11 (LTC 10.7, ETH 10.3, LINK 9.7, DOGE 8.5). BNB 2.3, FIL 1.2.
  - By epoch: 39% (Aug 2020–Apr 2021), then 19.6%, 14.7%, **7.6%** (Nov 2021–Jun 2022).
  - When Binance cut maximum leverage from 125x to 50x on 2021-07-23, BTC USDT-carry fell from **33.0% to 10.2%** p.a. (Sharpe 14.4 to 7.9). Carry is the price of retail access to leverage.
- **Relation to margin borrowing:** the same mechanism as A4 and A5. Long-side leverage demand sets funding.
- **Testability:** high, but the strategy has decayed. B2 reports carry Sharpe negative in 2025.
- **Novelty:** low. Useful mainly to show that exchange leverage-policy changes are a regime variable.

### A7. Predictability of crypto returns: the impact of trading behavior (abstract only)
- **URL:** https://digitalcommons.uncfsu.edu/college_business_economics/314
- **Authors / org:** Kwamie Dunbar (WPI), Johnson Owusu-Amoako (Fayetteville State). Sep 2023.
- **Finding (abstract):** net-short positioning of speculative retail traders in crypto futures is a significant determinant of crypto returns. It survives controls for attention, uncertainty, sentiment and past returns. The PDF was not available; the direction, data (presumably CFTC COT) and horizon could not be checked.
- **Testability:** low. It concerns CME BTC/ETH positioning, not our universe. Our top-trader long/short filters were already rejected.

---

## B. Perpetual-futures positioning, funding, basis, liquidations

### B1. Fundamentals of Perpetual Futures
- **URL:** https://arxiv.org/html/2212.06888v7
- **Authors / org:** Songrun He and Asaf Manela (WashU St. Louis), Omri Ross and Victor von Wachter (Copenhagen/eToro). v7, Sep 2026 (first draft Dec 2022).
- **Sample:** Binance hourly, Jan 2020 to Mar 11, 2024. BTC, ETH, BNB, DOGE, ADA. Aave stablecoin rates as the risk-free rate; Kaiko order books; Binance trade archives for effective spreads.
- **Rules.**
  - Deviation ρ = annualised wedge between the perp and its no-arbitrage value under Binance's funding formula (interest 0.01%/8h, clamp ±0.05%).
  - **If ρ > 0: short perp, long spot. If ρ < 0: the reverse. Close when ρ first returns to 0.** Checked hourly; average hold **4–5 hours**.
  - Entry thresholds at ±53%, ±114% and ±179% annualised, depending on fee tier (large fund, small fund, retail).
- **Evidence.**
  - Zero cost, BTC: Sharpe 11.65 (return 52.6%, max drawdown −3.8%).
  - Retail fees, after effective spreads: BTC **3.27**, ETH **4.45**, BNB 6.63, DOGE 3.45, ADA 3.80.
  - Data-driven out-of-sample variant (parameters re-chosen on the trailing 6 months) has a positive zero-cost Sharpe every year, including 2023–2024.
  - The naive carry trade (A6) has Sharpe only 2.24 on the same data.
  - Most of the profit is **price convergence, not funding** (BTC: 37.6 of 52.6 points).
  - Mean |ρ| falls about 22 pp/year. Binance portfolio margin (Apr 20, 2022) cut deviations by a seventh to a third.
  - **Past spot returns positively predict deviations** (coefficients 0.08–0.17, t 4.5–10.8): extrapolative demand for leverage. Deviations co-move across coins.
- **Relation to margin borrowing:** the arbitrage side of leverage demand. Binance margin rates used as the risk-free rate give the same results.
- **Testability:** high (15-minute perp and spot closes plus funding approximate ρ), but **poor fit for our bot**: a 4–5 hour, fee-sensitive, delta-neutral arbitrage. The useful takeaways are (i) the premium is a clean cross-sectional signal; (ii) momentum in returns feeds the premium.
- **Novelty:** partly new. We have not used the perp-spot premium (as opposed to funding) as a signal.

### B2. Cryptocurrency as an Investable Asset Class: Coming of Age
- **URL:** https://arxiv.org/html/2510.14435v2
- **Authors / org:** Nicola Borri (LUISS), Yukun Liu (Rochester), Aleh Tsyvinski (Yale), Xi Wu (UC Berkeley). Oct 2025.
- **Sample:** CoinGecko Dec 2013 to Sep 2025 (16,468 coins after filters). Binance BTC perp carry Aug 2020 to May 2025.
- **Rules:** weekly, value-weighted quintile Q5−Q1 sorts. Coins below $1M market cap excluded. CMOM uses past 2-week returns.
- **Evidence.**
  - **CMOM +2.6%/week full sample (t 3.89), +2.1%/week post-2020 (t 3.70).** Most stable factor.
  - CSIZE −2.3% full, −0.9% post-2020 (t −1.69); weakening.
  - CVALUE significant (−3.5%, then −2.3% post-2020, sign per their sort convention).
  - MOM12, MOM24, volatility, volume and beta sorts are not significant.
  - **Carry trade Sharpe 6.45 (2020–2025), 4.06 from 2024, negative in 2025.** The authors attribute this to Ethena-type basis supply (about $14B stablecoin cap).
  - Cross-exchange arbitrage restricted to open (implementable) exchanges is far smaller: 0.038 per week, versus 0.685 per week across all exchanges (units as reported). The authors read the remainder as risk compensation.
- **Testability:** high (momentum on Binance perps).
- **Novelty:** context. It confirms that plain funding carry is dead and short-horizon momentum survived through 2025 in broad samples.

### B3. Robot Wealth: Quantifying and Combining Crypto Alphas, plus the strategy index
- **URLs:** https://robotwealth.com/quantifying-and-combining-crypto-alphas/ ; https://robotwealth.com/index-of-strategies/
- **Author / org:** Kris Longmore, Robot Wealth (Australian, English-language). Feb 3, 2024; index read Oct 2026.
- **Sample:** Binance perps, daily, late 2019 to early 2024. Bottom 20% by trailing 30-day dollar volume dropped.
- **Features.**
  - **Carry** = funding over the last 24 hours (cross-sectional).
  - **Momentum** = 10-day price change (cross-sectional).
  - **Breakout** = 9.5 − days since the 20-day high (time-series).
  - Target: next-day return *including funding*, cross-sectionally demeaned.
- **Findings.**
  - Carry decile has a "significant and sticky IC" (slow decay).
  - 10-day momentum has a **slightly negative IC (mild short-term reversal)** that decays slowly.
  - Breakout has a moderate time-series IC. Carry and breakout are negatively correlated.
  - Combined weight = 0.5 × (carry decile − 5.5) − 0.2 × (momentum decile − 5.5) + 0.3 × breakout/2, scaled to gross 1. No costs; the author says it "isn't a backtest".
  - **Sign caution:** the code goes *long* high-funding deciles. With Binance's convention, that means high-funding perps had higher next-day total returns. This conflicts with B4; the sign must be measured in our own data.
- **Strategy index (no stats):**
  - "Crypto Short-Term Reversal: a real but weak effect, unlikely to be profitable traded alone" (Apr 2024).
  - "Crypto Extreme Borrow Short Squeeze" (squeezes on extreme spot borrow rates) is **retired**. This matches our rejection of borrow-rate spikes as a long signal.
  - A paywalled Aug 2025 webinar covers a broader "double-sort" carry and **shorting new Hyperliquid listings**.
- **Testability:** high.
- **Novelty:** the listing short and the reversal-as-execution-aid are new to us. Carry overlaps our rejected funding work.

### B4. Trading Crypto Funding Rates, Part 1 (dima_quant Substack)
- **URL:** https://dimaquant.substack.com/p/does-funding-contain-useful-information
- **Author:** "dima" (@dima_quant), English-language Substack, location not stated. Sep 25, 2026.
- **Sample:** Binance perps 2023–2025, including retired contracts; monthly Top-20/50/100 market-cap buckets.
- **Rules:**
  - Funding summed per UTC day, averaged over the prior N days (3-day primary; 1–64 tested), annualised.
  - Daily quintiles. In the Top-50, **long the cheapest fifth, short the most expensive fifth**, half the account each side, equal weight.
  - 10 bp per dollar traded.
- **Evidence.**
  - Cheap minus expensive, gross: 10.7 bp (1 day), 19.4 bp (3 days), 21.3 bp (7 days).
  - Over 3 days, funding adds +41.5 bp but price takes back −22.2 bp: **cheap-funding coins lag on price.**
  - Gross Sharpe 0.55; **net Sharpe −0.47**; turnover 178× per year; net max drawdown −32.7%.
  - The spread was positive in 2023–2024 and **negative in 2025**.
  - Short lookbacks (1–8 days) work better than 32–64 days. Cheap funding plus strong 7-day momentum was the best combination (not tested net of costs).
- **Relation to margin borrowing.** This mirrors our rejected result: the expensive-to-short side's price drift is largely paid away in funding.
- **Testability:** high.
- **Novelty:** confirms our rejection. The useful twist is that funding works only as a short-horizon *filter* combined with momentum, and turnover control is decisive.

### B5. How $3.21B Vanished in 60 Seconds: the October 2025 crash (Kaiko, ex-Amberdata)
- **URL:** https://www.kaiko.com/resources/how-3-21b-vanished-in-60-seconds-october-2025-crypto-crash-explained-through-7-charts
- **Org:** Amberdata (NYC), now hosted by Kaiko. The page date 28/07/2025 is wrong; the event is Oct 10, 2025.
- **Facts.**
  - $9.89B liquidated in about 14 hours; **about 70% ($6.93B) in a 40-minute cascade (20:50–21:30 UTC)**; peak minute $3.21B at 21:15.
  - Longs 83.9% of liquidations. Aggregate OI fell $36.7B (−25%), 52% of that inside the 40 minutes.
  - BTC fell 6.8%, but maximum drawdowns were AAVE −69%, AVAX −69%, DOGE −65%, UNI −70% intraday.
  - Visible depth fell 98% ($103.6M to $0.17M). BTC perp spread peaked at 26 bp versus 0.02 bp.
  - No recovery statistics are given.
- **Relation to margin borrowing:** none directly. It is relevant to tail risk of the short basket and to a forced-selling reversal trade.
- **Testability:** **medium**. We have no liquidation feed; 5-minute OI drops plus price and taker flow serve as a proxy. See B9 on OI data quality.
- **Novelty:** new (event-driven forced-flow reversal). The evidence for reversal is *not* shown in the source.

### B6. Galaxy Research: State of Crypto Leverage, Q2 2026
- **URL:** https://www.galaxy.com/insights/research/crypto-leverage-report-q2-2026-defi-lending-decline-futures-open-interest
- **Author / org:** Zack Pokorny, Galaxy (NYC). Aug 17, 2026.
- **Facts:**
  - Crypto-collateralised lending $56.2B (−16.8% QoQ, −40% from the Q3 2025 high of $78.7B).
  - DeFi borrows $20.4B (peak $47.1B on Sep 19, 2025). Futures OI $103.2B.
  - Stablecoin borrow rates 3.9–5%.
  - Aave e-mode loans: LTV about 90%, health factor 1.06.
  - Notes that OI is not a pure leverage measure because of spot-hedged positions.
- **Testability:** low (context only). It does support using stablecoin borrow rates as a leverage-cycle gauge (A4).

### B7. The Quarter-Hour Effect
- **URL:** https://arxiv.org/html/2607.09426
- **Authors / org:** Chan Kim (KISDI, Korea), Peter Reinhard Hansen (UNC Chapel Hill). Jul 2026.
- **Sample:** Binance USDT-M perps (BTC, ETH, XRP, SOL, DOGE, ADA), Jan 2021 to Oct 2024.
- **Finding:**
  - Order imbalance in the **first 10 seconds** after each :00/:15/:30/:45 predicts returns over 4–12 hours.
  - Out-of-sample R² for opening returns averages 3.4%.
  - But the predictable component is about 0.5 bp per boundary, versus a 5 bp taker fee.
- **Testability:** **low**. It needs trade-level data, and 15-minute bars cannot isolate 10 seconds. At most an execution-timing aid.

### B8. Perpetual Futures and Basis Risk **[non-US: UBC / CUHK]**
- **URL:** https://ftp.aeaweb.org/conference/2026/program/paper/ByyFEfr4 (AEA 2026 program; draft May 19, 2025)
- **Authors:** Will Gornall, Martin Rinaldi, Yizhou Xiao.
- **Finding:**
  - Perp spreads are 49–83% tighter than quarterly futures.
  - In large market events, quarterlies fall 8–10% more than spot; perps only about 3% more.
  - Perp basis-trade drawdowns are about a third as large and mean-revert quickly.
- **Testability:** low relevance. It mainly says perp-spot dislocations in crashes are small and short-lived.

### B9. Reconciling Open Interest with Traded Volume in Perpetual Swaps
- **URL:** https://arxiv.org/abs/2310.14973 (*Ledger* vol. 9, 2024)
- **Authors:** Ioannis Giagkiozis, Emilio Said.
- **Finding:** using 2023 tick data from seven exchanges, BTC-perp OI is **systematically misquoted by some of the largest exchanges**. Some figures are implausible; others look like delayed liquidation messages. The abstract does not name the exchanges.
- **Use:** a caveat for any OI-based signal (idea 8). Check Binance OI changes against signed taker volume.

---

## C. Cross-sectional factor research

### C1. Common Risk Factors in Cryptocurrency
- **URLs:** https://www.nber.org/papers/w25882 ; PDF read: https://cowles.yale.edu/sites/default/files/2022-10/LiuTsyvinskiWu2019%20COMMON%20RISK%20FACTORS.pdf
- **Authors / org:** Yukun Liu, Aleh Tsyvinski (Yale), Xi Wu. JF 2022 (WP 2019).
- **Sample:** 1,707 coins with market cap above $1M, 2014–2018. Weekly returns from daily closes.
- **Rules:** weekly quintile sorts, value-weighted, Q5−Q1.
- **Evidence.**
  - Size (market cap) −3.4%/week.
  - Momentum: 1-week 2.7%, 2-week 3.3%, **3-week 4.1%**, 4-week 2.5% per week. 8- to 100-week momentum not significant.
  - Dollar volume about 3.2%; volatility about 3%.
  - **Momentum works only in larger coins:** above-median size 4.2%/week, below-median 0.6% (not significant).
  - All nine significant strategies are spanned by CMKT, CSMB and CMOM. Gross of costs.
- **Testability:** high. Note that our Fama–MacBeth already controls for 10 price features, probably including these.

### C2. Value Premium, Network Adoption, and Factor Pricing of Crypto Assets
- **URLs:** EFMA 2022 PDF (read): https://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2022-Rome/papers/EFMA%202022_stage-3032_question-Full%20Paper_id-231.pdf ; published as *Crypto Value, Factor Pricing, and Market Segmentation*, Management Science, doi 10.1287/mnsc.2024.05875
- **Authors / org:** Lin William Cong, G. Andrew Karolyi (Cornell), Ke Tang, Weiyi Zhao (Tsinghua). Draft Apr 2022.
- **Sample:** 4,007 coins, 2014–2021; core sample of 616 with on-chain address data.
- **Evidence.**
  - Full sample, short-term "momentum" long-shorts are **negative** (reversal): 1-week −4.1%, 2-week −2.4%, 3-week −2.5%, 4-week −1.2% per week.
  - Size × 2-week momentum double sort: the long-short rises from **−19.5%/week (smallest quintile) to +4.1%/week (largest quintile, t 3.2)**.
  - Value = −(past 52-week return): +5.7%/week (t 2.7). Network growth (addresses): +4.0%/week (t 2.8).
  - Momentum factor built from the largest 20%, reversal factor from the smallest 80%. Their C-5 model beats LTW in and out of sample.
- **Relation:** none to margin. It implies the **sign of short-horizon return predictability depends on size and liquidity.**
- **Testability:** high (Binance perps, with 30-day ADV as the size proxy).
- **Novelty:** the size-conditional sign is the useful twist.

### C3. Artemis Crypto Factor Model Analysis: March 2026 Update
- **URL:** https://research.artemis.ai/p/artemis-crypto-factor-model-analysis
- **Author / org:** Maggie Schwierking, guest post for Artemis (NYC). Mar 6, 2026.
- **Definitions:**
  - Momentum: long top 25%, short bottom 25% on **3-week mean return ÷ standard deviation of daily returns** (at least 30 assets).
  - Value: market cap ÷ fees, long cheap.
  - Size: bottom 50% vs top 50%.
  - Growth: 2-week fee and daily-active-user growth.
- **Evidence:**
  - Feb 2026, with the market at −23.5%: momentum +11.3%, value +10.9%, size −8.6%.
  - A Nov 2025 study cited: momentum 75% annualised, size 53% annualised.
  - No costs, no Sharpe, figures in images only. Weak evidence.
- **Testability:** medium. Momentum yes; value and growth need fee/DAU data we lack.

### C4. Quantpedia Premium update on Babayeva & Aliyev, "Crypto Has Fundamentals: A Seven-Factor Model" (SSRN 6818558) **[non-US, summary only]**
- **URL:** https://vvv.quantpedia.com/quantpedia-premium-update-july-30th/
- **Sample:** 90 tokens, Jan 2020 to May 2026, weekly.
- **Findings (as summarised):**
  - **Short-term reversal, not momentum.**
  - A **perpetual-futures funding-sentiment factor** is significant at 1%, alongside on-chain quality, value and residual volatility.
  - Size is subsumed by volatility. Out of sample, the model explains about 63% of single-token return variation.
  - Indicative strategy return 80.3%, volatility 61%. The funding factor's construction is not described.
- **Testability:** medium.
- **Novelty:** it conflicts with C2 and B2 on momentum in recent liquid samples. Our own test must settle it.

### C5. tradingstrategy.ai reference page: secondary summaries of perp-factor papers **[non-US; I read the summaries, not the papers]**
- **URL:** https://tradingstrategy.ai/docs/learn/carry-trade.html (offset section "Priority papers")
- **Cao, Luo, Cheng, Dong (Edinburgh), *Anatomy of Cryptocurrency Perpetual Futures Returns* (SSRN 6365329):**
  - Perp return = spot premium + log basis + expected funding spread.
  - **Of 134 candidate signals, 48 are significant, and all are spanned by a basis plus price-volume two-factor model.** A search snippet for another version said 170 signals, 63 significant.
- **Chi, Hao, Hu, Ran, *An Empirical Investigation on Risk Factors in Cryptocurrency Futures* (J. Futures Markets 2023):** basis is the strongest predictor; basis-momentum adds nothing; predictability fades from daily to monthly.
- **Fan, Jiao, Lü, Tong (2023), interest-rate crypto carry:** 43.4% annualised, Sharpe 0.74.
- The same page says the BIS paper finds higher standardised carry predicts more short-side liquidations (consistent with my reading of A5).
- **Testability:** high (perp premium from klines).
- **Novelty:** the basis/premium sort is not in our rejected list, which covers funding regimes and borrow-rate levels. It overlaps with funding, so it needs the cost-aware framing in idea 6.

### C6. Behavioural mechanism papers (abstract pages)
- **Kogan, Makarov, Niessner, Schoar, *Are Cryptos Different? Evidence from Retail Trading*.** NBER w31317 (2023), JFE 159 (2024). https://www.nber.org/papers/w31317 . About 200k eToro traders who are contrarian in stocks and gold **trade momentum-style in crypto**. This is the micro-foundation for the momentum, basis and funding comovement in A5, B1 and C1.
- **Liu & Tsyvinski, *Risks and Returns of Cryptocurrency*.** RFS 2021; NBER w24877. https://www.nber.org/papers/w24877 . Crypto returns are driven by crypto-specific factors: **strong time-series momentum** and investor attention. The abstract page gives no numbers.

---

## D. Event-driven: listings, perp launches, unlocks, market-maker loans

### D1. How Futures Trading Changed Bitcoin Prices (FRBSF Economic Letter 2018-12)
- **URL:** https://www.frbsf.org/wp-content/uploads/el2018-12.pdf (full text read)
- **Authors / org:** Galina Hale (SF Fed), Arvind Krishnamurthy (Stanford), Marianna Kudlyak (SF Fed), Patrick Shultz. May 7, 2018.
- **Finding.**
  - BTC peaked at $19,511 on Dec 17, 2017, the day CME futures started.
  - Mechanism (Fostel–Geanakoplos 2012): before a shorting instrument exists, only optimists can express views and they bid the price up. **Introducing a way to short lets pessimists in**, and the price reverses.
  - The post-futures decline was larger than the two other 2017 drawdowns and had not recovered by late April 2018.
  - The decline was gradual because pessimists entered slowly: first-week CME volume was about 12k BTC versus about 200k BTC daily spot turnover.
- **Relation to margin borrowing.** Direct, at the event level. The **first day a coin becomes shortable on Binance** (USDT-M perp launch, or cross/isolated margin listing) is the crypto analog. Our MarginData shows whether shorts actually arrive.
- **Testability:** **high**. Binance announcements are timestamped; 869 perp symbols include delisted ones.
- **Novelty:** new event type for us.

### D2. "ai16z and VVV see double-digit price drops since 'death-trap' perps listings" (The Block)
- **URL:** https://www.theblock.co/post/339220/ai16z-and-vvv-see-double-digit-price-drops-since-death-trap-perps-listings-analyst-says
- **Author / org:** Brian McGleenon, The Block (US). Feb 6, 2025.
- **Facts:**
  - ai16z fell from $2.42 (Jan 2, 2025) to $0.38 (**−84%**) after its early-January Binance perp launch.
  - VVV fell from above $18 to $5.82 (**−67%**). "Vine" is named too.
  - Mechanism, per Arete Capital's I. Paveliev: perps let holders short aggressively while dumping spot, and market makers pull back after listing.
  - Binance's reply: derivatives aid price discovery.
- **Evidence:** anecdotal (2–3 tokens, no benchmark).
- **Testability:** high. It motivates idea 4.

### D3. What Does an Exchange Listing Actually Deliver in 2026? (The Tie)
- **URL:** https://www.thetie.io/insights/what-does-an-exchange-listing-actually-deliver-in-2026
- **Author / org:** Jackson Moss, The Tie (NYC). Jul 13, 2026.
- **Sample and method:** 1,844 listing events on major exchanges (Binance, Coinbase, OKX, Bybit, Kraken, Upbit, Bithumb), Jan 2023 to Jun 2026, CCData. BTC-adjusted returns, winsorised 1/99.
- **Findings.**
  - Returns **rise before Day 0**, then the BTC-adjusted return goes **flat or negative soon after listing**. The post-listing drift **largely mean-reverts within two weeks**.
  - **First listings** and the **smallest market-cap quintiles** show the biggest pop *and* the biggest post-listing decline.
  - A **large pre-listing volume spike on other exchanges (D−3 to D0)** predicts *lower* D+7 and D+14 returns ("pulls forward demand").
  - Volume stays elevated for weeks while price fades. Spikes are smaller and fade faster in 2024–2026. No exchange is consistently better for price.
  - Numbers are only in charts, not text.
- **Testability:** **high** for Binance listings (announcements plus klines). Upbit/Bithumb volumes are available for the pre-spike condition.
- **Novelty:** new. Our Korean-pump short is a related but different trigger.

### D4. What Does a Binance Listing Deliver When You're Already on Three or More Major Exchanges? (The Tie)
- **URL:** https://www.thetie.io/insights/what-a-binance-listing-delivers-for-already-listed-tokens
- **Author / org:** Jackson Moss, The Tie. The page says Jul 30, 2026; the index says Aug 11, 2026.
- **Sample:** 14 tokens newly listed on Binance spot after being on 3 or more majors.
- **Finding:**
  - Median BTC-adjusted return climbs to **about +7% by D+9**, stays flat to about D+21, then **declines steadily**.
  - Cross-exchange 1% depth roughly doubles and spreads narrow persistently.
  - Small sample, no significance tests.
- **Implication:** for seasoned tokens the fade starts later (about 3 weeks) than for first listings.

### D5. Most Token Unlocks Don't Move the Market (The Tie)
- **URL:** https://www.thetie.io/insights/venture-cliffs-token-unlocks-2026
- **Author / org:** Hari Iyer, The Tie. Aug 25 / Sep 1, 2026.
- **Sample:** 101 tokens, 12,350 priced unlock events, Jan to Aug 19, 2026.
- **Findings.**
  - The median event equals **0.20% of 30-day ADV**; 95.6% of events are below one day's volume. Investor allocations are under 4% of the $21B unlocked.
  - Only 544 events exceed one day of volume.
  - **Screen: ADV ≥ $30M and unlock > 25% of ADV gives 27 events in 2026** (for example Ondo at 4–6× ADV).
  - **No price-impact test.** The author says share of volume measures scale, not realised impact.
- **Testability:** medium. Unlock schedules must be scraped (Tokenomist and similar).
- **Novelty:** new. It gives a defensible event filter (size relative to liquidity).

### D6. Optimal vesting structure (Pantera, posted on Unlocks Calendar Substack)
- **URL:** https://unlockscalendar.substack.com/p/optimal-vesting-structure
- **Author / org:** Lauren Stephanian, Pantera Capital (US). Aug 29, 2022.
- **Sample:** more than 150 data points from 3 funds. Returns beta-adjusted against BGCI; measured on the day of, day after and one week after unlocks.
- **Findings (directional, numbers only in charts):**
  - Linear vests show lower volatility and less negative impact than date-specific cliffs.
  - A 6-month cliff beats 1-year or no cliff.
  - Counter-intuitively, larger initial cliff unlocks had *less* negative impact than smaller ones.
- **Testability:** low–medium. It suggests separating cliff from linear events in idea 9.

### D7. Market maker deals are quietly killing crypto projects (Cointelegraph Magazine)
- **URL:** https://cointelegraph.com/news/market-maker-deals-quietly-killing-crypto-projects
- **Author:** Yohan Yun. Apr 16, 2025.
- **Mechanics:**
  - The project lends tokens to a market maker for about **one year**. The market maker either returns them or repays "at a higher price", which is the call-option leg.
  - Reported pattern: the market maker **sells the loaned tokens at listing, pushing the price down, then buys back cheaper and returns them.**
  - A CoinGecko chart of six loan-option projects all declined.
  - An Onchain Bureau claim linked OM's roughly 90% crash to an expiring FalconX loan; it was denied and later deleted.
  - Signals named: thin depth versus agreed KPIs, public loan-option governance proposals (Wintermute, DWF), loan expiries near month 12.
  - No systematic statistics.
- **Relation to margin borrowing.** A market maker hedging or dumping a loaned token is a borrow-to-dump flow, the same economics as a CEX margin short. In our data the visible proxies are **early MarginData borrow surges on new listings** and **perp short build-up (OI up, price down, negative taker flow) in the first weeks**.
- **Testability:** medium (proxies only; no deal data).

### D8. The Effect of Positive and Negative Events on Cryptocurrency Prices **[non-US]**
- **URL:** https://ideas.repec.org/a/ahs/journl/v7y2022i1p16-31.html
- **Author:** Emrah Öget. J. Research in Economics, Politics & Finance, 2022.
- **Finding (abstract level):** listing, delisting and airdrop announcements and SEC actions, window (−5, +10). Negative events produce more significant abnormal returns (22 versus 8 significant ARs; 13 versus 3 CARs). No magnitudes on the page.
- **Testability:** medium (our Binance delisting announcements). Weak source.

---

## E. DeFi lending (no return predictability found)
- **E1. Bertomeu, Martin, Sall, *Measuring DeFi Risk*** (WashU), arXiv 2609.07902, Sep 2026. https://arxiv.org/abs/2609.07902 . A fragility early-warning metric built from aggregate DeFi deposits and borrowings; fragility rose past prudent levels around mid-2021. No token-return tests. Low relevance.
- **E2. Heimbach, Schertenleib, Wattenhofer, *Short Squeeze in DeFi Lending Market*** **[non-US, ETH Zurich]**, arXiv 2302.04068. https://arxiv.org/abs/2302.04068 . The Nov 2022 attempt to borrow CRV on Aave and dump it to profit from a short failed, but left more than $1.5M of bad debt. Enablers: a large share of supply was borrowable, and protocol response was slow. A case study of borrow-to-dump and squeeze risk, not a signal.
- **Other.** Sun, Stasinakis, Sermpinis (arXiv 2206.11973, UK) studies Aave liquidity risk with no return results. **I found no read source showing that Aave/Compound utilisation or borrow rates predict token returns.** This is consistent with our rejection of borrow-rate levels.

---

## F. Seen only as search snippets (not read; not used as evidence; candidates for a follow-up if access allows)
- HoKwang Kim, "The 72-Hour Shock? Preliminary Evidence from 52 Token Unlock Events on Binance" (SSRN 6632838). Snippet: 46 of 52 events negative within 72 hours, mean −16.97%, 2023–2025; labelled preliminary.
- "Failure of Cross-Sectional Alpha Screening on Cryptocurrency Perpetual Futures" (SSRN 6701738). Snippet: no net alpha at the 8-hour horizon on 10 Binance perps.
- Inan, "Predictability of Funding Rates" (SSRN 5576424); He, Wang, Zhang, funding-rate template (SSRN 6185958).
- Mercik, Zaremba, Demir, "Crypto Factor Zoo" (ICM repository, blocked). Snippet: 2–3 factors absorb all alphas, liquidity variables dominate, momentum most robust to costs.
- Fieberg, Liedtke, Metko, Zaremba (2023, Quantitative Finance), "Cryptocurrency factor momentum."
- Bank of Canada SAP 2026-13 (Aave V3 leverage and liquidations); BIS WP 1183 (Aave V2: borrowing is mainly speculative).
- Ante (2019), exchange listings: +5.7% abnormal return on listing day. LO:TECH market-maker survey. Keyrock study of 16,000 unlock events.
- Robot Wealth Pro posts (paywalled): "A broader crypto carry trade" (Aug 2025), "Crypto carry strategy review" (Apr 2024).

---

# Top ideas to backtest

Common protocol for all ideas:
- Data window 2024-10 to 2026-10. Calibrate on 2024-10 to 2025-09; test out of sample on 2025-10 to 2026-10. For MarginData-based ideas: 2025-02 to 2025-12 in sample, 2026 out of sample.
- Costs: Binance taker 4–5 bp per side plus 2–5 bp slippage for altcoins, actual 8-hour funding paid or received, and delisted symbols included.
- Hedge: beta-adjusted BTC (or the existing long market basket).
- Report: net weekly mean, t-statistic (Newey–West), Sharpe, max drawdown, turnover, and correlation with the current borrow basket. Add each new variable to the existing Fama–MacBeth with the 10 price controls plus the persistence factor.

**1. Days-to-cover borrow basket (Hong et al. 2015 [A1]; Da et al. 2026 [A2])**
- Universe: coins in MarginData with an active Binance USDT-M perp and 30-day median futures quote volume ≥ $5M.
- Signal (weekly, Monday 00:00 UTC):
  - DTC_flow = mean over 7 days of (24h borrowed $) ÷ mean over 7 days of (spot + perp daily quote volume).
  - Variant DTC_stock = Σ over 30 days of (borrowed − repaid) ÷ 30-day ADV.
  - Optional third variant: divide by the Binance-held token balance from DefiLlama, as a utilisation proxy.
- Portfolio:
  - Short the top 10 by DTC. Apply the same funding exclusion (3-day average funding < −0.1%/8h is excluded). Hedge long BTC/market. Hold 1 week.
  - Compare against (a) the current persistence top 10 (baseline about +0.9%/week) and (b) a 3 × 3 double sort of persistence × DTC.
- Pass condition: DTC is significant in Fama–MacBeth with persistence included, or the double-sort top cell improves net Sharpe by ≥ 0.3.

**2. Abnormal borrow, conditioned on coin-level "borrow-signal profitability" (Da et al. 2026 [A2]; Rapach et al. 2016 [A3])**
- abnB_i,t = (7-day mean of 24h borrowed $ ÷ ADV) minus its own trailing 90-day mean, standardised cross-sectionally each day.
- SSP_i,t = −β from a rolling 120-day per-coin regression (at least 60 daily observations) of the next-3-day BTC-adjusted return on lagged abnB.
- Weekly: split coins at the cross-sectional median of SSP. Within each half, short the top quintile and long the bottom quintile by abnB, equal weight, hold 1 week. Run as a long-short spread and also as a short-only filter on idea 1.
- Hypothesis: the spread is significant **only in the high-SSP half**. If so, restrict the production short basket to high-SSP coins.

**3. Aggregate leverage-froth index to time the hedge or a market short (BIS crypto carry [A5]; Gorton et al. [A4]; Rapach et al. SII [A3]; Christin et al. [A6]; He et al. [B1])**
- Components, each as a rolling 180-day z-score of its 7-day mean:
  - (a) Binance cross-margin hourly borrow rate for USDT (plus USDC/FDUSD).
  - (b) Cross-sectional median 3-day funding of the top 50 perps.
  - (c) BTC and ETH perp premium (perp close ÷ spot close − 1, from 15-minute bars).
  - (d) Total MarginData borrowed $ summed across coins, log, detrended, standardised (SII analog).
  - LFI = mean of the available z-scores.
- Tests:
  - Predictive regressions of next 7, 14 and 30-day returns of BTC and of an equal-weighted top-50 alt basket, plus their realised skewness and max drawdown, on LFI.
  - Expanding-window out-of-sample R² versus the historical mean.
  - Proxy long-liquidation intensity: count of 1-hour aggregate OI drops > 3% with BTC < −2%.
- Trading rule:
  - LFI > +1.5: cut the long hedge of the short basket by 50% (net short) for 14 days, or short the BTC perp standalone for 14 days.
  - LFI < −1: keep the full hedge. Otherwise neutral.
- Pass condition: lower drawdown and higher net Sharpe for the combined book versus a constant hedge.

**4. "Shortability shock": first Binance perp or margin listing of an already-trading token (FRBSF 2018 [D1]; The Block 2025 [D2]; The Tie [D3, D4])**
- Events:
  - Binance announcements "Binance Futures will launch USDⓈ-M XXXUSDT perpetual" for tokens already trading on Binance spot or elsewhere for ≥ 14 days.
  - Separately, "Binance Margin will add XXX" (cross or isolated) announcements.
  - Exclude tokens that launch spot and perp together; those are idea 5.
- Entry: short the perp at the first 15-minute close ≥ 1 hour after perp trading opens. For margin events, short at announcement + 15 minutes using the existing perp.
- Exit: fixed horizons of 3, 7, 14 and 28 days. Report the full CAR path from −14 to +28 days, BTC-beta-adjusted.
- Splits:
  - Pre-event 14-day run-up (top tercile expected worst).
  - Market cap / FDV tercile.
  - Early MarginData presence (borrowed $ in the top 20 within 72 hours).
  - Funding at entry (skip if 3-day average < −0.1%/8h).
- Equal weight, at most 8 concurrent positions.

**5. New-listing fade, conditioned on early borrow flow and pre-listing spike (The Tie 2026 [D3, D4]; Cointelegraph market-maker loans [D7]; Robot Wealth "shorting new listings" [B3])**
- Universe: all new Binance spot+perp listings 2024-10 to 2026-10, delisted ones included.
- Entry: at the D+2 daily close, short the perp if the price is above the D0 listing-day VWAP.
- Exit: D+14, with D+30 as a variant. For tokens already on 3 or more major exchanges, enter at D+10 and exit at D+35 instead (D4).
- Conditioning flags:
  - (i) "Borrow-to-dump proxy": coin in MarginData with borrow/repay ratio > 2 or in the top 20 by borrowed $ during D0–D7.
  - (ii) Other-exchange or Upbit/Bithumb volume on D−3 to D0 ≥ 3× its prior 7-day mean.
  - (iii) Smallest market-cap tercile among new listings.
- Hypothesis: the fade is concentrated where (i), (ii) or (iii) hold. Size with a stop at +25% adverse to cap squeeze risk.

**6. Funding/basis as a cost-aware filter and tie-breaker for the borrow basket (He et al. [B1]; Cao et al. and Chi et al. via [C5]; dima [B4]; Robot Wealth [B3])**
- For each borrow-basket candidate compute:
  - P_i = 3-day mean perp premium versus spot (15-minute bars).
  - F_i = 3-day mean funding.
- Variants:
  - (a) Current rule (exclude F < −0.1%/8h).
  - (b) Exclude the bottom cross-sectional quintile of F (relative rather than absolute).
  - (c) Require P_i ≥ 0, so the short leg earns positive carry and price convergence.
  - (d) Rank by DTC (idea 1) × sign(P).
- Standalone check: a weekly (not daily) sort on P_i across the top 100 by volume. Short the top quintile, long the bottom, including funding. Use a turnover buffer (rebalance only when a coin moves at least 2 quintiles) to avoid the 178× turnover that killed B4.
- Pass condition: higher net weekly return for the borrow basket with no loss of breadth.

**7. Size-conditional momentum / reversal sleeve on Binance perps (Liu–Tsyvinski–Wu [C1]; Cong–Karolyi–Tang–Zhao [C2]; Borri et al. 2025 [B2]; counter-evidence in Robot Wealth [B3] and Q-7 [C4])**
- Universe: USDT-M perps with ≥ 60 days of history and 30-day ADV ≥ $5M. "Large" = top 20% by 30-day ADV; "rest" = the others.
- Weekly:
  - In "large": long the top quintile of 2-week return (or 3-week mean ÷ daily std, as in C3), short the bottom quintile.
  - In "rest": long the bottom quintile of 1-week return, short the top quintile.
  - Inverse-volatility weights, hold 1 week.
- Report the two legs separately, net of costs and funding, and their correlation with the borrow basket.
- Main question: does the momentum sign survive in 2024–2026 liquid perps, or has it flipped to reversal as B3 and C4 suggest?

**8. OI-flush forced-selling reversal (Kaiko/Amberdata Oct 2025 [B5]; Gornall et al. [B8]; BIS [A5]; data caveat B9). Exploratory: no read source shows the reversal.**
- Detection on 5-minute data:
  - Coin flush: OI drops ≥ 12% within 60 minutes, price falls ≥ 8%, and taker sell volume ≥ 65% of volume, while aggregate top-100 OI drops ≥ 4% in the same hour (forced-flow regime).
  - Confirm with signed taker volume, since OI can be misquoted (B9).
- Entry: buy the perp at the first 15-minute close after the OI decline stops (OI change ≥ 0 over 15 minutes). Hedge with a beta-adjusted BTC short.
- Exit: +24 hours, with +72 hours as a variant. Stop at −10%.
- Universe: top 100 by ADV. Skip coins with a delisting or monitoring-tag announcement within 30 days.
- Pass condition: positive net mean with t > 2 across at least 3 separate market-wide flush days, so the result is not driven by Oct 10, 2025 alone.

*Lower-priority idea, documented above:* **token-unlock short** (The Tie [D5], Pantera [D6]).
- Events with unlock value ≥ 25% of 30-day ADV and ADV ≥ $30M.
- Short from D−7 to D+3 versus BTC. Split cliff versus linear.
- Test whether a MarginData borrow rise in D−14..D−1 (informed pre-event shorting) sharpens the effect.
- Requires scraping unlock schedules.
