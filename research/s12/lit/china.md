# Chinese-language crypto quant ecosystem (mainland / HK / TW): extracted strategies

Prepared 2026-10-23 for the MarginData / Binance USDT-M bot.

**Scope**
- FMZ 发明者量化: forum, digest, strategy square, the official blog, and its Chinese mirror 宽客在线 quantinfo.com.
- Chinese crypto media: ChainCatcher 链捕手, TechFlow 深潮, Odaily 星球日报, PANews, MarsBit / BlockWeeks 区块周刊, 吴说 Wu Blockchain, 界面新闻, and the 新浪财经 blockchain channel.
- OKX 欧易 Academy and OKX Orbit.
- Chinese-authored GitHub research and the 邢不行 quant forum.

About 45 pages were opened. 23 entries are listed below, and some entries group several pages on one topic. The 9 entries marked ★ were read in full or across several pages.

**Conventions**
- "Known #n" refers to the confirmed results in the brief:
  - #1: weekly persistent-borrow short basket, with a −0.1%/8h funding filter and a BTC/market hedge;
  - #2: repay-surge short;
  - #3: Korean-pump short;
  - #4: TRY-spike short.
- "Rejected" refers to the brief's rejected list.
- **fund8** is funding normalised to 8 h: fund8 = f × 8 / interval_h. Binance now mixes 1 h, 4 h and 8 h settlement (see C3).
- Testability is judged against the data listed in the brief. Dates are publication dates.
- **(author claim)** marks something the author asserts without evidence. **(inference)** marks my own reasoning, which is not in the source.

---

## Ecosystem overview: what Chinese sources focus on

1. **Execution-first strategy writing.** FMZ produces the largest volume of Chinese crypto-quant writing:
   - grids;
   - spot-perp and cross-exchange funding arbitrage;
   - multi-coin hedging;
   - event bots for listings and delistings;
   - more recently, "AI workflows".

   Posts usually include code but rarely honest out-of-sample statistics. The strongest quantitative work is the 2020 multi-coin hedging series by 小草 (C1), a few 2023 data studies published under the FMZ blog account "zero" (B5, C6, C7), and the 2026 cross-sectional posts (C2–C4).
2. **庄家 / 庄币 ("whale-controlled coins").** This is the dominant derivatives theme in Chinese media. A holder of most of the spot float controls the mark price, pushes funding to the cap and squeezes perp shorts. The community's indicators are:
   - OI vs circulating cap;
   - futures/spot volume;
   - persistent negative funding;
   - Binance funding-cap and settlement-interval interventions;
   - the "Binance Alpha → Binance futures" listing path.
3. **Listing and delisting events.** Three recurring themes: new-listing decay (shorting new perps), shorting delisted perps, and the opposite case, the "delisting squeeze" (ALPACA, April 2025).
4. **Market-maker token loans plus call options.** These are the standard explanation for post-listing decay.
5. **Funding carry as arbitrage, not a factor.** Funding is treated as an arbitrage product (期现套利 spot-perp, or cross-exchange), not as a cross-sectional factor. Practitioners agree yields compressed after 2021: opening premiums fell from about 5/1000 to 1/1000 by 2022, and in 2025–26 BTC/ETH carry was "near or below T-bills".
6. **Margin borrowing.** It is discussed mostly through OKX's 杠杆多空比 (margin long/short ratio: borrowed USDT ÷ borrowed coin for a pair) as a sentiment gauge, and through anecdotes of borrow-rate shocks (OMG, 2021). **I found no Chinese source that statistically tests margin borrow/repay flows the way MarginData does.**

**Access gaps**
- **Search index and budget.** The WebSearch index is US-centric and returned thin Chinese results. The session-wide search budget then ran out mid-task, so the second half was done by direct navigation:
  - FMZ blog archive pages 1–17;
  - quantinfo.com category pages;
  - links inside articles.
- **Blocked sites:**
  - 知乎 Zhihu: HTTP 403 with a JS challenge. Several relevant columns were found but could not be read: 庄家 manipulation, funding-rate "人性的演练场", and unlocks.
  - CSDN: HTTP 521, including 邢不行's official blog and his "币圈庄家教你如何坐庄" post.
  - gitee: HTTP 503.
  - Baidu: captcha.
  - Tencent author pages: rendered by JS only.
  - WeChat originals: only mirrors were reachable.
  - 新浪: intermittently HTTP 503.
  - CNKI (知网): not reached.
- **Language note.** FMZ publishes Chinese originals (fmz.com Chinese pages and quantinfo.com) and official English translations (blog.mathquant.com and fmz.com/digest-topic). I read whichever version was reachable and give both URLs where I found them.

---

## Summary table

| # | Source (short) | Date | Theme | Testability | Novelty vs brief |
|---|---|---|---|---|---|
| A1 | OKX 杠杆多空比: Academy definition + Orbit FIL post | 2022-12 / 2026-10 | margin long/short composition | low–med | new angle |
| A2 | 界面新闻: OMG borrow-rate shock before the BOBA airdrop | 2021-11 | airdrop-driven borrowing | med | twist on Known #1/#2 |
| A3 | FMZ: funding-arb status, borrow-to-short negative-funding arb | 2022-04 | arbitrage-driven borrowing | high (as a conditioning variable) | twist on Known #1/#2 |
| A4 | Market-maker token loans (agintender, 光武, Alex, Min Jung, 区块链小猫) | 2023–2026 | MM borrowing and hedging | low | context |
| B1 ★ | Owen.btc (ChainCatcher): 庄家 controls spot → mark price | 2024-06 | controlled coins | med–high | new filter |
| B2 ★ | 熊市妖币自查手册 (MarsBit / BlockWeeks) | 2026-05 | controlled-coin checklist | high (partly) | new |
| B3 ★ | ALPACA delisting squeeze (TechFlow, ChainCatcher) | 2025-04 | delisting squeeze, funding-cap changes | high | new |
| B4 ★ | FMZ: short grid on delisted perps | 2026-05 | delisting short | high | new |
| B5 ★ | FMZ post-listing perp study + PANews, Klein Labs, Animoca listing statistics | 2023-11 – 2026-03 | new-listing decay | high | new |
| B6 | FMZ pump-fade short (@Gianbin) | 2026-03 | pump short | high | overlaps Known #3/#4 |
| B7 | MarsBit "10 minutes to spot a 庄" (danny) | 2026-04 | on-chain stage detection | low | low |
| B8 | FMZ: follow liquidation signals | 2026-03 | liquidations | low (no liquidation history) | low |
| C1 ★ | FMZ 小草 multi-coin hedge (strategy + 4-part research) | 2020-04/05 | alt/BTC cross-sectional reversion | high | medium |
| C2 ★ | FMZ 24h Roll-Out + public replication | 2026-07/09 | mechanical attention effect | high | **new** |
| C3 ★ | FMZ 牛来: momentum + funding cross-sectional composite | 2026-09 | factor composite | high | medium |
| C4 | FMZ APFF factor factory | 2026-09 | factor definitions and governance | high | medium |
| C5 ★ | CryptoOption-Research (Chinese GitHub) | 2026 | IS/OOS momentum, reversal, funding arbitrage | high | evidence on decay |
| C6 | FMZ: spread on correlation with BTC | 2023-11 | beta/correlation factor | high | new |
| C7 | FMZ: small cap vs low price | 2023-12 | size | low–med | low |
| C8 | Chinese factor-community methodology (LUCIDA, 邢不行 forum, FMZ AI factors, two GitHub repos, 未央网 LTW) | 2021–2026 | methodology | — | low |
| D1 | FMZ funding arbitrage: 2021 rules, coin-margined short, TRB cross-exchange, cross-exchange workflow | 2021–2026 | carry and arbitrage | med | low |
| E1 | 雷锋网 OKEx big data; AiCoin "resonance"; OKX K-line lesson 27 | 2019–2024 | account long/short ratio | — | rejected class |
| E2 | Unlock studies in Chinese media (translations) | 2023, 2026 | unlocks | low (no unlock data) | context |

---

## A. Margin borrowing and lending

### A1 OKX 杠杆多空比 (margin long/short ratio)

**Sources**
- 一文学会看懂交易数据, «Учимся читать торговые данные за одну статью»
  - URL: https://okx.com/cn/learn/learn-to-read-trade-data
  - Simplified Chinese; published 2022-12-06, modified 2024-04-24; OKX 欧易 Academy.
  - The same text appears in the Singapore edition, 一文学会如何看懂交易数据: https://www.okx.com/zh-hans-sg/learn/how-to-know-trading-data-cn (modified 2025-02-24).
- OKX Orbit post by 静待花开: "$FIL FIL杠杆数据：合约市场几乎全都在做多！", «Маржинальные данные FIL: на фьючерсах почти все в лонге!»
  - URL: https://www.okx.com/en-us/orbit/insight/90482426840000
  - Chinese; 2026-10-20.

