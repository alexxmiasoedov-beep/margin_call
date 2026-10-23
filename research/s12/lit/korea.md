# Korean crypto community and quant ecosystem: extracted strategies

Prepared 2026-10-23 for the MarginData / Binance USDT-M bot. Scope: Korean-language communities, media,
research houses, regulators and academic papers, plus English-language output of Seoul-based research
houses (Four Pillars, Tiger Research). About 40 pages were opened. 34 with usable content are listed below.
The ten marked ★ were read in full.

Conventions
- KST = UTC+9. Upbit and Bithumb reset their daily candle and "change %" at 09:00 KST = 00:00 UTC. That is
  also Binance's daily open and a funding timestamp, so any "09:00 effect" has to be separated from it.
- "Korean share" = (Upbit + Bithumb KRW volume in USD) / (Upbit + Bithumb + Binance USDT-M volume). This is
  the same definition as confirmed strategy #3 in the brief.
- "Known #n" refers to the brief's confirmed results: 1 = persistent-borrow weekly short basket,
  2 = repay-surge short, 3 = Korean-pump short, 4 = TRY spikes, 5 = Upbit flags (logging only).
- Testability is judged against the data listed in the brief. Dates are publication dates.
- Claims not supported by a source are marked **(inference)**.

## Ecosystem overview: what Korean sources focus on

1. **Exchange notices as catalysts.** Most Korean trading talk and media analysis concerns:
   - listings (상장빔, "listing beam");
   - deposit/withdrawal suspensions (가두리 펌핑, "caged pumping");
   - caution designations (유의빔);
   - delistings (상폐빔).
   The common mechanism: Korean venues have no shorting, so arbitrage is the only thing that caps a
   pump. Any transfer suspension or thin float lets KRW prices detach from global prices.
2. **The kimchi premium.** It is read as a gauge of retail heat and as an arbitrage or hedge trade:
   buy Upbit spot and short 1× on Binance.
3. **Clock effects.** The best-known example is the "promised 09:00" (약속의 09시).
4. **Manipulation anatomy.** Regulator cases describe API wash orders and top-account concentration.
5. **Kimchi-premium academic work.** Determinants, arbitrage, and ML prediction of listing surges.

**Gaps.** No Korean source found discusses Binance cross-margin borrow/repay data or margin interest
rates as signals. Derivatives commentary is mostly translated CryptoQuant/Glassnode BTC-level funding/OI
news, with no rules. The closest borrowing analogs are Upbit/Bithumb's 2025 coin-lending products and the
Korean stock-lending (대차) literature (section F).

---

## A. Caged pumps around deposit/withdrawal suspensions (가두리 펌핑, 유의빔, 상폐빔)

### A1 ★ Tiger Research: the "caged pumping" phenomenon
- **Title:** "한국 가상자산 시장과 가두리 펌핑 현상" — «Корейский рынок цифровых активов и феномен „накачки в садке“»
- **Source:** https://reports.tiger-research.com/p/korean-cex-fnp · KR · 2023-10-23 · Jay Jo (Tiger Research)
- **Strategy / mechanism:**
  - When one exchange suspends deposits and withdrawals, cross-exchange arbitrage stops and the float is fixed.
  - Speculators push the price and retail follows. Korean retail "watches suspension notices as a catalyst".
  - Causes: hacks, network upgrades, congestion, foundation requests, exchange maintenance.
  - Pumps are often aided by multi-account wash trading and bots.
  - No trading rules are given.
- **Evidence:**
  - CRV, Aug 2023 (halt after the Curve exploit): peaks of Bithumb 7,500 KRW, Coinone 3,928 and Upbit 1,300,
    against a global price of ~800 KRW. The Bithumb premium was ~938%, and the price returned to the global
    average "immediately" after resumption.
  - APT, Sep 2023: Upbit halted for about half a day after a mis-deposit. The price ran ~72% above the global
    average, peaking at 9,465 KRW.
- **Margin link:** none. The caged venue cannot be shorted by anyone.
- **Data / testability:** medium.
  - Needs suspension and resumption notice timestamps; Korean candles exist.
  - The Binance-perp reaction is measurable.
- **Novelty:** this event type is not in the brief.
  - Main use: a false-positive filter for known #3, since caged spikes raise Korean volume share without
    Binance participating.

### A2 ★ Digital Asset / Newstomato: base rates for spikes after suspension notices
- **Title:** "[디지털애셋]입출금 중단 뒤 급등 패턴…코인 '가두리 펌핑' 여전" — «Паттерн взлёта после приостановки ввода/вывода… „садковая накачка“ продолжается»
- **Source:** https://newstomato.com/ReadNews.aspx?no=1297414 · KR · 2026-04-10 · 박재연 (디지털애셋/뉴스토마토)
- **Strategy / mechanism:** this is the only systematic count found. It covers all Upbit and Bithumb
  suspension notices from 2025-12-01 to 2026-04-02.
- **Evidence:**
  - Before the FSS warning of 2026-02-09: 17 notices (excluding delisted assets). 4 of them (23.5%) rose
    more than 20% within 24 h:
    - Upbit: DEEP, ZK (max +939.16%), NAP (+476.84%);
    - Bithumb: WITCH (+30.30%).
  - After 2026-02-09 (Bithumb only): 21 notices, of which 6 (28.57%) rose more than 20%:
    DRIFT +87.31%, PEAQ +206.94%, WAXP +179.09%, SOLV +80%.
  - Turnover in the first 6 h after a notice was a median 5.72× the pre-notice level.
  - Spikes last "minutes to hours", and prices re-adjust after the restriction is lifted. No figures are
    given for the reversal.
- **Margin link:** none.
- **Data / testability:** medium.
  - Needs notice scraping.
  - Several of these coins (ZK, DRIFT, WAXP, SOLV, DEEP; to verify in the symbol list) have Binance perps,
    so spillover is measurable.
- **Novelty:** the base rates are new: roughly one in four notices is a lottery ticket.
  - It is cross-validated by Four Pillars (B11): ZKsync spiked ~970% around a Feb-2026 maintenance window.

### A3 Bizwatch: LWA and RDNT caged pumps
- **Title:** "코인 '가두리 펌핑' 또 기승" — «„Садковая накачка“ монет снова набирает силу»
- **Source:** https://news.bizwatch.co.kr/article/mobile/2024/10/21/0012 · KR · 2024-10-22 · 최용순 (Bizwatch)
- **Strategy / mechanism:** case reporting only, with no rules. The smaller-float venue spikes more.
- **Evidence:**
  - LWA, Oct 2024: Coinone +780% (34 → 299 KRW, then 80 KRW). Bithumb +40% (31 → 43 → 33).
  - RDNT, after a ~$50m hack and caution designation:
    - Coinone +438% at dawn on Oct 17 (93 → 500 KRW, closing at 280);
    - Bithumb +90% (97 → 183);
    - Upbit (BTC market only) was unaffected.
  - The practice "noticeably decreased" compared with 1–2 years earlier.
- **Margin link:** none.
- **Data / testability:** medium.
  - RDNT has a Binance perp. The Korean spike happened while the coin was hack-damaged abroad, so the
    Binance perp almost certainly did not join **(inference)**.
- **Novelty:** confirms that caged pumps decouple from Binance, so Binance should not be shorted on them.

### A4 Bizwatch: TAIKO caged pump
- **Title:** "또 가두리 펌핑…업비트 '100원'·빗썸 '300원'" — «Снова садковая накачка: Upbit „100 вон“, Bithumb „300 вон“»
- **Source:** https://news.bizwatch.co.kr/article/mobile/2026/06/24/0017 · KR · 2026-06-25 · 최용순
- **Strategy / mechanism:** case reporting; the pump stayed on one venue while the global price did not move.
- **Evidence (TAIKO):**
  - Jun 21: ~120 KRW on every exchange.
  - Jun 22: deposits halted and the coin was designated 유의 (caution) after a security incident.
  - Day 1 after the halt: Bithumb +193% (126 → 369); Upbit +18%.
  - Jun 24: Bithumb +66% (196 → 326). That morning: Upbit low-100s KRW, Bithumb high-200s, global low-100s
    (≈3× gap).
  - Bithumb took more than 50% of global volume (CMC). Market cap was ~20bn KRW.
