# Kazakhstan / Central-Asian / CIS crypto-quant literature scan

Scan date: 2026-10-23. Prepared for the MarginData short-bot team (Binance USDT-M futures).

**Scope note.** I found very few substantive Kazakhstan or Central-Asian quant sources. Kazakh-language trading content was effectively absent. So I widened the scan, as the brief allowed, to Russian-language CIS sources widely read in Kazakhstan (Habr, smart-lab, vc.ru, Teletype, ForkLog, EXMON, SecurityLab) and to Russian and Ukrainian academics (HSE Moscow, Sumy State University). Every entry carries one of these labels:

- **[KZ]**: Kazakhstan media, institution or author.
- **[CIS-prac]**: CIS practitioner blog or post.
- **[CIS-media]**: CIS crypto media or vendor.
- **[RU/UA-acad]**: academic paper.

**Testability scale.**

- **High**: can be run on our dataset as it is.
- **Medium**: needs a proxy or a small extra dataset.
- **Low**: needs data we do not have, such as P2P history, liquidations, L2 order books, on-chain wallet labels, or tick data.

Sources actually read: about 40 pages and PDFs. 33 of them are the source entries below; the rest were scanned and found unusable (end of section 2, and the cross-reference in section 4). I read 8 deeply: AC-1 to AC-4, CIS-1, CIS-2, CIS-4 and CIS-8, plus a close read of CIS-9 and KZ-1. Pages I found but could not read are listed in section 4 and are not cited for content.

---

## 0. Key findings

1. **No margin-borrow analytics in this ecosystem.** Apart from CryptoCode, whose work was excluded, no Kazakhstan or CIS source I read uses Binance margin borrow/repay volumes, borrow rates, utilization or the margin long/short ratio as a signal. Margin appears only as leverage mechanics or beginner education. The MarginData approach looks unique among Russian-language sources.
2. **What Kazakh media and institutions focus on:**
   - regulation (AIFC/AFSA, National Bank of Kazakhstan);
   - legal fiat on-ramps (Binance KZ, Bybit KZ, ATAIX) and the P2P premium of USDT over the tenge;
   - the state crypto reserve (Alem Crypto Fund);
   - market-neutral funds sold to wealthy clients;
   - weekly recaps of Western analytics (ETF flows, open interest, funding).

   I found no original Kazakh quant research with rules and numbers.
3. **What CIS practitioners focus on:** funding-rate arbitrage (cross-exchange and spot–perp), pump screeners, listing and Launchpool trading, and high-frequency lead-lag. Quality is mostly low: single trades and no costs. Two posts are honest and quantitative: CIS-1 (288k strategies tested with realistic fills) and CIS-2 (a capitulation-volume rule with a trade list).
4. **The most rigorous material is academic.** Dobrynskaya (momentum/reversal and downside beta), Caporale & Plastun (momentum after abnormal days) and Volodin & Spiridonov (pairs stat-arb) all use 2014–2020 CoinMarketCap or Bitfinex data. They need re-testing on 2024–26 Binance perps.
5. **Recurring testable themes:**
   - price up while open interest falls, read as short covering (the futures analog of our confirmed repay-surge short);
   - post-listing decay of new tokens;
   - momentum over 1–2 weeks and reversal over 1–2 months;
   - rebounds after volume-capitulation days;
   - squeezes in "zombie" legacy tokens with extreme negative funding.
6. **Two risk notes for a hedged short book:**
   - **The long-BTC hedge pays funding.** On Binance this was about 3.4% a year over the trailing 12 months and 6.7% annualized in June–September 2026. That is roughly 0.07–0.13% a week, worth checking against the +0.9% a week basket result (CIS-5).
   - **Auto-deleveraging (ADL) can force-close profitable shorts in liquidation cascades** (CIS-16).

---

## 1. Kazakhstan sources [KZ]

### KZ-1. Forbes Kazakhstan: «Как состоятельному инвестору зарабатывать на крипторынке» (How a wealthy investor can earn in the crypto market)

| Field | Detail |
|---|---|
| URL | https://forbes.kz/articles/kak-sostoyatelnomu-investoru-zarabatyvat-na-kriptorynke-edb664 |
| Language, date | Russian, 2026-06-08 |
| Author | Rafael Nagapetyants, Doctor of Economics, senior partner at Movchan's Group. The piece promotes the CARF crypto fund-of-funds, launched April 2026 with a $100k minimum. |
| Strategy | A market-neutral sleeve: (a) cross-exchange arbitrage; (b) basis trade, long spot plus short perp to earn funding; (c) DeFi stablecoin lending against 1.5–3× collateral; (d) MEV. No entry or exit rules, thresholds or holding periods are given. |
| Claimed evidence | Model portfolio of such funds: 13.7% average annual return, max drawdown under 3%, worst month no worse than −1% in 2020 and 2022. Correlation with BTC is 0.18 in BTC declines and 0.35 in rises. The method is "on request"; the period and fees are not disclosed. This is marketing. |
| Margin-borrow link | None. The lending is DeFi collateral lending. |
| Testability | Basis-trade leg: High (Binance spot, perp and funding history). Other legs: Low. |
| Novelty | Low. Useful as a realistic benchmark: institutional market-neutral crypto returns about 14% a year with a small drawdown (see Idea 8). |

### KZ-2. Kursiv Research: «Ставка против навеса: как не дать керри-трейдерам все уронить» (The rate versus the overhang: how not to let carry traders crash everything)

| Field | Detail |
|---|---|
| URL | https://kz.kursiv.media/2026-10-14/dmnn-stavka-protiv-navesa-kak-ne-dat-kerri-treyderam-vse-uronit/ |
| Language, date | Russian, 2026-10-14 |
| Author | Sergey Domnin, Kursiv |
| Content | Macro article, not crypto. It describes a tenge carry trade: foreign holdings of Kazakh government securities rose from $2.4bn to $5.6bn (Sep 2025–Aug 2026), and their share from 4.8% to 7.9%. The TONIA–SOFR spread is 12.5–14.5 percentage points. USD/KZT went from 540.74 to 464.55, about 14% tenge appreciation. An ARDL model gives +$60m a month of foreign inflow per +1 pp of spread and −$14m per +1 VIX point. The author warns of a "sudden stop" and cites Turkey in March 2021 (lira −15% in one day) and Egypt in 2022 (about −60%). Next NBK rate decision: 2026-10-23. |
| Crypto link | None in the article. My inference: a tenge sudden stop would raise local USDT demand and the P2P premium (KZ-3). That is the tenge analog of our confirmed Turkish-lira spike result, but not measurable on Binance global. |
| Testability | Low. There is no tenge pair or P2P history in our data. |
| Novelty | Kazakh regime context only. |

### KZ-3. profinance.kz: «P2P курс USDT/KZT — купить и продать криптовалюту 2026» (P2P USDT/KZT rate)