**What it is**
- Definition: "该指标展示某一时刻，BTC/USDT杠杆借入计价货币（USDT）与借入标的货币（BTC）的累计数额比值。" That is, the cumulative borrowed quote (USDT) divided by the cumulative borrowed base coin for the pair.
- A low ratio means more coin is borrowed, i.e. more margin shorting. A high ratio means more margin longs.
- The Academy presents it as a sentiment gauge only. There are no thresholds and no direction rule.
- Practitioner use (the Orbit post): FIL long-side borrow was 1,904,400 FIL-equivalent against 13,400 on the short side. The author wrote "杠杆多空比大幅拉升，多头极度拥挤" (the ratio surged, longs are extremely crowded) and read it as bearish: a break of support would trigger a long-liquidation cascade.
- This is the usual contrarian reading of extremes. The post gives no outcome.

**Evidence:** a definition and one opinion post; no statistics.

**Relation to margin borrowing:** direct. The indicator measures the composition of margin borrowing: longs borrow the quote currency, shorts borrow the coin. MarginData only shows the coin-borrow side, plus any stablecoin rows the channel posts.

**Data and testability: low–medium.**
- Binance cross margin pools USDT borrowing across all coins, so a per-coin long/short split cannot be rebuilt from MarginData.
- Only a market-level version is feasible: stablecoin borrowed $ ÷ non-stablecoin borrowed $. This works only if MarginData lists USDT/USDC/FDUSD rows **(inference)**.
- Third-party API wrappers indicate OKX exposes a BTC/ETH series through its trading-data API (not verified here). Either way, it is not in our dataset.

**Novelty:** a new angle. It looks at the long/short composition of borrowing, whereas Known #1/#2 use the level and persistence of coin borrowing.

### A2 界面新闻: OMG borrow-rate shock

**Source:** 加密货币交易所币安规则朝令夕改，日内多次大幅加息OMG日化15%被指高利贷，暂停提币临时提出退空投换减息, «Binance меняет правила на ходу: за день несколько повышений ставки, OMG — 15% в сутки, «ростовщичество»; вывод приостановлен»
- URL: https://www.jiemian.com/article/6806914.html
- Chinese; 2021-11-12; 界面新闻, citing 蓝鲸财经.

**What happened** (ahead of the 1:1 Boba Network airdrop snapshot for OMG holders):
- Binance raised the OMG margin borrow rate from under 0.1% per day to 10%, then to 15% per day. That is about 5475% APR, described as "较日前上涨近20倍" (nearly 20× the prior level).
- It suspended OMG withdrawals.
- It switched OMG perpetual funding to every 2 hours.

**Why:** Binance did not require borrowers to return airdropped tokens. Borrowing and holding OMG at the snapshot therefore captured BOBA with no net price exposure. Interest refunds were offered to users who repaid before the snapshot or returned the airdrop within 48 h.

**Evidence:** an event report with no price statistics.

**Relation to margin borrowing:** direct. Borrow demand here was neither shorting nor hedging but airdrop farming. The report also shows Binance's toolkit around such events: rate hikes and a change of funding interval.

**Data and testability: medium.**
- Binance announcements (airdrop support, snapshots, HODLer Airdrops, Launchpool) can flag event windows.
- Hourly margin rates (625 assets) and MarginData (from 2025-02) show the borrow response.

**Novelty:** a twist for Known #1/#2. It suggests filtering event-driven borrow and repay surges around snapshots. It is not a standalone strategy.

### A3 FMZ: status of the funding strategy, and borrowing for negative-funding arbitrage

**Source:** "Recent Situation and Recommended Operation of Funding Rate Strategy", «Текущее положение и рекомендации по стратегии на ставке финансирования»
- URL: https://www.fmz.com/bbs-topic/9208
- FMZ's English translation of a Chinese forum post; 2022-04-08; FMZ forum (profile "Ninabadass").

