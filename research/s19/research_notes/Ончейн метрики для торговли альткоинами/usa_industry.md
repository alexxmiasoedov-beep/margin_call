# US/English industry research: on-chain metrics for trading altcoins (hours to weeks)

Notes compiled 2026-11-10. Evidence tags used on every finding:
**[Q]** a quantified study with a stated sample and method; **[M]** provider methodology or documentation;
**[V]** a vendor or analyst claim with no published systematic test (marketing, commentary, a "Quicktake");
**[C]** a single case or anecdote; **[T]** my own no-key API test on 2026-11-10.
"via search summary" means the page could not be opened directly (404, 403, paywall or JS-only), so the content
comes from the search engine's summary of it and should be re-checked before it is quoted as fact.

## Q1. Which on-chain signal families do the providers say work for altcoins, how do they compute and interpret them, and which don't work?

### Takeaway
Glassnode, CryptoQuant, Coin Metrics, Nansen, Santiment, IntoTheBlock/Sentora, Kaiko and Chainalysis present almost
every altcoin flow metric as context or a risk flag, not as a validated predictor. The only public systematic test of
"whale deposit to exchange" signals I found (Presto Research, Feb 2025; BTC, ETH and SOL on Binance) found almost no
explanatory power for 1–6 h drawdowns (R² 0.002–0.054). The only vendor backtest of smart-money holdings (Nansen, 2022)
is old, in-sample and has not been replicated. For altcoins, the quantified evidence is stronger for supply events
(unlocks, Q2) and for manipulation and liquidity diagnostics (Chainalysis, Kaiko) than for following flows. Most
exchange-flow and label data for altcoins sits behind paid APIs. Free, no-key data covers DEX pools, Hyperliquid
positions, ERC-20 holders and tags, stablecoin supply and basic ERC-20 activity, but not labelled exchange flows.

### Cited Findings