| Field | Detail |
|---|---|
| URL | https://profinance.kz/crypto/p2p |
| Language, date | Russian. Live aggregator, read 2026-10-23 ("updated 4 minutes ago"). |
| Content | Official USD/KZT (NBK) 447.94. Binance Kazakhstan P2P: buy USDT at 464.25 (+3.6% over the official rate), sell at 454.05 (+1.4%), buy/sell spread 2.2%. Bybit KZ: buy at 457.80 (+2.2%). Payment rails: Kaspi, Halyk, Alatau City Bank. |
| Strategy | None. The page documents a persistent USDT premium of about 1.4–3.6% over the official tenge rate. |
| Margin-borrow link | None. |
| Testability | Low. No historical P2P data. |
| Novelty | A Kazakhstan-specific level, not a signal. |

### KZ-4. crypto.ru: «P2P в Казахстане — арбитраж криптовалют, сервисы по обмену, торговля на бирже» (P2P in Kazakhstan: crypto arbitrage, exchange services, trading)

| Field | Detail |
|---|---|
| URL | https://crypto.ru/p2p-v-kazakhstane/ |
| Language, date | Russian, 2026 (undated, © 2026) |
| Author | Unsigned; editor-in-chief Vlad Krylov listed. Russian site about Kazakhstan. |
| Content | P2P arbitrage cycle: buy on one P2P desk, sell on another. A cycle of 0.5% or more counts as "successful"; up to 5% is "rare". Venues: Binance KZ, Bybit KZ, ATAIX Eurasia. Legal points: the AFSA P2P regime has applied since March 2024; criminal liability applies above 2,000 MRP of income (MRP = 3,932 KZT); unlicensed P2P is illegal. |
| Margin-borrow link | None. |
| Testability | Low. |
| Novelty | None for the bot; background context. |

### KZ-5. Digital Business: «Казахстан запустил первый государственный крипторезерв» (Kazakhstan launched its first state crypto reserve)

| Field | Detail |
|---|---|
| URL | https://digitalbusiness.kz/2025-09-29/kazahstan-zapustil-perviy-gosudarstvenniy-kriptorezerv/ |
| Language, date | Russian, 2025-09-29 |
| Content | Alem Crypto Fund was created by the Ministry of AI and Digital Development, is managed by Qazaqstan Venture Group and is registered in the AIFC. Its first purchase was BNB, bought with Binance Kazakhstan. Size, amount and exact trade date are not given. |
| Strategy | None. A one-off state flow event. |
| Margin-borrow link | None. |
| Testability | Low (n = 1, BNB only). |
| Novelty | A Kazakh state-flow event, not a strategy. |

### KZ-6. Forbes Kazakhstan: «В чем особенность бессрочных фьючерсов на криптовалюту» (What is special about perpetual crypto futures)

| Field | Detail |
|---|---|
| URL | https://forbes.kz/articles/v-chem-osobennost-bessrochnyh-fyuchersov-na-kriptovalyutu-16ab53 |
| Language, date | Russian, 2024-08-25 |
| Author | Ksenia Kuznetsova, KPMG CCA |
| Content | IFRS-9 classification of perps; funding every 1, 4 or 8 hours; Binance BTC perp volume about $200bn a week in H1 2024. |
| Strategy | None. |
| Margin-borrow link | None. |
| Testability | Not applicable. |
| Novelty | None. |

### KZ-7. Kapital.kz: «Биткоин затормозил у максимумов: что остановило сентябрьское ралли» (Bitcoin stalled near its highs: what stopped the September rally)

| Field | Detail |
|---|---|
| URL | https://kapital.kz/finance/153647/bitkoin-zatormozil-u-maksimumov-chto-ostanovilo-sentyabrskoe-ralli.html |
| Language, date | Russian, 2026-10-01 |
| Author | Dmitry Chepelev, Kapital.kz |
| Content | Weekly recap: BTC futures open interest 644k BTC (lowest since 4 March), funding back positive, ETF flows (+$769m over 9 sessions), negative Coinbase premium, Fear & Greed 71. Quotes 10x Research, CryptoQuant and Bitget Wallet. The author reads the OI decline as deleveraging. |
| Strategy | No rules. It shows what Kazakh financial media track. |
| Margin-borrow link | None. |
| Testability | Not applicable. |
| Novelty | None. |

### KZ-8. Profit.kz: «Едиге Давлетгалиев: от ботов до ICO» (Edige Davletgaliev: from bots to ICOs)

| Field | Detail |
|---|---|
| URL | https://profit.kz/articles/11330/Edige-Davletgaliev-ot-botov-do-ICO/ |
| Language, date | Russian, 2017-08-04 |
| Author | Interview by Aleksandr Galiev with a Kazakh student developer. |
| Content | An early crypto-exchange arbitrage bot ("quite successful", no numbers). A wallet-monitoring anecdote: 66,000 BTC moved from a dormant wallet linked to BTC-e about 4 hours before BTC-e went offline, and BTC fell from about $2,800 to $2,300. |
| Margin-borrow link | None. |
| Testability | Low. On-chain inflow/outflow signals are already rejected in our tests. |
| Novelty | None. |

### KZ-9. Freedom Finance Global (on-air.ffin.kz): «ТОП-3 стратегии торговли криптовалютой в 2025 году» (Top 3 crypto trading strategies in 2025)

| Field | Detail |
|---|---|
| URL | https://on-air.ffin.kz/crypto-top |
| Language, date | Russian, 2025. Webinar landing page. |
| Content | No strategy content; claims "+6000%" on a best options trade. Included only to document that Freedom Broker's public crypto material is education and marketing. |
| Margin-borrow link | None. |
| Testability | Not applicable. |
| Novelty | None. |

---

## 2. CIS practitioner and media sources (Russian-language, widely read in Kazakhstan)

### CIS-1 [CIS-prac]. smart-lab: «Проверил 288 тысяч стратегий на криптобиржах: почему почти все проигрывают комиссиям» (I checked 288 thousand strategies on crypto exchanges: why almost all lose to fees). Read deeply.

| Field | Detail |
|---|---|
| URL | https://smart-lab.ru/blog/1362320.php |
| Language, date | Russian, 2026-10-13 |
| Author | r2d2 (ziscode blog), author of spreadlab.tech. The post promotes the service but is self-critical. |
| Data | 11 large coins (BTC, ETH, SOL, XRP, DOGE, BNB, ADA, LINK, AVAX, SUI, LTC). Spot and futures on Bybit, Binance and MEXC (66 markets). Best prices and volumes every 0.1 s. About 288k variants per recalculation: momentum, pullback, lagging-market catch-up and cross-exchange gaps; 6 timeframes from seconds to 1 h; exits by time, limit or trailing stop. |
| Execution model | 350 ms latency. Fill at the worst price inside the exchange's update gap. A limit exit counts only if price trades through it. Taker and maker fees on both sides. Paper trading must reproduce the historical trades. |

**Results**

