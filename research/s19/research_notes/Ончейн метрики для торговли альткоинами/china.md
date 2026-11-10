# How the Chinese-speaking crypto community uses on-chain data to trade altcoins (focus: Binance USDT-M perps)

Legend for every finding: **[QUANT]** has a stated sample/statistic; **[ANECDOTAL]** case study or opinion; **[PROMO]** author sells a related product; **[ALLEGATION]** disputed by the named party; **[SNIPPET]** seen only in a search-result summary, page not fetched. Dates are publication dates unless said otherwise. Most sources below are Chinese-language (simplified: ChainCatcher 链捕手, Odaily 星球日报, PANews, TechFlow 深潮, BlockBeats 律动, WuBlockchain 吴说; traditional/Taiwan: BlockTempo 動區, BNext 數位時代, cnyes 鉅亨網). A few foreign studies are included because Chinese media translated and spread them; that is flagged.

## 1. Who is most cited (analysts, media, research firms, tools) and what methods do they describe?

### Takeaway
Chinese-language on-chain "alpha" mostly reaches traders as short news items. Aggregator media (ChainCatcher, Odaily, BlockBeats, PANews, TechFlow, WuBlockchain; BlockTempo and cnyes in Taiwan) pass on a few wallet trackers using a fixed formula, 「据链上分析师 X 监测」 ("according to monitoring by on-chain analyst X"). The trackers are 余烬 EmberCN and Ai姨 (@ai_9684xtpa), who write in Chinese, plus Lookonchain, Spot On Chain, onchainschool.pro, Bubblemaps and Arkham, whose posts are passed on in translation. Method-level long reads come from a small set of practitioner-writers: Haotian, Owen.btc, agintender/danny, 加密韋馱 Skanda, Jonas of Foresight Ventures and FMZ/MathQuant. PANews (author Frank) also publishes data journalism. Firms (0xScope, BlockSec/MetaSleuth, OKLink, SlowMist, Coinglass) supply labels, clustering and derivatives data. I found no Chinese research firm that publishes a validated, testable on-chain rule for trading altcoins.