- **Margin link:** none. **Data / testability:** medium. **Novelty:** same lesson as A3.

### A5 Hankyung and News1: the November 2025 Upbit hack freeze
- **Title:** "업비트 해킹 후 126% 뛴 코인도...입출금 중단의 역설 [한경 코알라]" — «После взлома Upbit одна монета выросла на 126%… парадокс приостановки ввода/вывода»
- **Source:**
  - https://www.hankyung.com/article/202511282040i · KR · 2025-11-28 · 조미현 (Hankyung);
  - News1 headline https://www.news1.kr/finance/blockchain-fintech/5990490 (2025-11-27; body not retrievable).
- **Strategy / mechanism:** a natural experiment of an exchange-wide freeze. The pumped names were small
  Solana ecosystem tokens with thin Upbit float.
- **Evidence:**
  - After the hack, Upbit halted all deposits and withdrawals.
  - 지토 (Jito, JTO; ticker inferred) traded ≥35% above the global price.
  - ORCA went from near-zero volume to ~330bn KRW of 24 h turnover; the News1 headline says +72% in a day.
  - Meteora also spiked.
- **Margin link:** none.
- **Data / testability:** high for this single episode: Upbit candles exist, and JTO has a Binance perp
  (ORCA perp availability to verify). It is a single event, so it is only illustrative.
- **Novelty:** a filter for known #3. During venue-wide freezes, Korean share spikes while Binance may stay flat.

### A6 ★ Newsis: caution-designation pumps and rotational pumping
- **Title:** "업비트 알트코인 폭등 현상, 이유는?" — «Почему на Upbit взлетают альткоины?»
- **Source:** https://www.newsis.com/view/NISX20250110_0003028508 · KR · 2025-01-10 · 이지영 (Newsis)
- **Strategy / mechanism:**
  - On a 유의 (caution) designation, Upbit suspends deposits. The float is trapped and a Korea-only spike
    follows ("가두리빔", caged beam).
  - Despread (이승화) and Korbit (김민승) describe "순환펌핑" (rotational pumping): similar candidate coins
    are pumped one after another without fundamentals, and can crash at any time.
- **Evidence:**
  - SBD: designated 2024-12-30 at 2,800 KRW, reached 17,400 KRW on 2025-01-09 (+521%). 99% of CMC volume
    was on Upbit.
  - BTG: +228% in one day ahead of its delisting (상폐빔). About 90% of its volume was on Upbit.
  - On Jan 9, Alpha Quark, Strike, SBD and Cobak were Upbit's top 4 by turnover (~10tn KRW combined).
  - On Jan 10: CBK −20.20%, AQT −12.77%, STRIKE −9.04%.
- **Margin link:** none.
- **Data / testability:** low for Binance shorts, since most of these coins lack Binance perps. Medium for
  measuring "rotation" (contagion of Korean pumps across similar coins).
- **Novelty:** the rotation idea is new.
  - After one Korea-heavy coin spikes, the next candidates spike **(inference: testable as cross-coin
    contagion in Korean-share pumps)**.

### A7 Tiger Research: Korean market structure and HIFI
- **Title:** "가상화폐 열풍의 주역, 한국 가상자산 시장" — «Главная сила криптоажиотажа — корейский рынок цифровых активов»
- **Source:** https://reports.tiger-research.com/p/korean-crypto-market · KR · 2024-03-21 · Jay Jo
- **Strategy / mechanism:** structural description with no rules.
- **Evidence:**
  - HIFI rose more than 120% in a day (2024-03-13, ~2,400 → 3,700 KRW), with a >120% gap to global, during a
    transfer suspension ahead of an Ethereum upgrade.
  - On Bithumb, the top-10 holders had more than 70% of supply and more than 40% of volume; new inflows were
    2.5× day over day.
  - On 2024-03-21: altcoins were ~78% of Upbit+Bithumb volume, the kimchi premium was ~10%, and stablecoins
    also traded at a >10% premium.
- **Margin link:** none.
- **Data / testability:** medium for HIFI (delisted perp history exists). The holder-concentration data is
  internal to the exchange, so it is not replicable.
- **Novelty:** low.

---

## B. Listing pumps (상장빔) and the post-listing fade

### B1 ★ CryptoListing.ws: listing and delisting price-reaction statistics
- **Title:** "상장 공지 가격 반응: 업비트·바이낸스·빗썸 2026 통계" — «Ценовая реакция на объявления о листинге: статистика Upbit, Binance, Bithumb 2026»
- **Source:** https://cryptolisting.ws/ko/listing-price-reaction/ · KR page of a listing-alert site, CC BY 4.0,
  no named author · data from 2026-04-09 to 2026-10-22
- **Strategy / mechanism:**
  - Implication: the offshore peak after an Upbit listing notice arrives fast (median 36 min), so a fade
    short should start 30–60 min after the notice.
  - Negative notices (Binance monitoring tag, Bithumb delisting, Binance futures delisting) bottom within hours.
  - Figures are the best or worst trade within 24 h of detection, often measured on another venue's perp.
    They are extremes, not returns.
  - Only tokens already trading elsewhere are included. The post-peak path is not reported.
- **Evidence (24 h extremes):**

  | Event | n | Median peak / trough | Middle 50% | ≥10% move | Median time to peak/trough |
  |---|---|---|---|---|---|
  | Upbit spot listing | 70 | +33.6% | +18.8% to +68.7% | 90% | 36 min |
  | Bithumb spot listing | 44 | +18.6% | +8.8% to +36.1% | 66% | 2.7 h |
  | Binance futures listing | 18 | +39.7% | +18.8% to +57.9% | 83% | 8.3 h |
  | Binance spot listing | 10 | +49.9% | +14.7% to +65.4% | 80% | 66 min |
  | Binance spot delisting | 34 | −27.9% | −35.3% to −23.6% | 97% | 7.5 h |
  | Binance monitoring tag | 31 | −15.2% | −17.7% to −12.6% | 97% | 1.5 h |
  | Bithumb delisting | 23 | −22.4% | −27.2% to −9.5% | 74% | 5.9 h |
  | Binance futures delisting | 13 | −21.6% | −36.7% to −15.7% | 100% | 68 min |
  | Upbit delisting | 13 | −12.7% | −23.7% to −6.3% | 69% | 16.3 h |

- **Margin link:** none.
- **Data / testability:** high (Binance perps plus Upbit listing time).
- **Novelty:** high. Listing-fade and notice-driven shorts are not in the brief.

### B2 ★ Four Pillars: "The Dying Upbit Listing Pump"
- **Title:** "The Dying Upbit Listing Pump" — «Умирающий листинговый памп Upbit»
- **Source:** https://research.4pillars.io/en/data/content/the-dying-upbit-listing-pump · EN (Seoul research
  house) · 2026-08-12 · Ponyo (Four Pillars)
- **Strategy / mechanism:**
  - Implied rule: fade strong listing days and hold to day 7.
  - The edge is decaying with Upbit volume (ADV $1.9bn in Feb → $590m in Jul → $460m in Aug 2026).
  - The base price for "day-1 gain" is not defined in the article.
- **Evidence:**
  - Sample: 58 new Upbit KRW markets from January to early August 2026.
  - Through 2026-06-14: median day-1 gain +42% on median turnover of ₩142bn. Ten were triple-digit, e.g.
    ELSA +144%, EDGE +230%, SLX +198%.
  - From 2026-06-15: 14 fresh listings with a median day-1 gain of +10% (₩54bn). 8 of 14 closed day 1 below
    the open.
  - Tokens moved from the BTC market to a KRW pair: median +19%.
  - **For listings up >40% on day 1, the day-7 close was 20–65% below the day-1 high (median 45%), in both
    regimes.**