- **Lead-lag:** Binance and Bybit futures lead; MEXC follows about 0.2 s later (spot about 0.1 s). A 3-second direction forecast was right in 57–74% of out-of-sample cases, but the edge was about +0.006% against a 0.05–0.07% round-trip fee, so it is untradable.
- **BTC leads altcoins:** alts move about +0.02% over the next 30 s. Statistically significant, but below the fee.
- **Funding:** a screener's "OGN +0.72%/day" shrank to about 0.15% once payment windows were aligned (MEXC pays every 4 h, Bybit every 8 h). RSR's +0.66%/day flipped sign. Stable edges of 0.1–0.2% a day exist, recovering fees in 1–3 days, but the first 3 paper positions lost after fees and spread.
- **What survived:** pullbacks and impulses on 1 h and 10–15 min futures, +0.2–0.5% per trade after fees, 45–65% win rate. None of 860 ideas passed on 35 hours of data; 10–20 passed on 14 days.
- **Overfitting example:** the first autopilot made 88 trades in a day, +$0.02 before fees and −$10.37 after.

| Field | Detail |
|---|---|
| Validation protocol | An idea must be profitable on the selection data and on each half of the validation data; rank by the weaker half; at least 15 validation trades; 90% confidence. Commenters suggested Bonferroni or Benjamini–Hochberg corrections, White's Reality Check and the deflated Sharpe ratio. |
| Margin-borrow link | None. |
| Testability | Lead-lag: Low (needs tick data). Funding-window alignment: a must-apply lesson for any funding test (High relevance). Pullback/impulse rules: too vague (Low–Medium). |
| Novelty | Methodological. It confirms that BTC→alt lead-lag is not tradable at our resolution and gives a good anti-overfitting checklist for the other analyst. |

### CIS-2 [CIS-prac]. smart-lab: «Простейшая закономерность на рынке способна принести 100% прибыли. Пишем ботов для крипторынка.» (The simplest market pattern can bring 100% profit: writing bots for crypto). Read deeply.

| Field | Detail |
|---|---|
| URL | https://smart-lab.ru/blog/1231817.php |
| Language, date | Russian, 2025-11-18 |
| Author | Roman Akumov ("crypto_maniac") |
| Rule | A "capitulation" day: the daily candle closes below its open and its volume is at least 2× the average volume of the previous 60 daily candles. Go long at the next day's open (00:00 UTC) and exit at that day's close (24 h). |

**Evidence** (Binance futures daily data, about 2,500 bars or roughly 6.8 years per the code; the text says 5 years):

| Market | Trades | Win rate | Total return (simple sum) | Max drawdown | Fees |
|---|---|---|---|---|---|
| ETHUSDT | 60 | ~60% | +94.6% | ~20% | Not included |
| BTCUSDT | 63 (41 wins / 22 losses) | ~65% | +84.3% | ~10% | Not included |

The author estimates fees at about 0.1% per trade. There is no significance test. Commenters asked whether 59 or 61 days, or 3–4× volume, would change the result; the author did not test it. A live bot trades BTCUSDT on BingX.

| Field | Detail |
|---|---|
| Margin-borrow link | None directly. As a guard it matters for shorts: do not short into a capitulation rebound. |
| Testability | High. Daily bars from our 15-min klines; extend to all perps; add fees and funding. |
| Novelty | New to us. Volume-capitulation reversal is not in either list (Idea 4). |

### CIS-3 [CIS-prac]. Habr: «Что такое фандинг арбитраж и как сделать автоматический поиск спредов» (What funding arbitrage is and how to automate the spread search) and «Арбитраж ставок финансирования — создаём скрипт для отслеживания возможностей» (Funding-rate arbitrage: building a script to track opportunities)

| Field | Detail |
|---|---|
| URL | https://habr.com/ru/articles/983154/ and https://habr.com/ru/articles/965072/ |
| Language, date | Russian, 2026-01-06 and 2025-11-10 |
| Author | negrbluad, who promotes the @Fandyng_Bot Telegram bot. |
| Cross-exchange rule (983154) | Long on the exchange with negative funding, short on the one with positive funding, equal size. Profit = (F_short − F_long) − fees. Filters: USDT/USDC perps only; \|F\| ≥ 0.002%; spread ≥ 0.01% by default, 0.03% for "fat" setups; both exchanges must pay at the same hour. Open 5–10 minutes before the funding time and close both legs after the payment. Leverage 1–3x. The scanner covers 10 CEXs plus Hyperliquid every 60 s. |
| Spot–perp rule (965072) | Rank all perps by funding minus twice the maker fee, take the top 20, and skip coins already up "hundreds of %". |
| Evidence | One trade (MEXC −0.25% vs Bitget +0.0035%): +$400 net after $112 of fees. No backtest. A reader found bugs in the code. |
| Margin-borrow link | None. |
| Testability | Cross-exchange: Low (we have Binance only). A Binance-only "funding snipe" (open shortly before funding, close after): Medium–High, because funding history plus 15-min klines can test price drift around funding timestamps. |
| Novelty | Low. The "skip coins that already pumped" filter is a squeeze-risk guard. |

### CIS-4 [CIS-prac]. Teletype: «АРБИТРАЖ ФАНДИНГА» (Funding arbitrage). Read deeply.

| Field | Detail |
|---|---|
| URL | https://teletype.in/@f_vspm/X0XeRKRws4T |
| Language, date | Russian. Dated 22 April, year not shown; the venues it names (Extended, Variational, Ethereal, Hibachi) imply 2025–26. |
| Author | VSPM, who promotes a parser (apparatura.xyz) and a paid channel. |

**Rules**

- **Structure:** delta-neutral, either across two exchanges or spot plus perp.
- **Stable variant:** spreads of 20–60% APR, held a week or more.
- **Spike variant:** 100% to several thousand % APR, held hours to days, typically during volatility spikes.
- **Entry and exit:** enter only when the long leg is priced below the short leg (a favourable entry basis) and exit when that inverts. Use limit orders in $250–500 steps.
- **Sizing:** at most 1/3 of the portfolio per structure (about $30k in the example); about $200k is the practical portfolio ceiling.
- **Risk limits:** portfolio leverage 1.5–2x, margin usage at most 60%, 5–6 positions at a time, checks at 00/08/16 UTC.
- **Liquidity filters:** volume, open interest (OI) and book depth. Heuristic: "a large gap between OI and volume can indicate market makers farming funding".

| Field | Detail |
|---|---|
| Evidence | Claimed 40–60% a year, unverified. Anecdote: a RAVE pump spread averaged about 2,500% APR. |
| Margin-borrow link | None. Futures margin only. |
| Testability | Binance spot–perp carry: High. Cross-exchange: Low. The OI/volume heuristic: Medium (we have OI and volume), for example to flag coins whose funding is "manufactured". |
| Novelty | The sizing and entry-basis rules, and the OI/volume heuristic, are new to us (Idea 8). |

### CIS-5 [CIS-prac]. smart-lab: «Кредитное плечо стоит денег, даже когда цена стоит на месте: 7 715 выплат финансирования по биткоину на Binance…» (Leverage costs money even when price stands still: 7,715 BTC funding payments on Binance)

| Field | Detail |
|---|---|
| URL | https://smart-lab.ru/blog/1359344.php |
| Language, date | Russian, 2026-10-06 |
| Author | IQSF |