### Cited Findings
**Trackers and how media relay them**
- 余烬 EmberCN has a verified Binance Square creator profile with the bio "分享链上数据 On chain data sharing。Twitter:@EmberCN" ("sharing on-chain data"). — [Binance Square profile](https://www.binance.com/en-JP/square/profile/ember)
- Typical relay [ANECDOTAL]: 「据链上分析师余烬（@EmberCN）监测，币安人生庄家在过去 24 小时内继续买入约 1000 万美元的币安人生，推动该代币进一步上涨 15%」 ("the 币安人生 operator kept buying ~$10M in 24h, pushing it up another 15%"). It separates an on-chain buy address (8.62M tokens, about $6.33M) from a "CEX 提币地址" (exchange withdrawal address) that took 5.666M tokens (about $4.07M) out of Binance 8 hours earlier. The repost shows only a relative date, and the article does not explain how the 庄家 ("operator") addresses were identified. — [BitRSS repost of ChainCatcher](https://bitrss.com/%E6%95%B0%E6%8D%AE-%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9F%E5%BA%84%E5%AE%B6%E8%BF%87%E5%8E%BB-24-%E5%B0%8F%E6%97%B6%E5%86%8D%E4%B9%B0%E5%85%A5%E7%BA%A6-1000-%E4%B8%87%E7%BE%8E%E5%85%83%E4%BB%A3%E5%B8%81-218547)
- EmberCN also contests other trackers' attributions. In October 2025 he argued that the cluster of high-profit COAI addresses that Bubblemaps found was "more likely an external quant/arbitrage team than the project team". [SNIPPET] — [ChainCatcher EN, COAI tag](https://www.chaincatcher.com/en/tags/COA)
- Ai姨 (@ai_9684xtpa) mostly follows large-cap whales, not small altcoins [ANECDOTAL]:
  - 2025-09: an address deposited about 25.7k ETH (~$117M) to Binance after nine months of inactivity. [SNIPPET] — [ChainCatcher via itiger](https://www.itiger.com/news/2566031979)
  - 2025-09: a 2017 ETH OG deposited 2,200 ETH to Bybit, with 8,310 ETH deposited to exchanges that year. [SNIPPET] — [itiger](https://www.itiger.com/news/2567617761)
- Lookonchain is relayed constantly in Chinese:
  - A whale deposited 12M BIO (~$3.79M) to Binance; the tokens had come from a Bio Protocol vesting wallet. [SNIPPET] — [itiger](https://www.itiger.com/news/2561265545)
  - "BTC OG 内幕巨鲸" ("BTC OG insider whale"): wallets linked to it withdrew 59M 币安人生 from Binance. Details in section 4. — [ChainCatcher via itiger, 2026-04-14](https://www.itiger.com/news/2627442903)
- onchainschool.pro is relayed for team-wallet moves, e.g. AIA on 2026-01-21. — [ChainCatcher via itiger](https://www.itiger.com/news/2605104847)

**Media long reads that carry the methods (all fetched)**
- Haotian (@tmel0211), WuBlockchain, 2022-12-15: on why on-chain data analysis is easy to misread. — [WuBlockchain](https://wublock.substack.com/p/analysis-why-is-on-chain-data-analysis)
- Jonas@Foresight Ventures, Odaily, 2023-06-13: indicators for short squeezes (轧空) in small-cap altcoins. — [Odaily](https://www.odaily.news/post/5187731)
- FMZ/MathQuant, 2023-11-20 (reposted 2024-03-20): post-listing price path of new Binance perpetuals. — [StockSharp repost](https://stocksharp.com/zh/topic/25589/unveiling-the-price-dynamics-analyzing-performance-post-listing-on-perpetual-contracts/)
- Owen.btc, ChainCatcher via 吴说, 2024-06-26: 「揭秘：庄家是如何操纵现货合约价格最终收割散户」 ("How operators manipulate spot and futures prices to harvest retail"). — [ChainCatcher](https://www.chaincatcher.com/article/2130706)
- Presto Research's whale-deposit study, translated by Odaily and published 2025-01-10. This is a foreign (Korean firm) study that circulated in Chinese. — [ChainCatcher](https://www.chaincatcher.com/article/2161902)
- PANews (Frank), 2025-09-12: 335 Binance Alpha tokens. — [TechFlow repost](https://www.techflowpost.com/article/detail_28128.html)
- agintender, WuBlockchain, 2025-09-11: the MYX case. — [WuBlockchain](https://wublock.substack.com/p/the-myx-affair-a-deliberately-orchestrated)
- 可达鸭 (Psyduck Fomo), ChainCatcher, 2026-04-15: 「拆解 RAVE 庄家控盘术」 ("taking apart RAVE's operator control"). — [ChainCatcher](https://www.chaincatcher.com/article/2258740)
- danny/agintender, Odaily, 2026-04-15: framework for operator phases. — [Odaily](https://www.odaily.news/zh-CN/post/5210278)
- 加密韋馱 Skanda (@thecryptoskanda), Odaily, 2026-04-22: systematic shorting of "妖币". — [Odaily](https://www.odaily.news/zh-CN/post/5210424)

**Firms and tools named in Chinese material**
- 0xScope (Scopescan):
  - "Entity" (实体) clustering by a graph-computation weighting algorithm that combines dozens of rule types, tuned with deep learning.
  - Claimed scale in 2023, when OKX Ventures invested: 30M+ high-risk addresses and 120M Web3 entities. These are investor claims.
  - [SNIPPET] — [ChainCatcher](https://www.chaincatcher.com/article/2085491); [BlockBeats via cnyes](https://news.cnyes.com/news/id/5105260)
- BlockSec MetaSleuth: Chinese fund-tracking tutorial that filters flows by direction and time range, plus an address-label API. — [MetaSleuth docs (zh)](https://docs.metasleuth.io/zh_cn/yong-hu-shou-ce/tutorials/advanced-analysis-lightweight-fund-tracking)
- SlowMist: publishes a Chinese asset-tracing handbook. — [SlowMist handbook (CN)](https://www.slowmist.com/report/SlowMist-Crypto-Asset-Tracing-Handbook(Beta-CN).pdf)
- OKLink: explorer covering 40+ chains, with CEX asset dashboards and AML products. [SNIPPET] — [Alchemy dapps listing](https://www.alchemy.com/dapps/oklink)
- Coinglass: Skanda's data source (under an API sponsorship) for K-lines, order book, OI, funding, liquidations, long/short and taker ratios. — [Odaily 2026-04-22](https://www.odaily.news/zh-CN/post/5210424)
- Bubblemaps:
  - V2 was made public with "Magic Nodes" to find hidden wallet links and a per-token concentration score. [SNIPPET] — [itiger](https://www.itiger.com/hans/news/2539501882)
  - "Clusters" link wallets with a common funding source or transfer pattern; "bundles" are wallets that bought in the same block or within seconds of launch. [SNIPPET] — [Bubblemaps blog](https://blog.bubblemaps.io/what-is-bubblemaps-the-visual-onchain-analytics-tool-explained/)
- GMGN: Solana-centric "聪明钱" ("smart money") profit ranking with copy-trading. The interface is free, with a 1% fee per swap. [SNIPPET] — [MadeOnSol comparison](https://madeonsol.com/compare/debank-vs-gmgn)
- Arkham: entity labels. Presto used Arkham labels "supplemented by own research" to classify VC/MM deposits. — [ChainCatcher 2025-01-10](https://www.chaincatcher.com/article/2161902)
- Community Dune dashboard with Chinese and English titles: 「币安 Alpha 2.0 独家准确数据」 ("Binance Alpha 2.0 exclusive accurate data"). [SNIPPET] — [Dune](https://dune.com/pandajackson42/binance-alpha-20-purchase-dex-tokens-directly-on-binance-cex)
- litangdingzhen.me: third-party site that counts how many Binance Alpha airdrop accounts have already sold. BlockBeats relays its numbers. [SNIPPET] — [BlockBeats via itiger](https://www.itiger.com/news/2543061717)
- BTC-cycle style metrics exist in Chinese but are BTC/ETH-centric:
  - CryptoQuant's Chinese user guide: "交易所巨鲸比率" (exchange whale ratio, the top-10 inflows as a share of all inflows) above 85% is read as bearish. [SNIPPET] — [CryptoQuant zh guide](https://userguide.cryptoquant.com/zh/quick-start/ju-jing-pao-shou)
  - Glassnode publishes a Chinese edition of its weekly. — [Glassnode Chinese weekly](https://insights.glassnode.com/chinese/the-week-onchain-week-8-2024-chinese)

### Inferences
- The Chinese ecosystem is driven by news flashes. Deposits that were followed by a drop, and withdrawals followed by a pump, get written up; misses are not, so the public record has a strong selection bias. Media verbs are typically 「疑似」 ("suspected") and 「或将出售」 ("may sell"), not outcomes.
- The native Chinese trackers (EmberCN, Ai姨) focus mostly on large-cap whales, meme "operators" and Hyperliquid whales. Team and market-maker deposits in mid-cap altcoins are more often English trackers' work (Lookonchain, Spot On Chain, onchainschool.pro), relayed in Chinese.
- The only quantified material that bears on altcoin trading horizons is:
  - descriptive: PANews (Alpha tokens), FMZ (new perps);
  - negative: Presto (whale deposits);
  - small-sample and promotional: Skanda (妖币 shorts).

### Gaps
- I found no altcoin-signal research in this context from SoSoValue, Footprint Analytics or Chainbase. I also found none from HashKey, Matrixport, HTX, OKX or Binance Research (Chinese editions); the Matrixport item that surfaced was macro "altcoin season" commentary.
- No CNKI or other academic Chinese paper on altcoin on-chain trading signals turned up.
- I found no interviews in which EmberCN or Ai姨 explain their own labelling methods; their methods have to be inferred from their posts.
- "Most cited" is a qualitative judgement from repeated appearance in relays; no citation counts were found.

## 2. Which signals do they use, what concrete rules do they claim, and is there quantified evidence?

### Takeaway
The rules that recur and come closest to testable are not pure on-chain flow signals. They are supply-control plus derivatives structure: very concentrated spot (「控盘」 "controlled float", e.g. >60% or >96% of float in a few wallets), open interest close to or above circulating market cap or exchange spot float, futures volume large relative to spot, and extreme negative funding. Chinese writers treat this mix as the signature of 「妖币/庄币」 ("manipulated / operator coins") and of 「逼空/轧空」 ("short squeeze") risk, which is the main danger for a pump-shorting bot. Other signals in use are:
- token unlocks (「解锁抛压」 "unlock sell pressure", the best quantified; declines start about 30 days before);
- airdrop dumping (「空投砸盘」), quantified for Binance Alpha;
- DEX liquidity-pool withdrawals (「撤池」);
- team/VC/market-maker exchange deposits. These are the most publicised, but the only quantified test found (Presto) shows almost no predictive power.

The most systematic Chinese attempt to short 妖币 on Binance found two things:
- predicting when manipulation starts, and shorting the top, both fail out of sample;
- only a "wait for the operator to abandon defence" (「弃盘点」) breakdown short survived, and its live sample is tiny.

### Cited Findings
**A. Derivatives plus supply-control ("squeeze") rules**
- Jonas@Foresight Ventures (Odaily, 2023-06-13) [ANECDOTAL; 3 cases plus 2 mentioned]:
  - Funding below −0.1% per period (about 0.3% a day, >100% annualised) marks extreme bearish crowding; below −0.75% the rise accelerates.
  - OI close to circulating market cap means a lot of trapped liquidity. Futures volume near 50% of spot volume makes forced covering likely.
  - OI up ≥50% in the short term means "main funds entering"; falling OI means take profit.
  - Squeezes are more extreme the more concentrated the 筹码 ("chips", i.e. supply).
  - The three cases:

    | Token, dates | Supply control | Funding | OI vs market cap | Futures vs spot volume | Move |
    |---|---|---|---|---|---|
    | LINA, late May–early Jun 2023 | ~50% of float locked (22% via LUSD staking + ~23% bought by main players) | hit the −2% cap on May 31 and Jun 3 | ~$50M vs ~$70M | ~$50M vs ~$90M | 2–3x in a week |
    | ARPA, May 2023 | market maker had switched to DWF | low near −1% | ~$30M vs ~$40M | not given | 3–4x in 2 weeks |
    | MTL, Jun 2023 | ~10% of float held by main players | about −1.8% | ~$60M vs ~$80M | not given | 2–3x; unusual Upbit volume |

  - Signs of a top: the altcoin's spot or futures volume reaches ETH's, or price swings more than 20% within 4 hours.
  - Binance changed contract parameters on LINAUSDT on Jun 3 and on MTLUSDT on Jun 7.
  - [Odaily](https://www.odaily.news/post/5187731)
- Owen.btc (ChainCatcher via 吴说, 2024-06-26) describes a 庄 ("operator") playbook [ANECDOTAL]:
  - Pick a low-float token with circulating market cap of 1–10M USDT and Binance-style futures at 20–30x.
  - Accumulate about 60% of the float; about 2M USDT of bids is enough to control spot.
  - Control spot, and with it the 标记价格 ("mark price"), so the operator's own longs cannot be liquidated.
  - Let retail open shorts, then collect funding.
  - Red flags he gives: low on-chain/spot volume with high futures volume (futures about 60x spot on Gate for one token); price up while volume falls; funding −0.66% per 8h (about −1.98% a day); OI above circulating market cap. SRM paid about 16% per 24h in funding.
  - [ChainCatcher](https://www.chaincatcher.com/article/2130706)
- RAVE (ChainCatcher, 2026-04-15) [ANECDOTAL; internally inconsistent]:
  - Spot: six Gnosis Safe multisigs hold 96.36% of supply, one address 76.94%; CEXes hold 3.56%, of which Bitget has 88.3%; retail EOAs hold 0.06%.
  - OI is $294M, and "OI/交易所现货" (OI to exchange spot float) is 102.9%. The article's own figures for the two sides are identical.
  - Funding is negative on all exchanges, which the author calls 「经典逼空死局」 ("a classic short-squeeze deadlock").
  - In 24h, liquidations were about $41.6M, 73% of them shorts. Binance held 22.3% of OI but only 8.3% of liquidations.
  - [ChainCatcher](https://www.chaincatcher.com/article/2258740)
- Skanda (Odaily, 2026-04-22) [QUANT but small live sample; PROMO for HertzFlow]:
  - Definition: 「妖币」 is a token with a spot 控盘比例 ("control ratio") above about 96% and a Binance perp. Its 「操纵周期」 ("manipulation cycle") is a 20–50% pump-and-dump completed within 96 hours.
  - Data:
    - 221 non-TradFi Binance contracts listed after 2025-03-01, of which 70 were rated high or ultra-high manipulation;
    - 1,447 cycles labelled across 55 coins;
    - sources: Coinglass, the Binance API and Etherscan V2 transfers. No holder-concentration or exchange-deposit feature is used.
  - Results:
    - Predicting manipulation onset: F1 0.72 in training, about 0.1 on holdout.
    - "摸顶空" ("short the top"): the first version reached Sharpe +0.72 in backtest but did not hold out of sample; the constrained version had Sharpe −0.28.
    - "弃盘点" ("abandonment point") short: two consecutive 1H bodies close below a 5% support break, with a 3% trailing stop. Live it won about 50% with slightly negative PnL. Realistic costs then killed it: slippage often ≥2%, practical position under ~$200, order-book depth around 70K. The author also found look-ahead bias in the support calculation.
    - Final early-entry variant V4A: backtest of 166 trades with single-digit stop-outs, average loss ~1% and max drawdown −1.87%. Live it fired on ~26% of triggers with 100% wins and ~25% PnL, on a tiny sample. Median hold ~1h; about 2–3 signals a day across 70 coins. Exact thresholds are withheld.
  - [Odaily](https://www.odaily.news/zh-CN/post/5210424)

**B. Holder-concentration and "operator phase" heuristics**
- danny/agintender (Odaily, 2026-04-15) [ANECDOTAL; PROMO for a shorting vault]:
  - Do not trust Top-10 share alone. Merge wallets that have direct transfers, simultaneous buys, or gas funded from the same CEX withdrawal address.
  - Wash-trading check: 24h volume divided by holders (800 holders and $2M a day is about $2,500 per holder, a red flag).
  - Watch DEX LP adds and removals; price rising while LP depth thins means a planned exit.
  - If the top 10% of trades are more than 60% of volume, a few addresses drive the price (Gini coefficient suggested).
  - Phases from wallet-count growth against price:
    - 拉升 ("markup"): price +30% while wallets grow only +5%;
    - 出货 ("distribution", the most dangerous): flat price while wallets grow +20%;
    - 已跑 ("already exited"): price falls while the wallet count does not.
  - [Odaily](https://www.odaily.news/zh-CN/post/5210278)
- ChainCatcher's 「收割模板」 ("harvest template") narrative, MYX → AIA → COAI, cites MYX holder concentration "as high as 97%". [SNIPPET] — [ChainCatcher EN](https://www.chaincatcher.com/en/article/2216361)
- COAI: 87.9% of supply in ten wallets, followed by a fall of about 88%. A Bitget piece gives about −96%; the figures conflict. [SNIPPET] — [KuCoin news flash](https://www.kucoin.com/news/flash/coai-token-collapse-exposes-systemic-risks-in-ai-driven-defi-ecosystem)

**C. Listing-structure patterns (Binance Alpha → futures → spot)**
- PANews (Frank, via TechFlow, 2025-09-12), 335 Binance Alpha tokens [QUANT, descriptive, survivorship-prone means]:
  - Average return since listing +74.6%; average maximum gain 190%. 81 tokens (24%) halved, the worst by more than 97%.
  - 121 tokens (36%) had futures. Futures-only tokens (no spot listing, 94 tokens) averaged +230%, maximum gain 355%, and +27% over 7 days.
  - Tokens without futures averaged −1.7% over 7 days.
  - Futures + BSC + no spot + no airdrop (26 tokens) averaged +620%.
  - Airdropped Alpha tokens averaged only about +29%; 91 of 144 were down.
  - The author's reading: airdrops add cheap 筹码 and sell pressure, and 「仅上合约的代币更容易被轧空」 ("futures-only tokens are easier to short-squeeze"). He warns of overfitting.
  - [TechFlow](https://www.techflowpost.com/article/detail_28128.html)
- FMZ/MathQuant (2023-11-20) [QUANT, descriptive]:
  - Data: 2023 Binance perpetuals, 4h bars, first 150 days, equal-weight normalised path.
  - New contracts fell on average, more so the longer they traded, with no rebound within about half a year; the decline is larger relative to the market.
  - Listings clustered in bull phases (February and October 2023).
  - Suggestion: short on the first trading day. No returns, costs or funding were given.
  - [StockSharp repost](https://stocksharp.com/zh/topic/25589/unveiling-the-price-dynamics-analyzing-performance-post-listing-on-perpetual-contracts/)

**D. Token unlocks (代币解锁 / 解锁抛压)**
- Keyrock, relayed by ChainCatcher (2024-12-06) [QUANT per the originals; the relay gives no sample size]:
  - 90% of unlocks put negative pressure on price, and prices often start falling about 30 days before.
  - Team unlocks hit hardest; investors hedge; ecosystem unlocks can support price.
  - Unlocks above 5% of supply cause immediate volatility.
  - [ChainCatcher](https://www.chaincatcher.com/article/2155623)
- Other coverage of the same study:
  - CryptoSlate gives the sample as 16,000+ unlocks and says the better entry is about 14 days after an unlock. [SNIPPET] — [CryptoSlate](https://cryptoslate.com/90-of-token-unlocks-drive-prices-down-declines-begin-a-month-ahead/)
  - Tokenomist: size relative to circulating supply matters more than whether recipients are insiders. [SNIPPET] — [Tokenomist](https://tokenomist.ai/research/do-token-unlocks-crash-prices)
- Applied in Chinese case write-ups [ANECDOTAL]:
  - ZKJ had about 15.53M tokens (~$30.3M) unlocking on 2025-06-19, "partly priced in" by the crash four days earlier. — [BlockTempo 2025-06-16](https://www.blocktempo.com/binance-alpha-points-change-zkj-koge-crash/)
  - MYX released 39M tokens (3.9% of supply) near its price peak; an earlier, similar unlock was followed by −58%. — [WuBlockchain 2025-09-11](https://wublock.substack.com/p/the-myx-affair-a-deliberately-orchestrated)

**E. Airdrop dumping (空投砸盘)**
- BlockBeats (2024-05-23), via cnyes, airdrop study [QUANT]:
  - Sample: 40 airdrops up to 2023 and 2,098,698 wallets.
  - Only 10 of 40 were higher after two months; all design categories trended 10–40% lower at 60 days.
  - Broad airdrops roughly doubled the share of sellers.
  - Wallet data is DEX-only, so sellers who sent tokens to a CEX are undercounted. No causal claim is made.
  - [cnyes/BlockBeats](https://news.cnyes.com/news/id/5572315)
- Binance Alpha airdrop sell-through, BlockBeats in June 2025 citing litangdingzhen.me [QUANT, snapshot]:

  | Alpha airdrop | Accounts sold / eligible | Share sold | Profit per account |
  |---|---|---|---|
  | F | 20,180 / 29,745 | ~68% | ~$50 |
  | HOME | 13,095 / ≤32,000 | ≥41% | ~$66 |
  | CARV | 32,426 / 39,528 | ~82% | ~$57 |

  [SNIPPET] — [itiger: F](https://www.itiger.com/news/2543061717); [itiger: CARV](https://www.itiger.com/hans/news/2546212569)
- "88% of airdropped tokens lose value within 3 months" appears in Taiwanese media (2025-09-25) with no source study named. Treat it as unsourced. — [BNext](https://www.bnext.com.tw/article/89411/88-of-airdropped-tokens-lose-value-within-3-months)

**F. Team / VC / market-maker / whale exchange deposits (项目方/做市商/巨鲸 充值)**
- The only quantified test found is Presto Research, translated by Odaily (2025-01-10) [QUANT, negative]:
  - Data: BTC, ETH and SOL on Binance, 2021-01-01 to 2024-12-27; deposit thresholds $20M / $20M / $8M; entity labels from Arkham.
  - Outcome measured: maximum drawdown over 1h and 6h after the deposit.
  - Across 12 scenarios R² was 0.0017–0.0537, i.e. "extremely weak". Restricting to VC/MM deposits raised R² only slightly, possibly from noise reduction.
  - VC/MM share of whale deposits: ETH ~61%, SOL ~32%, BTC ~13%.
  - [ChainCatcher](https://www.chaincatcher.com/article/2161902)
- Market-maker economics that explain why MM deposits are ambiguous:
  - MMs commonly borrow tokens from the project for 1–2 years (the loan / call-option model). [SNIPPET] — [cnyes](https://news.cnyes.com/news/id/5559046)
  - In the retainer model the project keeps tokens in its own exchange account and the MM trades them via API. [SNIPPET] — [ChainCatcher zh-tw](https://www.chaincatcher.com/zh-tw/article/2172881)
  - Wintermute's CEO, translated by Odaily (2025-02-05), says supply rises after listing and once market-making starts. MM call-option agreements give MMs an incentive to sell above the strike. On-chain transfers are "rebalancing and cross-venue arbitrage". — [ChainCatcher](https://www.chaincatcher.com/article/2165791)

**G. On-chain perps: Hyperliquid whales as "开单指标" ("trade-entry indicator")**
- Odaily (Wenser, 2025-03-11) [ANECDOTAL]:
  - Retail treats certain Hyperliquid addresses (「内幕哥」, "insider bro") as entry signals.
  - Example: a whale deposited $1.6M about 16h before shorting BERA at $13 after listing and made ~$589K in under 2 hours.
  - No formal hit rate is given; the win rate is described only as 「高的不像话」 ("absurdly high").
  - Coinbase's Conor Grogan disputed the "insider" label for one address, saying its funds were phishing proceeds.
  - [TechFlow/Odaily](https://www.techflowpost.com/article/24180)
- A Chinese guide stresses that Hyperliquid's order book and API are public: 「数据完全链上可查」 ("all data can be checked on-chain"). [SNIPPET] — [OneKey zh-CN](https://onekey.so/blog/zh-CN/ecosystem/copy-trading-on-hyperliquid/)

#### Glossary (Chinese → English → Russian)
- 庄家 / 庄 — "the house": the market operator controlling a token (the project's market-cap team, a hired MM or a whale) → «кукловод»/оператор монеты. Also 市值管理 — market-cap management → «управление капитализацией»; 做市商 — market maker → маркетмейкер. — [ChainCatcher/Owen.btc](https://www.chaincatcher.com/article/2130706)
- 控盘 / 控盘比例 — controlling the float / share of float controlled → контроль предложения / доля под контролем. 筹码 / 筹码集中度 — "chips": supply / its concentration → распределение / концентрация монет. — [ChainCatcher RAVE](https://www.chaincatcher.com/article/2258740)
- 妖币 / 庄币 — "demon coin" / operator coin: a manipulated low-float coin with a Binance perp → «бесовская»/манипулируемая монета. 操纵周期 — manipulation cycle → цикл манипуляции. 弃盘点 — the point where the operator abandons the price → точка, где оператор бросает монету. 摸顶空 — shorting the top → шорт в вершину. — [Odaily/Skanda](https://www.odaily.news/zh-CN/post/5210424)
- 逼空 / 轧空 — short squeeze → шорт-сквиз. 拉盘 / 砸盘 — pump / dump → разгон / слив. 接盘侠 — bag holder → тот, кто покупает у оператора на вершине. 小号 — alt account → дополнительный аккаунт. — [ChainCatcher/Owen.btc](https://www.chaincatcher.com/article/2130706); [Odaily 2023](https://www.odaily.news/post/5187731)
- 吸筹 / 拉升 / 出货 / 已跑 — accumulation / markup / distribution / already exited → набор / разгон / раздача / ушёл. — [Odaily/danny](https://www.odaily.news/zh-CN/post/5210278)
- 割韭菜 / 收割 — "cutting leeks": harvesting retail → «стрижка» розницы. — [WuBlockchain/Haotian](https://wublock.substack.com/p/analysis-why-is-on-chain-data-analysis); [ChainCatcher EN](https://www.chaincatcher.com/en/article/2216361)
- 内幕巨鲸 / 内幕哥 — "insider whale" → «кит-инсайдер». 开单指标 — trade-entry indicator → сигнал на вход. — [TechFlow/Odaily](https://www.techflowpost.com/article/24180)
- Not tied to one article: 充值 / 提币 — deposit to / withdraw from an exchange → депозит / вывод; 净流入 / 净流出 — net inflow / outflow; 归集 — sweeping deposit addresses into a hot wallet → свип; 地址标签 — address label; 实体聚类 / 实体归集 — entity clustering; 女巫 — Sybil (multi-accounts); 撤池 — pulling LP → снятие ликвидности; 刷量 — volume farming / wash trading → накрутка объёма.

### Inferences
- For a bot that shorts retail pumps, the most useful Chinese content is about squeeze risk, not entry. Their consensus profile of a coin where shorts get killed:
  - spot float controlled (≥60% per Owen.btc; ≥96% per Skanda's 妖币 definition);
  - Binance perp listed, ideally futures-only with no Binance spot (PANews);
  - OI at or above circulating market cap or exchange-held float;
  - funding ≤ −0.1% per interval and worsening.

  This matches the owner's s11 finding that funding absorbs most of the short edge on expensive-to-borrow coins.
- Skanda's results fit the bot's experience: attempts to short "the top" failed out of sample, and the only surviving idea was a breakdown-confirmation short after the operator stops defending the price, with a ~1h median hold. That is a timing rule computable from candles alone.
- **Testable with free data (no API keys)**:
  - Funding history, klines and taker volume come from Binance's public endpoints; OI and long/short history from the data.binance.vision "metrics" archive (already used in s14/s17); Alpha listing times from Binance's public bapi (s18). With these the owner can test:
    - (a) squeeze-danger flags — funding below −0.1% or −0.75% per interval, OI growth ≥50%, futures/spot volume ratio, OI over market cap — as a veto on pump-shorts;
    - (b) the FMZ day-1 short on new perps, including costs and funding;
    - (c) PANews' futures-only and BSC conditions as squeeze-risk modifiers;
    - (d) Skanda's 妖币 universe, defined purely from candles (frequency of 20–50% round trips within 96h), and the "two 1H closes below a support break + 3% trail" short. The support definition has to be specified.
  - Circulating supply for OI/market cap needs a free source. Binance's public product endpoint is believed to carry a circulating-supply field, but this is unverified (see Gaps).
  - Unlock tests need a historical unlock calendar; no key-free API was confirmed (see Gaps).
- Team/MM deposit alerts are the least promising to automate. The only quantified test is negative, labels need paid or manual sources, and the cases in section 4 show deposit-to-crash lead times of days, with many deposits not followed by crashes.

### Gaps
- No Chinese source gives a hit rate or sample for "项目方向交易所充值 X% 流通量 → 下跌" ("project deposits X% of float to an exchange → price falls") on altcoins. Lookonchain's OM figure (4.5% of float) is one case.
- No Chinese quantified study of exchange net inflow or outflow for altcoins at an hours-to-weeks horizon was found. The Chinese CryptoQuant and Glassnode material is BTC/ETH-centric.
- Skanda withholds V4A's exact thresholds, so his live result cannot be replicated as published.
- No quantified Chinese study of Binance HODLer airdrop tokens after listing was found (search returned only individual cases).
- I could not verify whether Binance's public product endpoint gives circulating supply, or whether the Alpha token-list bapi gives holder concentration. alpha.json from s18 is not in the working tree, so its fields could not be checked.

## 3. How do they identify project, market-maker and exchange-deposit wallets without paid tools, and which free tools do they rely on?

### Takeaway
Chinese practitioners use standard clustering heuristics:
- addresses that appear in the same transaction, and UTXO change addresses;
- deposit-address tracing into exchange hot and cold wallets;
- common gas-funding source;
- same-block or near-simultaneous transactions, including "bundles" of launch-block buyers;
- similar CEX-withdrawal patterns and wallet creation times;
- behavioural fingerprints such as trade sizes, timing and number of tokens traded.

They mostly work through free web front-ends: explorers (BscScan/Etherscan, OKLink), Arkham's free tier, Bubblemaps V2, MetaSleuth, DeBank, GMGN, Dune and the Hyperliquid public API. Writers repeatedly stress that labels are off-chain inferences: two respected tools or analysts can cluster the same wallets correctly but attribute them to different owners (COAI, OM).

### Cited Findings
- Haotian (WuBlockchain, 2022-12-15) explains how labels are made:
  - Common-spending heuristic (multiple inputs mean one owner) and UTXO one-time-change heuristic.
  - Labels then spread through deposit-address tracing and hot/cold wallet classification.
  - Accuracy depends on how many "seed" addresses an entity uses and how often it rotates them; rotation and mixers make labels decay.
  - Labels are off-chain estimates, not facts.
  - [WuBlockchain](https://wublock.substack.com/p/analysis-why-is-on-chain-data-analysis)
- OneKey's Chinese guide (updated 2026-05-15) lists heuristics with traceability ratings:
  - 启发式聚类 ("heuristic clustering"): addresses together in one transaction;
  - 资金流图谱 ("fund-flow graph"): a path ending at a KYC withdrawal address becomes traceable;
  - 时序分析 ("timing analysis"): same block or quick succession, even through intermediaries;
  - common gas-payment address, rated 「中高」 ("medium-high");
  - DApp interaction fingerprints such as typical size and opening-time habits on Hyperliquid and dYdX;
  - CEX withdrawal to a self-custody wallet, rated 「极高」 ("extremely high"), the most direct link.
  - [OneKey zh-CN](https://onekey.so/blog/zh-CN/ecosystem/on-chain-address-tracking/)
- danny/agintender (Odaily, 2026-04-15) applies these to finding operators:
  - Use bubble maps to merge wallets with direct transfers.
  - Check whether they bought at the same time.
  - Trace gas money to a shared CEX withdrawal address.
  - [Odaily](https://www.odaily.news/zh-CN/post/5210278)
- EmberCN's COAI analysis (October 2025) shows the "which owner" step [SNIPPET]:
  - Same entity: the addresses withdrew BNB from Binance in highly similar patterns and were created at similar times.
  - Bot, not team: since July they had traded dozens of Alpha tokens daily with thousands of transactions; each traded 240+ tokens with 45k+ transactions in 30 days.
  - Bubblemaps' version of the same cluster: 60 wallets, each funded with 1 BNB from Binance around March 25, holding more than half of the top-100 COAI trader slots and about $13M profit. Bubblemaps said there was "no evidence linking the core team".
  - [ChainCatcher EN tag page](https://www.chaincatcher.com/en/tags/COA)
- RAVE (2026-04-15): the analysis splits holders into team/contract multisigs (Gnosis Safe), labelled CEX addresses and retail EOAs, and compares CEX-held spot with derivatives OI. — [ChainCatcher](https://www.chaincatcher.com/article/2258740)
- Exchange-side labels used in relays (Chinese wording):
  - 「CEX 提币地址」 ("CEX withdrawal address"): an address funded by a withdrawal from an exchange hot wallet;
  - 「团队钱包」 ("team wallet") / 「Vesting 钱包」 ("vesting wallet"): an address that received tokens from a vesting contract.
  - [BitRSS/ChainCatcher](https://bitrss.com/%E6%95%B0%E6%8D%AE-%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9F%E5%BA%84%E5%AE%B6%E8%BF%87%E5%8E%BB-24-%E5%B0%8F%E6%97%B6%E5%86%8D%E4%B9%B0%E5%85%A5%E7%BA%A6-1000-%E4%B8%87%E7%BE%8E%E5%85%83%E4%BB%A3%E5%B8%81-218547); [itiger BIO](https://www.itiger.com/news/2561265545); [itiger AIA](https://www.itiger.com/news/2605104847)
- 0xScope weights dozens of rule types in a graph algorithm. A Chinese write-up shows four seemingly unrelated EOAs merged into one 实体 ("entity"). [SNIPPET] — [ChainCatcher](https://www.chaincatcher.com/article/2085491)
- Bubblemaps:
  - Clusters are found from a common funding source or transfer pattern; bundles from same-block or seconds-after-launch buys. [SNIPPET] — [Bubblemaps blog](https://blog.bubblemaps.io/what-is-bubblemaps-the-visual-onchain-analytics-tool-explained/)
  - V2 is public and free for core features. [SNIPPET] — [itiger](https://www.itiger.com/hans/news/2539501882)
- Free and freemium tools named:
  - BscScan/Etherscan holder lists and contract verification. [SNIPPET] — [CoinGecko guide](https://www.coingecko.com/learn/bscscan-an-ultimate-guide-to-using-it)
  - OKLink multi-chain explorer. [SNIPPET] — [Alchemy listing](https://www.alchemy.com/dapps/oklink)
  - MetaSleuth fund-flow tracking. — [MetaSleuth zh](https://docs.metasleuth.io/zh_cn/yong-hu-shou-ce/tutorials/advanced-analysis-lightweight-fund-tracking)
  - Arkham free tier (basic entity search) and GMGN free interface. [SNIPPET] — [MadeOnSol](https://madeonsol.com/compare/debank-vs-gmgn)
  - Dune community dashboards. [SNIPPET] — [Dune](https://dune.com/pandajackson42/binance-alpha-20-purchase-dex-tokens-directly-on-binance-cex)
  - litangdingzhen.me for Alpha airdrop sell counts. [SNIPPET] — [itiger](https://www.itiger.com/news/2543061717)
  - Hyperliquid public order book and API. [SNIPPET] — [OneKey](https://onekey.so/blog/zh-CN/ecosystem/copy-trading-on-hyperliquid/)
- Skanda's pipeline used Etherscan V2 for historical transfers plus the Coinglass API (sponsored) and the Binance API. — [Odaily](https://www.odaily.news/zh-CN/post/5210424)
- Presto's academic-style test relied on Arkham labels plus its own research to tag VC/MM deposits. — [ChainCatcher](https://www.chaincatcher.com/article/2161902)

### Inferences
- In this literature a market maker is identified mainly by inherited labels (Arkham, or tracker naming such as "Wintermute", "Web3Port-linked") plus behaviour: two-way flows with several exchanges, transfers to MEXC/OKX/Binance right after unlocks, and many tokens traded at high frequency. Chinese writers rarely publish the address-level evidence chain, so their attributions cannot be audited from the articles alone.
- **Free-data feasibility for the owner**:
  - Without keys, the realistic path is public RPC (e.g. `eth_getLogs` on ERC-20 Transfer for a token contract taken from Binance's public Alpha list) plus a small hand-curated set of exchange hot-wallet addresses copied from free explorer labels. Deposit-address sweeps can be found because each user deposit address forwards to a known hot wallet.
  - This is engineering-heavy and rate-limited. Given Presto's negative result, it is better used as a squeeze-risk/concentration snapshot (share of supply on CEX vs in team multisigs vs OI, as in the RAVE analysis) than as a timing signal.
  - Etherscan, Arkham and Coinglass APIs all need keys; the free web front-ends are fine for manual case checks.

### Gaps
- No Chinese step-by-step guide was found on finding an exchange's deposit addresses (deposit → sweep → hot wallet) for a specific altcoin. The method is described only abstractly (Haotian) or used implicitly in tracker posts.
- A search snippet described a 「同区块」 ("same-block") heuristic: a string of addresses takes almost all supply at launch, and the small addresses that receive chips in the same block are assumed to belong to the 庄家集团 ("operator group"). The page I fetched (w3hitchhiker, 2022) carried the substance only in a video, so the heuristic's Chinese source is unverified; Bubblemaps' "bundle" feature is the documented equivalent.
- Free availability and accuracy of OKLink and Arkham entity labels for small BSC/Base tokens was not established.

## 4. Documented cases where on-chain signals preceded big altcoin pumps or dumps

### Takeaway
The best-documented Chinese-covered cases are dumps that came days to hours after visible on-chain supply events:
- team- or investor-linked wallets depositing to exchanges (OM, April 2025);
- a market maker selling right after listing (MOVE, December 2024);
- large holders pulling DEX liquidity (ZKJ/KOGE, June 2025);
- a market maker exiting several thin altcoins as Binance cut futures limits (ACT, April 2025);
- an unlock near a squeezed top (MYX, September 2025).

Pump cases (币安人生 2026, MYX 2025, RAVE 2026, LINA/ARPA/MTL 2023) are preceded by accumulation or withdrawal from exchanges into a few wallets. Shorts then get squeezed through negative funding and OI larger than the available float. Nearly all cases are ex-post narratives, several attributions are disputed, and none gives lead-time statistics.

### Cited Findings
**OM (MANTRA), April 2025 — dump preceded by exchange deposits [ALLEGATION; QUANT for the flow]**
- Lookonchain: since April 7, at least 17 wallets deposited 43.6M OM (about 4.5% of circulating supply, ~$227M) to exchanges, mainly Binance and OKX. Two were linked to investor Laser Digital, which denied it and said the wallets were not Laser's; Cointelegraph reported the Arkham labels might be wrong.
- Spot On Chain: whales sent 14.27M OM to OKX three days before the crash. [SNIPPET]
- OM fell from above $6 to below $0.50 on April 13 (UTC). Mantra blamed "reckless liquidations". [SNIPPET]
- [Cointelegraph](https://cointelegraph.com/news/mantra-om-token-collapsed-24-hours); [CoinMarketCap Academy](https://coinmarketcap.com/academy/article/mantra-token-plunges-90percent-after-dollar227-million-moved-to-exchanges-sparking-liquidity-and-insider-dumping-concerns)
- OKX said the slide started at 2025-04-14 02:28:32 (UTC+8). Based on public on-chain data and internal data, it said the token's economic model had changed significantly since October 2024, and that multiple on-chain addresses with similar operating patterns had large deposits and withdrawals across exchanges. [SNIPPET] — [ChainCatcher EN](https://www.chaincatcher.com/en/article/2177061)
- In December 2025 OKX alleged that linked accounts had borrowed USDT against OM collateral to buy more OM. [SNIPPET] — [ChainCatcher EN](https://www.chaincatcher.com/en/article/2177061)

**MOVE (Movement), December 2024 — market-maker dump after Binance listing [QUANT per Binance; ALLEGATION re: Web3Port/Rentech]**
- Binance said a market maker sold about 66M MOVE on 2024-12-10, the day after listing, with very few buys, and made about $38M USDT. Binance froze the proceeds, banned the MM, and the project pledged to compensate users.
- CoinDesk's reporting, relayed in Chinese, named Rentech, which appeared on both sides of the deal, and Web3Port-linked wallets.
- An on-chain analyst also flagged about 75,000 wallets that claimed and bundle-sold more than 60M MOVE in the December 9 airdrop.
- [SNIPPET] — [ChainCatcher](https://www.chaincatcher.com/article/2179528); [BlockTempo](https://www.blocktempo.com/behind-the-collapse-of-the-movement-token)

**ZKJ / KOGE, 2025-06-15 — liquidity pull in a points-farmed pool [ANECDOTAL; disputed attribution]**
- The setup: Binance Alpha points (volume × liquidity, plus a bonus for LPs) packed farmers into the ZKJ–KOGE PancakeSwap pool, inflating volume without real buyers.
- The sequence, as reported:
  - three addresses withdrew more than $30M of two-sided liquidity, first draining the thinner KOGE pool, then selling ZKJ and opening short hedges;
  - a wallet starting 0x364 withdrew 4.2M ZKJ and 18k KOGE from OKX and sold them.
- The result: ZKJ fell from $1.946 to $0.3767 (−80.6%) in about 2 hours, and KOGE from $61 to $8.46. Coinglass counted about $210M of liquidations that night, about 70% in ZKJ contracts.
- A ZKJ unlock of 15.53M was due June 19.
- From June 17 Binance stopped counting trades between Alpha tokens toward points.
- [BlockTempo 2025-06-16](https://www.blocktempo.com/binance-alpha-points-change-zkj-koge-crash/)
- Polyhedra blamed "abnormal on-chain trades" and Wintermute deposits; KOGE denied selling. [SNIPPET] — [Forklog](https://forklog.com/en/researchers-identify-causes-of-zkj-and-koge-crash-on-binance-alpha/)

**ACT and other thin alts, 2025-04-01 — MM exits plus Binance futures-limit cuts [ANECDOTAL; disputed]**
- On-chain data showed Wintermute clearing ACT, DEXE, HIPPO and KAVA around the crash; ACT fell as much as 55%. Wintermute said it was arbitraging an AMM price dislocation; Binance blamed one user's $1.05M ACT spot sale.
- Binance changed ACT futures three times in four days:
  - 03-28: leverage cap 25x → 10x;
  - 03-31: maximum position $9M → $4.5M;
  - 04-01 18:30: $3.5M, with forced reduction of positions above the limit.
- After that, ACT OI reportedly dropped 75% and the insurance fund lost about $2M.
- [ChainCatcher 2025-04-02](https://www.chaincatcher.com/article/2175258)

**MYX Finance, August–September 2025 — low-float squeeze, unlock at the apex [ALLEGATION]**
- Structure: under 20% of supply circulating.
- The run-up:
  - +1,132% in about 7 days, to above $17 on September 8–9;
  - perp turnover of $6–9B a day; Binance moved MYX funding to hourly; up to 50x leverage.
- The unlock: 39M MYX (3.9%) released near the peak. Afterwards Hack VC sent 835k MYX to MEXC.
- The article calls the trade "one-way" for both sides and warns of survivorship bias in the success stories.
- [WuBlockchain 2025-09-11](https://wublock.substack.com/p/the-myx-affair-a-deliberately-orchestrated)
- A Rena Labs / Insider.Cash report found 249 anomalies in 9,200+ minute-level data points. [SNIPPET] — [Cointelegraph](https://cointelegraph.com/news/myx-finance-trading-activity-market-manipulation-report)
- PANews counted MYX at 123x since its Alpha listing (as of 2025-09). — [TechFlow](https://www.techflowpost.com/article/detail_28128.html)

**COAI (ChainOpera AI), September–October 2025 — concentrated supply, then collapse [SNIPPET; attribution disputed]**
- Listed on Binance Alpha and futures on 2025-09-25 at about a $15M market cap, peaking above $8B.
- Ten wallets held 87.9% of supply, and the token later fell about 88%.
- The profitable-wallet cluster was attributed differently by Bubblemaps and EmberCN (see section 3).
- [ChainCatcher EN](https://www.chaincatcher.com/en/article/2216361); [KuCoin flash](https://www.kucoin.com/news/flash/coai-token-collapse-exposes-systemic-risks-in-ai-driven-defi-ecosystem); [ChainCatcher EN tag](https://www.chaincatcher.com/en/tags/COA)

**AIA, 2026-01-21 — team-wallet outflow right after Binance perp listing [ANECDOTAL; outcome not reported]**
- About $3.7M of AIA left a team wallet about 5 hours earlier; $778k went to a new wallet, 「或将出售」 ("may be sold").
- Price at the time was $0.255 (market cap about $51.03M). Binance had listed the AIA USDT-M perp the day before.
- [ChainCatcher via itiger](https://www.itiger.com/news/2605104847)

**币安人生, March–April 2026 — exchange withdrawals by "insider"-labelled wallets before a pump [ANECDOTAL]**
- Lookonchain: about a month before 2026-04-14, two wallets linked to the 「BTC OG 内幕巨鲸」 ("BTC OG insider whale") withdrew 59M 币安人生 from Binance at $0.074 (~$4.38M). The tokens were later worth $19.5M, more than $15M unrealised. — [ChainCatcher via itiger](https://www.itiger.com/news/2627442903)
- EmberCN reported the 「庄家」 buying about $10M in 24h (+15%), combining an on-chain buyer with a separate Binance withdrawal address. — [BitRSS/ChainCatcher](https://bitrss.com/%E6%95%B0%E6%8D%AE-%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9F%E5%BA%84%E5%AE%B6%E8%BF%87%E5%8E%BB-24-%E5%B0%8F%E6%97%B6%E5%86%8D%E4%B9%B0%E5%85%A5%E7%BA%A6-1000-%E4%B8%87%E7%BE%8E%E5%85%83%E4%BB%A3%E5%B8%81-218547)

**RAVE, April 2026 — squeeze where OI exceeded exchange float [ANECDOTAL]** (details in section 2A). — [ChainCatcher](https://www.chaincatcher.com/article/2258740)

**LINA, ARPA and MTL, May–June 2023 — squeezes with locked or held supply, deeply negative funding and OI ≈ market cap; 2–4x within 1–2 weeks [ANECDOTAL]** (details in section 2A). — [Odaily](https://www.odaily.news/post/5187731)

### Inferences
- Lead times in these cases are measured in days: OM deposits from April 7 before the April 13 crash, a 14.27M OM inflow 3 days before, and the 币安人生 withdrawal about a month before. MOVE, ZKJ/KOGE and ACT give hours or less. A 5-minute bot cannot recover these signals reliably without curated labels, and the triggering flow is visible only in hindsight.
- A recurring pattern is directly relevant to shorts: a Binance perp is listed (or Binance sets hourly funding or high leverage) on a coin whose float sits in a few wallets. The squeeze runs until an unlock or MM/team distribution, or until Binance cuts leverage or position limits, and then the coin collapses.
  - Exchange parameter-change announcements (LINA/MTL 2023, ACT 2025) are a free, public, timestamped event stream.
  - That makes them more testable than wallet flows; the owner already archives Binance announcements.

### Gaps
- No case study gives the base rate: how many comparable deposits by team, VC or MM wallets were not followed by a dump.
- MOVE's precise announcement dates and the Binance wording were seen only in search summaries.
- AIA's price outcome after the 2026-01-21 team-wallet move was not found.
- A claim that Bubblemaps called the MYX airdrop "the largest Sybil attack in crypto history" appeared only in a snippet with an unclear source and was not used.

## 5. Pitfalls, failure modes and manipulation warnings

### Takeaway
Chinese writers warn, often explicitly:
- labels are guesses and can be wrong or contested (OM/Laser Digital, COAI);
- exchange flows are confounded by internal sweeps, rebalancing, MM inventory, loan returns and hedging;
- motive cannot be read from the chain;
- the deposit → dump signal is statistically weak (Presto R² ≤ 0.054);
- trackers' alerts lag and suffer survivorship bias ("success stories");
- volume and points farming make fake activity, and operators can bait followers;
- out-of-sample decay and costs (slippage ≥2%, depth around 70K, position size ≤ $200) destroy backtests on manipulated coins;
- exchange rule changes (leverage or position-limit cuts, hourly funding) can flip a trade either way.

### Cited Findings
- **Labels are inferred, decay, and cannot show motive.**
  - Haotian (2022-12-15): exchange and entity tags are estimates; label quality depends on seed addresses and rotation.
  - Large transfers to hot or cold wallets may be internal consolidation (归集). Transfers between exchanges may be a large account withdrawing. Outflows to unknown addresses may be withdrawals or the same party reorganising.
  - Off-chain hedging is invisible on-chain.
  - [WuBlockchain](https://wublock.substack.com/p/analysis-why-is-on-chain-data-analysis)
- **Attribution disputes are common.**
  - OM: Laser Digital denied that the Lookonchain-linked wallets were its own, and Cointelegraph reported the Arkham labels might be wrong. — [Cointelegraph](https://cointelegraph.com/news/mantra-om-token-collapsed-24-hours)
  - COAI: Bubblemaps saw a single entity with "no evidence of team involvement"; EmberCN saw external quant bots. [SNIPPET] — [ChainCatcher EN tag](https://www.chaincatcher.com/en/tags/COA)
  - Hyperliquid "insider": Conor Grogan said the funds were phishing proceeds. — [TechFlow/Odaily](https://www.techflowpost.com/article/24180)
- **Deposit signals are statistically weak.** Presto (2025-01-10): R² 0.0017–0.0537 across 12 scenarios. The authors warn against vendors who oversell on-chain indicators and recommend on-chain data for fundamentals and after-the-fact explanation, not trading signals. — [ChainCatcher](https://www.chaincatcher.com/article/2161902)
- **Market-maker deposits are ambiguous.**
  - MMs hold loaned inventory (1–2 years). [SNIPPET] — [cnyes](https://news.cnyes.com/news/id/5559046)
  - Wintermute's CEO describes on-chain moves as rebalancing and cross-venue arbitrage, and says the firm has been "never net short since 2020". — [ChainCatcher 2025-02-05](https://www.chaincatcher.com/article/2165791)
  - ACT: Binance blamed a user's spot sale, not the MM. — [ChainCatcher 2025-04-02](https://www.chaincatcher.com/article/2175258)
- **Wash and points volume hides the real buy side.**
  - ZKJ/KOGE farming volume masked the absence of real bids; Binance changed its points rules from 2025-06-17. — [BlockTempo](https://www.blocktempo.com/binance-alpha-points-change-zkj-koge-crash/)
  - danny's checks: volume per holder and the share of the largest trades. — [Odaily](https://www.odaily.news/zh-CN/post/5210278)
- **Survivorship bias and one-way trades.** MYX: "most 'success stories' on display are simply survivorship bias"; the trade was one-way for longs and shorts alike, with 50x leverage and hourly funding. — [WuBlockchain](https://wublock.substack.com/p/the-myx-affair-a-deliberately-orchestrated)
- **Overfitting and costs.**
  - Skanda: manipulation-onset prediction fell from F1 0.72 to about 0.1 out of sample; the top-short reached Sharpe −0.28; an early rule with Sharpe 15+ was "suspicious" and contained look-ahead bias; slippage was often ≥2% with practical size under ~$200. — [Odaily](https://www.odaily.news/zh-CN/post/5210424)
  - PANews warns its Alpha findings may be overfit and are 「并不能作为实际的投资判断依据」 ("not a basis for real investment decisions"). — [TechFlow](https://www.techflowpost.com/article/detail_28128.html)
- **Exchange risk-control changes.**
  - Binance cut LINAUSDT and MTLUSDT parameters during the 2023 squeezes. — [Odaily](https://www.odaily.news/post/5187731)
  - ACT's three cuts in four days preceded the −55% crash, OI −75%. — [ChainCatcher](https://www.chaincatcher.com/article/2175258)
  - Owen.btc argues that widening funding bands (about ±2%) increases the operator's extraction from shorts. — [ChainCatcher](https://www.chaincatcher.com/article/2130706)
- **Spot control means futures do not reflect real demand.**
  - Because perps price off a spot index, an operator controlling spot also controls the mark price and can protect its own leveraged positions. — [ChainCatcher/Owen.btc](https://www.chaincatcher.com/article/2130706)
  - RAVE: with 96% of 筹码 in six wallets the operator 「可以随时拉盘，也可以随时砸盘」 ("can pump or dump at any moment"). — [ChainCatcher](https://www.chaincatcher.com/article/2258740)
- **Copy-trading on-chain whales has lag and slippage, the whale can reverse or exit, and "insider" is a community guess.** — [TechFlow/Odaily](https://www.techflowpost.com/article/24180); [OneKey](https://onekey.so/blog/zh-CN/ecosystem/copy-trading-on-hyperliquid/)
- **Some bots manipulate copy-traders directly.** A 2026 arXiv paper describes adversarial bots in meme-coin copy-trading that front-run, hide positions and fake sentiment to extract value from followers. This is a non-Chinese source that surfaced in Chinese-query results. [SNIPPET] — [arXiv 2601.08641](https://arxiv.org/html/2601.08641)
- **Airdrop data blind spots.** DEX-only wallet data misses transfers to a CEX, so it undercounts sellers. — [cnyes/BlockBeats](https://news.cnyes.com/news/id/5572315)
- **Unlocks are priced early.** Keyrock: declines start about 30 days before an unlock, so an event-day short is late. — [ChainCatcher](https://www.chaincatcher.com/article/2155623)
- **New listings: the gain is already in before listing.** FMZ: pre-listing rises may have captured the "listing benefit". — [StockSharp/FMZ](https://stocksharp.com/zh/topic/25589/unveiling-the-price-dynamics-analyzing-performance-post-listing-on-perpetual-contracts/)
- **Many writers sell something.** Skanda (HertzFlow), danny (youcanshortit vault), Wintermute's CEO (self-defence), and Bubblemaps and 0xScope as vendors. — [Odaily](https://www.odaily.news/zh-CN/post/5210424); [Odaily](https://www.odaily.news/zh-CN/post/5210278); [ChainCatcher](https://www.chaincatcher.com/article/2165791)

### Inferences
- For a pump-shorting bot the biggest practical risk the Chinese literature points to is not a missed on-chain dump signal. It is being the short in a 控盘 coin: concentrated float, futures-only or thin spot, OI ≥ float, negative funding, and possibly hourly funding set by Binance.
- A cheap and robust use of Chinese practice is as a veto filter, built from public Binance data:
  - funding extremes and the speed of their change;
  - OI growth and OI relative to market cap or float;
  - futures/spot volume ratio;
  - whether the coin trades on Binance spot at all;
  - recent Binance parameter-change announcements.

  Wallet-flow alerts are better kept as manual context.
- Any test should use Skanda's lessons:
  - time-split out-of-sample checks;
  - realistic slippage on thin books, ≥2% on 妖币;
  - funding paid by shorts;
  - no look-ahead in support or resistance levels.

### Gaps
- No Chinese quantified study of how often on-chain alerts (EmberCN, Ai姨, Lookonchain) are wrong or reversed was found.
- No Chinese source documented a confirmed case of operators deliberately staging on-chain moves to bait trackers. Searches returned only whales flipping positions (e.g. 「Strategy 对手盘」, the "Strategy counter-trader") with no proof of intent; the arXiv paper is the only systematic evidence and is not Chinese.
- Internal-transfer misreads are documented mainly for BTC and exchange-reserve contexts (Haotian; Binance hot/cold reshuffles). No altcoin-specific Chinese example of a sweep misread as a "project dump" was found.