- **Margin link:** none.
- **Data / testability:** high.
- **Novelty:** high. It gives the holding horizon and a regime break.

### B3 ★ Four Pillars: 2025 Korean CEX listings post-mortem
- **Title:** "2025 Korean CEX Listings Post-Mortem" — «Посмертный разбор листингов корейских CEX за 2025 год»
- **Source:**
  - https://research.4pillars.io/en/research/2025-korean-cex-listings-post-mortem · EN · 2026-03-11 · c4lvin;
  - KR version: https://www.blockmedia.co.kr/archives/1063994 (2026-03-17).
- **Strategy / mechanism:**
  - Test design: buy each new KRW listing at the day-1 close and hold, without a hedge, to 2026-03-11.
    The period includes the bear market since Oct 2025.
- **Evidence:**
  - Sample: 59 Upbit and 144 Bithumb new KRW pairs in 2025.
  - Upbit −69.5% (median −80.9%); Bithumb −69.1% (median −82.1%).
  - Binance's own 2025 listings (92, from Messari): −71.7%.
  - Only 2 of 59 Upbit names were in profit: KITE +232.8% and BARD +9.3%. 46% of Upbit names were in the
    −75% to −90% band.
  - Bithumb: H1 cohort −77.3%, H2 cohort −59.4%. Dual-listed and Bithumb-only tokens performed about the same.
- **Margin link:** none.
- **Data / testability:** high, but a BTC or market hedge is required.
- **Novelty:** medium. New-token drift is known globally; the Korean listing day as the entry anchor is new.

### B4 ★ Blockmedia: PIEVERSE, the Bithumb-first pattern
- **Title:** "[상장빔의 민낯] 빅2의 유동성 공조 '상장은 업비트, 폭등은 빗썸' …파이버스 3일의 기록" — «[Изнанка листингового пампа] „Ликвидностная координация“ большой двойки: листинг на Upbit, взлёт на Bithumb — три дня Pieverse»
- **Source:** https://www.blockmedia.co.kr/archives/1124820 · KR · 2026-08-07 · 오수환, 명정선 (Blockmedia)
- **Strategy / mechanism:** the article's own signals:
  - price leads volume on the existing venue;
  - a pre-announcement surge;
  - a volume/price gap after listing;
  - a volume collapse much faster than the price decline;
  - withdrawal-limit cuts (Bithumb cut PIEVERSE withdrawal limits by 98.6% per transaction/day and 98.9%
    monthly).
  - The authors stress the data cannot prove leaks.
- **Evidence (PIEVERSE, on Bithumb since 2025-11-24):**
  - Apr 14–16: ~600s KRW, daily volume ₩0.6–1.5bn.
  - Apr 17: +8.8%, with price moving before volume. Apr 18: +19.3% over two days, volume 2.2×.
    Apr 19: above 1,000 KRW, volume 7×.
  - Apr 20, before the notice:
    - 03:00: 1,721 KRW;
    - 05:00: above 2,000 KRW, 9 h before the Upbit notice;
    - intraday high 2,900 KRW (+361% from the 629 low);
    - daily volume 11×, with more than ₩100bn traded before the notice.
  - Upbit notice at 14:00. Upbit trading started at 16:00 with an open of 1,431; the post-listing peak was
    1,608 at 20:00. The Bithumb high was never revisited.
  - Apr 22, 13:00: 1,306 KRW. 24 h volume was −69.8% from its peak while the price was −11.1%.
  - Aug 6: ~1,080–1,092 KRW (−62% from the peak).
  - Similar cases:
    - SPK: Bithumb 45 → 78 KRW before Upbit trading started; peak 94 about 6 h later;
    - IRYS: volume 93× normal three days before the notice; peak 140 KRW.
- **Margin link:** none.
- **Data / testability:** high: Bithumb candles, Upbit first-trade time, and Binance perps where they exist.
  Perp availability for PIEVERSE, SPK and IRYS must be checked.
- **Novelty:** high. It gives a conditional "sell the news" rule (T2).

### B5 Bizwatch: listing effects by exchange, Q1 2025
- **Title:** "'상장빨' 잘 먹히는 가상자산거래소는?" — «На какой бирже лучше всего „работает“ листинговый эффект?»
- **Source:** https://news.bizwatch.co.kr/article/mobile/2025/05/30/0008 · KR · 2025-06-01 · 최용순;
  data from the valuation firm 애피와
- **Strategy / mechanism:** pump size is not proportional to turnover; thin venues pump more.
- **Evidence (Q1 2025):**
  - Listings: Bithumb 45, Coinone 20, Korbit 21, Upbit 13.
  - Average listing-day rise: Korbit 214%, Upbit 140%, Bithumb 39%.
  - Upbit's average listing-day turnover was ₩658.3bn, more than 90% of the five KRW venues combined.
    Upbit took 91% of new-listing volume over the first 14 days.
  - PEAQ on Korbit: +1,455%, then −80–90% within one minute.
- **Margin link:** none. **Data / testability:** high for Upbit coins that have perps.
- **Novelty:** supports B1/B2. Q1 2025 was the strongest regime.

### B6 Bizwatch via Daum: near-simultaneous Binance + Korean listing dumps (설거지)
- **Title:** "상장빔 대신 '설거지'…신규상장 코인 주의보" — «Вместо листингового пампа — „мытьё посуды“ (слив на розницу)… предупреждение о новых монетах»
- **Source:** https://v.daum.net/v/20250921110114533 · KR · 2025-09-21 · 최용순 (Bizwatch)
- **Strategy / mechanism:**
  - A Binance listing followed closely by a Korean listing used to trigger rallies. Now it is followed by
    joint declines, because supply is released into the Korean listing.
- **Evidence:**
  - OPEN: Binance listing on the 8th at ~high-200s KRW; Upbit/Bithumb listing on the 10th at ~1,500 KRW;
    −30% over more than a week.
  - ZKC: listed on all three venues on the 15th at 2,100 KRW; 1,000 KRW within 4 trading days (more than −50%).
  - HOLO: Binance and Upbit on the 11th, Bithumb on the 17th; ~900 → ~500 KRW in 7 trading days (−40%).
- **Margin link:** none. **Data / testability:** high.
- **Novelty:** high. This is the direct basis for T3.

### B7 Dealsite: the October 2021 Upbit listing beams
- **Title:** "거세지는 업비트 상장빔...투자 피해 '주의보'" — «Усиливающийся листинговый памп Upbit… предупреждение об убытках инвесторов»
- **Source:** https://dealsite.co.kr/articles/79402 · KR · 2021-10-19 · 김가영 (Dealsite)
- **Strategy / mechanism:** per anonymous industry sources, manipulators pre-accumulate, use "leading
  rooms" (리딩방), and sell about **2 hours after listing**. At the peak, KRW prices were 3–5× overseas
  prices (Korea-only buying).
- **Evidence (2021-10-15 listings):**
  - NU: 314 → 10,000 KRW (+3,000%) within 20 min.
  - SOL: +55%. MATIC: +270%.
- **Margin link:** none.
- **Data / testability:** outside our sample.
- **Novelty:** a historical anchor for the timing of the dump.

### B8 Klein Labs via Blockmedia: 2024 listing impact (low value)
- **Title:** "Why Meme Coins are Surging and Upbit is Strong — 'The Structure Reveals the Answer'" — «Почему растут мемкоины и силён Upbit: ответ — в структуре»
- **Source:** https://www.blockmedia.co.kr/research-english/892145 · EN/KR · 2025-04-18 · Klein Labs (via 명정선)
- **Evidence:**
  - After listing, Upbit's 24 h volume exceeded half of Binance's.
  - Tokens already listed elsewhere react on Upbit "as if first-listed".
  - Binance had the best 7- and 30-day post-listing returns.
  - No numbers are given.