**Statistics** (BTCUSDT funding on Binance since September 2019):

- A constant $100k long would have paid $81,420 in funding, about 81% of the position over 7 years, with no trades.
- The 2021 average cost was 30.6% a year, and 92.7% of 2021 payments were paid by longs.
- The base rate of 0.01% per 8 h (10.95% a year) applied in 35.2% of payments.
- Extremes: maximum 0.249% (8 Feb 2021); the +0.3% cap was hit on 12 Feb 2020 and the −0.3% floor on 13 Mar 2020.
- 28 Jun – 24 Sep 2026, annualized long cost: Binance 6.7%, Bybit 5.0%, Bitget 5.2%. Trailing 12 months: Binance 3.39%, Bybit 2.83%. All three stayed at or below the base rate that summer.

| Field | Detail |
|---|---|
| Strategy | None predictive. |
| Margin-borrow link | None. |
| Testability | Descriptive (we hold the full funding history). Use it as the cost baseline for the long-BTC hedge leg of our short basket: about 0.07–0.13% a week at current rates. |
| Novelty | None. A cost reminder. |

### CIS-6 [CIS-prac]. Teletype: «Рекомендации по работе с PUMP SCREENER для Binance & ByBit» (How to work with a pump screener for Binance and Bybit)

| Field | Detail |
|---|---|
| URL | https://teletype.in/@tradingdiary/CbfT957fJ7u |
| Language, date | Russian, 2025-02-03 |
| Author | Aleksandr "Prostoy Sanya" (@tradingdiary) |

**Rules**

- The screener flags price rises of 0.1–100% within 1–30 minutes.
- Small, early pumps (0.5% in 1 min, 1% in 2 min): long.
- Large, fast pumps (2% in 1 min, 3% in 3 min): short.
- Confirm with rising volume and rising open interest ("an excellent confirmation of a pump").
- Enter early when the coin was flat before. Check the 15m/1h chart and avoid entries at local highs. If the long was missed, consider a short.
- Exit on the 1-minute MACD histogram fading.

| Field | Detail |
|---|---|
| Evidence | None (screenshots only). |
| Margin-borrow link | None. |
| Testability | Medium. 1-minute data is not available; 15-min klines plus 5-min OI can approximate it. |
| Novelty | Low. It overlaps our pump-short work. Its "OI rising confirms the pump" against ATAS's "OI falling means short covering" (CIS-7) gives a testable split (Idea 1). |

### CIS-7 [CIS-media]. ATAS blog: «Стратегии торговли криптовалютными фьючерсами» (Crypto futures trading strategies)

| Field | Detail |
|---|---|
| URL | https://atas.net/ru/blog/crypto-futures-trading-strategies/ |
| Language, date | Russian, 2026-07-31 |
| Author | ATAS Team. ATAS is an order-flow software vendor with CIS roots; the text says it is for product familiarization. |

**Rules** (qualitative, no thresholds):

- Price up and OI up: new money, a stronger trend.
- Price up and OI down: mass closing of short positions, i.e. short covering.
- Extreme positive funding: excessive optimism. Negative funding: panic.
- Liquidation clusters are "fuel" for cascades.
- Heavy market buying with stalled price means a limit seller is absorbing demand, which often precedes a local reversal.
- Do cash-and-carry when funding is "too high".

| Field | Detail |
|---|---|
| Evidence | None. |
| Margin-borrow link | None directly. The OI-falling rally is the futures analog of a spot-margin repay surge. |
| Testability | OI/price divergence: High (5-min OI and 15-min klines). Absorption: Low; it is also the same idea as our rejected "big taker buys that don't move price". |
| Novelty | The OI-divergence split is new to us (Idea 1). |

### CIS-8 [CIS-media]. EXMON Academy: «Мертвые протоколы: обзор заброшенных криптопроектов и ММ» (Dead protocols: abandoned crypto projects and market makers). Read deeply.

| Field | Detail |
|---|---|
| URL | https://academy.exmon.pro/ru/mertvye-protokoly-obzor-zabrosennyx-kriptoproektov-i-mm |
| Language, date | Russian, 2026-08-22 |
| Author | "Astra EXMON", the editorial voice of EXMON. |

**Claims**

- "Zombie" tokens have no developer activity and little on-chain activity, and exchange deposits come from only 2–3 addresses.
- Market makers (MMs) keep them alive under liquidity-provision agreements: an option to buy below market plus a monthly retainer, with a 0.2–0.5% spread and at least $10–50k of depth per side. If the project has no money, exchange maker rebates pay instead.
- One of the signs: perp funding sits at extreme levels for days, for example −0.75% every 4 h. Three of five signs make a token a "zombie".
- An MM may accumulate 70–80% of the float. Examples: XVG +300% in 2 days; LUNC burn news gave 40–70% moves that reversed. Shorts above 3x leverage are called near-certain liquidation.
- Named tokens: SNT, XVG, FTT, ELF, BTS, LUNC, OMG, REV, SRM, WTC, NEBL, PPC, NMC, QTUM, GAS, STRAX, ARK, STEEM.

| Field | Detail |
|---|---|
| Evidence | Anecdotal; the figures are unsourced. |
| Margin-borrow link | Indirect. These legacy coins are likely regulars in the margin-borrow lists (my inference, to check against MarginData). |
| Testability | Medium–High: funding history, listing age, volume, and Monitoring Tag dates from Binance announcements. |
| Novelty | It frames squeeze risk for shorts in legacy tokens, beyond our existing funding < −0.1%/8h exclusion (Idea 5). |

### CIS-9 [CIS-prac]. Sergey Tereshkin: «Резкое падение мемкоинов после листинга на Binance: почему это происходит?» (Why memecoins crash after a Binance listing)

| Field | Detail |
|---|---|
| URL | https://sergeytereshkin.ru/publications/rezkoe-padenie-memkoinov-posle-listinga-na-binance-pochemu-eto-proiskhodit |
| Language, date | Russian, 2025-02-07 |

**Data table** (drop after Binance listing; days after listing):

| Token | Drop | Days |
|---|---|---|
| ZEREBRO | −94.4% | 32 |
| SWARMS | −93.1% | 27 |
| "A ALCH" (as printed) | −91.4% | 27 |
| AVAAI | −85.9% | 15 |
| MELANIA | −89.6% | 14 |
| BIO | −87.3% | 31 |
| TRUMP | −80.5% | 15 |
| SONIC | −75.8% | 26 |
| SOLV | −80.7% | 17 |
| ANIME | −74.8% | 11 |

The method is not stated (no listing dates or base prices) and the sample looks hand-picked. Explanations given: holders take profits after listing, weak fundamentals, bots selling in the first minutes, concentrated holdings. There is no short rule; the advice is "don't buy right after listing".

| Field | Detail |
|---|---|
| Margin-borrow link | None. |
| Testability | High (announcements plus klines, including delisted symbols). |
| Novelty | Supports Idea 2. Post-listing decay is not in our lists. |