**What it says** (a status update on FMZ's Binance funding arbitrage: long spot and short the perp, across many coins):
- Opening premiums fell from "generally 5/1000" to "generally 1/1000".
- Slippage rose, and rates above 100% APR had not been seen for a long time.
- Recommendations:
  - concentrate on a few high-rate coins;
  - use several venues;
  - trade extreme rates "with caution", such as the OMG airdrop case at −5.4%.
- The post notes that FTX's "spot market allows direct borrowing to short, with automatic loan repayment after a buy, which makes negative-rate arbitrage easier".

**Evidence:** practitioner observations; no statistics.

**Relation to margin borrowing:** direct. Negative-funding arbitrage means borrowing the coin on margin, selling spot and going long the perp. A borrow surge that coincides with deeply negative funding and a negative basis is therefore plausibly hedged arbitrage, not directional shorting **(inference)**.

**Data and testability: high, as a conditioning variable.** It needs MarginData borrow events, funding, and the spot/perp basis from 15-min spot and futures klines.

**Novelty:** a new twist on Known #1/#2. Our current filter only drops coins with funding below −0.1%/8h.

### A4 Market-maker token loans and call options (five pages)

**Sources**
- @agintender, 做市算法揭秘：护盘还是砸盘？做市商如何使用借币, «Алгоритмы маркет-мейкинга: поддержка или слив? Как ММ используют заёмные токены»
  - URL: https://finance.sina.com.cn/blockchain/roll/2025-07-20/doc-infhcaau4134150.shtml
  - Chinese; 2025-07-20; via 吴说, from an X post. The author labels the case study as fictional.
- 光武 (founder of Canoe), 庄家操盘往事：做市商与项目方、交易所的「爱恨情仇」, «Истории «庄家»: любовь и вражда ММ, проектов и бирж»
  - URL: https://www.odaily.news/zh-CN/post/5184536
  - Chinese; 2023-01-16; Odaily, via TechFlow.
- Alex, 做市还是做庄？解密项目方与做市商的"秘密交易", «Маркет-мейкинг или манипуляция? Тайные сделки проектов и ММ»
  - URL: https://www.techflowpost.com/article/11664
  - Chinese translation of an X post; 2023-04-06; TechFlow.
- Min Jung (Presto Research), via 吴说, on how token loans plus call options work, «Как работает схема «заём токенов + колл-опцион»»
  - URL: https://wublock123.com/articles/article-27062
  - 2024-05-13.
- 区块链小猫, 做市商暗箱操作曝光：零成本代币贷款+看涨期权，散户被收割, «Разоблачение ММ: бесплатные займы токенов и коллы, розница — под нож»
  - BlockWeeks (paragraph.com); 2026-07-28.

**What they say**
- The project lends tokens to market makers:
  - about 2–3% of supply in the examples;
  - tenor of 1–2 years;
  - typically 3–5 MMs;
  - with zero-cost calls struck 50–100% above the index for tokens not yet trading.
- The MM runs delta-neutral. Agintender's illustrative example: 3M tokens are lent and about 2.3M are sold at the open, partly to fund bids and partly to hedge; perps are shorted against the option delta, and the MM gamma-scalps ("高卖低买", sell high, buy low).
- Agintender's thesis: "做市商目前的最优解就是拿到项目方的 token 后开盘就卖掉" (the MM's current optimum is to sell the project's tokens at the open), given illiquid alts and 12–24-month contracts.
- 光武: an MM "reserve ratio" of 30–50% of circulating cap is needed for control, and exchanges give MMs unsecured loans.
- Alex: Wintermute's hedging around ARB added at least 16M tokens to supply.

**Evidence:** mechanism descriptions. ARB is a real case; the rest are illustrations.

**Relation to margin borrowing:** the borrowing is off-exchange (project → MM). It is hedged through spot sales and perp shorts, not Binance cross margin. A possible Binance footprint is perp OI and a negative basis at listing **(inference)**.

**Testability:** low directly. It supports B5 (new-listing decay).

**Novelty:** context.

---

## B. Futures positioning, controlled coins, listings and delistings

### B1 ★ Owen.btc (ChainCatcher): how a 庄家 controls spot and perp prices

**Source:** 揭秘：庄家是如何操纵现货合约价格最终收割散户, «Разоблачение: как «庄家» управляет ценой спота и перпетуала и стрижёт розницу»
- URL: https://www.chaincatcher.com/article/2130706
- Chinese; 2024-06-26; Owen.btc (@OwenJin12, formerly in trading-risk management), via 吴说 / ChainCatcher.

**Mechanism and stages**
1. Pick a coin with a small circulating cap (about 1–10M USDT) and 20–30× perps.
2. Accumulate about 60% of the float on declines.
3. Do not sell. Keep USDT to absorb the thin spot asks.
4. The mark price, built from spot, is now under control.
5. Open perp longs that cannot be liquidated.
6. Pump with little capital or wash trades.
7. Retail shorts pile in, and negative funding is paid to the whale every 8 h.

The controller has three income sources: the spot round trip, funding, and **lending out the held coins** ("将持有的币借出获取借贷收益").

**Observable signals cited**
- Futures volume about 60× spot (a Gate example).
- Price rising on declining volume, with MACD divergence.
- Spot and perp long/short skews pointing opposite ways (retail is short in perps).
- Funding such as −0.66%/8h (about −1.98%/day).
- OI above the spot circulating cap aggravates the dislocation.
- Funding caps of ±2% are common, and wider caps raise the whale's profit.
- Exchanges adjusted funding on LINA and MTL, which the author calls past pump coins.
- SRM earned about 16% in 24 h from funding in an extreme case.

**Advice:** avoid small caps with high-leverage perps, watch abnormally large |funding|, and check unlock and vesting schedules.

**Evidence:** experience-based; no data **(author claim)**.

**Relation to margin borrowing: direct and important.** The controller can be the **lender** in the margin pool, so borrowing to short such a coin means borrowing from the squeezer. High borrow utilisation in a controlled coin is then a squeeze precondition rather than an informed-short signal **(inference)**.

**Data and testability: medium–high.**
- Available: the futures/spot volume ratio (USDT-M 15-min klines vs Binance spot klines), 5-min OI, funding with its interval, and price.
- Missing: circulating market cap. Proxies (spot volume, DefiLlama wallet balances) are weak.

**Novelty:** new as a squeeze-risk filter for every short strategy. The current guard is only funding below −0.1%/8h.

### B2 ★ MarsBit / BlockWeeks: 熊市妖币自查手册 (checklist for manipulated coins)

**Source:** 熊市妖币自查手册, «Чек-лист самопроверки «монет-демонов» на медвежьем рынке»
- URL: https://blockweeks.com/view/230181 (also mirrored on paragraph.com/@blockweeks)
- Chinese; 2026-05-03; MarsBit, from threads by @tradinghoex and @0xBenniee, translated by @0xBenniee.

**Two reference patterns**
- **MYX squeeze:** accumulation from late August 2025, a month-long range that lured shorts, then $3.39 → $14.09 in one day on 2025-09-08.
- **COAI pump-and-dump:** listed in September 2025 at $0.22, perps went live on Aster on 2025-10-06, intraday all-time high of about $44–45 on 2025-10-12, almost no base.

**Checklist and thresholds**

| Item | Rule in the source |
|---|---|
| Float | Initial float of 10–20% for strongly controlled coins (MYX 9.21% at TGE, COAI 19.65%). Judge control by circulating cap, not FDV. |
| OI vs price | OI rising with price = squeeze in progress. Price falling while OI rises = exit warning. |
| Vol/OI | Normally 3–8×. Above 20× = fake volume (MYX about 24× during its squeeze). |
| Fake OI | A small venue's OI about equal to Binance's for a small cap is likely fake. Huge OI with a tiny largest liquidation ($300M OI, $50k max liquidation) is inflated. |
| Funding | Weighted funding below −0.05% across several 8 h periods = squeeze setup. Funding turning positive = exit. GWEI at +0.08% around 04-18 confirmed acceleration. |
| Order book | (bid − ask)/(bid + ask) above 0.4 for hours = accumulation. |
| Taker flow | Several consecutive hours of seller-dominant taker flow = distribution. |
| Wallets | Clusters: COAI 60 wallets funded with 1 BNB each; MYX 6 wallets with 2,240 buys; SIREN 200 wallets holding 50% of supply. |
| Venue path | A thin-spot coin with an Aster perp listed near Binance futures. Binance Alpha listing → Binance futures is the key step. |
| CEX inflows | Large inflows = exit, but can also be bait. |

**Evidence:** case studies **(author claims)**; no statistics.

**Relation to margin borrowing:** none directly. These coins are often futures-first, i.e. not borrowable on Binance margin **(inference)**.

**Data and testability**
- High for the funding, OI, Vol/OI and taker rules, and for the Alpha → futures path (from announcements).
- Low for the wallet and float items.
- The order-book rule overlaps the brief's rejected 3%-depth imbalance test.

**Novelty:** new. It defines a **lifecycle** (persistent negative funding during the squeeze, then a funding flip or OI rising into a falling price as the exit) rather than a level filter.

### B3 ★ ALPACA: the delisting squeeze (two articles)

**Sources**
- 回望羊驼：当利空成为短暂的财富密码, «Оглядываясь на «альпаку»: когда плохая новость стала мимолётным кодом к богатству»
  - URL: https://www.techflowpost.com/article/25364
  - Chinese; 2025-04-30; 深潮 TechFlow.
- 退市不跌反涨？揭开 ALPACA 背后的资本"轧空剧本", «Делистинг — а цена вверх? Разбор «сценария шорт-сквиза» ALPACA»
  - URL: https://www.chaincatcher.com/article/2178972
  - Chinese; 2025-04-27; Fairy (ChainCatcher).

**Timeline**

| Date (2025) | Event |
|---|---|
| 04-10 | ALPACA ranks 7th of 17 in Binance's vote-to-delist. |
| ~04-19 | Volume up with little price change (suspected accumulation). |
| 04-24 | Binance announces spot delisting on 05-02 and perp settlement on 04-30. Price falls 0.0329 → 0.029, then rises 195% within an hour. |
| 04-24 to ~04-27 | Price reaches 0.3477 within three days, about 12×. |
| 04-25 | Binance moves ALPACA funding to hourly settlement with a ±2% cap; a 1× short loses at least 48% per day. |
| 04-26 | ALPACA liquidations exceed BTC's, mostly shorts. |
| 04-29 | Funding cap raised to ±4%. Price then falls 0.27 → 0.067. |

Other facts:
- OI was several times the market cap, which had fallen below about $4–5M.
- Copy-trading leaders who shorted with high leverage were liquidated along with their followers.

**Evidence:** one well-documented event. The "庄家 script" is community analysis **(author claim)**.

**Relation to margin borrowing:** the spot supply was being delisted. Borrowing is not discussed. In Binance cross margin, coins being delisted lose margin borrowing earlier, so borrow availability disappears **(inference; check the announcements)**.

**Data and testability: high.** It needs announcements, funding with timestamps (interval changes show up as a change in settlement spacing), OI and klines.

**Novelty:** new. It gives a delisting-squeeze guard, and shows that a change of funding interval or cap can be used as an event marker.

### B4 ★ FMZ: short grid on Binance delisted perps

**Source:** 币安下架合约空头网格策略：从监控到自动交易 / "Shorting Binance Delisted Perpetuals: A Grid Strategy from Monitoring to Auto-Execution", «Шорт-сетка на делистингуемых перпетуалах Binance: от мониторинга до автоисполнения»
- Chinese: https://www.quantinfo.com/Article/View/2619.html
- English: https://blog.mathquant.com/2026/05/18/shorting-binance-delisted-perpetuals-a-grid-strategy-from-monitoring-to-auto-execution.html
- 2026-05-18; FMZ (author "zero").

**Rules**

| Element | Rule |
|---|---|
| Detection | Poll fapi/v1/exchangeInfo every 15 s. Trigger when a USDT perp's deliveryDate changes from the 4133404800000 placeholder to a real time. |
| Base short | Market short immediately, sized allocated capital × 50% × leverage. Per-contract allocation = balance × 80% / number of contracts. |
| Grid | 10 short cells over [0.9 P, P] using 40% of capital; 10% kept as buffer. Shift the range by 5% when it breaks. |
| Forced close | 60 min before delisting (Binance blocks new positions at T−30), by limit order 0.5% above market with up to 10 retries. |
| Recommended exits | A profit target; a rebound of 20–30% above the post-announcement low; a P&L drawdown of 30–50% from its peak. |
| Leverage | 5–10×. The author warns a 10% rebound at 10× is close to a wipe-out. |

**Observed behaviour**
- MLNUSDT lost about a third within 30 minutes.
- The largest drop comes in the first minutes, followed by choppy lower highs over several days.
- Some coins rebound for hours to a day, sometimes back to the pre-announcement level.

**Evidence:** anecdotal; no backtest.

**Relation to margin borrowing:** none directly.

**Data and testability: high.** It needs announcement timestamps, klines including delisted symbols, and funding.

**Novelty:** new. Event shorts on delistings are not in the brief.

### B5 ★ New-listing decay (FMZ study plus three listing-statistics reports)

**Sources**
- FMZ, "Price Performance After the Currency is Listed on Perpetual Contracts", «Динамика цены монеты после листинга перпетуала»
  - URL: https://blog.mathquant.com/2023/11/20/price-performance-after-the-currency-is-listed-on-perpetual-contracts.html (mirror: https://stocksharp.com/posts/m/79763)
  - English translation; 2023-11-20; FMZ (blog account "zero").
- PANews (compiled by Yuliya), 交易所"上线魔咒"调查：为什么89%的新币最终都沦为散户收割机？, «Расследование «проклятия листинга»: почему 89% новых токенов стригут розницу»
  - URL: https://www.bitget.com/zh-CN/news/detail/12560605305971
  - Chinese; 2026-03-26.
- Klein Labs, 流动性的真相：2024 交易平台上币效应研究报告, «Правда о ликвидности: эффект листинга на биржах в 2024»
  - URL: https://finance.sina.com.cn/blockchain/roll/2025-04-07/doc-inesismw5817089.shtml
  - Chinese; 2025-04-07, via 吴说.
- Animoca Digital Research via PANews, 研究：币安、OKX等五大交易所前三季度上币表现, «Листинги пяти крупнейших бирж за три квартала»
  - URL: https://blockweeks.com/article/47977
  - Chinese; 2024-11-02.
- Counterpoint: Haseeb Qureshi (Dragonfly) via 吴说 / TechFlow, 研究: 为什么代币上线币安后大幅下跌？
  - URL: https://wublock123.com/articles/article-27568
  - Chinese translation; 2024-05-26.

**FMZ method**
- Binance perp 4 h klines for 2023: 86 listings up to 2023-11-16, keeping the first 150 days after each listing.
- Each series is normalised to the first 4 h bar after listing (the opening chaos is skipped) and averaged across coins by days since listing.
- The same is repeated after dividing by the cross-coin index.

**FMZ finding**
- New contracts "almost all fall". The longer they are listed, the more they fall, with no rebound within half a year. The result also holds relative to the index.
- Suggested trade: short a fixed amount on the first day and close after some holding period, with "a high probability of making money" **(author claim)**.
- Listings cluster in bull markets.

**PANews:** 87 Binance spot listings in 2025. 89% have negative returns, and the average drawdown from listing is 71–80%. The decline is a slow bleed rather than a crash.

**Klein Labs** (10 venues, 2024; day-1/7/30 returns from the initial price, trimming 10% tails):
- Binance has the best day-7 mean and median.
- Its day-30 mean is slightly lower.
- Months differ strongly: Binance's May and September 2024 cohorts were up +87.8% and +94.9% at day 30, while April and July lost.
- Binance's share of 24 h volume after listing is 47%, rising to 53% by day 30.
- Bithumb is the only mid-tier venue still up at day 30.

**Animoca** (2024 year-to-date average return by exchange):

| Exchange | Listings | Average return |
|---|---|---|
| Binance | 44 | −27.00% |
| OKX | 47 | −27.30% |
| Bitget | 339 | −46.5% |
| KuCoin | >150 | −48.3% |
| Bybit | >150 | −50.2% |

**Haseeb (counterpoint):** the April 2024 decline was common to all new tokens, i.e. a sentiment repricing, and float did not correlate with performance.

**Relation to margin borrowing:** none directly. New listings often lack margin at first. The MM loan mechanics in A4 are the cited cause of the decay.

**Data and testability: high.**

**Novelty:** new event short. Entering at day 7 rather than at listing is my synthesis of FMZ and Klein Labs.

### B6 FMZ pump-fade short (@Gianbin)

**Source:** "Don't Panic When Coins Pump! Workflow-Powered Shorting to Catch the Pullback", «Не паникуй при пампе: шорт отката через workflow»
- URL: https://blog.mathquant.com/2026/03/13/dont-panic-when-coins-pump-workflow-powered-shorting-to-catch-the-pullback.html
- English translation of an FMZ Chinese post; 2026-03-13; strategy open-sourced by @Gianbin.

**Rules**

| Element | Rule |
|---|---|
| Scan | Every 15 min, all Binance USDT perps. Keep coins with 24 h gain above 10% (`minChange = 0.1`), top 20 by gain. |
| Hard skips | Already held; funding below −0.20%; OI below $30M; weekly drawdown above 5%; intraday drawdown above 5% (so only coins still near their highs). |
| Score | LLM score ≥ 8.0, with weights OI/MCap 3.5, K-line pattern 2.8, OI 1.5, volume 1.5, gain 0.5, funding 0.2. |
| Direction by funding | Funding ≥ −0.15% → short. Between −0.20% and −0.15% → "cautious short". |
| Sizing | Start with 50 USDT. Add 150 USDT when price is 50% above entry. Add 300 USDT when price is a further 70% above the first add. Cap 500 USDT. |
| Exits | Trailing take-profit activates at +35% unrealised and closes on a 5% giveback from the peak. The fixed stop is manual. |
| Regime | Best in ranging or bear markets; dangerous in a one-sided bull. |

**Evidence:** none.

**Data and testability: high**, except for market cap and the LLM score, which would need to be replaced by a rule.

**Novelty:** partly overlaps Known #3/#4 (pump fades). The new parts are the funding floor, the OI floor, the "still near the high" condition and the wide pyramiding.

### B7 MarsBit (danny): "10 minutes to tell whether a token has a 庄"

**Source:** 普通人如何用10分钟识别一个Token背后有庄？, «Как обычному человеку за 10 минут понять, есть ли за токеном «庄»»
- URL: https://www.bitget.com/zh-CN/news/detail/12560605350463
- Chinese; 2026-04-09; danny, via MarsBit.

**Content:** identifies the stage (accumulation / pump / distribution / gone) from account growth vs price.
- Price +30% with accounts +5% = a self-pump.
- Price flat with accounts +20% = distribution.
- 24 h volume ÷ holders, e.g. $2M across 800 holders, or about $2,500 each = wash trading.
- The top 10% of trades making up over 60% of volume = price driven by a few addresses.
- Merge linked wallets before measuring concentration.

**Testability:** low; it needs holder and on-chain data.

**Novelty:** low for us.

### B8 FMZ: following liquidation signals

**Source:** 用清算数据做量化交易：一套基于爆仓信号的 AI 自动化策略 / "Quantitative Trading with Liquidation Data", «Квант-трейдинг на данных о ликвидациях»
- URL: https://blog.mathquant.com/2026/03/18/quantitative-trading-with-liquidation-data-an-ai-automated-strategy-based-on-liquidation-signals.html
- 2026-03-18; FMZ.

**Rules:**
- Source: the Binance `!forceOrder@arr` liquidation stream.
- Size test: a z-score of the latest segment's liquidation volume against a baseline.
- Direction: if the long-liquidation share exceeds about 75%, go short; if it is below about 25%, go long. This is trend-following ("when longs get liquidated, go short").
- Confirmation from 1-min candles and the news; trailing and fallback stops.
- No thresholds or results are published.

**Testability:** low. There is no historical liquidation feed. A proxy from 5-min OI drops plus price moves would be a different signal.

**Novelty:** low.

---

## C. Cross-sectional factor research

### C1 ★ FMZ 小草: multi-coin hedge on Binance perps (strategy plus four-part research)

**Sources**
- 币安永续多币种对冲策略原版（做多超跌做空超涨）4月13日最新止损模块, «Оригинальная мультимонетная хедж-стратегия на перпетуалах Binance (лонг перепроданных, шорт перекупленных), стоп-модуль от 13 апреля»
  - URL: https://www.fmz.com/strategy/195226
  - Chinese; created 2020-04-04; 小草 (FMZ).
- Research on Binance Futures Multi-currency Hedging Strategy, Parts 1–4, «Исследование мультимонетной хедж-стратегии на фьючерсах Binance, ч. 1–4»
  - URLs: https://www.fmz.com/digest-topic/5584 , https://www.fmz.com/digest-topic/5588 , https://www.fmz.com/digest-topic/5605 , https://www.fmz.com/digest-topic/5621
  - English translations; 2020-05-09 to 05-14; FMZ (profile "善").

**Universe:** 23 Binance perps plus BTC: ETH, BCH, XRP, EOS, LTC, TRX, ETC, LINK, XLM, ADA, XMR, DASH, ZEC, XTZ, BNB, ATOM, ONT, IOTA, BAT, VET, NEO, QTUM, IOST.

**Index**
- Original: I = mean_i[(P_i/P_BTC)/(P_i0/P_BTC0)].
- Updated: I = mean_i[(P_i/P_BTC)/EMA(P_i/P_BTC)].

**Strategy 1:** short an equal-value alt basket and go long BTC for the same notional (`trade_value = 2000` per coin).

**Strategy 2 rules**

| Element | Rule |
|---|---|
| Signal | diff_i = r_i/I − 1, the coin's deviation from the index. |
| Target | target_i = −trade_value × diff_i / 0.01: short coins above the index, long coins below. Net exposure hedged with BTC. |
| Size | `trade_value` = 300 USDT per 1% of deviation on 10k capital, i.e. 3% of capital. The docs suggest 3–10%. |
| Rebalance | When \|target − current\| exceeds `Adjust_value` (≥ 40% of `trade_value`; 0.5 × `trade_value` in Part 4). Iceberg orders. |
| Caps | No new shorts when diff > 0.4 (`Max_diff`). No new longs when diff < −0.3 (`Min_diff`). |
| Equity stop | `Stop_loss = 0.8` of initial equity, raised after gains. |
| EMA α | 0.05 in the hourly backtests. 0.001 per minute live (swept over 0.0001–0.02), with the base-price update interval between 60 s and 30 min. |

**Evidence**
- **Part 1** (1 h bars, 2020-01-28 to 03-31, fees 0.05%): Strategy 1 ≈ +60% with about 20% max drawdown; Strategy 2 ≈ +100% in two months, also about 20% drawdown. The coin list was chosen after the fact (selection and survivorship bias).
- **Part 2** (EMA anchor; final equity on 10k, fees about 1.8–2.2k):

  | α | Final equity | Max drawdown |
  |---|---|---|
  | 0.01 | 21,116 | 14% |
  | 0.05 | 19,719 | 3% |
  | 0.1 | 18,735 | 1% |
  | 0.2 | 16,811 | ~0% |
  | 0.29 | 15,416 | ~0% |

- **Part 3** (stress test): a single coin trending away from the group loses 7× `trade_value` at +44% and about 6.5× at −33%. Losses accelerate on the falling side. Hence the 3% sizing, which gives about a 20% worst-case drawdown.
- **Part 4** (1-min data, 2020-02-21 to 04-15, fee 0.075%): final equity 10,271 on 10,000. Realised profit was +282 against 294 in fees, so **fees ate the edge**. α = 0.001 was best (+271 USDT). The zero-fee curve rises steadily.
- **Live:** leveraged users reported about +10% in a day, followed by a pullback after 04-13 driven by BNB's independent trend.

**Relation to margin borrowing:** none; perps only. Strategy 1, however, is short alts / long BTC, structurally the same as the Known #1 hedge.

**Data and testability: high**, with 15-min klines. The live 0.001-per-minute α corresponds to about 0.015 per 15-min bar, and the backtest's 0.05 per hour to about 0.0125.

**Novelty: medium.**
- Cross-sectional reversal itself is generic.
- The specific parts are: anchoring each alt/BTC ratio to its own EMA rather than using raw returns; deviation-proportional sizing with caps; and the documented sensitivity to fees.
- The source is from 2020, so decay is a risk.

### C2 ★ FMZ: the 24h Roll-Out effect (with the public replication)

**Sources**
- 屏幕上的 24h 涨跌幅会影响短线价格吗？——用 FMZ Rust 实现 Roll-Out TradFi 策略, «Влияет ли «изменение за 24 ч» на экране на краткосрочную цену? Стратегия Roll-Out на FMZ Rust»
  - Chinese: https://www.quantinfo.com/Article/View/2669.html (2026-08-31)
  - English: https://blog.mathquant.com/2026/09/04/can-the-displayed-24h-change-affect-short-term-prices-implementing-a-roll-out-tradfi-strategy-in-fmz-rust.html (2026-09-04)
  - FMZ ("zero").
- The replication FMZ cites: OctopusTakopi/24h-rollout-effect README, https://github.com/OctopusTakopi/24h-rollout-effect (English; data snapshot 2026-07-23).
- The origin: Robot James, "a truly idiotic crypto trade", https://robotjames.substack.com/p/a-truly-idiotic-crypto-trade (English; 2026-07-23; paywalled after the setup).

**Note:** the idea is Western; FMZ brought it into the Chinese community and moved it to TradFi perps. It is listed here because the FMZ article is how it reached the Chinese ecosystem, and because it is the most precisely specified testable rule I found.

**Mechanism:** exchange apps show a rolling 24 h % change. When a large candle from exactly 24 h ago leaves the window, the displayed number jumps even if the price does not move. If order flow reacts to that number (rankings, attention), returns become predictable.

**Crypto rule (replication):**
- Every hour, on completed 1 h candles, for each non-stablecoin USDT perp:
  - short for 1 h if the candle exactly 24 h ago was the largest positive candle of the trailing 24;
  - long if it was the largest negative candle.
- Enter at the next candle open and exit an hour later.

**Replication results** (788 perps including delisted, 2020-01-01 to 2026-07-22, data.binance.vision)

All signals, gross of costs:

| Measure | Result |
|---|---|
| Full sample | 1,165,160 signals, +4.75 bps per trade, win rate 49.9% |
| Trailing 4 years | +3.66 bps per trade |
| By year | 2020 +8.2; 2021 +10.7; 2022 +10.1; 2023 +3.5; 2024 +3.9; 2025 +4.2; 2026 +2.1 bps |
| Hourly portfolio | t = 4.2, Sharpe about 2.1 before costs |
| After costs | 10 bps taker round trip: −6.3 bps per trade. 4 bps maker round trip: −0.3 bps. |
| By trigger size | From +0.5 bps for triggers under 1% to +39 bps above 20% |
| By holding period | 1 h hold +3.7 bps; 24 h hold −7.3 bps |
| Placebo | Candle ages 1–23 average −0.21 bps. Age 24 gives +1.87 bps (clustered t = 4.2) and is the only age that survives correction. |
| Long vs short | Since 2024 "the short side carries nearly all of it". |

The "deployable subset" (short only, trigger ≥ 10%, lagged volume ≥ $1M):
- 2,241 trades over 202 days in 2026.
- +23.9 bps gross and +19.9 bps net of maker fees. Funding costs −3.5 bps, leaving about +16.4 bps.
- Exiting at 30 minutes with a 15% stop gives +22.5 bps and cuts the worst trade from −49% to −16%.
- Tail risk: maximum adverse excursion p99 is 20.4%, and 5.13% of trades would be liquidated at 10×.
- Caveat: the subset was chosen on the same 2026 window (in-sample). The edge is decaying, and capacity is about $316k.

**FMZ TradFi variant**
- Shock(h) = 100·P(t)·[1/P(t−24h+h) − 1/P(t−24h)].
- Trade the sign of Shock30 when:
  - the absolute 24 h change is at least 4%;
  - |Shock30| ≥ 0.8 pp;
  - Shock5 has the same sign;
  - the spread is no wider than 30 bps.
- Execution: post-only maker entry resting up to 90 s.
- Exits: stop −0.4%, take-profit +0.6%, maximum hold 30 min, or when Shock30 decays below 20% of its entry value.
- No results; the strategy is a prototype.

**Relation to margin borrowing:** none directly. Large green hourly candles in Known #3/#4 pump coins would create mechanical roll-off shorts 24 h later, so overlap and incremental value need checking **(inference)**.

**Data and testability: high.** 15-min klines are enough: hourly candles can be built from them, and Shock30 computed on the 15-min grid.

**Novelty: new.**

### C3 ★ FMZ 牛来: a direction-free momentum + funding cross-sectional strategy

**Source:** 牛来上了币安合约，恐高也恐低，于是我去做了一个不赌方向的策略, ««牛来» вышел на фьючерсах Binance: боюсь и покупать на хаях, и ловить дно — сделал стратегию без ставки на направление»
- Chinese: https://www.quantinfo.com/Article/View/2670.html
- English: https://blog.mathquant.com/2026/09/04/the-bull-is-now-got-listed-on-binance-futures-i-was-afraid-to-chase-highs-or-buy-lows-so-i-built-a-strategy-that-doesnt-bet-on-direction.html
- 2026-09-04; FMZ.

**Context**
- The 牛来USDT perp listed on 08-30 at 11:30.
- Day one: 57.4% amplitude, +28.7%, realised minute volatility 95.7 bps, about $400M daily volume.
- It ranked first of 612 perps on lower-wick depth and frequency.
- Directional fades failed:
  - the deep-wick reversion ratio was 0.31;
  - in a 139-day sample a grid nearly always won in flat or rising windows but only 8% of the time in large down windows;
  - funding-settlement arbitrage did not work.
- The author's conclusion: meme perps behave like momentum assets, so trade cross-sectional trend instead.

**Rules**

| Element | Rule |
|---|---|
| Structure | Market-neutral long/short across Binance USDT perps. |
| Factors | A composite of (1) price momentum and (2) funding rate ("持仓结构", position structure). |
| Funding normalisation | fund8 = fr × 8 / interval. Of 768 contracts with records, 440 settle every 4 h, 324 every 8 h and 4 every 1 h. |
| Weights | Rolling cross-sectional OLS (Fama–MacBeth) over 120 four-hour periods (about 20 days), refit every 12 h. Coefficients are shrunk by their t-statistic (full weight if \|t\| ≥ 2) and normalised so that \|w1\| + \|w2\| = 1. |
| Portfolio | Long the top names and short the bottom (example: 10 + 10), inverse-volatility weights, portfolio volatility targeting. |
| Risk | Cross margin, at most 3× leverage. Flatten everything if long and short notionals differ by more than 8%. |

**Results** (author backtest, in-sample, short sample)

Daily return by rotation period:

| Rotation | Return, bps/day |
|---|---|
| 5 min | −579 |
| 1 h | −41.6 |
| 2 h | +34.5 |
| 4 h | +103.8 |
| 12 h | +118.0 |

- 4 h detail: per-period median +12.23 bps, mean +17.30, win rate 53%, n = 249 periods (about 41 days).
- 24 h rotation: median −22.62, mean +151.45 (n = 41). The author rejected it as driven by a few big wins.
- Inverse-volatility weighting raised the median from 36.5 to 68.0 bps and the win rate from 53% to 57%. The worst period improved from −2021 to −1422 bps.
- The author notes that factor signs flip when the universe or window changes.

**Relation to margin borrowing:** none.

**Data and testability: high.** It needs 15-min klines and funding with its settlement interval.

**Novelty: medium.** Momentum and funding carry are generic. The specific points are:
- funding treated as a positioning factor whose sign is estimated from the data;
- a sweet spot at 4–12 h rotation;
- explicit normalisation of the settlement interval.

### C4 FMZ APFF: an adaptive factor factory for perpetuals

**Source:** 让因子接受持续考核：在 FMZ 实现 APFF 多品种永续合约策略, «Пусть факторы проходят постоянную аттестацию: мульти-активная перпетуальная стратегия APFF на FMZ»
- Chinese: https://www.quantinfo.com/Article/View/2672.html
- English: https://blog.mathquant.com/2026/09/09/put-factors-under-continuous-evaluation-implementing-the-apff-multi-asset-perpetual-strategy-on-fmz.html
- 2026-09-09; FMZ ("zero"); version v0.1.0.

**Factor seeds** (each starts with a 20% budget)

| Factor | Definition |
|---|---|
| MOM_ex | (RET_7D − RET_4H) / RV_7D, over 42 four-hour bars, skipping the latest |
| REV | −RET_4H / RV_24H |
| FUND | −Z_TS(funding normalised to its interval), over about 30 days |
| PREM | −Z_TS(premium) |
| OIC | sign(price move) × Z_TS(24 h Δlog OI notional) |

**Evaluation**
- Forward samples are recorded at each 8 h decision and mature 8 h later.
- Rank IC is shrunk by n/(n+60). Returns are cost-adjusted long/short.
- Promotion from OBSERVING to TRIAL needs at least 180 samples; TRIAL to ACTIVE needs 90 more, stability ≥ 0.75 and P(positive) ≥ 0.90.
- Weekly reweighting with 70/30 smoothing and at most ±5 pp per update.
- A factor goes DORMANT when both its mean IC and its mean net return are negative over the last 90 samples.

**Universe:** 30 Binance USDT perps ranked by 24 h volume, listed at least 90 days, kept while they stay in the top 40; BTC is the hedge.

**Portfolio**
- Top and bottom ~20%, at most 6 names per side.
- Weight ∝ max(0.05, |α|) / RV_7D, capped at 8% per symbol; gross exposure 60%.
- BTC hedge when estimated β exposure exceeds 2% of equity.
- Cost assumption 4 bps one-way.
- Drawdown scaling: 100% budget below 4% drawdown, 70% at 4–7%, 40% at 7–10%, zero at 10% or more.

**Evidence:** none; only synthetic validation. The author writes that "long-term return performance still requires further out-of-sample evidence".

**Relation to margin borrowing:** none.

**Data and testability: high.** The premium factor needs spot vs perp klines or premium-index klines.

**Novelty: medium.** The precise definitions are useful for building our own factor tests, and the OI-confirmation factor is not in the brief.

### C5 ★ CryptoOption-Research (Chinese GitHub)

**Source:** CryptoOption-Research — 加密货币期权与永续合约多时间维度量化策略研究, «Исследование мульти-таймфреймовых квант-стратегий на криптоопционах и перпетуалах»
- URL: https://github.com/3099404236/CryptoOption-Research
- Chinese README; 2026 (data to 2026-10); GitHub user 3099404236; course research.

**Cross-sectional test setup**
- 20 Binance USDT-M coins.
- Every Monday, rank by past L-day return; long the top 20% and short the bottom 20%, equal notional.
- In-sample 2020-07 to 2023; out-of-sample 2024-01 to 2026-10.

| Lookback L | Momentum IS → OOS | Reversal IS → OOS |
|---|---|---|
| 7 days | +6.3% → +7.1% | −23.7% → −20.5% |
| 14 days | +6.6% → −6.4% | −22.8% → −6.5% |
| 28 days | +29.5% → −21.0% | −34.5% → +12.1% |
| 56 days | +41.8% → −15.2% | −44.0% → +5.7% |

- Long-only top 20% with a 56-day lookback: +99.6% → −5.7%.
- Equal-weight buy-and-hold: in-sample +91.9%, out-of-sample +2.1%.
- Units are period returns as given in the README summary; annualisation is not stated.
- The author acknowledges survivorship bias: the pool is today's large coins.

**Funding arbitrage** (long spot, short perp, 1.2× capital)
- BTC, always on: +7.1%/yr (drawdown 3.3%) in-sample → +5.2%/yr out-of-sample.
- A "7-day average funding > 0" filter does not help out-of-sample: BTC +4.0%, ETH +1.7%.
- 2025–26 returns are "near or below T-bills".

**Trend (CTA) on BTC/ETH:** in-sample Sharpe about 2 → out-of-sample about 0. Example: BTC 1 h, 28-day momentum went from +71.9% / Sharpe 2.13 to +3.8% / −0.02. The median out-of-sample Sharpe across 50 variants is about 0.

**Second-scale tests (Deribit):** momentum after jumps loses 11–12.5 bps per trade; basis reversion loses about 11 bps.

**Takeaway:** the long-horizon crypto momentum of Liu–Tsyvinski–Wu "directly failed" out-of-sample in 2024–26. Reversal at 28–56 days turned positive out-of-sample. Only 7-day momentum held up.

**Relation to margin borrowing:** none.

**Data and testability: high.** We can rerun it on our 869 symbols including delisted ones, which removes the survivorship bias.

**Novelty:** evidence on decay. It supports short lookbacks (7 days or less) and multi-week reversal.

### C6 FMZ: spread on correlation with BTC

**Source:** "The Correlation Between the Rise and Fall of Currencies and Bitcoin", «Корреляция роста и падения монет с биткоином»
- URL: https://blog.mathquant.com/2023/11/17/the-correlation-between-the-rise-and-fall-of-currencies-and-bitcoin.html
- English translation; 2023-11-17; FMZ ("zero").

**Method**
- 144 Binance USDT perps listed by 2023-01-01; 4 h klines from 2023-01-01 to 2023-11-16.
- Pearson correlation of each normalised price series with BTC.
- Long the 40 most correlated coins and short the 40 least correlated.

**Result**
- Highly correlated coins rose more, and the low-correlation short leg "played a good hedging role". No figures are given.
- The author acknowledges look-ahead bias. In a split-sample check (correlation from the first 1500 bars, returns afterwards) the "conclusion [was] unchanged".

**Relation to margin borrowing:** none directly. Idiosyncratic, low-correlation names plausibly overlap with controlled coins and persistently borrowed coins **(inference)**.

**Data and testability: high.**

**Novelty:** a new factor for us (beta/correlation).

### C7 FMZ: low market cap vs low price

**Source:** "Which is More Suitable for Bottom Fishing, Low Market Value or Low Price?", «Что лучше для ловли дна: низкая капитализация или низкая цена?»
- URL: https://blog.mathquant.com/2023/12/04/which-is-more-suitable-for-bottom-fishing-low-market-value-or-low-price.html
- 2023-12-04; FMZ ("zero").

**Method**
- 205 Binance perps matched to the CoinMarketCap top 1000, with cap computed on total supply.
- Weekly rebalancing (every 42 × 4 h bars) of equal-weight groups: the 20 lowest-priced coins and the 10 lowest-cap coins, against an equal-weight index of all coins.

**Result:** low price performed about like the market. Small caps "far exceeded" the index in 2023. No figures are given.

**Data and testability:** low–medium. There is no market-cap data in our set; quote volume could serve as a proxy.

**Novelty:** low (a size factor).

### C8 Methodology from the Chinese factor community (weak evidence)

**LUCIDA (& FALCON):** the series 如何利用多因子策略构建强大的加密资产投资组合, «Как построить сильный крипто-портфель на многофакторной стратегии»
- Parts read: Odaily 因子合成篇, https://www.odaily.news/post/5192981 (2024-02-06), and ChainCatcher 因子正交化篇, https://www.chaincatcher.com/article/2113868 (2024-02-08).
- Content: MAD winsorisation (crypto data is fat-tailed), selection by ICIR, Ledoit-Wolf shrinkage, PCA and orthogonalisation; daily frequency.
- No factor results appear in the text.

**邢不行 quant forum (量化小论坛):** post by Sancky, 精华帖分享｜小白从零开始研究自己的因子, «Лучший пост: новичок с нуля исследует свой фактор»
- URL: https://news.qq.com/rain/a/20250424A06T4J00
- Chinese; 2025-04-24 (posted to the forum 2025-04-13).
- The author took one of 191 A-share price-volume factors and applied it to crypto coin selection on hourly data (6 days = 144 bars).
- Shorter holding periods looked best before costs. With fees, the high-turnover hourly version "归零" (went to zero).
- Excluding the top 10% of coins by volume changed nothing. The author suggests moving to 4 h bars.
- Lesson: hourly cross-sectional crypto factors die on fees.

**FMZ (ianzeng123):** 多因子策略不是大厂专属：独立quant的研究框架, «Многофакторные стратегии — не только для крупных фирм»
- URL: https://www.quantinfo.com/Article/View/2613.html
- 2026-04-01.
- Factors generated by an LLM on the top 150 perps by volume, filtered by Rank IC ≥ 0.02.
- Early IC was 0.04–0.07 and decayed to about 0.008, or below zero, within weeks.

**GitHub, wangCy021005/binance_strategy**
- URL: https://github.com/wangCy021005/binance_strategy
- Chinese README; © 2026.
- Claims momentum IC of +0.05 on Binance vs −0.02 in A-shares, a funding short threshold of 0.1%, and "Sharpe 0.7, 16%/yr" **(author claim; no evidence shown)**.

**未央网 translation of Liu–Tsyvinski–Wu:** 数字货币如何定价？有哪些常见的风险因子？
- URL: https://www.weiyangx.com/395784.html
- Findings: the size spread is about 5.8% per week; short-horizon momentum is significant; 60–100-week momentum is not (weekly data, 2014–2020, CoinMarketCap).
- This is a pre-perp-era benchmark that C5 shows has decayed.

**Novelty:** low. Useful mainly as a caution about fees and decay.

---

## D. Funding carry and arbitrage

### D1 FMZ funding-arbitrage family (four posts)

**币安永续资金费率套利（牛市年化100%） / "Binance Perpetual Funding Rate Arbitrage (100% of Annualized Rate in Bull Market)"**
- URL: https://www.fmz.com/bbs-topic/9276
- English repost (2022-04-25) of a 2021 FMZ strategy.
- Rules:
  - long spot, short the perp at 2×, across at least 30 symbols at once;
  - enter when historical funding exceeds a threshold (not specified); avoid new coins;
  - exit when funding falls below −0.2%, when it becomes too low, or when a symbol spikes.
- Returns: average funding above 0.15%/8h in March 2021 gives 0.45% per day, about 164% gross. The author estimates "≈100%" in a bull market and "≈20%" otherwise **(author estimates)**. The worst funding seen was −0.75%.

**"Quantitative Implementation of Currency-Based Short-Selling Fee Arbitrage Strategy"**
- URL: https://blog.mathquant.com/2025/02/07/quantitative-implementation-of-currency-based-short-selling-fee-arbitrage-strategy.html
- 2025-02-07.
- A 1× short of the coin-margined BTCUSD perp, which preserves the cash value.
- Binance BTC_USD funding accumulated about +50% over five years from 2020. Coin-margined BNB funding accumulated negative.

**TRB cross-exchange funding:** "Mastering Everything – Introduction to FMZ New Version of Trading Terminal (with TRB Arbitrage Source Code)"
- URL: https://blog.mathquant.com/2024/01/05/mastering-everything-introduction-to-fmz-new-version-of-trading-terminal-with-trb-arbitrage-source-code.html
- 2024-01-05.
- During the TRB squeeze, Binance funding was −2% per 4 h against OKX at −1.5% per 8 h. Long Binance / short OKX gave a theoretical carry of about 7.5% per day.
- The price spread narrowed from about 50 to under 10 USDT. Reported profit was about 5,000U.

**"Funding Rate Arbitrage Strategy: Automated Implementation with AI and Workflows"**
- URL: https://blog.mathquant.com/2026/02/26/funding-rate-arbitrage-strategy-automated-implementation-with-ai-and-workflows.html
- 2026-02-26.
- A cross-exchange perp funding spread (Binance / Hyperliquid / Lighter), traded only if:
  - the 8 h rate spread exceeds 0.3 × the spread's range;
  - each venue has at least $100k of 24 h volume and a bid-ask spread of no more than 0.3%;
  - the round-trip cost is below 2 × the rate spread.

**Relation to margin borrowing:** a reverse cash-and-carry would need margin borrowing. These strategies mostly avoid it, using perp-perp legs or a long spot leg.

**Data and testability:** medium. We only have single-venue data, so the cross-exchange legs cannot be tested.

**Novelty:** low. Chinese practice treats funding as arbitrage, not as a cross-sectional factor (C3 is the exception).

---

## E. Rejected class and context

### E1 Account long/short ratios (all in the brief's rejected class)

**雷锋网 via 阿里云创业:** OKEx合约大数据——巧用基差和多空比，玩转比特币合约, «Big data по контрактам OKEx: как использовать базис и long/short»
- URL: https://startup.aliyun.com/info/1041722.html
- Chinese; 2019-11-04; author 木子.
- Before the BTC crash of 2019-09-24, the account long/short ratio was at least 1.8 (peaking at 1.96). Advice: "当多空比数值异常，最好选择空仓观望" (when the ratio is abnormal, stay flat).
- Basis is defined as perp minus index.

**AiCoin:** 即将新高，如何巧妙利用共振信号, «Скоро новый максимум: как использовать сигналы резонанса»
- URL: https://www.aicoin.com/article/424440.html
- Chinese; around 2024-10.
- A "resonance" of OKX and Binance account long/short ratios; a ratio below 1 is read as whales being long.
- Claims a "恐怖的100%" (terrifying 100%) win rate **(author claim; no sample)**.

**OKX Academy:** 零基础学K线丨27 常用分析指标9—欧易交易大数据指标
- URL: https://www.okx.com/zh-hans/learn/zero-based-bitcoin-analysis-indicators-9-okex-trading-big-data-indicators-cn
- 2022-12-06.
- The account long/short ratio's correlation with price flips sign by timeframe: negative on 1 h, positive on 4 h.
- The "elite" (top-account) net-position indicator is mostly negatively correlated with price.
- Two or more consecutive periods of taker buys above taker sells are read as inflow. This was rejected in the brief.

**OKX Academy, Singapore edition (A1 page):** an OI/volume quadrant reading with no data:
- OI and volume both rising = a trend is starting;
- both falling = the trend is ending;
- volume falling while OI rises = "大行情爆发的前兆" (a precursor to a big move);
- volume rising while OI falls = late-stage profit taking.

**Novelty:** none. Everything here is in the brief's rejected class (top-trader or global long/short), except the OI/volume quadrant, which is a qualitative folk rule.

### E2 Unlock studies in Chinese media (translations)

**6th Man Ventures via TechFlow:** 代币解锁如何影响价格？基于5000个项目的大数据分析
- URL: https://www.techflowpost.com/article/11809
- 2023-05-04.
- Unlocks above 1% of circulating supply show a negative correlation with price.
- The median falls a further 5% after the unlock; the strongest correlation, −18%, is at 15 days after.
- Drops of up to 20% occur before large unlocks.

**新浪财经** (an AI-generated digest): 代币解锁警报核心指向解锁前抛售主体
- URL: https://finance.sina.com.cn/stock/usstock/summary/2026-07-01/doc-inifhvwy3077366.shtml
- 2026-07-01.
- Cites three studies:
  - Keyrock (16,000 events): drawdowns are concentrated in the 30 days before the unlock.
  - Tokenomist (236 events, 2024-06 to 2026-03): the effect is concentrated in early, thin-float tokens and mostly priced in before the date.
  - A Hong Kong Polytechnic University (香港理工大学) paper by 金学 (2026-04; 52 unlocks of Binance-listed tokens, 2023–25): the effect depends on liquidity, market regime and unlock size relative to float. I could not locate this paper.

**Relation to margin borrowing:** no source described pre-unlock hedging by borrowing (解锁前借币对冲) with data. Such hedging would show up as borrow growth before the unlock and a repay surge right after it, which fits Known #2 but is untested **(inference)**.

**Data and testability:** low. Our dataset has no unlock calendar; one could be added from Tokenomist or CoinMarketCap.

**Novelty:** context.

### Other FMZ items read (low value)
- "Exploration of Counter-Trend Short-Term Mean Reversion Strategy" (2025-06-27): 5-min bars; go long when ATR(14) > 2 × SMA20(ATR) and close < SMA20; exit when ATR falls back to its mean, stop 3%, take-profit 6%, pyramiding 5. No results.
- 币圈稳定暴富法？从知乎热帖到实战回测的真相 (https://www.quantinfo.com/Article/View/2603.html, 2026-01-27): a debunk of a viral Zhihu BTC/ETH pair trade (when BTC rises 2%, long BTC / short ETH). The FMZ backtest from October 2025 to January 2026 returned +2.2%, with 6 take-profits and 14 stop-losses (30% win rate).
- AI workflow for new Binance perp listings (2026-03-24): stop 10%, take-profit 25%, trailing stop from +30% with an 8% giveback; the entry is abandoned if the pullback target is not hit within 2 h. No statistics.
- Basket stat-arb on TradFi perps (2026-08-26): no results.

---

## Cross-cutting observations for implementation

1. **Normalise funding.** 440 of 768 Binance USDT perps settle every 4 h, 324 every 8 h and 4 hourly (C3), so always use fund8. Treat a change in settlement spacing (8 h → 4 h → 1 h) as an event: Binance shortens the interval when funding pins at the cap (B3; also OMG in A2).
2. **Squeeze lifecycle.** Sources B1–B3 agree:
   - deep negative funding that persists, with OI rising alongside price, means a squeeze is running;
   - the exit is marked by funding flipping positive, OI rising while price falls, or an exchange change of cap or interval (ALPACA: the cap went to ±4%, then the price fell 75%).
3. **Who lends.** Controlled coins are often thin-spot or futures-first (Alpha → futures). On coins that are borrowable on Binance margin, the risk is that the lender is the controller (B1).
4. **Fees dominate.** Every Chinese test that reported costs found minute- or hourly-frequency cross-sectional signals dying on taker fees: C1 Part 4, C3 at 5 min and 1 h, the 邢不行 forum post in C8, and the C2 replication at taker fees. In practice the floor is 4–12 h rotation or maker execution.
5. **Decay.** Long-horizon momentum failed out-of-sample in 2024–26 (C5), and funding carry yields compressed (A3, C5, D1). Prefer short lookbacks and walk-forward evaluation only.

---

## Top ideas to backtest

All rules use Binance USDT-M data from 2024-10 to 2026-10, including delisted symbols. Report:
- results net of 4 bps (maker) and 10 bps (taker) round trips, plus actual funding;
- results by quarter;
- maximum adverse excursion;
- overlap with Known #1–#4.

### H1 Short the 24 h roll-off (sources: C2)
- **Universe:** all USDT perps, excluding stablecoin bases. Require lagged 24 h quote volume of at least $1M (sum of the prior 24 hourly bars).
- **Bars:** hourly candles built from 15-min klines on UTC hour boundaries.
- **Entry:** at the open of hour t, look at the completed candles c(t−24) … c(t−1). If c(t−24) has the highest return of the 24 and that return is at least +10%, short at the open of t.
- **Exit:** baseline after 30 min, i.e. at the close of the second 15-min bar. Variants: 15, 45 and 60 min. Stop at 15% adverse, checked against the 15-min high.
- **Mirror long:** if c(t−24) has the most negative return and it is −10% or worse, go long. Report separately; it is expected to be weak since 2024.
- **Checks:**
  - placebo with candle ages 23 and 25;
  - results by year;
  - incremental value vs Known #3/#4 pump events;
  - whether the edge is larger on coins present in MarginData.
- **Benchmarks from the source:** +23.9 bps gross (+19.9 net of maker fees) per trade on the in-sample 2026 subset; +4.75 bps gross across all signals in the full sample, and decaying.

### H2 Split margin-borrow signals by funding and basis, and filter event-driven borrowing (sources: A1, A2, A3, B1)
- **Base signals:**
  - the Known #1 weekly top-10 persistent-borrow basket;
  - the Known #2 repay-surge shorts;
  - MarginData from 2025-02 onwards.
- **Classify each coin-week or event** using the trailing 24 h mean of fund8 and the mean spot-perp basis b = P_perp/P_spot − 1 (from 15-min closes):

  | Class | Condition |
  |---|---|
  | ARB (borrowing likely funds reverse cash-and-carry) | fund8 ≤ −0.03% and b ≤ −0.10% |
  | DIRECTIONAL | fund8 ≥ 0 and b ≥ −0.05% |
  | MIXED | everything else |

- **Hypothesis:** DIRECTIONAL names have more negative forward returns (7 days for the basket, 24–72 h for events) than ARB names, and ARB names have fatter right tails (squeezes). If this holds, replace the hard −0.1% exclusion with "short DIRECTIONAL and MIXED only".
- **Event filter:** drop names that have any Binance announcement matching airdrop / snapshot / HODLer Airdrops / Launchpool / Megadrop / token swap / redenomination / migration in [t−7 d, t+3 d]. Compare Sharpe with and without the filter.
- **Optional overlay** (OKX-style margin long/short at market level): R_t = stablecoin borrowed $ over 24 h ÷ non-stablecoin borrowed $ over 24 h, if MarginData carries stablecoin rows. Test whether R in the top decile of its 90-day history predicts a negative next-7-day return for the long BTC/market hedge leg.

### H3 The negative-funding squeeze lifecycle (sources: B1, B2, B3)
- **Universe:** all USDT perps. Flag whether each coin has Binance spot or is futures-only.
- **SETUP** at settlement s:
  - fund8 ≤ −0.05% for at least 3 consecutive 8 h-equivalent settlements;
  - OI change over 24 h ≥ +20%;
  - price change over 24 h ≥ +10%.

  Extra flags:
  - the settlement interval was shortened in the last 72 h;
  - the perp/spot 24 h quote-volume ratio is at least 10;
  - 24 h volume ÷ OI is at least 20.
- **Test A, an avoid-short filter:** measure forward returns 24 h, 72 h and 7 days after SETUP. If the mean is positive or the right tail is extreme, block all bot shorts on that coin (Known #1–#4, H1, H4, H5) until an exit trigger fires. Also report what share of our historical short losses occurred in SETUP regimes.
- **Test B, the dump short:** after a SETUP, short at the first of these:
  1. a settlement with fund8 ≥ 0;
  2. a 4 h price change below −5% while the 4 h OI change is positive (the B2 exit warning);
  3. a widening of the funding cap, i.e. |funding| above the previous cap.

  Hold 72 h, with a stop at entry × 1.3. Hedge with BTC.

### H4 Short delistings with a squeeze guard (sources: B3, B4)
- **Events:** Binance announcements of USDT-M perp delisting or settlement, and spot delistings of coins that have perps. T0 = announcement time, Td = perp settlement time.
- **Entry:** short the perp at the close of the first 15-min bar after T0 (variant A), or at T0 + 1 h, skipping the initial dump (variant B).
- **Exit:**
  - Td − 60 min;
  - stop if the price exceeds 1.25 × the post-T0 low (the FMZ 20–30% rebound rule);
  - emergency exit if settlement moves to every 4 h or more often with fund8 ≤ −0.5%.
- **Guard: skip the event if any of these holds at T0:**
  - mean fund8 ≤ −0.05% over the prior 3 settlements;
  - OI ÷ 24 h spot quote volume above the 90th percentile across all events;
  - 7-day volume up at least 2× while the absolute 7-day return is below 10% (pre-announcement accumulation, as with ALPACA).
- **Compare** guarded vs unguarded returns and maximum adverse excursion per event.

### H5 Short the decay of new perp listings (sources: B5, A4)
- **Events:** every new Binance USDT-M perp listing (the first kline).
- **Entry variants:**
  - A (FMZ): short at the open of the second 4 h bar after listing;
  - B (Klein Labs): short at the day-7 close;
  - C: short at the day-30 close.
- **Hedge:** equal notional long an equal-weight market basket, or BTC.
- **Hold:** 30, 60 or 90 days, ending early at delisting. Stop at +100% (variant: no stop).
- **Skip** if fund8 ≤ −0.1% at entry (consistent with Known #1).
- **Split** futures-first listings (no Binance spot at listing; Alpha-tagged where announcements show it) from spot-listed ones.
- **Portfolio:** equal weight across live positions, rebalanced weekly. Report funding paid and received.

### H6 Cross-sectional reversion on alt/BTC ratios anchored to their own EMA (source: C1)
- **Universe:** the top 30 USDT perps by trailing 30-day volume, listed at least 90 days, refreshed monthly. BTC is the numeraire and the hedge.
- **On each 15-min bar:**
  - x_i = P_i / P_BTC;
  - b_i ← α·x_i + (1 − α)·b_i, with α ∈ {0.005, 0.0125, 0.03};
  - r_i = x_i / b_i; I = mean(r_i); d_i = r_i / I − 1.
- **Target notional:** −K·d_i / 0.01, with K = 3% of equity.
  - Freeze adds when d_i > +0.40 on the short side or d_i < −0.30 on the long side.
  - Trade only if |target − current| > 0.5 K.
  - Hedge net delta with the BTC perp. Equity stop at 80%.
- **Costs:** 4–5 bps per side plus funding. Report by year.
- **Benchmark:** C1's Strategy 1 (a static short alt basket against long BTC), as a check on the Known #1 hedge.

### H7 Momentum + funding composite, 4 h vs 12 h rotation (sources: C3, C4, C5)
- **Universe:** the 40 most liquid perps by trailing 30-day quote volume, listed at least 90 days. BTC is excluded and used as the hedge.
- **Factors**, computed every 4 h:

  | Factor | Definition |
  |---|---|
  | MOM | (RET_7D − RET_4H) / RV_7D |
  | FUND | trailing 24 h mean of fund8 |
  | OIC (optional) | sign(RET_24H) · z_ts(Δlog OI over 24 h, 30-day window) |
  | BORROW (optional) | MarginData persistence score |

- **Weights:** rolling 120-period cross-sectional regressions of next-4 h returns on cross-sectional z-scores. Multiply each coefficient by min(1, |t|/2) and normalise. Refit every 12 h using only past data (walk-forward).
- **Portfolio:**
  - long the top 10 and short the bottom 10 by composite, with weights ∝ 1/RV_7D;
  - gross exposure up to 200% (at most 3× leverage);
  - BTC beta hedge when |β·exposure| exceeds 2% of equity;
  - costs 4 bps per side.
- **Compare** 4 h, 12 h and 24 h rotation, and report out-of-sample only.
- **Key question:** does BORROW add anything after MOM and FUND, i.e. is Known #1 a repackaged momentum/funding effect?

### H8 Spread on correlation with BTC (source: C6)
- **Schedule:** weekly, Monday 00:00 UTC.
- **Universe:** all perps with at least 60 days of history and 30-day average volume of at least $5M per day.
- **Signal:** ρ_i = correlation of coin i's 4 h returns with BTC over the prior 30 days.
- **Portfolio:** long the top quintile by ρ and short the bottom quintile, equal notional, held one week. Net of costs and funding.
- **Interactions:**
  - double-sort with MarginData persistence to see whether the low-ρ, persistently borrowed names drive Known #1;
  - check whether low-ρ shorts have a higher squeeze incidence (links to H3).