- **Testability / novelty:** low value; it supports B1.

### B9 ★ Park, Lee, Kim (Yonsei), JKSCI: predicting Upbit listing surges
- **Title:** "A Machine Learning–Based Analysis of Short-Term Surges and Listing Premiums for Newly Listed Altcoins on Korean Exchanges Using Offshore Prices and Social Signals" — «Машинный анализ краткосрочных взлётов и листинговых премий новых альткоинов на корейских биржах по офшорным ценам и социальным сигналам»
- **Source:** https://journal.kci.go.kr/jksci/archive/articlePdf?artiId=ART003305943 · KR (EN abstract) ·
  JKSCI 31(2):87–96, Feb 2026 · Eun Hong Park, Yeong-In Lee, Ha Young Kim
- **Strategy / mechanism:**
  - Sample: 144 Upbit KRW listings from Jan 2021 to Dec 2025; 107 had Binance USDT 1-min data.
  - **Listing time = the first Upbit trade minute (API).** This is a workaround that needs no notices.
  - Gap = Upbit / (Binance × daily USD/KRW) − 1.
  - Labels: maximum return within N days ≥ θ; premium ≥ 10%.
  - Features:
    - pre-listing Binance 1-min log-return mean, standard deviation and 95th percentile of |r|;
    - volume;
    - social mentions (6-month EWMA z-score from Bitcointalk/Altcointalk).
  - Tickers split 74 / 16 / 17 for train / validation / test.
- **Evidence:**
  - Surge ≥5% within 1 day: MLP AUC 0.83, precision in the top-10% 0.50, lift 1.70. Logistic regression
    0.72, rising to 0.80 with social features.
  - Joint surge + premium event: logistic regression AUC 0.85, rising to 0.89 with social features.
  - Top composite cases:
    - MINA (2023-10-24): maximum return 116.6%, maximum premium 280.3%;
    - 0G (2025-09-22): 78% / 264%;
    - SEI (2023-08-16): 153.8% / 130.9%.
  - **The top pumpers had high pre-listing Binance volume and volatility.**
  - Caveats: only 17 test tickers, and the label thresholds are inconsistent (5% vs 10%).
- **Margin link:** none.
- **Data / testability:** high. All features except social come from our Binance data.
- **Novelty:** new. Pre-listing Binance activity tells which Upbit listings pump hardest, which is useful for
  ranking and sizing T1.

### B10 Digital Asset: shrinking listing liquidity
- **Title:** "업비트·빗썸 신규코인 거래 '-78%' '-50%'...하락장에 '상장' 효과 시들" — «Торги новыми монетами Upbit и Bithumb: −78% и −50%… листинговый эффект угасает на падающем рынке»
- **Source:** https://www.digitalasset.works/news/articleView.html?idxno=42326 · KR · 2026-08-06 · 박범수
- **Evidence:**
  - Sample: 95 Upbit and 179 Bithumb KRW listings, 2025-01-01 to 2026-06-30.
  - Average initial turnover (listing day + next day) fell −78% on Upbit and ~−50% on Bithumb.
  - Upbit by quarter (Q1'25 → Q2'26): ₩1,168.4bn, 356.4bn, 598.5bn, 414.0bn, 214.8bn, 259.5bn.
- **Use / testability:** a regime variable for T1. **Novelty:** medium.

### B11 Four Pillars: "The Tale of the Tail in the Korea CEX"
- **Title:** "The Tale of the Tail in the Korea CEX" — «Сказка о „хвосте“ на корейских CEX»
- **Source:** https://research.4pillars.io/en/research/the-tale-of-the-tail-in-the-korea-cex · EN · 2026-07-20 ·
  Heechang (Four Pillars, with SurfAI)
- **Evidence:**
  - Tail assets (outside the top 30) are 58% of Upbit volume and 52% of Bithumb's, against 23% on Binance and
    19% on Coinbase.
  - BTC is ~9% of Korean flow. KRW pairs are ~30% of global spot volume in 2026. Upbit has ~72% of domestic
    volume.
  - In a panel of 605 listings, the median Upbit listing sheds most of its debut liquidity within 10–15 weeks.
  - ZKsync spiked ~970% around a Feb-2026 maintenance window. The article also mentions the "promised 9 a.m.".
- **Use / testability:** background. Cross-validates A2 and C1.

---

## C. Clock effects

### C1 ★ Korbit Research: the "promised 09:00" pumps
- **Title:** guest column "'약속의 09시'…" (Hankyung via Bloomingbit) — «„Обещанные 09:00“…»
- **Source:** https://bloomingbit.io/feed/news/76240 · KR · 2024-10-09 · 김민승, head of Korbit Research Center
- **Strategy / mechanism:**
  - Some coins repeatedly spike at 09:00 KST; communities call them "09시 경주마" (09:00 racehorses).
  - Two of the five KRW exchanges reset change-% at 09:00, so a coin that jumps at 09:00 tops the gainers
    ranking that momentum chasers sort by.
  - Implied rule: fade 09:00 spikes in Korea-heavy coins.
  - Typical spike: +10–25%, peaking 1–2 h after 09:00 (sometimes much later), and fully round-tripping by the
    next morning in about half the episodes.
- **Evidence (five anonymized coins, Sep–Oct 2024):**
  - L: 59 → 67 (11:00) → 60 (07:00 next day); 68 → 90 (17:00) → 79; 84 → 95 (10:00) → 85 (13:00).
  - H: 610 → 718 (11:00) → 650 (01:00); 658 → 755 (22:00) → 706.
  - A: 585 → 722 (17:00), then 500 by Oct 3, with failed 09:00 rebound attempts.
  - C: 157 → 181 (11:00) → 157 (05:00).
  - S: 540 → 576 (20:00) → 498 (07:00).
  - Common features:
    - all had sudden 09:00 volume surges with no news;
    - they are listed on more Korean venues than on Binance;
    - one coin has more than 50% of its supply on domestic exchanges;
    - L was delisted from Binance on 2024-08-26;
    - the same names recurred in the 2023 "순환펌핑" (rotational pumps).
- **Margin link:** none.
- **Data / testability:** high (Upbit/Bithumb hourly candles; Binance perps where they exist).
- **Novelty:** a twist on known #3: clock-conditioned and with a smaller threshold.
  - Must be separated from 00:00 UTC effects.

### C2 Bloomingbit (from Edaily): time-of-day returns on Upbit BTC
- **Title:** "코인 수익률, 오전에 가장 낮아…새벽 전후 상승세 높다" — «Доходность монет ниже всего утром… выше всего около рассвета»
- **Source:** https://bloomingbit.io/feed/news/31684 · KR · 2022-08-04 · Bloomingbit newsroom, citing
  랩투아이 (Lab to I, CEO 오종환)
- **Evidence (three years of Upbit BTC candles, non-parametric tests):**
  - Lowest average returns from **09:00 to 11:00 KST**; higher returns from 04:00 to 06:00 KST.
  - BTC tends to rise at the start and end of the month and fall mid-month.
  - Volume and volatility are lowest from 19:00 to 21:00 KST.
  - The CEO notes that volume surges at the Korean stock-market open and BTC tends to fall.
- **Data / testability:** high.
- **Novelty:** low–medium. Worth checking on Korea-heavy altcoins.

---

## D. Kimchi premium research and practice

### D1 ★ Cho, Park, Ahn (Kookmin): kimchi-premium statistical arbitrage
- **Title:** "김치프리미엄과 환율 변동 예측을 활용한 가상화폐의 통계적 차익거래 연구" — «Статистический арбитраж криптовалют на основе кимчи-премии и прогноза валютного курса»
- **Source:** https://www.kais99.org/jkais/journal/Vol24No10/vol24no10p041.pdf · KR · J. KAIS 24(10):354–363,
  2023-10 · 조기정, 박종현, 안현철