### CIS-10 [CIS-prac]. Teletype: «стратегия действий после листинга» (What to do after a listing)

| Field | Detail |
|---|---|
| URL | https://teletype.in/@grassinside/b4aywJO1tN7 |
| Language, date | Russian, 2025-05-23 |
| Author | GrassInside |
| Stage table | 0–5 min: hyper-pump, then a sell-off. 5–60 min: a dip of −20 to −40%. 1–7 days: sideways or volatile. 2–6 weeks: a second rise on news or listings. |
| Holder rules | Sell 20–30% in the first 5–10 minutes if price is above 2–3× and liquidity is $0.5–1M. Re-buy up to 20% after a 15–25% drop from the peak with RSI below 30, rising 1h volume and a bullish candle. |
| Evidence | None. |
| Margin-borrow link | None. |
| Testability | Medium. The first-hour pattern needs 1-minute data; 15-min bars give a coarse view. |
| Novelty | Supports Idea 2's choice of entry time (after the first day). |

### CIS-11 [CIS-prac]. vc.ru: «Ловим иксы на листинге: стратегии торговли на Binance Launchpool и Launchpad» (Catching multiples at listing: Binance Launchpool and Launchpad strategies)

| Field | Detail |
|---|---|
| URL | https://vc.ru/crypto/1932903-strategii-torgovli-na-binance-launchpool-i-launchpad |
| Language, date | Russian, 2025-04-18 |
| Author | Yuri Yartsev (SLOTH WAY) |
| Claims | Price often drops up to −40% in the first 5–10 minutes and then rebounds. Sell farmed tokens immediately to avoid a −50% drop. No statistics; promotional. |
| Margin-borrow link | None. |
| Testability | Medium. |
| Novelty | Low. |

### CIS-12 [CIS-media]. ForkLog: «У DWF Labs нашли сомнительные сделки минимум на $65 млн» (Questionable DWF Labs deals worth at least $65m found)

| Field | Detail |
|---|---|
| URL | https://forklog.com/news/u-dwf-labs-nashli-somnitelnye-sdelki-minimum-na-65-mln |
| Language, date | Russian, 2023-04-12 |
| Author | Lena Jess |
| Content | The on-chain researcher Nay says DWF Labs bought tokens (many deals at a 10–20% OTC discount) and then deposited nearly all of them on centralized exchanges; at least $65m was confirmed. SSV, SNX, TIME and FLOKI fell 10–40% after DWF's first exchange deposits, some more than 90%. DWF's Andrei Grachev replied. |
| Margin-borrow link | None. This is about market-maker token flows (priority 2). |
| Testability | Low. It needs wallet-level on-chain labels; our DefiLlama Binance balances are aggregate. |
| Novelty | An event class: market-maker OTC-discount purchase, then exchange deposit, then a dump. |

### CIS-13 [CIS-prac]. smart-lab: «Завьялов Илья Николаевич про DWF Labs» (Ilya Zavyalov on DWF Labs)

| Field | Detail |
|---|---|
| URL | https://smart-lab.ru/blog/964558.php |
| Language, date | Russian, 2023-11-28 |
| Content | DWF's model, citing CoinDesk: buy tokens OTC at a discount, announce it as an "investment", pay in small instalments, and use project tokens as collateral for prop trading (a liquidation risk). Examples: CRV, SPELL, FLY (−99.86%). No price statistics. |
| Margin-borrow link | Partial. Inventory is used as exchange collateral, a mechanism close to token loans. |
| Testability | Low. |
| Novelty | Background for the market-maker angle. |

### CIS-14 [CIS-media]. PANews summary of a DWF Labs report, via Bitget News (DWF Labs is the market maker co-founded by Andrei Grachev; CIS-linked, English text)

| Field | Detail |
|---|---|
| URL | https://www.bitget.com/news/detail/12560605212824 |
| Language, date | English, 2026-02-23 |
| Claim | "Over 80% of tokens fall below their initial offering price within 90 days after the TGE." Causes cited: overvaluation, falling liquidity, airdrops, early unlocks. No sample, period or exchange is given. |
| Margin-borrow link | None. |
| Testability | High, through Idea 2. |
| Novelty | Supports Idea 2. |

### CIS-15 [CIS-media]. SecurityLab blog: «Скрытые pump-and-dump комнаты: когда маркет-мейкеры играют против вас» (Hidden pump-and-dump rooms: when market makers play against you)

| Field | Detail |
|---|---|
| URL | https://www.securitylab.ru/blog/personal/Bitshield/355603.php |
| Language, date | Russian, 2025-06-08 |
| Author | KiberZorro |
| Content | Stages: accumulation of 20–40% of the float, launch, promotion after +50–100%, distribution at 3–10×. Red flags: straight-line rises with no pullbacks, volume jumps of 100–1000× without news, activity at odd hours, spoofing and layering. No data. |
| Margin-borrow link | None. |
| Testability | Medium. Straight-line rises can be measured as 15-min return autocorrelation or a low ratio of drawdown to rise, plus volume z-scores. |
| Novelty | Low. It overlaps the pump-short work. |

### CIS-16 [CIS-media]. ForkLog: «Сговор китов и ADL: что произошло в «черную субботу»?» (Whale collusion and ADL: what happened on "Black Saturday"?)

| Field | Detail |
|---|---|
| URL | https://forklog.com/exclusive/sgovor-kitov-adl-konets-bychki-chto-zhe-proizoshlo-na-rynke-v-chernuyu-subbotu |
| Language, date | Russian, 2025-10-23 |
| Author | Alex Kondratyuk |
| Content | The October 10–11, 2025 crash: over $19bn of liquidations across 1.6m traders; BTC's Binance wick reached $102k. About $90m of USDe was dumped on Binance, where collateral was valued from Binance's own order book until the 14 October fix; that caused about $1bn of liquidations, and wBETH and bnSOL were also hit. Binance paid $283m in compensation. ADL force-closed profitable shorts. |
| Lesson for a short-biased bot | Profitable shorts can be ADL'd in a cascade, breaking the hedge. Avoid liquid-staking or wrapped tokens as collateral, and watch the ADL indicator. |
| Margin-borrow link | None. |
| Testability | Low. We have no liquidation or ADL history. |
| Novelty | A risk note only. |

### CIS-17 [CIS-prac]. Habr: «Провалился в кроличью нору крипты — и вернулся с арбитражным ботом в кармане» (Fell down the crypto rabbit hole and came back with an arbitrage bot)

| Field | Detail |
|---|---|
| URL | https://habr.com/ru/articles/900160/ |
| Language, date | Russian, 2025-04-12 |
| Author | Evgeny Pishchikov |
| Content | Atomic multi-hop DEX arbitrage on Solana (2–4 swaps via Raydium and Meteora); a wallet he studied made about $7–12 an hour. His earlier centralized-exchange trend bots: backtests of +100–200%, live results much lower. |
| Margin-borrow link | None. |
| Testability | Low. |
| Novelty | Illustrates the gap between backtest and live results. |

