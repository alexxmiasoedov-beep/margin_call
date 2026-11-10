# Korea: how Korean practitioners, research firms, media, exchanges and regulators use on-chain and exchange-flow data to trade altcoins (Upbit, Bithumb, Coinone, Korbit; coins with Binance USDT-M perps)

Research date: 10.11.2026. Searches were mostly in Korean. Tags used below: **[def]** official definition or rule; **[quant]** quantified finding; **[case]** anecdote or single case; **[claim]** opinion or interpretation; **[snapshot]** my own call to a free public API on 2026-11-10 09:16 UTC (18:16 KST). "Search summary" means the text came from a search-engine summary and the page itself was not opened. Treat those items as weaker.

Main finding for the bot owner: in the Korean sources I found, the most useful "on-chain" signal for Korean altcoin flows is not a wallet tracker. It is the exchanges' own deposit-surge and market-alert flags, which can be read free and without keys (Upbit `market_event`, Bithumb `virtual_asset_warning` and `assetsstatus`). Wallet-level tracking of Upbit/Bithumb deposits needs entity clustering (CryptoQuant, Arkham), which is paid or partly closed. It also breaks when exchanges rotate wallets.

## Q1. Which Korean sources are most credible and most used, and what methods do they describe?

### Takeaway
The strongest Korean primary sources are the exchanges themselves (the Upbit 2024 transparency report, the Upbit and Bithumb public APIs and notices) and the regulator (FSC/FSS press releases on unfair trading). Research firms add structural studies of listings and the kimchi premium: Tiger Research, Four Pillars, the KIF report reposted by Xangle, and a 2026 Yonsei paper in a KCI journal. CryptoQuant is the most-cited on-chain vendor in Korean media, but it is used mostly for market-wide deposit metrics and a few exchange-specific reserves (e.g., XRP on Upbit). I found it used much less for per-altcoin Upbit/Bithumb flows. Korean media mostly relay these metrics, or rebuild episodes from exchange price and volume data, without on-chain evidence.