- **Strategy / mechanism:**
  - Data: daily Upbit vs Binance BTC, 2017-09-26 to 2023-04-06.
  - The premium is regressed on USD/KRW.
  - Rule: if the current premium is below the model-predicted premium, buy BTC on Upbit, transfer it and sell
    on Binance. Reverse the trade when the round trip nets at least 1%.
- **Evidence:**
  - Regression: R² 0.032, intercept 0.2118, slope −0.0002 per KRW (≈ −2 pp of premium per +100 KRW of
    USD/KRW).
  - Backtest 2020-01-01 to 2023-04-06: 376–380 trades, with reported cumulative return of
    ×4,709 (official FX), ×4,932 ("unofficial", BTC-implied FX) and ×4,536 (LSTM FX).
  - These results ignore slippage, transfer time and minimum transfer units, and are in-sample. They are not
    credible.
- **Margin link:** none.
- **Data / testability:** high, but only as a regime input.
- **Novelty:** low. Useful facts: the premium mean-reverts and moves against USD/KRW.

### D2 Yang (Dankook): arbitrage on the BTC Korea–abroad price gap
- **Title:** "비트코인의 국내외 가격차이를 이용한 차익거래에 관한 연구" — «Арбитраж на разнице цен биткоина в Корее и за рубежом»
- **Source:** https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002549675 ·
  KR · Asset Management Review 7(2):1–20, 2019 · 양철원 (abstract only)
- **Evidence:**
  - 2015-07 to 2018-12: mean premium 3.71%, maximum 55.72% (mean $223, maximum $8,358).
  - Significant drivers: Google Trends gap, Naver Trends, per-transaction cost, mempool backlog. In other
    words, attention plus limits to arbitrage.
- **Novelty:** low.

### D3 Ok, Kim, Kim (University of Seoul, HUFS): is the kimchi premium a bubble?
- **Title:** "Is the Kimchi premium a speculative bubble?" — «Является ли кимчи-премия спекулятивным пузырём?»
- **Source:** https://pure.uos.ac.kr/en/publications/is-the-kimchi-premium-a-speculative-bubble/ · EN ·
  Finance Research Letters 57:104207, 2023 (abstract only)
- **Evidence:** Eom's (2021) positive link between the premium and volume/volatility disappears with
  time-varying coefficients and bootstrap confidence intervals.
- **Use:** do not treat the premium as a stable predictor; this is a caveat for T8.

### D4 ★ Bank of Korea research via MTN: the stablecoin kimchi premium
- **Title:** "규제가 키운 '스테이블코인 김프'…한은 연구진 '외환시장 충격은 막아'" — «Регулирование раздуло „кимчи-премию по стейблкоинам“… исследователи Банка Кореи: зато защищает валютный рынок»
- **Source:** https://news.mtn.co.kr/news-detail/2026090312214798130 · KR · 2026-09-03 · 송요섭 (MTN),
  reporting 김지현 and 조상흠 (BOK International Finance Research Team)
- **Strategy / mechanism:** the USDT/KRW premium is a "pure" gauge of Korean retail attention.
  - Korea's closed market keeps attention shocks inside crypto prices instead of USD/KRW.
- **Evidence:**
  - Korea's USDT premium has a median of 1.67% since 2022 (Ukraine 1.86%, South Africa 1.80%).
  - A 1-SD rise in BTC search volume widens the premium by 0.85 pp, with no FX effect.
  - Where Binance opened direct fiat–stablecoin trading, premiums fell 0.33–0.38 pp.
  - When the local price exceeds Binance's, stablecoins flow in from Binance.
- **Margin link:** none.
- **Data / testability:** high (Upbit/Bithumb KRW-USDT plus USD/KRW).
- **Novelty:** medium. It is the anchor for the T8 regime gauge.

### D5 Tiger Research with Kaiko: kimchi premium overview
- **Title:** "김치 프리미엄 현상 총정리: 한국 가상자산 시장의 특징과 원인" — «Всё о кимчи-премии: особенности и причины корейского рынка»
- **Source:** https://reports.tiger-research.com/p/kimchi-premium-101-kor · KR · 2024-11-07 · Jay Jo
- **Evidence:**
  - Days with a premium above 5% in H1 2024 were 5.6× the H2 2023 count.
  - Average altcoin maximum drawdown on KRW markets was ~70% in H1 2024.
  - Listing premiums: AVAIL ~1,255% at its Bithumb listing (Jul 2024), later ~3%. CRV ~700% during its halt.
    USDC 165% at listing.
  - **Altcoin premiums fade as volume stabilizes and supply arrives.**
  - Alleged API wash trading and caged pumping in WOO, LWA and RDNT.
- **Use:** supports T5. **Novelty:** medium.

### D6 CryptoQuant user guide: Korea Premium Index
- **Title:** "김치 프리미엄 지표 (Korea Premium Index)" — «Индекс корейской премии»
- **Source:** https://userguide.cryptoquant.com/ko/cryptoquant-metrics/fund-premium/korea-premium-index ·
  KR · live document · CryptoQuant (Korean firm)
- **Evidence (a stated historical observation, not a test):**
  - "Historically ≥16% marked short-term or market tops".
  - Above 0 means strong retail buying; below 0 means weak retail buying.
- **Use:** an upper anchor for T8. Readings of 16% or more are rare in 2024–2026.

### D7 Clien: kimchi / reverse-premium arbitrage
- **Title:** "김프, 역프 차익을 통한 바이낸스 - 업비트 간 재정거래법" — «Арбитраж Binance–Upbit на кимчи-премии и обратной премии»
- **Source:** https://www.clien.net/service/board/cm_vcoin/15863333 · KR · 2021-02-04 · 안산토박이 (Clien)
- **Strategy:**
  - When the reverse premium is ≤ −3%: buy a transfer coin (XRP, XLM, TRX or EOS) in Korea, send it to
    Binance and sell for USDT.
  - When the premium is ≥ +3%: buy on Binance, send back to Korea and sell. That is ≈ 6% per round trip.
- **Evidence (comments only):** the main risk is the premium widening further (−4–5% went to −6%), and the
  premium is "mostly FX".
- **Novelty:** low.

### D8 FMKorea: practitioner view of kimchi arbitrage in 2024
- **Title:** "업비트 / 빗썸 - 바이낸스 차익거래 아비트리지, 김프거래" — «Арбитраж Upbit/Bithumb — Binance, торговля кимчи-премией»
- **Source:** https://www.fmkorea.com/7290336701 · KR · 2024-07-26 · 초코차 (FMKorea)
- **Strategy:**
  - The hedge form is to buy Upbit spot and short Binance futures, closing both at convergence.
  - The premium must be computed from bid/ask quotes, not last trades.
  - Round-trip cost ≈ 0.2% (Upbit 0.05%, Binance futures 0.05%).
- **Evidence:** the author runs a 5-second spread monitor. Plain kimchi arbitrage has been "effectively gone
  for ~2 years". A ≥0.2% gap appeared once, for 28 s, on Bithumb.
- **Margin link:** the hedge leg of Korean premium trades sits on Binance futures or margin. Korean premium
  episodes therefore create Binance short positions that are not directional bets (basis for T6).

### D9 TradingView (Tommy_Trader): the "Kimchi Soup" premium indicator
- **Title:** "1. 김치 프리미엄(Kimchi Premium)이란?" / indicator "김프찌개" — «Что такое кимчи-премия?» / индикатор «Кимчи-суп»
- **Source:** https://kr.tradingview.com/chart/BTCUSDT/gxfSTBIC/ · KR · 2025-02-27 · Tommy_Trader
- **Strategy:**
  - The premium is charted as candles with RSI (70/30), Stochastic (90/10) and Bollinger-band breaks.
  - The same hedge structure: when the premium is low or negative, buy in Korea and short 1× abroad; close
    both legs at a high premium.
- **Evidence:** no backtest is given. **Novelty:** low; it confirms the hedge practice used in T6.