### CIS-18 [CIS-prac]. Two educational funding explainers

- smart-lab «Фандинг: за что трейдеры платят каждый день?» (Funding: what traders pay for every day), Whitelist, 2025-08-25: https://smart-lab.ru/blog/1196580.php
- vc.ru «Фандинг в арбитраже криптовалют…» (Funding in crypto arbitrage), unsigned, 2025-07-08: https://vc.ru/money/2087796-fanding-v-kriptovalyutnom-arbitrazhe

Both list cash-and-carry, cross-exchange arbitrage, funding "scalping" (hold over the payment) and a contrarian long at deeply negative funding. Neither gives thresholds or data. Margin-borrow link: none. Testability: not applicable. Novelty: none.

### Other CIS pages read with nothing usable

- smart-lab 1091291 (cmd_trader, 2024-12-05): claims 7–8% a week, no rules.
- Habr 956510 (alizar, 2025-10-14): relays a claim about the October 10 crash.
- t.me/s/quant_valerian: management topics, not trading.
- t.me/s/bad_quant: OsEngine and Moscow Exchange content.
- fortraders.org interview with Eduard Khan (2020-08-31): fractal-channel breakouts, no data.
- smart-lab 1314408: Moscow Exchange content.

---

## 3. Academic papers (Russian and Ukrainian) [RU/UA-acad]

### AC-1. Dobrynskaya V. (HSE University, Moscow): "Cryptocurrency Momentum and Reversal". Read deeply.

| Field | Detail |
|---|---|
| URL | HSE conference version (file dated 2021-11-17): https://conference.hse.ru/files/download_file_ex?hash=FAE0AB2DC7A67656E89A0B1CB27D8C7D&id=3B5EE9A5-0B18-458A-9458-B4ED0F6C6664. Also SSRN abstract 3913263. |
| Language | English |
| Data | About 2,000 coins with market cap above $1m (CoinMarketCap), 2014–2020, weekly, winsorized. |
| Method | Sort coins by cumulative return over the past J weeks. Losers are the bottom 30%, winners the top 30%; portfolios are cap-weighted. Hold the winner-minus-loser (WML) portfolio for K weeks. Rebalance weekly with overlapping 1/K cohorts; a version that rebalances every 2, 4, 6 or 8 weeks is also reported. |

**Results** (annualized; t-stat, then Newey-West t in brackets):

| Sort J / hold K (weeks) | WML return | Significance |
|---|---|---|
| 1 / 2 | +57% | t 2.14 [NW 1.61] |
| 2 / 2 | +70% | t 2.46 [NW 1.98], the best momentum cell |
| 1 / 4 | +42% | t 2.80 [NW 1.62] |
| 1 / 1 | +40% | not significant |
| 4 / 8 | −468% | t −5.16 [NW −2.56] |
| 6 / 6 | −299% | NW −2.54 |
| 1 / 12 | −1,038% | NW −2.08 |

- Momentum holds for horizons up to about 2–4 weeks; reversal sets in beyond about 4–6 weeks.
- With less frequent rebalancing, the strongest reversal comes from sorting on 4–6-week returns and rebalancing every 6–8 weeks, at over 100% a year.
- Past losers drive the reversal: long-only loser portfolios earn +400% to +1,400% a year when K is 8 weeks or more.
- About a third of the strategies keep a significant alpha against a five-factor model. The author notes momentum has become less significant in recent years.

| Field | Detail |
|---|---|
| Caveats | CoinMarketCap microcaps. The magnitudes are implausible for tradable perps, and the reversal is driven by microcap losers. |
| Margin-borrow link | None. |
| Testability | High (869 perps over 2 years), but only about 100 weekly observations, so results will be noisy. |
| Novelty | Cross-sectional momentum and reversal are not in our tested lists (Idea 3). |

### AC-2. Dobrynskaya V.: "Is Downside Risk Priced in Cryptocurrency Market?". Read deeply.

| Field | Detail |
|---|---|
| URL | HSE working paper BRP 79/FE/2020: https://wp.hse.ru/data/2020/09/16/1583081932/79FE2020.pdf. A RePEc listing seen in search gives the journal version as International Review of Financial Analysis 91 (2024), article 102947; I read the working paper. |
| Language | English |
| Data | 1,711 coins with market cap above $1m, 2014–2018 (data from Liu, Tsyvinski and Wu, "LTW"), weekly. Betas are measured against LTW's cap-weighted market index. |
| Method | 26-week rolling two-beta CAPM: the downside beta (β⁻) uses weeks when the market return is below zero. Sort into quintiles, equal-weighted, rebalanced weekly. |

**Results**

- Top minus bottom quintile by β⁻: +2.6% a week (136% a year), significant.
- In that 5−1 portfolio only β⁻ is significant (0.32, t 2.13).
- Long the high-β⁻ quintile, short BTC: +3% a week (160% a year).
- Sorting on regular beta: 69% a year, not significant. Sorting on upside beta: −11% a year, not significant.
- The β⁻ factor is orthogonal to LTW's size and momentum factors.

| Field | Detail |
|---|---|
| Margin-borrow link | None. |
| Testability | High. |
| Novelty | A new factor for us, mainly useful as a risk-attribution check for the short basket (Idea 6). |

### AC-3. Caporale G.M. (Brunel University) and Plastun A. (Sumy State University, Ukraine): "Momentum Effects in the Cryptocurrency Market After One-Day Abnormal Returns". Read deeply.

| Field | Detail |
|---|---|
| URL | Brunel working paper 1917 (October 2019): https://www.brunel.ac.uk/economics-finance-and-accounting/research/pdf/1917-Oct-GMC-Momentum-effect-in-the-Cryptocurrency-Market-after-One-day-Abnormal-Returns.pdf. The Springer listing seen in search gives the published version as Financial Markets and Portfolio Management 34 (2020), pp. 251–266. |
| Language | English |
| Data | BTC, ETH and LTC against USD, hourly, 2017-01-01 to 2019-09-01. |
| Definition | Daily return R = close / open − 1. A day is an overreaction day if R > mean + k·σ (positive) or R < mean − k·σ (negative). k = 2 for BTC and 1.5 for ETH and LTC. The window used for the mean and σ is not stated in the working paper. |
| Timing parameter | The hour by which an overreaction is usually evident (time zone not stated). Positive days: BTC 18:00, LTC 13:00, ETH 12:00. Negative days: BTC 16:00, LTC 14:00, ETH 13:00. |

**Strategy 1** (same day: enter at the timing hour in the direction of the move, close at the end of the day). All results significant.

| Coin | Positive days: trades / win rate / per trade | Negative days: trades / win rate / per trade |
|---|---|---|
| BTC | 49 / 86% / +2.92% | 46 / 91% / +4.40% |
| LTC | 38 / 97% / +8.19% | 39 / 85% / +4.38% |
| ETH | 58 / 78% / +8.75% | 57 / 75% / +5.87% |

**These results have look-ahead bias.** Trades are taken only on days that ended as overreactions, so days that crossed the threshold intraday and then reversed are excluded. The true edge is unknown.