### Cited Findings
**Exchanges and regulator (primary)**
- [def] Upbit runs a dedicated surveillance unit with three teams: 상시감시팀 (continuous monitoring), 심리분석팀 (trade analysis and referral to authorities) and 온체인모니터링팀 ("on-chain monitoring team, in charge of on-chain data analysis related to abnormal-trading assets"). It also runs the UMO (Upbit Market Oversight) system and an automated "account-linkage analysis" system. (2024 report) — [Upbit 2024 transparency report (PDF)](https://static.upbit.com/reports/transparency_report/upbit_transparency_report_2024.pdf)
- [def] Upbit monitors circulating supply (유통량 모니터링) in three steps. It collects each project's issuance and unlock plan (발행 및 보호예수 해제 계획), receives the project's wallet addresses (지갑주소를 전달받아) and compares the plan, those wallets and public info platforms. Upbit says it is the only Korean exchange that publishes each project's 유통량 계획표 (supply schedule) in the asset info tab, and it has run a 유통량 이슈 제보 (supply-issue tip-off) channel since 01.12.2023. — [Upbit 2024 transparency report (PDF)](https://static.upbit.com/reports/transparency_report/upbit_transparency_report_2024.pdf)
- [def] Bithumb says it is the only Korean exchange that publishes, for each coin every 10 minutes, the holding share and trading share of the top-10 accounts (상위 보유자 10명의 보유 비중과 거래 비중). The FSC said it is considering how this is disclosed, because some investors or syndicates do "추종매매" (copy/follow trading) off this indicator. (13.10.2026) — [Newsway](https://www.newsway.co.kr/news/view?ud=2026101309511600235)
- [def] FSC two-year review of the Virtual Asset User Protection Act (가상자산이용자보호법, in force 19.07.2024), published 20.07.2026. The FSC built "AI-based surveillance that analyses manipulation second by second (초 단위) and finds suspect groups and suspect intervals automatically". Exchanges must run abnormal-trading extraction criteria and report to the FSC/FSS. — [FSC press release 87357](https://www.fsc.go.kr/no010101/87357?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)

**Research firms and academic work**
- [quant] Tiger Research, "김치 프리미엄 현상 총정리" (Kimchi Premium 101), by Jay Jo with Kaiko data, 07.11.2024. Findings:
  - Each Korean exchange has its own liquidity pool, and foreigners are excluded.
  - Travel-rule-confirmed outflows of ≥1M KRW to overseas VASPs were about 52 trillion KRW in H1 2024, about 2× H2 2023.
  - Days with premium >5% in H1 2024 were 5.6× the H2 2023 count.
  - Premium spikes on transfer-blocked or newly listed coins: CRV about 700% (Aug 2023, withdrawals halted), AVAIL about 1,255% at the Bithumb listing (Jul 2024, later about 3%), USDC 165% at the Bithumb listing.
  - The report also mentions 가두리 펌핑 and an FIU probe of many elderly accounts trading via API from the same overseas IP.
  — [Tiger Research](https://reports.tiger-research.com/p/kimchi-premium-101-kor); mirror at [TokenPost research 133](https://www.tokenpost.kr/research/133)
- [quant] Four Pillars, "2025 한국 거래소 원화 상장 토큰 사후 진단 보고서", by c4lvin, 11.03.2026. Sample: 59 Upbit and 144 Bithumb KRW listings in 2025, each bought at the listing-day close and held to 11.03.2026.
  - Portfolio ROI: Upbit −69.5%, Bithumb −69.1%; Binance −71.7% on Messari's 92 listings.
  - Median ROI: −80.9% and −82.1%.
  - Only 2 of 59 Upbit tokens were positive (KITE +232.8%, BARD +9.3%).
  - The 50 tokens listed on both exchanges averaged −69.4%, versus −68.9% for the 94 Bithumb-only tokens.
  - The report has no on-chain or supply-side (unlock, airdrop, market-maker) analysis. — [Four Pillars](https://research.4pillars.io/ko/research/2025-korean-cex-listings-post-mortem)
- [quant] Korea Institute of Finance (KIF) report "한국의 가상자산시장과 '펌프앤덤프' 현상에 대한 고찰", reposted by Xangle 09.08.2023:
  - Method: Kamps–Kleinberg moving-average thresholds on hourly OHLCV of "김치코인" (Korean-issued or mainly Korea-traded coins), Oct 2021, 16,560 observations.
  - Up to about 4.7% of hourly observations were flagged as pump-and-dump. 60–80% of pumps were followed by dumps (80.39% under the strictest rule). 21 of 23 kimchi coins (91.3%) showed the pattern.
  - 389 of 625 listed coins (62.24%) traded on only one Korean exchange. — [Xangle](https://xangle.io/research/detail/1425)
- [quant] Park, Lee and Kim (Yonsei), JKSCI vol. 31 no. 2, Feb 2026, a KCI journal:
  - Sample: 144 Upbit KRW listings 2021–2025; 107 of them were already on Binance USDT.
  - Features: pre-listing Binance 1-minute price and volume statistics, plus Bitcointalk/Altcointalk mention z-scores.
  - Target "surge ≥5% within 1 day after Upbit listing": MLP AUC 0.83–0.84, top-decile precision 0.50, lift 1.70.
  - Target "surge plus Upbit–Binance premium": logistic regression with social factor, AUC 0.89.
  - Top cases: MINA (24.10.2023) max return 116.6% with max Upbit–Binance gap 280.3%; 0G (22.09.2025) 78% and 264%; SEI (16.08.2023) 153.8% and 130.9%.
  - Top cases had high pre-listing Binance volume and volatility.
  - The paper cites Korea at about 9% of global spot volume and Upbit at about 70% of domestic volume. — [JKSCI PDF](https://journal.kci.go.kr/jksci/archive/articlePdf?artiId=ART003305943); DOI [10.9708/jksci.2026.31.02.087](https://doi.org/10.9708/jksci.2026.31.02.087)

**CryptoQuant as cited in Korean media**
- [quant] Altcoin deposit transactions to exchanges, 7-day cumulative: about 29,800 on 14.09.2026, about 78,000 on 28.09.2026 (+160%), the highest since Oct 2025. Depositing addresses roughly tripled. CryptoQuant links this to likely selling. (Sep–Oct 2026) — [DigitalToday](https://www.digitaltoday.co.kr/news/articleView.html?idxno=704320)
- [quant] Earlier: altcoin deposit transactions about 45k/day, the highest in about 2 months; BTC exchange inflow about 49k BTC on 30.06.2026. (Jul 2026) — [Blockmedia](https://www.blockmedia.co.kr/archives/1113148)
- [def] Exchange Whale Ratio = share of the top-10 inflows in total exchange inflow (CryptoQuant). — [CryptoQuant](https://cryptoquant.com/asset/btc/chart/flow-indicator/exchange-whale-ratio)
- [def] Korea Premium Index = percent difference between the VWAP on Korean exchanges and on other exchanges. — [CryptoQuant user guide (KO)](https://userguide.cryptoquant.com/ko/cryptoquant-metrics/fund-premium/korea-premium-index)
- [quant] CryptoQuant per-exchange XRP reserves, 28–30.10.2026 per the article: Upbit 6.42B → 6.44B XRP; Bithumb 1.847B → 1.837B; Binance 2.69B → 2.47B. The article warns that a falling balance alone does not reveal intent. (31.10.2026) — [TokenPost](https://www.tokenpost.kr/news/cryptocurrency/430597)
- [quant] Upbit's "XRP 순 지갑 흐름 지배율" (share of net wallet flow) went from 13% on 07.06.2026 to 31% on 14.06.2026, the highest since May 2024. It was read both ways: momentum shift, or "whales preparing to take profit". (15.06.2026) — [Pinpoint News](https://www.pinpointnews.co.kr/news/articleView.html?idxno=460314)

**Media and community methods**
- [case] Blockmedia's "[상장빔의 민낯]" series (07.08.2026) rebuilds listing episodes from hourly price and volume data on both exchanges. The article itself says there is no on-chain evidence, and that price and volume alone cannot prove leaks or manipulation. — [Blockmedia](https://www.blockmedia.co.kr/archives/1124820)
- [claim] Korean guides describe the usual tool stack: Etherscan, Solscan and Blockchair for transactions; Arkham, Nansen and DeBank for entity labels. They read exchange inflow as possible selling and outflow as holding, and warn that on-chain data cannot see trades inside an exchange. (Search summary) — [Coinyong guide](https://coinyong.com/guide/onchain-analysis-guide)
- [case] Korean-language on-chain whale items often come from foreign sleuths in translation. Example: an Onchain Lens item, translated by ChainCatcher KR, about a whale buying 1,267,251 ACX after a Binance listing notice and depositing it all to Binance. — [ChainCatcher KR](https://www.chaincatcher.com/ko/article/2155600)
- [claim] A Korean-language TechFlow piece warns against reading wallet moves as whale accumulation. — [TechFlow KR](https://www.techflowpost.com/ko-KR/article/35202)

**Glossary (Korean — English — Russian)**
- 입금량 급등 — deposit-volume surge — всплеск депозитов
- 거래량 급등 — volume surge — всплеск оборота
- 가격 급등락 — sharp price swing — резкий рост/падение
- (글로벌) 가격 차이 — gap to global price — расхождение с мировой ценой
- 소수 계정 거래 집중 — concentration of trading in a few accounts — концентрация в немногих аккаунтах
- 주의 종목 / 시장 경보 — caution flag / market alert — предупреждение
- (거래) 유의 종목 — warning designation, the step before delisting — «под наблюдением», кандидат на делистинг
- 거래지원 종료 — delisting — делистинг
- 입출금 중단 — deposit/withdrawal suspension — приостановка ввода/вывода
- 가두리 펌핑/가두리빔 — "fish-cage pump", a pump while transfers are blocked — памп в «садке»
- 유의빔 / 상폐빔 — pump after a warning designation / pump before delisting — памп после предупреждения / перед делистингом
- 상장빔 — listing pump — листинговый памп
- 경주마 — "racehorse", orders timed to the daily-change reset to reach the top-gainers list — «скаковая лошадь»
- 김프 / 역프 — kimchi premium / discount — кимчи-премия / дисконт
- 유통량 계획(표) — circulating-supply schedule — график обращения
- 재단 지갑 — foundation wallet — кошелёк фонда
- 세력 — syndicate — «силы», манипуляторы
- 추종매매 — follow/copy trading — сделки вслед
- 고가매수 / 허수주문 — high-price buy orders / spoof orders — покупка по завышенной цене / фиктивные заявки
- 순유입/순유출 — net inflow/outflow — чистый приток/отток

### Inferences
- For Korean-retail flows, the exchanges are the most credible "on-chain-adjacent" data publishers. Upbit has its own on-chain team, collects project wallets and publishes supply schedules. Bithumb publishes top-10 account concentration. Research firms do not publish per-coin Upbit/Bithumb deposit flows, and CryptoQuant's exchange-specific coverage appears in Korean media only for majors such as XRP.
- The Korean research consensus (Four Pillars, KIF, JKSCI) is that Korean listings and kimchi-coin pumps mean-revert hard. That matches the owner's s15 result: shorting after Korean listings works.
- JKSCI suggests the size of a Korean listing pump is partly predictable from Binance pre-listing activity. This is directly testable with free data: Binance 1m klines plus Upbit minute candles.

### Gaps
- I found no Korean-language methodology from Xangle (beyond the KIF repost and 유의 event pages), DeSpread, Coinness, 한경 코알라, CoinDesk Korea, Kaia or other Korean foundations, or the Upbit Investor Protection Center/UDC that defines per-altcoin Upbit/Bithumb flow metrics. These were not reached within the search budget; they may exist.
- I did not find a CryptoQuant Korean QuickTake that tests altcoin flows into Upbit or Bithumb specifically, beyond XRP reserves and dominance.
- A KAIST thesis claim (an Lee/An 2025 study of 18 Upbit cases with volume up ≥10,000% vs the previous day, April–Dec 2024, showing pump-then-dump) appeared only in a search summary. I could not verify it.

## Q2. What concrete, testable rules do Korean sources claim about Korean exchange flows, and what quantified evidence exists?

### Takeaway
Six rules recur, and only a few have numbers:
1. The listing run-up happens before or around the listing, and decay follows (strong quantified evidence).
2. Transfer-blocked coins (가두리) and warning-designated coins (유의빔/상폐빔) pump inside Korea, then collapse when arbitrage reopens or delisting comes (many cases; the FSC names 가두리 as a manipulation technique).
3. 유의종목 designation usually ends in delisting (81% of resolved cases; median 17 days).
4. Deposit surges mean supply arrives to sell, as written into the exchange flags. I found no published return study.
5. A high kimchi premium goes with large listing pumps and outflow arbitrage (some quant).
6. Market-wide altcoin exchange deposits rising means volatility or selling ahead (CryptoQuant; no outcome stats).

### Cited Findings
**Listing pumps and decay**
- [quant] Upbit coins rose on average +60.2% from the listing notice to the actual listing (20 listings, May–Jul 2025), about 3× other exchanges. The source is unnamed "industry". (12.08.2025) — [Herald Business](https://mbiz.heraldcorp.com/article/10552038)
- [quant] Returns from the listing-day close to 11.03.2026: Upbit −69.5%, Bithumb −69.1%, median about −81% (see Q1). — [Four Pillars](https://research.4pillars.io/ko/research/2025-korean-cex-listings-post-mortem)
- [case] PIEVERSE, Bithumb-listed since 24.11.2025, Upbit notice 20.04.2026 14:00 KST, trading from 16:00.
  - On Bithumb it rose 629 → 2,900 KRW (+361%) before and around the notice. Bithumb volume went 1.16B KRW on 17.04 → 18.08B on 19.04 → 198.12B on 20.04.
  - Upbit's first hour traded 59.12B KRW. Combined 24h volume peaked at 568.5B KRW on 21.04, then fell 69.8% within a day.
  - On 21.04 Bithumb cut per-transaction and daily withdrawal limits by 98.6%.
  - Price was −62% from the peak by 06.08.2026.
  - Blockmedia estimates that ">90% of the expected listing move was completed on Bithumb before the Upbit notice". The same article covers SPK and IRYS: IRYS volume was 93× normal three days before its Upbit notice. — [Blockmedia, 07.08.2026](https://www.blockmedia.co.kr/archives/1124820)
- [quant] JKSCI 2026: pumps after Upbit listing, and the premium over Binance, are predictable ex ante (AUC up to 0.89). — [JKSCI](https://journal.kci.go.kr/jksci/archive/articlePdf?artiId=ART003305943)
- [quant] Listing supply grew: 95 new Upbit KRW listings in the CEO's first year vs 53 in the prior year (1.8×). The share of profitable listings was 1.9% vs 8.4%. (Search summary, 2026) — [Nexblock](https://www.nexblock.co.kr/article/1002442)

**가두리 (transfer-blocked) pumps — named by the FSC as a manipulation technique**
- [def] FSC, 20.07.2026: '가두리' = "using a temporary block of deposits/withdrawals of a coin on one or some exchanges to push the price up, then disposing of holdings". The other named techniques were '경주마', API high-frequency trading, API-key rental, '대형고래' (including overseas-exchange-linked manipulation) and SNS pre-buy meme schemes. — [FSC 87357](https://www.fsc.go.kr/no010101/87357?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [case] LumiWave (LWA), Coinone: transfers halted 14.10.2024; on 16.10 the price went 34 → 299 KRW (+780%), then 80. On Bithumb: 31 → 43 (+40%).
  [case] Radiant (RDNT), after its hack, Coinone: 93 → 500 KRW (+438%), close 280. On Bithumb: 97 → 183 (+90%). — [Bizwatch, 22.10.2024](http://news.bizwatch.co.kr/article/mobile/2024/10/21/0012)
- [case] Upbit hack on 27.11.2025 (445억 KRW, corrected from 540억; Solana-based assets). Upbit halted deposits and withdrawals for all assets.
  - ORCA rose +72% in a day on Upbit (to 2,830 KRW) — [News1](https://www.news1.kr/finance/blockchain-fintech/5990490); [Fnnews](https://www.fnnews.com/news/202511271509265963)
  - Jito traded >35% above the global price, and ORCA's 24h turnover was about 3,300억 KRW — [Hankyung, 28.11.2025](https://www.hankyung.com/article/2025112825811)
- [case] GMT: about +500% on Bithumb while transfers were halted for hacking, with a >200% premium over Binance, then a crash after reopening (search summary). — [Sedaily Signal](https://signal.sedaily.com/article/13501504)

**유의빔 / 상폐빔 (warning and delisting pumps)**
- [case] Steem Dollars (SBD) was designated 유의 on Upbit on 30.12.2024 and rose 2,800 → 17,400 KRW (+521%) by 09.01.2025. Upbit had 99% of CoinMarketCap volume. BTG rose +228% in a day about 2 weeks before delisting. The next day Kobato fell 20.2%, Alpha Quark 12.8% and Strike 9.0%.
  An analyst quoted in the article: "the core of 유의빔 and 상폐빔 is 가두리빔", because Upbit halts deposits after designation. The article also describes "순환펌핑" (rotation into the next likely designation). (10.01.2025) — [Newsis](https://www.newsis.com/view/NISX20250110_0003028508)
- [quant] 219 유의 designations on Upbit (49), Bithumb (102) and Coinone (68), Jan 2025–Sep 2026.
  - Of 148 with a known outcome, 120 (81%) ended in delisting and 28 were lifted.
  - Designation to delisting decision: median 17 days (range 9–91); 100 of 120 decisions came within 30 days. Designation to lift: median 29 days.
  - The author warns that missing lift notices may inflate the delisting share. — [Economybloc](https://economybloc.com/article/122051/)
- [case] Reasons for designations: supply-plan violations ("유통량 계획을 공시 없이 임의로 변경"). Example: Boundless (ZKC), designated about 17 days after listing by DAXA members jointly. Others: STMX (May 2025, issuance and supply-plan changes), BTG (Feb 2025, non-disclosure), FLOW (Dec 2025, hack). (Search summary) — [MT](https://www.mt.co.kr/stock/2025/10/18/2025101715533581444); [Blockmedia FLOW](https://www.blockmedia.co.kr/archives/1025777)

**Deposit surges as a sell-supply signal**
- [def] Deposit surge is one of the five DAXA alert types, built into the exchange flags (definitions in Q4). — [Etoday, 04.07.2023](https://www.etoday.co.kr/news/view/2262834)
- [case] BONK, 2026:
  - A governance attack moved about 4.43 trillion BONK (about 5% of supply, about $20M) from the foundation treasury to an attacker wallet. The proposal passed with 99.9%, with only 7 wallets voting.
  - The four KRW exchanges designated BONK 유의 on 07.07.
  - Upbit and Coinone delisted it. Bithumb lifted the designation on 07.08, reopened deposits and added BONK to a deposit-reward promotion (입금왕).
  - BONK deposits to Bithumb then rose >500% above normal, triggering the '위험' (danger) label. — [Bloter, 11.09.2026](https://www.bloter.net/news/articleView.html?idxno=673419)
- [quant] CryptoQuant: a +160% rise in altcoin deposit transactions over two weeks (Sep 2026) was read as "selling likely". No forward-return statistics were given (see Q1). — [DigitalToday](https://www.digitaltoday.co.kr/news/articleView.html?idxno=704320). The counter-view: "deposits are positioning, not executed trades" — [Nestree](https://www.nestree.io/altcoin-exchange-deposits-surge-2026/)

**Kimchi premium and flows**
- [quant] Premium >5% days rose 5.6× between H2 2023 and H1 2024, alongside large travel-rule outflows (about 52 trillion KRW in H1 2024). — [Tiger Research](https://reports.tiger-research.com/p/kimchi-premium-101-kor)
- [quant] Listing pumps on Upbit come with large Upbit–Binance gaps (MINA 280%, 0G 264%, SEI 131%). — [JKSCI](https://journal.kci.go.kr/jksci/archive/articlePdf?artiId=ART003305943)

### Inferences
- Rule types 2 and 3 (가두리, 유의빔) are **Korea-internal**. When transfers are blocked, Korean prices decouple from Binance, so these pumps are not by themselves a Binance-perp short signal. The Binance-relevant cases are pumps with open transfers: listings, and broad retail rotations with high Korea volume share. That is what s15 already exploits.
- A deposit surge on Upbit or Bithumb for a coin already pumping in Korea is the closest public proxy for "supply arriving to sell into Korean retail". It fits the owner's finding that Korean flows predict Binance declines, but no Korean source has tested it.
- FREE-TEST 1: compare Binance returns over 1–7 days after deposit-flag onsets, for coins with a Binance perp, against a same-coin placebo, as in s15. Upbit `DEPOSIT_AMOUNT_SOARING` is already logged by the bot (`upbit_flags.csv` since 10.11.2026; first week in s17: D-flag shorts +4.4% at 48h, n=20 over 17 coins; V+D the same day +6.7%, n=7; too few to conclude) — [research/s17/ВЫВОДЫ.md](../../../s17/ВЫВОДЫ.md). The missing piece is Bithumb `DEPOSIT_AMOUNT_SUDDEN_FLUCTUATION`, which carries a CAUTION/WARNING/DANGER step and also flags coins that have no Upbit market (in the 10.11 snapshot: PEPE, MERL, AVL, Q, AXIS). History must be collected going forward; see Q4.
- FREE-TEST 2: the 유의 designation (Upbit `market_event.warning` flipping to true, or Bithumb `market_warning`=CAUTION) leads to delisting in about 81% of resolved cases within a median of 17 days. Test the Binance perp path from designation to delisting, and separately the "유의빔" window.
- FREE-TEST 3: replicate the JKSCI predictor for the s15 listing journal: Binance pre-listing volume and volatility versus the size of the Korean pump and the later decline.

### Gaps
- I found no public study of price or returns after Upbit or Bithumb deposit-surge flags (searched in Korean; none found). The question is open.
- I found no quantified Korean study linking "large on-chain deposit of token X into Upbit/Bithumb" to later Korean or Binance returns. The evidence is anecdotal or flag-based.
- I found no source documenting "상장 전 입금" (deposits opened before trading starts) as a measurable signal.

## Q3. How do Korean practitioners identify Upbit/Bithumb wallets and deposit addresses, and which free tools do they use?

### Takeaway
Identification relies on third-party entity labels: Etherscan public labels, Arkham and Nansen, and CryptoQuant entity data, which covers Upbit and Bithumb reserves at least for XRP. Free labels are partial. The Etherscan "Upbit" label page shows only "Upbit 1–7" without login. Exchanges rotate wallets: Upbit replaced its wallets after the 27.11.2025 hack. Upbit and Bithumb use per-user deposit addresses that sweep into hot wallets, so free tracking of individual deposits is hard, and one documented data artifact (XRP "leaving" Upbit) misled watchers.

### Cited Findings
- [snapshot] Etherscan's public label page for Upbit lists "Upbit 1" to "Upbit 7"; more entries sit behind sign-in. — [Etherscan](https://etherscan.io/accounts/label/upbit)
- [def] After the hack, Upbit moved to new wallets, told users to issue new deposit addresses, and to delete old Upbit addresses saved in personal wallets or other exchanges. (Dec 2025) — [Dunamu news](https://www.dunamu.com/news/1569); [TheElec](https://www.thelec.kr/news/articleView.html?idxno=44624)
- [quant] CryptoQuant's per-exchange XRP reserves cover Upbit and Bithumb (Upbit 6.44B XRP, Bithumb 1.84B, 30.10.2026). — [TokenPost](https://www.tokenpost.kr/news/cryptocurrency/430597)
- [quant] XRPwallets/Harvest, 29.10.2026: Upbit about 6.41B XRP, 2.9× Binance. Thirteen Korean exchange wallets together hold about 8.55B XRP, 8.6% of supply. (Search summary) — [Harvest XRP rich list](https://harvest.finance/ko/xrp-rich-list)
- [case] In June 2025 CryptoQuant data showed Upbit's XRP balance falling from >6B (18.06) to about 1B. A YouTuber posted "5.5B XRP withdrawn from Upbit". Upbit gave no comment, and analysts suspected a data error or rebalancing. (27.06.2025) — [Investing KR](https://kr.investing.com/news/cryptocurrency-news/article-1530716). Upbit was back at about 6.4B XRP by Oct 2026 — [TokenPost](https://www.tokenpost.kr/news/cryptocurrency/430597)
- [claim] The free stack named in Korean guides: Etherscan, Solscan, Blockchair, Arkham, Nansen, DeBank. On-chain data cannot see trades inside an exchange. (Search summary) — [Coinyong](https://coinyong.com/guide/onchain-analysis-guide)
- [claim] A Korean Telegram directory lists CryptoQuant's Korean alert channel (@cq_alert_kr) for large BTC exchange deposits, plus the official Upbit and Bithumb notice channels. (Search summary) — [telegram.pe.kr](https://www.telegram.pe.kr/channels/collections/korea-crypto-official)
- [case] Hobbyist Korean tooling exists, such as an "온체인 선행 포착" (on-chain early detection) Telegram bot on GitHub. Its quality is unverified. — [GitHub onchain-radar](https://github.com/sepower384/onchain-radar)
- [def] Upbit itself receives wallet addresses directly from projects to monitor supply. It does not say these addresses are published. — [Upbit 2024 transparency report (PDF)](https://static.upbit.com/reports/transparency_report/upbit_transparency_report_2024.pdf)
- [snapshot] Upbit's wallet-status endpoint (deposit/withdrawal suspensions) needs an API key: `https://api.upbit.com/v1/status/wallet` returns `no_authorization_token`. Bithumb's equivalent is public: `https://api.bithumb.com/public/assetsstatus/ALL`. On 10.11.2026, 57 of 524 assets had deposits suspended and 4 had withdrawals suspended (WAVES, ENJ, INIT, USD1). — [Upbit API](https://api.upbit.com/v1/status/wallet); [Bithumb API](https://api.bithumb.com/public/assetsstatus/ALL)

### Inferences
- With free data and no keys, wallet-level tracking of Upbit/Bithumb deposits for ERC-20 altcoins is possible only in principle. One would need labelled hot-wallet lists (partial and stale after rotations) and public-RPC `eth_getLogs` for Transfer events. This is fragile; the exchange flags in Q4 are the cheaper proxy.
- Bithumb `assetsstatus` gives a free, real-time feed of deposit/withdrawal suspensions, the precondition for 가두리. For Upbit, suspensions are visible only through notices or a key.

### Gaps
- I found no public, maintained list of Upbit/Bithumb deposit-sweep or hot wallets, nor how many addresses CryptoQuant or Arkham attribute to them.
- I could not confirm which altcoins (beyond BTC, ETH, XRP and stablecoins) CryptoQuant tracks per Korean exchange. The documentation pages were not reached.

## Q4. What do Korean exchanges and regulators publish that can serve as on-chain-adjacent signals, and how are the flags defined?

### Takeaway
All five KRW exchanges run the DAXA "시장 경보" (market alert) system, launched 04.07.2023, with five caution types: price swing, volume surge, deposit surge, global price gap, and concentration in few accounts. Upbit publishes exact windows. Volume, deposit and few-account flags use a 24h window ending 09:00 KST, are posted at 10:00 KST and last 24h. Thresholds are ranges (100–300%, 40–80%), set per coin. Bithumb adds three severity steps (CAUTION/WARNING/DANGER). Both exchanges expose current flags in free public APIs.

### Cited Findings
**DAXA framework (04.07.2023)**
- [def] DAXA caution types:
  - Price ±50% in 24h
  - Volume +100–300% "over the last 1–10 days"
  - Deposits +100–300% "over the last 1–10 days"
  - Price ≥5% away from CoinMarketCap
  - Few-account buy/sell participation 40–80%+ in 24h
  Each exchange sets exact values inside these ranges, per coin. Badges show in the trading window for up to 24h, and monitoring is real-time. — [Etoday](https://www.etoday.co.kr/news/view/2262834)

**Upbit (2024 transparency report: "업비트 시장 경보 안내")**

| Flag | Criterion | Posted | Released |
|---|---|---|---|
| 가격 급등락 | ≥50% move vs the previous day's close (last trade before 09:00 KST) | when it happens | when resolved |
| 거래량 급등 | volume in the 24h to 09:00 KST up ≥100–300% vs the prior 24h | 10:00 KST | after 24h |
| 입금량 급등 | deposits in the 24h to 09:00 KST up ≥100–300% vs the prior 24h | 10:00 KST | after 24h |
| 가격 차이 | ≥±5% vs the CoinMarketCap price | when it happens | when resolved |
| 소수 계정 집중 | top-account buy (sell) participation ≥40–80% in the 24h to 09:00 KST | 10:00 KST | after 24h |

The volume, deposit and few-account flags are marked "신규" (new); the other two existed before. — [Upbit 2024 transparency report (PDF)](https://static.upbit.com/reports/transparency_report/upbit_transparency_report_2024.pdf)

- [def] Upbit's help centre on few-account flags: issued when a rise comes with high buy participation by top accounts, or a fall with high sell participation. Exact exception rules are withheld "to prevent abuse and evasion". (Search summary; the page returned 403) — [Upbit support](https://support.upbit.com/hc/ko/articles/900005994766)
- [def] API: `GET https://api.upbit.com/v1/market/all?is_details=true` returns `market_event.warning` (bool, the 유의 designation) and `market_event.caution` with the booleans `PRICE_FLUCTUATIONS`, `TRADING_VOLUME_SOARING`, `DEPOSIT_AMOUNT_SOARING`, `GLOBAL_PRICE_DIFFERENCES` and `CONCENTRATION_OF_SMALL_ACCOUNTS`. The older `market_warning` string field is deprecated, and code still reading it silently lets flagged coins through. — [AlgoLab blog (2026)](https://algolab.co.kr/blog/altcoin-bot-universe-filter-upbit-2026); confirmed by my call.
- [snapshot] Upbit, 10.11.2026 09:16 UTC: 881 markets.
  - Flags are per asset, repeated across the KRW/BTC/USDT markets.
  - `DEPOSIT_AMOUNT_SOARING`: PIEVERSE, NXPC, AVAX, SOL.
  - `TRADING_VOLUME_SOARING`: PROM, WAVES, PIEVERSE, NXPC, AVAX, SENT, RENDER, ZIL (KRW), plus ENJ and CYS (BTC markets).
  - `CONCENTRATION_OF_SMALL_ACCOUNTS`: none.
  - `GLOBAL_PRICE_DIFFERENCES`: 175 markets, mostly thin BTC/USDT books. Only 6 KRW markets: EGLD, MANTRA, BLUR, SOPH, ZIL, ELF. All five KRW 유의 coins (EGLD, MANTRA, BLUR, SOPH, ZIL) also carried the price-gap flag.
  — [Upbit API](https://api.upbit.com/v1/market/all?is_details=true)

**Bithumb**
- [def] Bithumb's alert system (upgraded 06.08.2026) shows [주의]/[경고]/[위험] (CAUTION/WARNING/DANGER) for five types. Exact detection criteria are withheld "to prevent abuse and evasion", and trigger values may change within ranges.
  Exclusions:
  - Assets with global market cap ≥1조 KRW are excluded from the few-account flag.
  - Coins listed <96 hours ago are excluded from volume and deposit surge flags, because there is no comparison base.
  (Search summary of the Bithumb notice and X post; the notice returned 403) — [Bithumb notice 1643939](https://feed.bithumb.com/notice/1643939); [Bithumb on X](https://x.com/BithumbOfficial/status/2044329666870448614)
- [def] Bithumb's deposit surge compares the last 24h of deposits with the daily average of the previous 3 days. It is recalculated continuously and shown when the increase passes an undisclosed ratio. The flag disappears when deposits converge to the 3-day average. — [Bloter, 11.09.2026](https://www.bloter.net/news/articleView.html?idxno=673419)
- [def] Bithumb few-account bands seen in its UI: "소수계정 50% 이상 75% 미만" and "75% 이상 90% 미만". In one case (DAgent AI, listed 08.10.2026) the top-10 trading share was 93% while the badge showed 50–75%, a lag in the flag. Doppler Finance had a 90% top-10 share and daily turnover of 160.3B KRW (about 12× BTC), more than 60× its internal Bithumb float of 73.82M tokens. — [Newsway, 13.10.2026](https://www.newsway.co.kr/news/view?ud=2026101309511600235)
- [def] APIs:
  - `GET https://api.bithumb.com/v1/market/virtual_asset_warning` returns `{market, warning_type, warning_step, end_date}`. Observed types: `PRICE_SUDDEN_FLUCTUATION`, `TRADING_VOLUME_SUDDEN_FLUCTUATION`, `DEPOSIT_AMOUNT_SUDDEN_FLUCTUATION`, `PRICE_DIFFERENCE_HIGH`, `SPECIFIC_ACCOUNT_HIGH_TRANSACTION`. Steps: `CAUTION`, `WARNING`, `DANGER`.
  - `GET https://api.bithumb.com/v1/market/all?isDetails=true` returns `market_warning` = NONE/CAUTION.
  — [Bithumb warnings API](https://api.bithumb.com/v1/market/virtual_asset_warning); [Bithumb markets API](https://api.bithumb.com/v1/market/all?isDetails=true)
- [snapshot] Bithumb, 10.11.2026: 37 active warnings.
  - Deposit surge: ETH and KAIA (WARNING); AVAX, PEPE, MERL, AVL, NXPC, Q, AXIS (DANGER).
  - Volume surge (all DANGER): 11 coins, including ZIL, ENJ, AVAX, RSR, FCT2, XPLA.
  - Few-account: 13 flags (10 CAUTION, 2 WARNING, 1 DANGER).
  - End times: 33 of 37 warnings end at 01:59:59 KST the next day; price-gap ones end within the same evening.
  - 21 of 503 markets had `market_warning`=CAUTION.
  - AVAX and NXPC had deposit-surge flags on both Upbit and Bithumb the same day.
  — [Bithumb API](https://api.bithumb.com/v1/market/virtual_asset_warning)

**Regulator (FSC/FSS)**
- [def] FSC, 05.11.2025 — red flags for investors:
  - Low-liquidity coins surging in price or volume "without particular reason"
  - The price changing several times a second
  - Frequent flicker of the current-price border (현재가 테두리 깜빡임)
  - High-price buy or API order patterns
  - Excessive repeated small orders (단주매매)
  Penalties: ≥1 year in prison or fines of 3–5× the gain; 과징금 (administrative fine) of 2× the gain. — [FSC 85607](https://www.fsc.go.kr/no010101/85607?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [quant] FSC, 20.07.2026: two years under the Act — about 40 investigations, about 30 referrals, 25 suspects; average unfair gain about 1.4B KRW per case; about 8 coins per case. Two 과징금 were set at 125–165% of the gain. Plans: account payment freezes and whistle-blower rewards in the second-stage 디지털자산법. — [FSC 87357](https://www.fsc.go.kr/no010101/87357?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)

### Inferences
- Upbit's volume, deposit and few-account flags are daily features. They cover the day ending 09:00 KST (00:00 UTC) and appear at 10:00 KST (01:00 UTC). For a bot this is a once-a-day input with at least a 1h lag. The price and price-gap flags are real-time.
- Bithumb's flags are near-continuous, graded by step, and use a 3-day baseline. In that sense they are richer than Upbit's.
- Neither exchange's flags cover the riskiest window. Bithumb excludes listings younger than 96h from volume and deposit flags. Ranges and per-coin thresholds make the flags noisy. Major coins (SOL, AVAX, ETH) trigger deposit flags too, so filter to small caps that have Binance perps.
- Upbit's `GLOBAL_PRICE_DIFFERENCES` on KRW markets is a free real-time "premium ≥5% vs CMC" detector. In the snapshot it coincided 5 of 5 with 유의 coins, which fits the 가두리/유의빔 mechanism.
- The official Upbit definition explains the timing the bot observed in s17. There, the V and D flags were recomputed once a day around 01:00 UTC and held exactly 24h, while the P and G flags switched within the day, often for 5–30 minutes — [research/s17/ВЫВОДЫ.md](../../../s17/ВЫВОДЫ.md). So a D flag seen at about 01:00 UTC describes deposits made over the previous UTC day: the underlying deposits are 1–25h old when the flag appears. In the window it does not separate a one-off whale deposit from a steady flow.
- FREE-TEST: Upbit `market/all?is_details=true` is already polled every 5 minutes and logged (s17). Not yet logged: Bithumb `virtual_asset_warning` (step and `end_date`), Bithumb `market/all?isDetails=true` (`market_warning`) and Bithumb `assetsstatus/ALL` (deposit/withdrawal suspensions, the 가두리 precondition and an exclusion filter). All are free and keyless snapshots, so history accrues only from the first poll.

### Gaps
- I found no public historical archive of Upbit or Bithumb caution flags. I believe the APIs return current state only; I did not find a history endpoint.
- Exact current per-coin thresholds are undisclosed by both exchanges. Bithumb's full notice text could not be fetched (403).
- I did not check Coinone or Korbit flag APIs.
- Binance perp availability for the flagged coins could not be checked: Binance is geo-blocked from this sandbox. The owner's server can check it.

## Objective item 3: documented cases where on-chain or flow signals preceded Korean-retail pumps or dumps

### Takeaway
Documented Korean cases with explicit on-chain evidence are few, recent and contested. They involve foundation or partner wallets selling around Upbit listings (PRL), wallet-level front-running allegations (WIF, VVV), supply-plan disputes (KITE, ZKC), a foundation-treasury governance attack followed by a deposit surge to Bithumb (BONK), and FSC cases of a whale moving coins bought abroad into a Korean exchange and of foundation coins sold through API trading. Most documented pump/dump episodes rest on exchange data (price, volume, suspensions, flags), not on-chain data.

### Cited Findings
- [case] PRL, Upbit, Apr 2026:
  - Upbit halted the listing about 5 minutes before trading — [Nate, 28.04.2026](https://news.nate.com/view/20260428n29495)
  - About 90M PRL had moved from the foundation wallet to a separate wallet, then to ecosystem-partner wallets; part was sold on DEXes on listing day. Upbit later said the sales were within the disclosed supply plan. The Korean community widely shared wallet-tracking posts. (Search summary) — [Sedaily, 07.06.2026](https://www.sedaily.com/article/20052702); [TokenPost KOL index](https://www.tokenpost.kr/news/cryptocurrency/353969)
- [case] WIF and VVV, 2026: on-chain watchers alleged a wallet bought WIF about 3h before the Upbit listing notice and sold about 10 minutes after it; for VVV, a buy about 14h before and a sale 5 minutes after. Dunamu called the claims malicious, and Upbit said it is hard to call this front-running. — [Decenter](https://www.decenter.kr/article/20052637). Upbit separately said on-chain trades and transfers are unrelated to listing review, and warned of "상장 사기" (listing scams) (search summary) — [Decenter](https://www.decenter.kr/article/20053145?menu=blockchain)
- [case] KITE, 2026: a media outlet alleged a conflict between the foundation's lock-up extension and the supply schedule filed with Upbit. Upbit said the schedule shows month-end maximum circulating figures. — [NBNTV](https://www.nbntv.co.kr/news/articleView.html?idxno=4027150)
- [case] BONK, 2026: treasury drained by governance attack, then 유의 designation, then Upbit/Coinone delisting, then a deposit surge >500% to Bithumb with a '위험' label (details in Q2). — [Bloter](https://www.bloter.net/news/articleView.html?idxno=673419)
- [case] FSC, 03.09.2025: a "대형고래" (big whale) used hundreds of millions to billions of KRW for high-price buys and buy walls on one exchange. It also bought coins on an overseas exchange and deposited them into the Korean exchange to sell into the rise. Unfair gains were in the tens of billions of KRW, and it was detected by FSC monitoring. — [FSC 85233](https://www.fsc.go.kr/no010101/85233?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [case] FSC, 20.07.2026: a fast-track case referred in Oct 2024 involved selling foundation-held coins at high prices via high-frequency API buy/sell and spoof orders. — [FSC 87357](https://www.fsc.go.kr/no010101/87357?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [case] FSC, 05.11.2025: pre-placed sell orders at a target price, then hundreds of billions of KRW in API high-price buys pushing the price to target, repeated in cycles; gains in the tens of billions of KRW. — [FSC 85607](https://www.fsc.go.kr/no010101/85607?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [case] Sep 2026 (search summary): two brothers ran ultra-short manipulation on several coins; a token operator's staff wash-traded more than 90% of volume to win an exchange listing. — [Supple](https://supple.kr/news/cmudxdv9s003212j0fdsy5m3i); [Joongang Economy News](https://www.joongangenews.com/news/articleView.html?idxno=550425)
- [case] PIEVERSE (Apr 2026): the Bithumb run-up preceded the Upbit notice by about 9 hours (price passed 2,000 KRW at 05:00 KST). The signal was exchange volume (×7, then ×11 per day), not on-chain. — [Blockmedia](https://www.blockmedia.co.kr/archives/1124820)

### Inferences
- For the owner's strategy, the transferable pattern is this: Korean-exchange volume or deposit anomalies, combined with listing or supply events, precede local tops. On-chain wallet evidence is mostly used after the fact, as accusation, rather than as a tested lead signal.
- None of the Korean cases I found reports the matching Binance perp move. That link has to be measured by the owner, as in s15.

### Gaps
- I found no Korean case study that quantifies "token deposited on-chain into Upbit/Bithumb, then a dump on Binance futures".
- I found no documented Korean case of a market-maker wallet → Upbit deposit → dump with on-chain proof. The known MM-dump cases (e.g., MOVE) were not covered in the Korean sources I reached.

## Objective item 4: pitfalls, regulatory context, and manipulation that targets on-chain or flag watchers

### Takeaway
The main pitfalls are:
- Deposits are not sales.
- Exchange wallet rotations and data artifacts mimic huge flows.
- Flags lag, are thresholded in ranges, and skip new listings.
- Promotions (deposit rewards, trading events) inflate deposit and volume signals.
- Manipulators target the very indicators watchers use: the gainers list (경주마), top-10 concentration (추종매매), the current-price flicker, and transfer blocks (가두리).

Regulation (the 2024 Act, FSC AI surveillance, fines of 125–200% of gains) increasingly pushes manipulation into short, API-driven bursts.

### Cited Findings
- [claim] Exchange deposits are positioning, not executed sales — [Nestree](https://www.nestree.io/altcoin-exchange-deposits-surge-2026/). A falling balance does not reveal intent — [TokenPost](https://www.tokenpost.kr/news/cryptocurrency/430597)
- [case] The "5.5B XRP left Upbit" scare (Jun 2025) came from CryptoQuant data. Upbit gave no explanation, and analysts suspected a data error. — [Investing KR](https://kr.investing.com/news/cryptocurrency-news/article-1530716)
- [def] Upbit rotated to new wallets after the Nov 2025 hack. — [Dunamu](https://www.dunamu.com/news/1569)
- [def] Flag lag and granularity: Upbit's daily flags are posted at 10:00 KST — [Upbit report](https://static.upbit.com/reports/transparency_report/upbit_transparency_report_2024.pdf). A Bithumb badge showed 50–75% while the top-10 share was 93% — [Newsway](https://www.newsway.co.kr/news/view?ud=2026101309511600235). Bithumb excludes listings younger than 96h (search summary) — [Bithumb notice](https://feed.bithumb.com/notice/1643939)
- [case] Promotions contaminate flow signals:
  - Bithumb's "입금왕" deposit rewards (1–1.5%, max 2억 KRW per user) included BONK just as deposits surged >500% — [Bloter](https://www.bloter.net/news/articleView.html?idxno=673419)
  - Upbit's PIEVERSE TOP trading event had a 300k PIEVERSE prize pool (about 450M KRW) — [Blockmedia](https://www.blockmedia.co.kr/archives/1124820)
  - Regulators flagged listing-airdrop events as unfair-trading risks in 2024 (search summary) — [Bizwatch, 22.08.2024](https://news.bizwatch.co.kr/article/mobile/2024/08/22/0023)
- [def] '경주마' (racehorse): orders are concentrated "at the time when the price-change rate resets" to put a coin among the top gainers and attract followers — [FSC 87357](https://www.fsc.go.kr/no010101/87357?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=). The FSC worries about 추종매매 on Bithumb's top-10 data — [Newsway](https://www.newsway.co.kr/news/view?ud=2026101309511600235). The FSC lists the faked current-price flicker via micro API trades as a red flag — [FSC 85607](https://www.fsc.go.kr/no010101/85607?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [case] Cross-market price manipulation: wash trading in a USDT-market BTC price inflated KRW-converted prices of BTC-market coins on a coin-market exchange. This was the first 과징금 under the Act. — [FSC 85233](https://www.fsc.go.kr/no010101/85233?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=)
- [def] Legal context:
  - The Act has been in force since 19.07.2024. Exchanges must monitor continuously and report to the FSC/FSS and investigators.
  - Penalties: prison of ≥1 year (≥3 years for gains of 5–50억 KRW; ≥5 years above 50억), fines of 3–5× the gain, 과징금 of 2× the gain.
  - The second-stage 디지털자산법 is under review.
  — [FSC 87357](https://www.fsc.go.kr/no010101/87357?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=); [FSC 85607](https://www.fsc.go.kr/no010101/85607?srchCtgry=&curPage=&srchKey=&srchText=&srchBeginDt=&srchEndDt=); [Upbit report](https://static.upbit.com/reports/transparency_report/upbit_transparency_report_2024.pdf)
- [def] Market structure: foreigners are barred from Korean exchanges, and each exchange is a separate liquidity pool — [Tiger Research](https://reports.tiger-research.com/p/kimchi-premium-101-kor). 62% of coins traded on a single Korean exchange (2023 KIF) — [Xangle](https://xangle.io/research/detail/1425). Exchanges disagree on the same coin: BONK on 07.08 was delisted by Upbit and Coinone but un-designated by Bithumb — [Economybloc](https://economybloc.com/article/122051/)

### Inferences
- A flag-based short signal should exclude coins whose deposits are suspended (Bithumb `deposit_status`=0) or that are under 유의. Their Korean prices are caged and decoupled from Binance.
- Such a signal should also log exchange promotions where possible, since they inflate deposits and volume.
- With most manipulation now short and API-driven (minutes), daily flags (Upbit) catch aftermaths, not onsets. Bithumb's continuous flags are better suited to intraday use.

### Gaps
- I did not reach DAXA's own published criteria document for 유의 designations, or Upbit/Bithumb deposit-suspension policies (whether deposits are always halted on 유의). The Newsis analyst claim was not verified against notices.
- I found no statistics on how often 유의-designated coins are also under deposit suspension, or on the size of the Korean premium during 가두리 episodes beyond single cases (LWA, RDNT, ORCA, GMT, CRV, AVAIL).