### D10 AlgoLab blog: automating kimchi-premium arbitrage
- **Title:** "김치프리미엄 차익거래 자동화 — 업비트·빗썸 vs 바이낸스 가격차 자동 트래킹·진입 가이드" — «Автоматизация арбитража кимчи-премии: отслеживание и вход»
- **Source:** https://algolab.co.kr/blog/kimchi-premium-arbitrage · KR · 2026-05-09 (updated 2026-08-07) ·
  AlgoLab blog
- **Strategy and implementation details:**
  - Compute the premium using Upbit **KRW-USDT** as the FX rate, not the bank rate.
  - Costs ≈ 0.33%. Alert tiers at ±2%, ±5% and ±10%.
  - Upbit withdrawal caps: ₩50m/day at KYC level 1, ₩500m/day at level 2.
  - BTC transfers take 10–60 min.
  - Upbit's deposit-status API lags by minutes and is "reference only".
- **Use:** the premium formula for T5 and T8.

### D11 Klein Labs via TokenPost: kimchi premium market note (low value)
- **Title:** "대한민국 암호화폐 시장 분석: '김치 프리미엄'이 견인하는 성장인가?" — «Корейский криптовалютный рынок: рост на кимчи-премии?»
- **Source:** https://www.tokenpost.kr/research/542 · KR · 2025-06-20 · Klein Labs
- **Evidence:** premium 8.5% (Mar 2024) and ~10% (Nov 2024); Upbit share 70–86%. The figures are
  internally inconsistent.
- **Novelty:** low value.

---

## E. Manipulation anatomy and official surveillance thresholds

### E1 ★ Korea Institute of Finance: pump-and-dump in Korean kimchi coins
- **Title:** "한국의 가상자산시장과 '펌프앤덤프' 현상에 대한 고찰" — «Корейский рынок цифровых активов и феномен pump-and-dump»
- **Source:** https://xangle.io/research/detail/1425 · KR · 2023-08-09 · Korea Institute of Finance weekly brief
  (republished on Xangle)
- **Strategy / mechanism:**
  - Kamps–Kleinberg detector on hourly OHLCV: price and volume exceed a trailing moving-average baseline by ε.
- **Evidence:**
  - Sample: 23 "kimchi coins", October 2021, 16,560 hourly observations.
  - Up to 4.7% of hours were flagged.
  - **Under the strictest ε, 80.39% of pumps were followed by a price drop (60–80% across ε settings).**
  - 21 of 23 coins showed the pattern, and intensity declined over time.
  - 62.24% of 625 KRW-listed coins were listed on a single exchange (FSC survey, H2 2022).
- **Margin link:** none.
- **Data / testability:** high; the detector can be replicated on Upbit hourly data.
- **Novelty:** low–medium. It provides a reversal base rate behind known #3.

### E2 ★ FSC press release: manipulation cases and top-10 account thresholds
- **Title:** "가상자산시장 시세조종 혐의자 수사기관 고발" — «Передача в следственные органы лиц, подозреваемых в манипулировании рынком цифровых активов»
- **Source:** https://fsc.go.kr/no010101/87235 · KR · 2026-07-01 · Financial Services Commission / FSS
- **Strategy / mechanism:**
  - **Case 1:** a whale bought about half of a token's global circulating supply over ~2 months
    ("수백억원", i.e. several tens of billions of KRW). It **pumped the overseas exchange first**; arbitrage dragged the Korean price up, and it
    **sold in Korea**. Gains in Korea exceeded the overseas losses.
  - **Case 2:** a domestic token with more than 70% of global volume in Korea:
    1. pre-accumulation;
    2. API market buy and sell orders several times per second to fake activity;
    3. manual buys at or above the 10th ask level;
    4. tranche selling into the chase.
- **Evidence:** official thresholds for the **top-10 accounts' share of trading**, which back the user's
  logged "small-account concentration" flag:
  - 투자주의 (caution): 50% to under 75%;
  - 경고 (warning): 75% to under 90%;
  - 위험 (danger): 90% or more.
- **Margin link:** none.
- **Data / testability:**
  - Low for account data.
  - Medium for the Case 1 pattern: a Binance-first pump followed by surging Korean share. This means known #3
    should not require the pump to start in Korea **(inference)**.
- **Novelty:** medium.

### E3 Asia Economy: four manipulation cases referred, September 2026
- **Title:** "금융당국, 가상자산 시세조종·부정거래 4건 고발·통보" — «Финансовые власти передали 4 дела о манипуляциях и мошенничестве с цифровыми активами»
- **Source:** https://view.asiae.co.kr/article/2026092319515025606 · KR · 2026-09-23 · Asia Economy
- **Strategy / mechanism:** three "ultra-short-term" API cases:
  1. buy inventory fast;
  2. send high-frequency tiny market orders from borrowed or nominee accounts to fake activity;
  3. place high-price limit bids from the main account;
  4. let pre-placed high asks fill into the move.
  - One issuer case used wash trading to meet listing-maintenance volume.
- **Use:** a microstructure signature.
  - Binance `trade_count` rises with a falling average trade size during a Korean pump.
  - The pump may be exhausted when tiny-trade intensity drops **(inference)**.

### E4 ★ Upbit Customer Center: market-warning rules
- **Title:** "업비트 시장 경보 제도 알아보기" (updated 2026-10-12) and "시장경보 현황 알아보기" (2026-05) — «Система рыночных предупреждений Upbit» / «Статус рыночных предупреждений»
- **Source:** https://support.upbit.com/hc/ko/articles/900005994766 and .../57911485574041 · KR.
  Retrieved via the Zendesk JSON API, because the HTML page returns 403.
- **Rules:**
  - Five auto-flags in three levels (주의 / 경고 / 위험), assigned and lifted automatically:
    global price difference, price surge/plunge, volume surge, deposit surge, small-account concentration.
  - 유의 is a separate manual designation (DAXA process) that can end in delisting.
  - Global-price reference: **CoinMarketCap**. A gap of **≥ ±10% triggers 주의**; ±3% to <10% is displayed
    but not flagged.
  - Listings younger than 96 h are excluded from the volume and deposit flags; their price flag uses the
    opening price.
  - **Since 2026-05-18 the price flag compares with the close 24 h ago, instead of "yesterday's close" (the
    09:00 KST cut).**
  - The small-account flag fires when top accounts' high buy participation accompanies a rise, or high sell
    participation accompanies a fall.
  - A historical status page exists from 2026-05-27.
  - Volume, deposit and price thresholds are not published ("to prevent abuse").
- **Use:** the "global price difference" flag can be rebuilt for the full two years from Upbit and Binance
  candles (Binance ≈ the CMC reference for perp coins), and the price flag can be approximated, instead of
  waiting for live logs.
- **Data / testability:** high for the reconstructable flags.
- **Novelty:** a twist on known #5.

---

## F. Lending and borrowing analogs: the closest Korean material to MarginData

### F1 Newstomato: Upbit and Bithumb coin-lending products
- **Title:** "코인 대출로 공매도 문 연 업비트·빗썸, 법망은 사각지대" — «Upbit и Bithumb открыли шорт через займы монет — законодательная „слепая зона“»
- **Source:** https://www.newstomato.com/ReadNews.aspx?no=1267925 · KR · 2025-07-09 · 신상민 (Newstomato)
- **Mechanism:**
  - **Upbit 코인빌리기:**
    - KRW collateral, borrowing 20–80% of collateral value, for up to 30 days;
    - forced repayment at a 92% lending ratio;
    - fees: 0.05% upfront plus 0.01% per 8 h, and 1.5% extra on forced repayment;
    - the article names only BTC. Other reports, seen only as search snippets and not read, say Upbit
      also offered XRP and USDT and later stopped USDT lending.
  - **Bithumb 코인대여:**
    - 10 coins, including USDT, ETH, XRP, SOL and PEPE;
    - up to 4× collateral, 0.05% per day, and a 1% fee on auto-repayment.
- **Margin link:** this is the first domestic borrow-to-sell facility, a Korean analog of Binance margin.
  The borrowable list contains only majors.