**Strategy 2** (next day: enter at the open in the direction of the move, exit at the timing hour; contrarian where marked):

| Coin | After positive days | After negative days |
|---|---|---|
| BTC | contrarian: 59% wins, +1.54%/trade (t 1.75, not significant) | 54%, +1.13% (not significant) |
| LTC | 37%, +1.63% (not significant) | 51%, +1.94% (t 1.93) |
| ETH | 43%, +2.24% (t 1.87) | contrarian: 67%, +3.96% (t 3.46) |

| Field | Detail |
|---|---|
| Margin-borrow link | None. |
| Testability | High (15-min klines). |
| Novelty | Momentum after an intraday abnormal-day signal is new to us (Idea 7). |

### AC-4. Volodin S.N. (HSE) and Spiridonov M.V.: «Сравнение эффективности статистического арбитража на фондовом рынке и рынке криптовалют» (Comparing the effectiveness of statistical arbitrage in the stock and crypto markets). Read deeply.

| Field | Detail |
|---|---|
| URL | https://publications.hse.ru/pubs/share/direct/225204978.pdf |
| Publication, language | Валютное регулирование. Валютный контроль, No. 9/2018, pp. 23–31. Russian. |
| Data | Bitfinex hourly data on 14 liquid coins. Pairs chosen by Pearson correlation, then Engle–Granger with an ADF test (critical values −3.43 / −2.58): DASH–ZEC, ZEC–EOS, ETH–EOS, ETH–ETC, BTC–BCH. Compared with 5 NYSE stock pairs. |
| Rule | Regress the log-returns of Y on X. The indicator is a z-score built from the residual and the regression coefficient. The z-band is optimized on December 2017 (for example 0.012 for DASH–ZEC). Short Y and buy X when the indicator crosses +z; do the reverse at −z; close both legs when the indicator reaches the opposite band. Fee 0.1% per entry. |

**Results** (December 2017 is in-sample; January and February 2018 are out-of-sample):

| Pair | Dec 2017 | Jan 2018 | Feb 2018 |
|---|---|---|---|
| DASH–ZEC | +76% | +14.3% | +18.3% |
| BTC–BCH | +83.0% | +16.0% | −10.4% |
| ETH–EOS | +48.0% | −22.9% | −9.8% |
| ETH–ETC | +54.9% | +4.1% | +10.8% |
| ZEC–EOS | +56.3% | −2.6% | +8.6% |

Crypto pairs were positive in 6 of 10 out-of-sample pair-months, against 5 of 10 for US stocks.

| Field | Detail |
|---|---|
| Caveats | Only 2 out-of-sample months and 5 pairs, during the 2018 bubble top. |
| Margin-borrow link | None. |
| Testability | High, but low priority. |
| Novelty | Pairs trading is not in our lists (listed under "also-rans" in section 5). |

---

## 4. Not accessible, not read, or not cited

- **Medium post "DWF Labs — мошеннические схемы, памп-дампы и скамы"** (DWF Labs: fraud schemes, pump-and-dumps and scams; cryptoshaman): HTTP 403, not read.
- **T-Bank Pulse post by Mr__T** about a failed funding-arbitrage trade: HTTP 503, not read.
- **vc.ru "Международная связка по арбитражу криптовалюты с Казахстаном"** (an international crypto arbitrage scheme involving Kazakhstan; Artem Crypto): HTTP 404.
- **Nazarbayev University repository search:** HTTP 404.
- **Maqsut Narikbayev University thesis** (Turgunov D., 2022, "Problems and perspectives of development of cryptocurrency market in Kazakhstan"): metadata only, PDF not read.
- **Search gaps:**
  - I found no Telegram channels of Kazakh quant traders.
  - Kazakh-language queries returned only generic Russian or English pages.
  - I found no AIFC, Astana Hub, KBTU or KazNU crypto-trading research.
  - Kazakhstan's rule that miners sell part of their output on AIFC exchanges appeared only in search snippets, which disagreed on whether it was later repealed. Not read, so not cited.
- **Search budget:** the session's web-search limit ran out near the end, so I could not do a final pass for Kazakh algorithmic-trader blogs.
- **Non-CIS cross-reference, not counted:** HackerNoon, "the highest funding rate on binance is usually a delisting in disguise" (KX, 2026-08-27). It argues that the top funding names are often flagged or delisting contracts and proposes symbol gates. It supports the guard in Idea 5.

---

## 5. Top ideas to backtest

Defaults for every idea unless stated otherwise:

- **Universe:** Binance USDT-M perps, including delisted symbols.
- **Costs:** 0.05% taker per side plus realized funding.
- **Funding:** normalize to an 8-hour equivalent when the funding interval is 1 h or 4 h.
- **Signals:** computed at a bar close; entry at the next 15-min bar open.
- **Reporting:** results with and without a long-BTC beta hedge, and by sub-period (2024-10→2025-09 and 2025-10→2026-10).
- **Multiple testing:** apply CIS-1's protocol (profitable on each half of validation, at least 15 trades) or a deflated Sharpe ratio, since every idea has a parameter grid.

### Idea 1. Short-covering pump fade: the futures-OI analog of our repay-surge short

**Sources:** CIS-7 (price up with OI down means short covering), CIS-6 (fast large pumps lead to shorts; OI rising confirms a pump), CIS-8 (squeeze moves of 40–70% that reverse), and our confirmed repay-surge and pump-short results.

**Universe:** perps excluding BTC and ETH, with a 7-day median daily quote volume of at least $3M and at least 30 days since listing.

**Signal** (15-min bar t):

- 1-hour return r1h = close_t / close_{t−4} − 1 is at least +6%, and at least 4 times the trailing 7-day standard deviation of 1-hour returns;
- 1-hour OI change ΔOI1h = OI_t / OI_{t−1h} − 1 is −3% or lower (5-min metrics aligned to the bar).

**Control arm:** the same price condition with ΔOI1h of +5% or more (new longs).

**Trade:** short at the open of bar t+1. Exit after 24 h. Stop-loss at +15% from entry. One trade per coin per 24 h.

**Grid:** r1h ∈ {5, 8, 12}%; ΔOI1h ∈ {−2, −5}%; holding period ∈ {4 h, 24 h, 72 h}.

**Extension ("double covering"):** require a MarginData repay surge for the same coin within ±2 h.

**Hypothesis:** pumps driven by covering (OI falling) mean-revert more than pumps driven by new longs.

### Idea 2. New-listing decay short

**Sources:** CIS-9 (10 Binance listings fell 75–94% within 11–32 days), CIS-14 (over 80% of tokens below TGE price within 90 days), CIS-10 and CIS-11 (dumps in the first hour, a sideways first week), CIS-12 (tokens bought OTC at a discount are dumped after exchange deposits).

**Events:** the first trading time T0 of a new perp whose base token is new: its first Binance spot, Alpha or pre-market listing, or its TGE, falls within ±7 days of T0. Use announcement timestamps; a fallback is the first spot kline. Exclude old tokens that are only now getting a perp.