#### Exchange inflows, outflows and reserves
- [M] CryptoQuant definitions: inflow is coins deposited to exchange wallets; outflow is coins withdrawn;
  netflow = inflow − outflow; "mean" = total flow ÷ transaction count, also given as a 7-day MA. Rising inflows are
  "mostly bearish" and rising outflows "mostly bullish". However:
  - inflows to derivatives-exchange wallets signal volatility risk, not direction;
  - inflows tied to staking or airdrops are neutral, and airdrop-related inflows should be read alongside funding and
    open interest because recipients hedge;
  - "a portion of large inflows is based on transactions among exchanges" (arbitrage);
  - signals need confirmation from other indicators.

  The page does not describe how CryptoQuant labels or clusters addresses, or how it treats internal transfers.
  — [CryptoQuant User Guide](https://userguide.cryptoquant.com/exchange-flows-indicators/exchange-in-outflow-and-netflow)
- [M/V] CryptoQuant's data guide says high "Top 10 inflow" values (the largest single deposits) have historically
  come with more selling pressure and short-term downside risk. For stablecoins the reading flips: inflow means buying
  power. No hit rate is published. — via search summary of
  [CryptoQuant data guide](https://docs.cryptoquant.com/data-guide/exchange/exchange-in-outflow-and-netflow) and the
  [QNT Top10 inflow chart](https://cryptoquant.com/asset/qnt/chart/exchange-flows/exchange-inflow-top10)
- [V] CryptoQuant weekly report, 29 Sep 2026:
  - the 7-day count of altcoin deposit transactions to exchanges was ≈78,000 on 28 Sep, against ≈29,800 on 14 Sep (+160%);
  - depositing addresses rose from ≈17,600 to ≈51,600;
  - both were the highest since Oct 2025;
  - quote: "When holders move coins to exchanges, they usually intend to sell."

  The report does not disclose the exchange set, the altcoin universe or how it aggregates, and gives no forward-return
  statistics. — [Cointelegraph, 30 Sep 2026](https://cointelegraph.com/markets/altcoin-exchange-deposits-spike-160-in-two-weeks)
- [V] A CryptoQuant Quicktake said the altcoin Exchange Inflow Transaction Count peaked on all exchanges just before
  both 2024 market tops. — via search summary of
  [Cryptorank feed](https://cryptorank.io/news/feed/3fd25-altcoins-selling-pressure-exchange-inflow-2025)
  (not opened, and the attribution to this page is uncertain).
- [V] The opposite heuristic, from CryptoQuant contributor Axel Adler Jr. (2025): "low exchange flows preceded
  significant altcoin price rallies", with about $1.6B a month of altcoin inflow as a trigger level. — via search summary of
  [NewsBTC](https://www.newsbtc.com/altcoin/binance-inflows-leading-altcoins-analyst/amp)
  - Both heuristics rest on 2–3 episodes, and neither gives a hit rate.
- [V] Headline framing that deposit spikes mean "higher volatility ahead", rather than a direction:
  [The Block on CryptoQuant](https://www.theblock.co/amp/post/407160/cryptoquant-bitcoin-ether-altcoin-exchange-deposits-volatility)
  (headline only; not opened).
- [M] Glassnode methodology:
  - exchange labels come from published exchange information plus proprietary clustering;
  - "entity-adjusted" metrics drop transfers between addresses of the same entity;
  - a transfer between two different exchanges counts as a withdrawal from one and a deposit to the other;
  - transfers within one exchange are excluded.

  — via search summary of Glassnode Studio metric descriptions
  ([example](https://studio.glassnode.com/charts/transactions.TransfersVolumeExchangesNet?a=BTC&e=okex))
- [Q, BTC] Glassnode's older study estimated that "true" (entity-adjusted) BTC on-chain volume averages only about 25%
  of raw volume. Unadjusted flow totals are therefore mostly churn. — [Glassnode Insights](https://insights.glassnode.com/true-bitcoin-volume)
- [V] Glassnode's altcoin coverage in 2026 is descriptive. Examples:
  - SOL on exchanges fell to ≈26.06M SOL on 14 Jan 2026, the lowest since Jan 2023;
  - the 1k–10k SOL cohort grew to ≈48M SOL.

  Both were cited as bullish. — [Cointelegraph, Jan 2026](https://cointelegraph.com/news/solana-slips-below-130-but-onchain-data-suggests-sol-remains-bullish)
  Glassnode's own description of its whale-exchange metric says whale exchange behaviour has been "directionally
  aligned with broader market conditions", which describes a coincident metric, not a leading one. — via search summary of
  [Glassnode workbench](https://studio.glassnode.com/workbench/btc-entities-supply-whale-exchanges-netposchange)
- [M] Coin Metrics exchange metrics:
  - covers deposits, withdrawals, counts, exchange supply, net flows, pairwise flows and point-in-time flows across
    21 exchanges ([Coin Metrics docs](https://docs.coinmetrics.io/network-data/network-data-overview/exchange));
  - coverage varies by asset, and the core coverage is BTC and ETH in Network Data Pro;
  - Coin Metrics writes that "deposit data for exchanges is likely to be imperfect";
  - rising exchange supply is ambiguous: it can mean more traders, or traders using the exchange "as a bank".

  — [Coin Metrics gitbook](https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/mining/exchange-flows);
  [Talos/Coin Metrics release](https://www.talos.com/insights/coin-metrics-expands-exchange-flow-and-supply-metrics-with-11-new-exchanges)
- [M] A volume-authenticity heuristic from an early State of the Network issue: an exchange with few demonstrable
  on-chain deposits but very high claimed volume "should be held in suspicion".
  — [Coin Metrics SOTN Issue 3](https://coinmetrics.substack.com/p/coin-metrics-state-of-the-network-30b)
- [T] The State of the Network URLs under coinmetrics.io now 301-redirect to talos.com/insights. —
  [old SOTN URL](https://coinmetrics.io/state-of-the-network/exchange-flow-metrics) (tested 2026-11-10)

#### Whale and large-holder flows, concentration
- [Q] **Presto Research**, Peter Chung and Jaehyun Ha, 6 Feb 2025.

  | Item | Detail |
  |---|---|
  | Assets and venue | BTC, ETH and SOL deposits into Binance |
  | Period | 1 Jan 2021 – 27 Dec 2024 |
  | Size thresholds | Whale Alert's $50M / $50M / $20M, scaled down to $20M / $20M / $8M for Binance's ~40% spot share |
  | Labels and data | Arkham plus the authors' own investigation; data from Dune |
  | Outcome measured | Maximum drawdown in the 1 h and 6 h after the deposit |
  | Scenarios | 12 |
  | Result | R² between 0.0017 and 0.0537 |
  | VC and market-maker subset | R² slightly higher, but still low |
  | VC/MM share of large deposits | ETH 61% (538 of 879), SOL 32%, BTC 13% |

  Verdict: large exchange deposits "lack the predictive power to serve as reliable trade signals". The authors' own
  caveats: arbitrary thresholds, a single exchange, the limits of R², and the fact that deposits capture only part of
  the supply side. — [Presto Research via OKX Learn](https://okxapi.goquant.io/nl/learn/prestoresearch-datafocus01092025)
- [V] Santiment has published two paywalled backtests over about 1,000 coins: "Whale Games: Backtesting the impact of
  large transfers on 1000+ coins" and "Sell-off alarm? Backtesting exchange data of 1000 coins". Their results were not
  accessible: paywalled, and direct fetches failed.
  — [Santiment Whale Games](https://insights.santiment.net/read/whale-games-backtesting-the-impact-of-large-transfers-on-1000-coins-santiment-weekly-pro-report-6299);
  [Santiment Sell-off alarm](https://insights.santiment.net/read/sell-off-alarm%3F-backtesting-exchange-data-of-1000-coins-(santiment-weekly-pro-report)-6275)
- [V] Santiment's public stance:
  - surges in $100K+ whale transactions often come just before local price peaks;
  - the effect is stronger in highly concentrated low-cap coins;
  - a whale moving coins to an exchange is "a whale selloff at worst, or a routine move to another exchange address at best".

  — via search summary of [Santiment insight](https://insights.santiment.net/read/following-massive-whale-deposits-to-see-which-coins-to-profit-take-8261)
- [C] A 2021 Santiment case: large AAVE and KNC transfers to exchanges were followed by price slides.
  — [Daily Hodl, 26 Feb 2021](https://dailyhodl.com/2021/02/26/massive-whale-transactions-sent-three-altcoins-into-a-spiral-according-to-crypto-analytics-firm-santiment)
- [M] Santiment runs a dashboard of large whale transfers of altcoins and stablecoins to exchanges, which is a
  monitoring tool, not a validation. — [Santiment dashboard insight](https://app.santiment.net/insights/read/check-out-the-whale-watcher-dashboard-and-see-when-altcoins-and-stablecoins-are-moving-to-exchanges-10641)
- [M/V] IntoTheBlock (now renamed Sentora):
  - "Large Transactions" are on-chain transfers above $100K, used as a proxy for whale and institutional activity;
  - "whales" are addresses holding more than 1% of circulating supply;
  - "Historical Concentration" tracks the whale share of supply. Example: DOGE's whale share rose from under 30% to
    nearly 50% within weeks.
  - Analysts note that large-transaction volume carries no buy/sell direction.

  — via search summaries of [Bitcoinist (LTC)](https://bitcoinist.com/litecoin-whales-active-50-market-cap-shifted-daily/amp/),
  [IntoTheBlock Medium](https://medium.com/intotheblock/a-deep-dive-into-crypto-asset-ownership-da17e4654b38),
  [Bitcoinist (TON; Sentora rename)](https://bitcoinist.com/toncoin-whales-break-record-large-volume-34-billion/).
  I found no published predictive test.

#### Smart money and labelled-wallet tracking
- [M] How Nansen builds Smart Money labels:
  - wallets are ranked on realized PnL, ROI and win rate over rolling windows (Smart Trader 30D, 90D, 180D and 2-year);
  - the all-time "Smart DEX Trader" threshold is about $1.5M cumulative realized profit, roughly the top 0.1% when introduced;
  - fund labels also use off-chain information;
  - whales were removed from Smart Money because they "don't necessarily earn similar returns".

  — via search summaries of [Nansen Academy, Smart Money 101](https://academy.nansen.ai/en/articles/2132837-smart-money-101),
  [Nansen methodology guide](https://www.nansen.ai/guides/what-is-smart-money-in-crypto-a-detailed-look-into-our-methodology)
  (404 on direct fetch, 2026-11-10), and
  [Nansen: Smart Money getting smarter](https://nansen.ai/post/smart-money-on-nansen-is-getting-smarter)
- [Q, vendor, in-sample] **Nansen 2022 backtest**, labelled "preliminary" by Nansen:
  - data: daily token holdings of all Ethereum Smart Money wallets up to Mar 2022, using point-in-time snapshots;
  - six momentum indicators were tested;
  - the best was the % change in the number of Smart Money addresses holding a token;
  - return-to-volatility ≈3.1, against ≈1.8 for holding ETH only, over Mar 2020 – Mar 2022.

  No transaction costs or out-of-sample test are reported. — via search summary of
  [Nansen research](https://www.nansen.ai/research/trading-crypto-with-nansen-smart-money) (404 on direct fetch; old
  research.nansen.ai links now redirect to nansen.ai/blog)
- [V] Nansen notes that price spikes were usually followed by a dip in the number of Smart Money holders
  (profit-taking). A rising holder count may signal consensus "but might also mean that it's late". — via search summary of
  [Nansen case studies](https://research.nansen.ai/articles/case-studies-on-successful-tokens)
- [M] Nansen now sells a backtesting API marketed as having "no look-ahead bias, no manual snapshotting, no rebuilding
  label history", meaning point-in-time labels. — [Nansen API: Backtesting data](https://docs.nansen.ai/api/backtesting-data);
  [Historical top holders](https://docs.nansen.ai/api/backtesting-data/historical-top-holders)
- [V, third party] A critique of Nansen's evidence:
  - its research publishes case studies, not blind tests;
  - labels are awarded on past PnL, so a wallet that was "smart last quarter" may not be smart now;
  - rolling windows reduce look-ahead bias but do not remove it.

  — via search summary of [Eco support article](https://eco.com/support/en/articles/14800361-nansen-smart-money-how-it-works)

#### Stablecoin supply and exchange stablecoin flows
- [V] CryptoQuant analysts treat stablecoin exchange netflows as "purchasing power on standby" and call Binance the main
  funnel for altcoin rotations. Example: analyst Maartunn reported +$3.2B of stablecoin inflows, "one of the strongest
  liquidity builds in over a month". — via search summary of CryptoQuant Quicktakes
  ([stablecoin inflows, ~Nov 2025](https://cryptoquant.com/insights/quicktake/690ef9e500e28a05eb738295-Stablecoin-inflows-signal-renewed-market-appetite);
  [altseason, ~Aug 2025](https://cryptoquant.com/insights/quicktake/689f92be76426d34a66e9137-Altseason-on-the-Horizon-Stablecoin-Liquidity-BTCD-Rejection-Signal-a-Shift)).
  The dates are inferred from the timestamp embedded in the Quicktake IDs.
- [V] A caveat from Axel Adler Jr.: stablecoins sent to derivatives exchanges are margin collateral, not spot buying
  power, so spot and derivatives venues should be separated. — via search summary of
  [axeladlerjr.com](https://axeladlerjr.com/stablecoins-exchange-inflow-bitcoin-signal/)

#### DEX activity, liquidity and manipulation diagnostics
- [Q] Chainalysis wash-trading and pump-and-dump heuristics (details in Q3/Q4). Measured wash trading is small relative
  to total DEX volume: each heuristic catches about 0.035–0.046% of DEX volume (Nov 2024), with a combined 2024 upper
  bound of $2.57B. It is concentrated in a few pools and actors: addresses trading in 4+ pools are 10% of flagged
  addresses but 43% of flagged volume, and only 0.2–0.3% of roughly 500k monthly active pools are involved.
  — [Chainalysis, 29 Jan 2025](https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/)
- [M] Kaiko on measuring liquidity:
  - order-book depth (e.g. 0.1% or 1% from mid) is treated as a forward-looking liquidity measure, unlike traded volume
    ([Kaiko](https://www.kaiko.com/resources/moving-markets-liquidity-and-large-sell-orders));
  - offshore exchanges held 69% of altcoin liquidity, up from 55% in early 2022 — via search summary of
    [Kaiko liquidity concentration report](https://research.kaiko.com/insights/the-crypto-liquidity-concentration-report);
  - altcoins are more exposed to liquidity shocks because of thinner books and fewer market makers — via search summary of
    [Kaiko](https://research.kaiko.com/insights/will-ftx-liquidations-trigger-an-altcoin-crash)
- [C] Kaiko on WLFI: perpetuals traded on several venues before the spot listing and unlock; there were brief
  sell-side order-book imbalances on Binance and Bybit. — via search summary of
  [Kaiko Research](https://research.kaiko.com/insights/wlfi-spot-market-launch-off-to-a-strong-start)

#### Staking and bridge flows
- [V/C] ETH validator exit queue in 2025:
  - it reached about 2.4–2.6M ETH (roughly $10–12B), with waits of 41–44 days;
  - the bearish reading: unstaking means supply coming to market, and stETH loop unwinds force selling;
  - the counterpoints: ETF and treasury-company demand absorbed it, and the entry queue overtook the exit queue in late Dec 2025;
  - no measured link between the exit queue and exchange deposits was shown.

  — [Cointelegraph](https://regional-front.cointelegraph.com/news/ethereum-exit-queue-10b-record-selling-pressure);
  [Decrypt](https://decrypt.co/335549/billions-in-ethereum-waiting-to-be-unstaked-could-add-sell-pressure-to-eth-analyst);
  [Cointelegraph, queues flip](https://cointelegraph.com/news/ethereum-staking-queues-flip)

#### Perp DEX (Hyperliquid) position transparency
- [V] Hyperliquid whale positions are public and tracked by dashboards (CoinGlass, Arkham, Hypurrscan). Aggregate whale
  exposure was reported at $2.9–6.2B across various news snapshots (dates vary; one is from Jun 2026, with longs and
  shorts about 50/50). CryptoSlate argues the tradable part is liquidation levels plus
  social attention, with "no promise about direction"; others call the predictive value of individual positions
  questionable. — [CryptoSlate](https://cryptoslate.com/why-viral-public-whale-liquidations-are-becoming-a-real-trading-signal-on-hyperliquid/);
  [crypto.jobs](https://crypto.jobs/news/hyperliquid-whale-s-38m-bitcoin-short-raises-questions-about-market-signal-validity)

#### Free, no-key reproducibility (my tests, 2026-11-10)

| Need | Free endpoint | Result | Limits |
|---|---|---|---|
| Stablecoin supply by chain | [DefiLlama stablecoins](https://stablecoins.llama.fi/stablecoins) | [T] HTTP 200. Circulating supply per chain, plus previous day, week and month | Supply only, not exchange flows |
| Token unlock schedules | [DefiLlama emissions](https://api.llama.fi/emissions) | [T] HTTP 402 "Upgrade to the paid API plan" | Paywalled. Tokenomist's free tier gives a monthly release overview and a 30-day emission horizon; Pro gives 4 years ([Tokenomist](https://tokenomist.ai/research/do-token-unlocks-crash-prices)) |
| Bridge flows | [DefiLlama bridges](https://bridges.llama.fi/bridges) | [T] HTTP 402 | Paywalled |
| DEX pools, prices, liquidity | [GeckoTerminal API v2](https://api.geckoterminal.com/api/v2/networks/eth/trending_pools) | [T] HTTP 200, no key | Rate limits not measured |
| Perp positions, OI, funding (on-chain venue) | [Hyperliquid info API](https://api.hyperliquid.xyz/info) | [T] HTTP 200 for `metaAndAssetCtxs`, no key | Hyperliquid venue only |
| ERC-20 holders, holder counts, entity tags | [Blockscout API v2](https://eth.blockscout.com/api/v2/tokens/0x1f9840a85d5af5bf1d1762f925bdaddc4201f984) | [T] HTTP 200. UNI `holders_count` = 429,906; the top-holders list carries entity tags (e.g. "Uniswap", OLI tag set) | One instance per chain; label coverage is sparse |
| Basic ERC-20 network activity | [Coin Metrics Community API catalog](https://community-api.coinmetrics.io/v4/catalog-v2/asset-metrics?assets=uni) | [T] For UNI, LINK and AAVE, 22 free daily metrics including AdrActCnt, AdrBalCnt, TxCnt, TxTfrCnt, SplyCur and CapMVRVCur (see note below) | Daily only. No exchange-flow metrics in the free tier |
| Labelled altcoin exchange flows | none found | CryptoQuant, Glassnode, Nansen, Arkham and Santiment all need an account or key | You would need to build your own labels |

Coin Metrics coverage note: SOL gets only price and reference-rate metrics free. A request for SOL AdrActCnt returned
HTTP 403 "not available with supplied credentials". XRP and DOGE do have AdrActCnt and TxCnt free.

### Inferences
- **Flow-following is not validated.** For hours-to-weeks trading of Binance-perp altcoins, the industry offers no
  validated flow-following edge. The one rigorous public test (Presto) is negative for majors at 1–6 h. Evidence for
  altcoins is anecdotal (Santiment and CryptoQuant episodes) or paywalled (Santiment's 1,000-coin backtests).
- **Read deposit spikes as volatility.** The most defensible use of a deposit spike is as a volatility or risk flag,
  not a direction call. CryptoQuant's own documentation says this for derivatives-wallet inflows, and The Block
  headlines its deposit-spike note as "higher volatility ahead".
- **Normalise flows the way providers do.**
  - Glassnode removes same-entity churn (entity adjustment).
  - CryptoQuant uses counts, mean flow per transaction and the Top-10 largest deposits.
  - The Tie scales by average daily volume (Q2); Keyrock and Messari scale by % of supply.

  This suggests normalising altcoin deposits by 30-day ADV and by circulating supply. Breadth measures (the number of
  depositing addresses, as in CryptoQuant's Sep 2026 note) are harder to distort with one internal sweep than raw USD sums.
- **The one positive smart-money result is a breadth measure.** Nansen's best indicator was the change in the number of
  smart wallets holding a token, not their dollar holdings. Smart-money labels built from realized PnL are
  backward-looking by construction, so any test needs point-in-time label snapshots.
- **For a no-key bot**, the reproducible building blocks are:
  - DEX liquidity and trades (GeckoTerminal);
  - Hyperliquid positions and funding;
  - holder counts and top holders (Blockscout);
  - stablecoin supply by chain (DefiLlama);
  - basic ERC-20 activity (Coin Metrics Community).

  Labelled CEX flows and unlock calendars through an API are effectively paywalled in Nov 2026.

### Gaps
- **Galaxy Research, The Block Research, Messari (originals), Token Terminal and Wintermute research.** I found no
  research from these on whether on-chain metrics predict altcoin returns. The Galaxy results were about tokenized CLOs
  and OTC desks.
- **Santiment's backtests.** The results of "Whale Games" and "Sell-off alarm?" (sample, thresholds, horizons, returns)
  were not readable.
- **Untested signal families.** I found no rigorous public test of any of these predicting altcoin returns on CEXs or perps:
  - stablecoin exchange inflows;
  - DEX volume or new-pool activity;
  - bridge netflows;
  - altcoin staking flows.
- **Provider internals.** CryptoQuant's and Glassnode's lists of covered altcoins and their full clustering methodology
  are not public.
- **Unverified IntoTheBlock/Sentora and Glassnode quotes.** The pages behind these were reached only through secondary
  outlets.

## Q2. What studies exist on token unlocks and on exchange deposits by teams or market makers before dumps? Quantified effects and sample sizes

### Takeaway
The studies agree on direction but not on how big or how general the effect is.
- **Keyrock** (16,000+ tranche events from 40 tokens): about 90% of unlocks come with negative pressure. Team unlocks
  average about −25%. Declines start roughly 30 days before the unlock and stabilise about 14 days after.
- **Tokenomist** (236 events, Jun 2026): no effect once each token is compared with its own quiet periods. Against
  similar peers, there is about a −15% median effect, but only in young (≤~120 days), thin-float tokens, and it is
  mostly priced in before the unlock.
- **The Tie** (Aug 2026): scaled by trading volume, 95.6% of 2026 unlock events were smaller than one day's volume.
  Only 27 of about 12,350 events passed its materiality screen.

Evidence on insider or market-maker deposits before dumps consists of well-documented single cases (OM, MOVE), not
systematic studies.

### Cited Findings

#### Keyrock, "From Locked to Liquidity: What 16,000+ Token Unlocks Teach Us"
Undated page; widely covered in media. — [Keyrock](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/);
[BeInCrypto coverage](https://beincrypto.com/keyrock-research-token-unlocks/)
- [Q] **Sample and method:**
  - "16,000 composite events" from **40 tokens**: each linear vesting tranche counts as an event;
  - 106 investor-unlock events;
  - daily prices from 30 days before to 30 days after each unlock, normalised against ETH;
  - a median price and volatility control taken from the month before the pre-window;
  - burn unlocks excluded.
- [Q] **Size buckets** (% of supply; the text switches between total and circulating supply): nano <0.1%;
  micro 0.1–0.5%; small 0.5–1%; medium 1–5%; large 5–10%; huge >10%.
- [Q] **Effect by size:**
  - about 90% of unlocks create negative price pressure;
  - bigger unlocks produce drops "2.4x" sharper, but the baseline is not specified;
  - after scaling for relative size, most buckets show similar suppression;
  - the link to size weakens beyond 7 days;
  - huge (>10%) unlocks did as well as or better than large (5–10%) ones.
- [Q] **Effect by recipient:**
  - team unlocks are worst, at about −25%, with a near-linear decline starting more than 30 days before;
  - investor unlocks show "controlled, slow, minimal" declines;
  - ecosystem-development unlocks average +1.18%;
  - community and airdrop unlocks are moderate.
- [Q] **Timing:**
  - the decline starts about 30 days before the unlock and steepens in the final week;
  - weighted volume peaks 28 or 14 days before;
  - prices stabilise about 14 days after the unlock;
  - volatility spikes on day 1 and subsides within 14 days;
  - suggested exit about 30 days before a major unlock and re-entry about 14 days after.
- [M/V] **Hedging and market makers:**
  - large recipients start hedging 1–2 weeks, or up to a month, before the unlock;
  - investors pre-hedge with futures and unwind gradually after, or use OTC sales or TWAP/VWAP execution;
  - teams rarely hedge;
  - huge unlocks cannot be fully hedged within 30 days.
- [C] **APE example:** a linear team unlock of 0.7% of supply a month began on 1 Mar 2023. APE fell 77% over the next
  seven months, against −9% for ETH.
- **Conflict of interest:** Keyrock is itself a market maker and OTC/hedging provider.

#### The Tie, "Most Token Unlocks Don't Move the Market"
Hari Iyer, 25 Aug 2026. — [The Tie](https://www.thetie.io/insights/venture-cliffs-token-unlocks-2026)
- [Q] **Metric:** unlock notional as a % of trailing 30-day mean ADV. The materiality screen is ADV ≥ $30M and an
  unlock above 0.25 days of volume, which leaves **27 events in 2026**.
- [Q] **Sample:**
  - at least $21B unlocked across 101 tokens in 2026, through 19 Aug;
  - 12,350 priced events, of which 12,343 have volume data.
- [Q] **Results:**
  - the median event is 0.20% of ADV;
  - 95.6% of events are below one day's volume;
  - about four in five are below 1% of ADV;
  - the 544 events above one day's volume have a median value of $189, mostly in thin names (BendDAO, Lyra, Silo).
- [Q] **Material examples:**
  - WhiteBIT: $2.19B, about 28× ADV;
  - Ondo: two January unlocks at about 4× and 6× ADV;
  - BTC ($7.4B) and Ripple ($5.0B) lead by dollar value but stay well below one day's volume.
- [Q] **Composition of unlocked value:**
  - investor allocations were only $780M (under 4%);
  - BTC mining 35%, Ripple escrow 24%, WhiteBIT 10%, SOL 7%.
- **What the piece does not do:** no price-impact backtest; no discussion of hedging, perps or market makers; covers
  only the 101 tokens The Tie tracks; about one-third of the value is forward-dated after the 7 May 2026 snapshot.
- [Q] **The Tie, 2023 (earlier study):** on average, prices declined into an unlock. Tokens facing large unlocks
  relative to average trading volume fell further within two weeks after the event. — via search summary of
  [CoinDesk, 21 Jul 2023](https://hotfix.coindesk.com/markets/2023/07/21/large-crypto-token-unlocks-drive-prices-lower-within-two-weeks-new-research-suggests)
  (primary not retrievable)

#### Tokenomist, "Tokenomics Insight: When Token Unlocks Actually Move Price"
Chawapat Peechapat, 29 Jun 2026. — [Tokenomist](https://tokenomist.ai/research/do-token-unlocks-crash-prices)
(page metadata; the body is JS-rendered and returned 403 to the fetch tool)
- [Q] From the page metadata: "A 236-event study: token-unlock price drops are real but conditional — concentrated in
  early-stage, thin-float tokens, and mostly priced in before the unlock."
- [Q] From the search summary:
  - a within-token placebo (each unlock window against the same token's own quiet windows) "finds nothing";
  - against similar-sized peers, the effect holds at a median of **−14.8%** for tokens with an "age gap of 120 days
    or less";
  - established tokens stay flat.
  — via search summary of the same URL
- [M] **Unlock schedules get revised.** Tokenomist recorded six versions of JUP's unlock schedule since its
  31 Jan 2024 launch. The changes in Nov 2025 and Feb 2026 cut the JUP due over the following year by 500M and then
  910M tokens. Backtests therefore need point-in-time schedules. — "JUP's 6 Unlock Schedule Versions: A Point-in-Time
  Data Example", 3 Nov 2026, listed on [Tokenomist research](https://tokenomist.ai/research/do-token-unlocks-crash-prices)
- [C] **Upcoming cliffs (Nov 2026),** expressed as % of circulating supply:
  - KITE: $75.5M Founder/Team and Private Investors cliff, 26.76% of circulating supply;
  - Allora: $24.19M backer and contributor cliff, 38.07%.

  — Tokenomist weekly digests listed on the same [page](https://tokenomist.ai/research/do-token-unlocks-crash-prices)

#### Messari (secondary coverage only)
- [Q] 619 unlock events across 41 assets. Most events add less than 2.5% to circulating supply. A significant price
  impact appears when an unlock exceeds 5–10% of circulating supply and no positive catalyst is coming. Tokens with
  larger monthly unlocks struggle to outperform other altcoins over the long term. The publication date is unverified.
  — [ChainCatcher on the Messari report](https://www.chaincatcher.com/en/article/2162595)
- [M] Messari's unlock pages show daily unlocks next to price and cover more than 150 tokens.
  — [Messari docs](https://docs.messari.io/docs/token-unlocks)

#### Kaiko
- [V] **Sep 2026 (ARB, PROVE, PUMP):** the market reaction depends more on the leverage and liquidity that build up
  around the event than on the size of the new supply. — via [TokenPost (Korean summary)](https://tokenpost.kr/news/insights/415142)
- [V] **2023, "Token Unlocks: Not All Built The Same":** SAND's investor-heavy allocation coincided with weaker
  performance around unlocks (SAND, AXS and DYDX compared). — [Cryptonomist](https://cryptonomist.ch/?p=180669);
  teaser at [Mondo Visione, 26 Jan 2023](https://mondovisione.com/news/token-unlocks-not-all-built-the-same-kaiko-research-deep-dive-2023126)

#### Deposits by teams, investors or market makers before dumps (case evidence)
- [C] **Mantra OM, Apr 2025 (Lookonchain, using Arkham labels):**
  - at least 17 wallets deposited 43.6M OM (4.5% of circulating supply, about $227M) to exchanges, starting around 7 Apr;
  - one Arkham-tagged "Laser Digital" wallet sent 6.5M OM (about $41.6M) to OKX in 7 transactions from 11 Apr. Laser
    Digital denies owning it;
  - Spot On Chain counted 14.27M OM sent to OKX three days before the crash.

  OM then fell about 90%. Mantra blamed forced liquidations by exchanges.
  — [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/mantra-token-plunges-90percent-after-dollar227-million-moved-to-exchanges-sparking-liquidity-and-insider-dumping-concerns);
  [Cointelegraph](https://cointelegraph.com/news/mantra-investors-dumped-om-before-90-percent-crash);
  [Cointelegraph feature](https://cointelegraph.com/news/mantra-om-token-collapsed-24-hours)
- [C] **Kaiko on the OM collapse:** 1% market depth across venues fell 74% to $473K within two hours, and funding
  rates turned negative. — via search summary of a [Kaiko page](https://marketing.kaiko.com/xrp-liquidity-race-as-crypto-etfs-deadlines-loom)
  (the page title does not match the content; attribution needs a re-check)
- [C] **Binance enforcement, Movement (MOVE):** about 66M MOVE were sold by a market maker shortly after the
  10 Dec 2024 listing, "with little buy support". Binance froze about 38M USDT of proceeds, which went into a buyback.
  This is the same market maker Binance offboarded on 9 Mar 2025 over GPS and SHELL. Detection came from the
  exchange's internal data; Binance did not name the firm.
  — [The Block, 25 Mar 2025](https://www.theblock.co/news/markets/2025-03-25-binance-move-market-maker-movement-38-million-usdt-buyback-program-347931);
  [Binance announcement, 9 Mar 2025](https://www.binance.com/en/support/announcement/4a5fa79a6c174db29c43122db732af1e)
- [C] **ARKM, Apr 2024:** Nansen flagged about $56M (more than 25.2M ARKM) sent to Binance and fresh wallets. Arkham
  replied that these were tokens unlocked "as per the published tokenomics".
  — [crypto.news](https://crypto.news/?p=14263572)
- [Q] **Chainalysis, DEX pump-and-dumps in 2024:**
  - 74,037 suspected pump-and-dump tokens, 3.59% of 2,063,519 tokens launched;
  - about 94% of the pools involved were dumped by the address that deployed the pool;
  - on average a pool was abandoned after 6.2 days (median 0; 90th percentile 8 days).

  This is the deployer-dump pattern at microcap scale. — [Chainalysis](https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/)

### Inferences
- **Where the studies converge.** The unlock effect is concentrated in:
  - team or insider allocations;
  - young, thin-float tokens;
  - unlocks large relative to liquidity (ADV) rather than to supply;
  - the period *before* the unlock (Keyrock: about 30 days; Tokenomist: "mostly priced in before"; The Tie 2023:
    decline leading up).

  A short opened at the unlock is late on average. Keyrock's 14-day post-unlock stabilisation points to fading
  continuation after the event.
- **Keyrock's "90%" is likely overstated.** Its 16,000 events come from only 40 tokens, and daily linear tranches with
  ±30-day windows overlap heavily. The effective independent sample is far smaller, and its only market control is ETH.
- **The unlock effect may partly be a young-token effect.** Tokenomist's null within-token placebo suggests young
  tokens drift down regardless of the unlock date (emissions, post-listing decay). This overlaps with the post-listing
  short already researched in this repo (s15), so the two signals should be tested together, not as independent edges.
- **Tradable universe.** The Tie's ADV normalisation can be reproduced for free (Binance klines plus a schedule).
  Material events are rare (27 in 2026 with ADV ≥ $30M), so for Binance USDT-M names the set of tradable unlock events
  each year is small, perhaps dozens.
- **Pre-unlock hedging moves perps first.** Keyrock describes hedging 1–4 weeks ahead, and Kaiko describes leverage
  building up around unlocks. This implies perp funding, open interest and basis may move before spot and before any
  on-chain deposit appears.

### Gaps
- **Missing primary details.** I could not open the primary Messari study (date, method), The Tie's 2023 study (sample
  size), the body of the Tokenomist study (statistics, significance, exact definitions) or Kaiko's Sep 2026 unlock note
  (seen only in a Korean summary).
- **Keyrock.** The publication date and the exact baseline behind "2.4x", "−25%" and "+1.18%" are not stated on the page.
- **No systematic studies of insider deposits.** I found none on "team or MM wallet deposits to CEX → forward returns"
  with a sample of more than a handful of cases. The evidence is cases (OM, MOVE, ARKM) labelled after the fact.

## Q3. How do industry analysts detect market-maker activity on-chain, and what is the documented relationship with price moves on centralized exchanges and perps?

### Takeaway
On-chain market-maker tracking means following Arkham- or Nansen-labelled MM wallets (Wintermute, DWF, Jump and others)
into exchange deposit addresses, plus DEX-side wash-trading signatures (Chainalysis). The sources stress that a
deposit shows inventory moving, not a sale. The relationship with price is documented as cases with mixed outcomes.
The only systematic test that includes MM deposits (Presto) found R² ≤ 0.054. The strongest documented MM dumps
(GPS, SHELL, MOVE) were caught by Binance's internal surveillance, not by on-chain watchers. The economic terms that
drive MM selling (token loans with call options) sit off-chain.

### Cited Findings
- [M] **How attribution works.** Flow analyses of market makers rely on Arkham labels: addresses tagged as Wintermute
  on one side and Binance hot wallets on the other. Arkham's "Intel Exchange" pays bounties for de-anonymising wallets,
  and Wintermute was a key subject of it. — [CryptoSlate](https://cryptoslate.com/major-market-maker-secretly-offloaded-1213-btc-onto-binance-during-new-years-eve-thin-liquidity/);
  [CoinDesk, 2 Aug 2023](https://coindesk-coindesk-prod.cdn.arcpublishing.com/business/2023/08/02/wintermute-a-major-trader-is-a-key-player-in-arkhams-controversial-dox-to-earn-platform/)
- [C] **Wintermute, New Year's Eve (year not verified in my extraction):**
  - about 1,213 BTC moved to Binance in thin holiday liquidity, 933 BTC of it net deposits on the day;
  - a further 624 BTC and 817 BTC followed over 1–2 Jan;
  - the heaviest deposits bracketed the intraday low of a BTC dip;
  - the article concedes that whether the firm sold immediately or staged inventory "remains unknowable from blockchain
    data alone".

  — [CryptoSlate](https://cryptoslate.com/major-market-maker-secretly-offloaded-1213-btc-onto-binance-during-new-years-eve-thin-liquidity/)
- [C] **Wintermute, Sep 2026:** about $160M of ETH moved to Binance and Coinbase as ETH was rejected near $2,667.
  Coverage says derivatives did more damage to the tape than the wallet transfer can be shown to have caused.
  — [Crypto Times, 12 Sep 2026](https://www.cryptotimes.io/2026/09/12/wintermute-moves-160m-in-eth-to-binance-and-coinbase-as-ethereum-rejects-2667/)
- [C] **A counter-case:** Wintermute deposited 3,834 BTC (about $256M) to Binance in one week while the price stayed
  roughly stable. — [Cryptorank](https://cryptorank.io/news/feed/c0baa-wintermute-bitcoin-binance-256m-week)
- [C] **Lookonchain and The Block (2024):** $537M of Binance deposits "tied to" a BTC price drop. Framed as a
  correlation between transfers to Arkham-tagged Binance deposit wallets and later declines.
  — [The Block](https://www.theblock.co/amp/post/303741/537-million-binance-deposits-tied-to-btc-price-drop-suggest-whales-selling-lookonchain)
- [C] **CoinDesk, 11 Sep 2023:** trading firms deposited millions in BTC, ETH and ARB to exchanges as a sell-off
  intensified. — [CoinDesk](https://coindesk-coindesk-prod.cdn.arcpublishing.com/markets/2023/09/11/trading-firms-deposit-millions-in-btc-eth-and-arb-to-exchanges-as-crypto-sell-off-intensifies/)
- [Q] **Presto Research (Feb 2025)**, VC and market-maker subset of large Binance deposits:
  - MMs and VCs made 61% of large ETH deposits, 32% of SOL and 13% of BTC;
  - restricting to this subset raised R² only slightly against 1 h and 6 h maximum drawdown (overall range 0.0017–0.0537);
  - the authors say the improvement may just reflect less noise in the sample.

  — [Presto via OKX Learn](https://okxapi.goquant.io/nl/learn/prestoresearch-datafocus01092025)
- [C] **Binance enforcement, unnamed market maker:**
  - for GPS and SHELL, offboarded on 9 Mar 2025 with its earnings confiscated to compensate users;
  - for MOVE, about 66M sold right after the 10 Dec 2024 listing, with about 38M USDT frozen.

  — [Binance](https://www.binance.com/en/support/announcement/4a5fa79a6c174db29c43122db732af1e);
  [Decrypt](https://decrypt.co/309291/binance-bans-market-maker-over-misconduct-with-gps-shell-tokens);
  [The Block](https://www.theblock.co/news/markets/2025-03-25-binance-move-market-maker-movement-38-million-usdt-buyback-program-347931)
- [C/V] **DWF Labs:**
  - the WSJ reported on 9 May 2024 that Binance's surveillance team found about $300M of DWF wash trades in 2023, plus
    manipulation of YGG and other tokens, and recommended offboarding;
  - Binance did not act and cited an Inca Digital review that found "minimal signs of anomalous trading";
  - DWF denies the claims.

  No regulator finding was found. — [The Block, 9 May 2024](https://www.theblock.co/news/business/2024-05-09-dwf-labs-denies-report-that-it-did-300-million-of-wash-trading-on-binance-last-year-293429)
- [V] **MM contract structure.** Under the "loan + call option" model, a market maker borrows project tokens with
  options to buy them at preset prices. KPIs are often vague. The agreements are undisclosed and off-chain, and can add
  hidden sell pressure. Cointelegraph reports six projects on loan-option deals that "tanked". Wintermute calls such
  deals "liquidity provision". — [Cointelegraph, Apr 2025](https://cointelegraph.com/news/market-maker-deals-quietly-killing-crypto-projects);
  [Crypto Briefing](https://cryptobriefing.com/market-maker-token-loans-transparency-scrutiny/)
- [Q/M] **Chainalysis, Jan 2025, on-chain signatures of manipulative market making and volume bots:**
  - rapid, near-identical buy/sell pairs;
  - addresses calling their own contracts instead of the Uniswap router (function selector 0x5f437312);
  - intermediary contracts that fire multiple wash trades;
  - multi-sender funding of many addresses.

  Case: the Volume.li bot service claims $257.5M of generated volume. One bot made 10,341 buy/sell pairs across five
  addresses in five days ($39,723), about 43% of one token's Uniswap volume over 27–30 Jul. The SEC charged four
  market makers on 9 Oct 2024 (ZM Quant, CLS Global, MyTrade, Gotbit) with generating artificial volume. Chainalysis
  says its on-chain method cannot be applied to centralized exchanges.
  — [Chainalysis](https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/)
- [M/V] **The perps link.**
  - Keyrock: investors and market makers pre-hedge unlocks with futures 1–4 weeks ahead, then unwind gradually
    ([Keyrock](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/)).
  - Kaiko: WLFI perps traded before the spot listing
    ([Kaiko](https://research.kaiko.com/insights/wlfi-spot-market-launch-off-to-a-strong-start)).
  - Kaiko: leverage built around unlocks matters more than the size of the supply
    ([TokenPost summary](https://tokenpost.kr/news/insights/415142)).
  - CryptoQuant: airdrop-related inflows should be checked against funding and open interest because of hedging
    ([CryptoQuant](https://userguide.cryptoquant.com/exchange-flows-indicators/exchange-in-outflow-and-netflow)).

### Inferences
- **On-chain sees inventory, not intent.** It shows MM inventory moving onto exchanges, but MMs move inventory all the
  time (rebalancing, hedging, cross-venue arbitrage). Without a sale or a basis change, a deposit is weak evidence;
  Presto's MM subset and the Wintermute counter-case both point that way.
- **Where MM selling hurts most:**
  - newly listed, thin-float tokens where an MM received a token loan (MOVE-type);
  - the window right after a listing, when buy support is thin.

  Both match the Binance-perp short-after-listing setups already studied in this repo. The key inputs, however (loan
  size and call strikes), are off-chain, so on-chain data only flags transfers from project treasury to MM to CEX.
- **Perps may lead on-chain.** Hedging runs through perps, so funding, OI and basis can move before, or instead of,
  on-chain deposits. A test should line up the timing of MM deposits against perp OI and funding changes, not against
  spot price alone.

### Gaps
- I found no systematic study (with a sample, method and forward returns) linking labelled MM wallet deposits to
  altcoin price or perp moves. Everything public is case-based, except Presto, which covers majors only.
- No Kaiko, Galaxy or Wintermute research describing a validated method for detecting MM wallets on-chain was found.
  Detection in practice relies on Arkham and Nansen labels.
- The DWF allegations rest on unnamed sources (WSJ); there is no regulator outcome.

## Q4. What do the providers warn about: label quality, clustering errors, exchange wallet reshuffles, bridges, look-ahead from retroactive labelling, survivorship, small samples, manipulation aimed at on-chain watchers?

### Takeaway
Providers and analysts openly acknowledge most of these pitfalls:
- noisy, user-sourced or AI-predicted labels (Arkham);
- exchange "housekeeping" that looks like whale buying or selling (CryptoQuant);
- inter-exchange arbitrage transfers;
- label revisions that rewrite history (Glassnode);
- schedule revisions (Tokenomist);
- heavy survivorship in token universes (Chainalysis: only ~1.7% of tokens launched in 2024 were still trading);
- cheaply faked activity metrics (wash-trading bots, multi-sender address farms).

Cross-chain bridges and deliberate spoofing of on-chain watchers are mostly undocumented. I found speculation but no
documented decoy-deposit campaign.

### Cited Findings

#### Label quality and attribution errors
- [C] **SharpLink:** Lookonchain posted Arkham data showing SharpLink depositing 4,364 ETH to OKX, a "pre-sell"
  pattern, which caused jitters. SharpLink said the wallet was not theirs, and Arkham said it was not one of the
  Arkham-verified SharpLink wallets. — [Cryptopolitan](https://www.cryptopolitan.com/de/sharplink-did-not-sell-eth-arkham-error/)
- [C] **US government BTC:** a false rumour that the US government was moving BTC came from community labels. Arkham
  lets users manually add labels and edit "Entities". — [CryptoSlate](https://cryptoslate.com/arkham-says-us-government-not-moving-bitcoin-labeling-issues-continue/)
- [C] **AI-predicted labels:** magenta labels on Arkham are low-confidence AI predictions, not verified wallets. This
  was raised during the OM attribution, where Laser Digital denied ownership.
  — [Cointelegraph](https://cointelegraph.com/news/mantra-investors-dumped-om-before-90-percent-crash)
- [C] **Vendor disputes:** Nansen publicly flagged Arkham's own ARKM transfers, and Arkham accused competitors of
  spreading "false rumors" (Apr 2024). — [crypto.news](https://crypto.news/?p=14263572);
  [Cointelegraph](https://cointelegraph.com/news/arkham-accuses-competitors-spreading-false-rumors-amid-token-selloff)

#### Exchange wallet reshuffles, internal and inter-exchange transfers
- [V] **CryptoQuant (Julio Moreno, Dec 2025):** apparent whale accumulation was exchange "housekeeping". After
  filtering exchange-internal transfers, BTC whales holding more than 1,000 BTC were net sellers through Dec 2025.
  — [Yellow](https://yellow.com/news/bitcoin-whale-accumulation-signals-were-exchange-housekeeping-cryptoquant-says)
- [M] **Glassnode label changes alter history.** One fix corrected for more than 100,000 BTC that Kraken moved into new
  wallets inside the exchange. Future flows of the same pattern are reclassified as internal automatically, and recent
  data points may be revised. — via search summary of [Glassnode changelog 2021](https://docs.glassnode.com/further-information/changelog/2021)
- [M] **CryptoQuant:** part of large inflows is inter-exchange arbitrage, not new selling.
  — [CryptoQuant User Guide](https://userguide.cryptoquant.com/exchange-flows-indicators/exchange-in-outflow-and-netflow)
- [V] **Cryptohopper:** exchange consolidations are probably the largest source of false "whale" alerts; sustained
  netflow is harder to fake with a single transaction. — [Cryptohopper](https://www.cryptohopper.com/blog/whale-wallet-tracking-signal-vs-noise-in-on-chain-data-13182)
- [M] **Coin Metrics:** deposit data for exchanges is "likely to be imperfect" and coverage is still being improved.
  — [Coin Metrics gitbook](https://gitbook-docs.coinmetrics.io/network-data/network-data-overview/mining/exchange-flows)

#### Look-ahead from retroactive labels and revised schedules
- [M] **Labels are revised after the fact.** Glassnode labels are revised over time and the changes alter historical
  exchange metrics (see the changelog above). A backtest run on today's labels uses information that was not available
  at the time.
- [M/V] **Smart-money labels.** Nansen's Smart Money labels are awarded on past PnL, so rolling windows reduce
  look-ahead bias but do not remove it ([Eco](https://eco.com/support/en/articles/14800361-nansen-smart-money-how-it-works)).
  Nansen's paid backtesting API claims point-in-time labels with "no rebuilding label history"
  ([Nansen docs](https://docs.nansen.ai/api/backtesting-data)).
- [M] **Unlock schedules.** JUP's schedule went through six versions in under three years, cutting 500M and then 910M
  tokens from next-year unlocks. An unlock backtest needs the schedule as it was known at the time.
  — [Tokenomist research listing](https://tokenomist.ai/research/do-token-unlocks-crash-prices)

#### Survivorship and universe construction
- [Q] **Chainalysis, 2024:**
  - 2,063,519 tokens were launched and 873,957 were listed on a DEX;
  - only about 1.7% of all launched tokens traded in the last 30 days of the study;
  - pump-and-dump abandonment had a median of 0 days.

  Any token-universe backtest is dominated by survivorship. — [Chainalysis](https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/)
- [Q] **The Tie's 2026 unlock universe** is limited to the 101 tokens in its data, not the whole market.
  — [The Tie](https://www.thetie.io/insights/venture-cliffs-token-unlocks-2026)

#### Small samples and vendor-driven evidence
- [Q] **Sample sizes behind the headline studies:**

  | Study | Sample |
  |---|---|
  | The Tie, 2026 | 27 material events |
  | Tokenomist, 2026 | 236 events |
  | Messari | 619 events over 41 assets |
  | Keyrock | 40 tokens, with heavily overlapping tranche events |
  | Presto | 12 regression scenarios over three assets |

  — [The Tie](https://www.thetie.io/insights/venture-cliffs-token-unlocks-2026);
  [Tokenomist](https://tokenomist.ai/research/do-token-unlocks-crash-prices);
  [ChainCatcher/Messari](https://www.chaincatcher.com/en/article/2162595);
  [Keyrock](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/);
  [Presto](https://okxapi.goquant.io/nl/learn/prestoresearch-datafocus01092025)
- [V] **Conflicts of interest:**
  - Keyrock is a market maker and hedging provider;
  - Nansen's smart-money evidence is self-published and labelled "preliminary";
  - Santiment's backtests are paywalled.

  — [Keyrock](https://keyrock.com/from-locked-to-liquidity-what-16000-token-unlocks-teach-us/);
  [Nansen](https://www.nansen.ai/research/trading-crypto-with-nansen-smart-money);
  [Santiment](https://insights.santiment.net/read/whale-games-backtesting-the-impact-of-large-transfers-on-1000-coins-santiment-weekly-pro-report-6299)
- [V] **Chainalysis caveats on its own numbers:**
  - its heuristics detect behaviour patterns, not intent;
  - MEV bots and arbitrageurs can look like wash traders;
  - the $2.57B wash-trading total is an upper bound (two heuristics may overlap: $704M and $1.87B);
  - the method changed year over year, so years are not directly comparable;
  - figures were corrected on 13 Feb 2025.

  — [Chainalysis](https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/)
  Secondary coverage cites different pump-and-dump shares (e.g. "4.52% in 2024 vs 3.59% in 2023"). The corrected
  primary page gives 3.59% for 2024, so use the primary.

#### Faked on-chain activity and manipulation aimed at watchers
- [Q] **Address farms and volume bots fake activity metrics.** In Chainalysis's "disperse" heuristic, a controller
  funds at least 5 managed addresses through a multi-sender. The average controller has 183 managed addresses (median 7,
  max 22,832), and $1.87B of 2024 DEX volume was flagged this way. Bots sell volume (Volume.li) and can make up about
  43% of a token's Uniswap volume. This directly distorts DEX volume, active-address, new-address and holder-count
  metrics. — [Chainalysis](https://www.chainalysis.com/blog/crypto-market-manipulation-wash-trading-pump-and-dump-2025/)
- [V] **Deliberate fakeouts are possible but undocumented.** Whales know deposits are tracked, which "opens the door to
  a fakeout situation"; no case is documented. — [Cointelegraph](https://cointelegraph.com/news/can-bitcoin-whale-deposits-to-exchanges-actually-predict-btc-price)
- [V] **Reflexivity:** public whale positions and liquidations on Hyperliquid become a "signal" through liquidation
  maps and social attention, not because they predict direction. — [CryptoSlate](https://cryptoslate.com/why-viral-public-whale-liquidations-are-becoming-a-real-trading-signal-on-hyperliquid/)

#### Data availability churn (affects reproducibility)
- [T] Several sources moved or closed between 2025 and 2026:
  - old Nansen research URLs return 404 or redirect to nansen.ai/blog;
  - Coin Metrics State of the Network URLs redirect to Talos;
  - DefiLlama's emissions (unlock) and bridge APIs return HTTP 402 (paid) as of 2026-11-10.

  — [Nansen research URL](https://www.nansen.ai/research/trading-crypto-with-nansen-smart-money);
  [Coin Metrics SOTN URL](https://coinmetrics.io/state-of-the-network/exchange-flow-metrics);
  [DefiLlama emissions](https://api.llama.fi/emissions); [DefiLlama bridges](https://bridges.llama.fi/bridges)

### Inferences
- **Practical rules for a bot-grade signal:**
  - freeze label sets with timestamps (point in time) and never re-run history on today's labels;
  - require deposit-address-level evidence (a user deposit address sweeping into a known hot wallet) rather than
    hot-wallet-to-hot-wallet moves, to avoid internal reshuffles;
  - drop transfers between two labelled exchanges, or treat them separately;
  - treat Arkham community or AI-predicted labels as unverified;
  - measure breadth (how many distinct depositors) alongside size;
  - validate out of sample, across both halves of the history (the repo's existing standard).
- **Cross-chain blind spots (my inference; no provider source found).** Many Binance-perp altcoins exist on several
  chains and on bridges. Single-chain holder or flow metrics will miss supply moving through bridges or held on
  another chain.
- **Address and holder growth is the easiest family to fake.** Multi-sender farms and wash bots inflate address,
  holder and DEX-volume counts cheaply. Weight these metrics down for small caps, or require that the addresses are
  economically active (hold value over time).

### Gaps
- I found no provider research quantifying bridge-flow errors in exchange-flow or holder metrics.
- I found no documented case of a deliberate decoy deposit aimed at Lookonchain, Arkham or Whale Alert followers; the
  idea is speculative in the sources found.
- No provider publishes an error rate for its labels (precision/recall of exchange or entity labels), so label noise
  cannot be quantified from public sources.