- **Data / testability:** low; no borrow data is published.
- **Novelty:** background only.

### F2 ★ Edaily via Daum: Bithumb USDT forced-repayment spike
- **Title:** "[단독] 빗썸 공매도, 하루 만에 500억 강제청산…보상 고작 1억" — «[Эксклюзив] Шорты на Bithumb: принудительные погашения на 50 млрд вон за день, компенсация — всего 100 млн»
- **Source:** https://v.daum.net/v/20251019180152506 · KR · 2025-10-19 · 최정훈 (Edaily)
- **Evidence:**
  - At 06:22:06 KST on 2025-10-11, USDT on Bithumb printed **5,755 KRW** while the best bid was 1,669. It
    fell back to 1,660 within ~3 s.
  - Auto-repayment buys executed from 06:30 to 07:11 at 1,481–1,650 KRW.
  - Scale: 1,999 users, 6,370 cases, ₩50.03bn auto-repaid.
  - Bithumb blamed a "kimchi-premium arbitrage algorithm".
  - The lending limit had already been cut from 400% (June) to 85% (September). The FSC had asked in July
    2025 to halt new lending.
- **Margin link:** this is a forced-repayment (buy-to-cover) cascade in a thin KRW order book, the same
  mechanism as a repay surge. The spike reverted within seconds. It supports the logic of known #2 and warns
  that repay-driven spikes are transient.
- **Data / testability:** not testable (USDT-KRW); illustrative only.

### F3 Lim & Jeon (Hanyang): profitability of stock borrowing by borrower type
- **Title:** "주식 대차거래 주체별 수익성 분석" — «Доходность сделок займа акций по типам заёмщиков»
- **Source:** https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART002510913 · KR ·
  J. Financial Engineering 18(3):31–57, 2019 · 임은아, 전상경 (abstract only)
- **Evidence:**
  - KRX stock borrowing, 2011-07 to 2016-06. Foreigners were ≈75% of borrowing.
  - The profitability of borrowing-based trades was weak or negative, and large deals lost more often.
  - There is no evidence that foreign borrowing systematically pushes prices down.
  - The Korean and English abstracts contradict each other on the sign of the price change, so treat the
    result cautiously.
- **Margin link:** borrowed volume is not automatically informed shorting; it depends on who borrows and
  why. This is the basis for T6.

### F4 Shim (Seoul National University): lending balance and earnings reactions
- **Title:** "대차잔고와 이익공시에 따른 주가 반응 관계 연구" — «Остаток займов акций и реакция цен на публикацию прибыли»
- **Source:** https://www.dbpia.co.kr/journal/detail?nodeId=T13143041 · KR · 2013 master's thesis · 심창섭
  (abstract only)
- **Evidence:**
  - Stocks with a high lending balance earn smaller excess returns over trading days 2–126 after earnings.
  - In the 3-day window there is a short-covering overshoot.
  - Returns **reverse from month 2 to month 11**.
  - Lending does not equal short selling.