**Trade:** short at T0 + 24 h, equal notional. Also test T0 + 1 h and T0 + 3 days.

**Exit:** T0 + 30 days, with a grid of {7, 14, 30, 60, 90} days.

**Stops:**

- price closes at 1.6 times the entry price or more;
- funding is −0.5% per 8 h or lower for two consecutive periods (a squeeze, which also costs shorts heavily).

**Report:**

- the mean, the median and the 95th-percentile loss;
- funding P&L (new listings often carry negative funding);
- split by listing type (spot plus perp versus perp-only, i.e. Alpha or pre-market);
- split by first-24h return (above or below 0).

### Idea 3. Momentum and reversal overlay on the borrow-short basket

**Source:** AC-1.

**Standalone test:** every Monday at 00:00 UTC, rank perps with at least 8 weeks of history by J-week return. Weight by 30-day quote volume as a proxy for market cap (and also test equal weights).

- **Momentum:** J = 2, K = 2. Long the top 30% and short the bottom 30%, with two overlapping cohorts.
- **Reversal:** J ∈ {4, 6}, K ∈ {6, 8}. Long the bottom 30% and short the top 30%.

**Overlay on our confirmed 10-coin weekly borrow basket:**

- (a) Drop coins in the bottom 30% by 4–6-week return, because past losers rebound per AC-1.
- (b) Tilt toward coins in the bottom 30% by 2-week return (continuing downward momentum).

Report the change in weekly return and Sharpe ratio after fees and funding.

### Idea 4. Capitulation-volume rebound, and a pause on shorts after it

**Source:** CIS-2.

**Signal:** a daily UTC candle that closes below its open, with quote volume at least m times the mean of the previous 60 days, for m ∈ {2, 3, 4}. Optional: the day's return is at most −2σ (60-day window).

**Trade:**

- (a) Long at the next 00:00 UTC open and exit 24 h later (also test 3 and 5 days). Run it on BTC, ETH and all perps with at least 90 days of history.
- (b) As a guard: open no new shorts, and halve existing shorts, in that coin for 48 h after a signal. Measure the effect on the borrow basket and on the pump-short strategies.

### Idea 5. Zombie-squeeze guard and post-squeeze short

**Sources:** CIS-8 (persistent funding around −0.75% per 4 h, pumps of 50–300% that reverse), CIS-16 (ADL risk to shorts), CIS-3 (skip coins that already pumped), and the HackerNoon cross-reference.

**"Zombie" universe:** perps listed at least 2 years, in the bottom quintile by 30-day median volume, or carrying a Binance Monitoring Tag (from announcements).

**Squeeze state:** normalized funding of −0.3% per 8 h or lower for at least two consecutive intervals, and a 72-hour return of +40% or more.

- **Rule A (guard):** no shorts while the squeeze state is active. Compare with our current exclusion of funding below −0.1% per 8 h.
- **Rule B (post-squeeze short):** after a squeeze, once funding is above −0.05% per 8 h for two consecutive intervals and price is still at least 30% above its pre-squeeze level, go short. Exit after 7 days or when price returns to the pre-squeeze level. Stop at +25%.

Also test, on the same universe, whether shorting from a Monitoring Tag or delisting announcement until futures settlement pays, given the funding drag.

### Idea 6. Downside-beta screen: attribution and filter for the short basket

**Source:** AC-2.

**Method:**

- Each week, regress each perp's returns on the market (a volume-weighted perp index excluding stablecoins; BTC as an alternative) using only periods with a negative market return; this gives β⁻. Use 26 weekly observations, or 90 days of daily returns given our short sample. Also estimate β⁺.
- Sort into quintiles, equal-weighted, hold 1 week, and compute Q5−Q1 and Q5 minus BTC. The original paper found +2.6% and +3% a week for 2014–2018.

**Uses:**

- Does β⁻ (and β⁺) explain the alpha of the borrow basket?
- If the β⁻ premium is still positive in 2024–26, exclude top-quintile β⁻ coins from shorts. If it is negative, tilt the shorts toward them.

### Idea 7. Momentum after an abnormal day, without look-ahead

**Source:** AC-3, rebuilt so the paper's look-ahead bias cannot occur.

**Same-day signal:**

- For each coin, compute the trailing 90-day mean μ and standard deviation σ of daily open-to-close returns, excluding today.
- At each hourly mark h from 06:00 to 20:00 UTC, compute the open-to-h return R_h.
- On the first time in a day that R_h ≥ μ + kσ, go long at the next 15-min open and exit at 00:00 UTC. Mirror this for shorts when R_h ≤ μ − kσ.
- k = 2 for BTC, 1.5 for alts, with a grid of {1.5, 2, 2.5}.

**Next-day variant:** at 00:00 UTC after a day whose open-to-close return was at least μ + kσ, enter in the direction of that day. Exit after a holding period from {4, 8, 12, 24} h. Also test the contrarian version for BTC after positive days.

**Expectation:** far below the paper's 75–97% win rates, which come from trade selection with look-ahead. Keep the strategy only if it survives at 15-min resolution after costs.

### Idea 8. Binance spot–perp funding carry with an announcement guard

**Sources:** CIS-3, CIS-4 (20–60% APR stable spreads, at most 1/3 of capital per position, 1.5–2x leverage, 5–6 positions), CIS-1 (align payment windows; small, stable edges), CIS-5 (base-rate cost baseline), KZ-1 (benchmark of 13.7% a year with drawdown under 3%).

**Universe:** coins with both a Binance spot USDT pair and a USDT-M perp, with 30-day median perp volume of at least $20M.

**Entry:** the average of the last 3 realized funding rates is at least +0.03% per 8 h (about 33% APR), the predicted next rate is at least +0.02%, and the perp is at or above spot. Buy spot and short the perp with equal notional. At most 6 positions, and at most 1/3 of capital in any one.

**Exit** on any of:

- the 3-period average falls below +0.005%;
- the perp trades more than 0.3% below spot;
- a Monitoring Tag, delisting or margin-delisting announcement for the coin;
- a change in the funding interval.

**Costs:** 4 × 0.05% taker per round trip (also test 0.02% maker).

**Report:** net APR, drawdown, number of days invested and capacity. Benchmarks: KZ-1's 13.7% a year and the 10.95% a year implied by base-rate funding.

**VSPM's OI/volume heuristic:** flag positions where OI divided by 24h volume is in the top decile, the "MMs farming funding" case, and check whether those spreads are more persistent.

### Also-rans (lower priority)

- **Pairs stat-arb on large coins (AC-4):** re-estimate monthly an Engle–Granger test (ADF below −3.43) on 30 days of hourly closes for the top-50 perps; enter at a residual z-score of ±2, exit at 0, stop at ±4.
- **Funding snipe (CIS-3):** price drift in the 15 minutes before and after Binance funding timestamps for coins with \|funding\| ≥ 0.1%.
- **"Straight-line pump" red flag (CIS-15):** a low ratio of drawdown to rise over a +50% run as an extra filter for pump shorts.