- **Margin link:**
  - High-borrow names underperform (≈ known #1), then reverse later. Check the persistent-borrow basket at
    2–8-week horizons, and consider exiting before a reversal.
  - The short-covering overshoot ≈ the repay-surge spike (known #2).

---

## G. Other material read (low value)

- **Kaiko Data Blog, "Exploring the Korean Crypto Market"** · EN, not Korean-authored · 2023-10-26
  - In 2023 YTD, more than 40 different Upbit instruments were #1 by daily volume on at least one day
    (XRP-KRW 70 days, BTC-KRW 64).
  - BTC was 9% and ETH 2% of Upbit volume. More than 75 Upbit instruments exceeded $1bn, all but two altcoins.
- **Decenter, "누가 어떻게 암호화폐 가격을 조작하는가"** · 심두보 · 2018-08-17
  - MITH +11,500% after its 2018 Bithumb listing; a WSJ count of 175 P&D episodes in Jan–Jun 2018; a list of
    methods. No rules.
- **smallake.kr (Korean HFT blog)** · ~2018-12
  - Summaries of P&D papers (3,767 Telegram / 1,051 Discord cases; 18% / 10% "successful"). No Korean data.
- **FMKorea, "두고두고 보려고 적어두는 킴단타 매매법"** · 2021-08-16 · discretionary TA, nothing testable.
- **Blockmedia, Glassnode-based (2026-10-22) and CryptoQuant-based (2026-05-20) funding/OI stories**
  - BTC- and altcoin-aggregate leverage commentary, no rules.
- **Gil & Kim, J. Industrial Studies (Dankook) 48(3), 2024** · crypto portfolio allocation vs KOSPI;
  irrelevant.

## Inaccessible or not found

- **Naver Blog and Cafe:** the search tool refuses these domains (crawler policy), so this major retail-strategy
  venue could not be read.
- **Blocked fetches:** coinpan.com posts and the Upbit help pages returned HTTP 403. Upbit help articles were
  read through the Zendesk JSON API instead.
- **Upbit notices API:** `api-manager.upbit.com` is behind Cloudflare from this sandbox. Scraping may need a
  normal IP or a headless browser. Listing times can be proxied by the first Upbit KRW candle (B9's method).
- **Paywalled papers:** RISS and DBpia full texts. Only abstracts were read for D2, D3, F3 and F4.
- **Search budget:** the cap of 200 searches per turn, shared across agents, ran out before DCInside, Brunch,
  Coinness and the Despread/Xangle archives were covered systematically.
- **Not found anywhere:**
  - Korean analysis of Binance cross-margin borrow/repay (MarginData-type) data or margin rates as signals;
  - liquidation-map (청산맵) strategies with explicit rules;
  - out-of-sample cross-sectional crypto factor papers on Korean data;
  - return statistics after Upbit 주의 flags.

---

## Top ideas to backtest

Common settings for all tests:
- Binance USDT-M perps; 15-min bars; fees and funding included.
- Excluded: coins whose 8 h funding at entry is below −0.1%, matching the existing basket rule.
- Report each test both unhedged and hedged with an equal-notional BTCUSDT long.
- Sample: 2024-10 to 2026-10, split at 2026-06-15 because of the B2 regime break.

### T1. Upbit KRW-listing fade on Binance perps (상장빔 숏)
- **Universe:**
  - every new Upbit KRW market where the token's Binance perp has traded for ≥7 days before the listing;
  - "fresh" listings tagged separately from BTC/USDT-market → KRW additions (B2: those pump less, median 19%).
- **Times and reference:**
  - t0 = the Upbit notice time if scraped, otherwise the first Upbit KRW 1-min candle (B9's method);
  - P0 = the perp close of the last 15m bar before t0.
- **Entry:**
  - Short at the close of the first 15m bar ending ≥45 min after t0, if the perp high since t0 is ≥ P0 × 1.15.
  - Variant: wait for the first 15m close below the prior bar's low after the post-t0 high.
- **Exit:** whichever comes first:
  - price ≤ P0 (full retrace);
  - stop at entry × 1.25;
  - time stop at 7 days.
- **Grid:**
  - entry delay {15, 45, 120, 360 min};
  - pump threshold {10, 15, 25, 40%};
  - time stop {1, 3, 7, 14 d};
  - stop {15, 25, 35%}.
- **Features to test:** pre-listing 24 h Binance volatility and volume (B9: they predict larger pumps); Upbit
  share of post-listing volume; quarterly initial turnover (B10).
- **Expected sample:** ~117 Upbit KRW listings in 2025 to Aug 2026, of which perhaps half have perps.
- **Sources:** B1 (median peak +33.6% at 36 min), B2 (day-7 close median 45% below day-1 high), B3, B5, B9, B10.

### T2. Bithumb-first pre-run-up: sell the Upbit open
- **Universe:** T1 events where the token traded on Bithumb KRW for ≥14 days before t0.
- **Condition:**
  - the Bithumb KRW price at t0 is ≥ 1.5 × its 7-day low; and
  - Bithumb 24 h turnover is ≥ 5 × its 14-day median.
- **Entry:** short at the close of the 15m bar containing the first Upbit KRW trade. Do not wait for a pump.
- **Exit:** 48 h, with take-profit at −25% and stop at +25%. Also log the day-7 result.
- **Control:** T1 events without a pre-run-up.
- **Hypothesis:** pre-run-up listings fade earlier and deeper. For PIEVERSE, the Upbit open of 1,431 was well
  below the Bithumb pre-notice high of 2,900; the Upbit high of 1,608 never revisited it; the price was −62%
  four months later. SPK and IRYS showed the same 3-day pre-notice pattern.
- **Sources:** B4.

### T3. Korean listing of a fresh Binance token as exit liquidity (설거지)
- **Universe:** tokens whose first Binance perp kline falls ≤14 days before their first Upbit or Bithumb KRW
  trade, including the same day.
- **Entry:** short at 15:00 UTC (00:00 KST) on the Korean listing day, i.e. the KST day-1 close (B3's anchor).
- **Exit:** time stop at 7 days; stop at +35%. Variants hold 3, 14 or 30 days.
- **Control:** fresh Binance perps without a Korean listing within 30 days, matched on perp age. This
  separates the Korean-listing effect from generic new-token drift and unlocks.
- **Monitoring:** record the funding paid.
- **Sources:**
  - B6: OPEN −30% in more than a week; ZKC −50% in 4 days; HOLO −40% in 7 days;
  - B3: −69.5% average from day-1 close for the 2025 cohort;
  - B2.

### T4. 09:00 KST clock-pump fade (약속의 09시)
- **Universe:** perps with a trailing-7-day Korean share ≥15%.
- **Trigger (all three):**
  - Upbit + Bithumb volume from 09:00 to 10:00 KST (00:00–01:00 UTC) is ≥5× its trailing-14-day median for
    the same hour;
  - the perp is ≥8% above its 08:45 KST (23:45 UTC) close at any 15m close between 09:00 and 11:00 KST;
  - there was no Upbit or Binance notice on the coin in the prior 24 h.
- **Entry:** short at the 11:00 KST (02:00 UTC) close, if the price is still ≥5% above the reference.
- **Exit:** the 08:45 KST close the next day (before the next reset), or when the price returns to the
  reference. Stop at +20%.
- **Placebos:**
  - the same rule at 15:00 and 21:00 KST;
  - the same rule at 00:00 UTC on coins with Korean share below 5%, to strip out the Binance daily-open and
    funding effect.
- **Second use:** tag known-#3 pumps that start between 09:00 and 10:00 KST and compare hit rate and maximum
  adverse excursion.
- **Sources:** C1 (about half of the nine episodes described fully round-tripped by the next morning; the
  rest only partly), C2 (BTC's worst returns from 09:00 to 11:00 KST), B11.

### T5. Weekly short basket on idiosyncratic Korean premium
- **Signal construction:**
  - For each coin with an Upbit KRW market and a Binance perp:
    prem_i = Upbit KRW close / (perp close × Upbit KRW-USDT close) − 1 (D10).
  - Idiosyncratic premium: idio_i = prem_i − prem_BTC, computed hourly.
- **Rebalance:** every Monday 00:00 UTC.
- **Universe:** coins with Upbit 7-day average turnover ≥ $2m.
- **Selection:** signal = mean idio_i over the last 72 h. Short the top 10 by signal where signal ≥ +2%.
- **Hedge and holding:** long BTC, or an equal-weight top-30 perp basket, at equal notional. Hold 1 week.
- **Exclusions:**
  - coins with a deposit-suspension notice in the last 7 days (caged, so arbitrage is blocked; report them as
    a separate bucket);
  - coins within 14 days of their Korean listing (they overlap T1 and T3).
- **Variants:**
  - rank by the 3-day change in premium instead of its level;
  - add a long leg on the bottom 10 (coins trading at a discount).
- **Sources:**
  - D5 (premiums fade as supply arrives);
  - B9 (premium spikes coincide with pumps);
  - E4 (≥10% is officially "abnormal");
  - D4 (the premium tracks retail attention);
  - A1–A4 (mechanism).

### T6. Separate kimchi-hedge borrowing from directional borrowing in MarginData
- **Status:** inference. Korean sources describe the hedge structure but never analyze Binance margin data.
- **(a) Refine known #1:**
  - For each persistent-borrow candidate, compute the average idio_i (from T5) over the borrow lookback.
  - Compare three variants:
    1. baseline;
    2. drop names with idio ≥ +2%;
    3. only names with idio ≥ +2%.
  - Hypothesis: variant 2 > baseline > variant 3. Borrowing that coincides with a Korean premium is the hedge
    leg of "buy Upbit + short Binance" trades and carries little negative information.
- **(b) Refine known #2:**
  - Tag repay surges within ±6 h of a premium collapse, defined as idio_i falling from ≥ +5% to ≤ +1% within
    24 h.
  - Compare forward 48 h returns of tagged and untagged surges under the existing repay-surge rule.
  - Hypothesis: hedge-unwind repays are mechanical and weaker. The opposite sign is possible if the Korean bid
    has vanished, so test both.
- **(c) Horizon check:** extend the persistent-borrow basket's holding to 2–8 weeks to look for a reversal
  (F4: short-covering overshoot and reversal after month 2).
- **Data:** MarginData from 2025-02, Upbit KRW candles, Binance perps.
- **Sources:** D7–D9 (hedge practice), F2 (forced-repayment spikes are transient), F3 and F4 (borrowing is
  not the same as informed shorting).

### T7. Shorts on Korean negative notices, plus flag reconstruction
- **Events:** Upbit and Bithumb notices for coins that have a Binance perp:
  - (a) 유의종목 지정 (caution designation);
  - (b) 거래지원 종료 (delisting decision).
- **Entry:** short at the first 15m close after the notice timestamp.
- **Exit:** 24 h (B1: Upbit delisting trough median −12.7% at 16.3 h; Bithumb −22.4% at 5.9 h). Stop at +20%.
- **Skip:** coins with Korean share ≥50% over the prior 7 days. This avoids caged "유의빔" and "상폐빔"
  squeezes (A6: BTG +228%, SBD +521%).
- **(c) Reconstructed flag (from E4):**
  - The Upbit "global price difference" flag is |prem_i| ≥ 10% sustained for ≥30 min.
  - Use it as a feature of known #3 (does a ≥ +10% gap at pump time raise the reversal rate?), not as a
    standalone short.
  - Exclude coins with an active deposit suspension: caged spikes do not transmit to Binance (A2–A5).
- **Negative control:** forward Binance-perp returns after deposit-suspension notices. Base rate from A2: 23.5–28.6% produce >20% Korean spikes.
- **Sources:** B1, E4, A2–A6.

### T8. Korean-heat regime filter
- **Gauges:**
  - USDT premium u = Upbit KRW-USDT close / official USD/KRW − 1 (D4);
  - BTC premium b = Upbit KRW-BTC / (Binance BTCUSDT × USD/KRW) − 1.
- **Regimes:**
  - hot: u ≥ its 90-day 80th percentile, or b ≥ +5%;
  - cold: u ≤ its 20th percentile, or b ≤ 0 (reverse premium, 역프).
- **Test:** compare known #3, T1, T4 and T5 by regime on hit rate, mean return and stop-outs.
- **Hypotheses:** Korean-pump shorts work best in hot regimes (larger retail overshoot). The listing fade weakens
  when listing liquidity is cold (B2, B10).
- **Standalone variant:** when b crosses above +5%, short an equal-weight basket of the 20 perps with the
  highest Korean share. Hold 7 days, hedged with BTC. CryptoQuant's ≥16% "top" level (D6) is too rare in this
  sample.
- **Caveats:** the premium's link to volatility is unstable (D3), and its level depends on USD/KRW (D1).
