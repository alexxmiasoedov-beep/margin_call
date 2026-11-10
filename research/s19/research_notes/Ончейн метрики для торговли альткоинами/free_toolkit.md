# Free, keyless on-chain data toolkit for altcoin research in Python (verified 2026-11-10)

## Q1. Which free keyless endpoints allow historical transfer queries (how far back), with what limits? What now needs a key?

### Takeaway
Keyless public RPCs are no longer a path to 1–2 years of logs on most chains. PublicNode now asks for a personal token for anything older than about 1–3 days on ETH/BSC/Arbitrum (about 3 weeks on Base). Ankr, BlockPI (private URL), OnFinality, Etherscan and HyperSync require keys. Cloudflare's gateway is dead. Keyless deep history does still exist:
- **Bulk Parquet**: AWS Public Blockchain bucket, covering ETH, Base, Arbitrum, BSC transactions only, and Hyperliquid.
- **SQD Portal**: works but is rate-limited and often overloaded.
- **RPCs that still serve history**: Tenderly's public gateway, MEV Blocker, Flashbots/Chainstack, BlockPI-public and Arbitrum's official RPC.
- **Other chains**: TronGrid's events API, Solana's official RPC (full ledger, slow) and Blockscout instances.
- **BSC is the weak spot.** There is no keyless RPC or Blockscout with deep logs, and AWS has no BSC logs.

### Cited Findings

#### Method
- Every "live" result below came from requests sent on 2026-11-10 between about 09:05 and 09:40 UTC, from a cloud sandbox through an HTTPS proxy.
- The EVM test was `eth_getLogs` with topic0 = `0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef` (ERC-20 Transfer). It used USDT (ETH, BSC, Arbitrum) or USDC (Base) and these query shapes:
  - a selective filter (topic1 = 0x…01, so the result is empty) over 1k / 10k / 100k / 1M blocks;
  - an unfiltered token query over 200 blocks;
  - single-block or 5-block queries at about 1 and 2 years back and at old absolute blocks;
  - `eth_getBalance` at about 1 month back, to test for an archive node.
- The source link in each row is the endpoint that was tested.

#### EVM public JSON-RPC, Ethereum (head = block 26,383,553)
| Endpoint (live test 2026-11-10) | getLogs block-range limit | Result cap | Deepest log history returned | Historical state (archive) |
|---|---|---|---|---|
| [ethereum-rpc.publicnode.com](https://ethereum-rpc.publicnode.com) | ≤9,000 blocks accepted inside the free window | none seen: 200 blocks returned 26,846 logs / 16.7 MB | only about the last 9,000 blocks (≈30 h). head−10,000 returns error -32602 *"Archive requests require a personal token. Get one at: https://www.allnodes.com/publicnode"* | no: even head−1,000 is "archive" |
| [gateway.tenderly.co/public/mainnet](https://gateway.tenderly.co/public/mainnet) | 5,000,000 blocks accepted with a selective filter | *"Query returned more than 20000 results."* | block 10,000,000 (2020-05-04) | yes (head−~1 month) |
| [rpc.mevblocker.io](https://rpc.mevblocker.io) | 10,000 OK; 100,000 returns "service temporarily unavailable" | *"query returned more than 10000 results. Try with this block range [...]"* | 2020-05-04 | yes |
| [rpc.flashbots.net](https://rpc.flashbots.net) | 10,000 OK; 100,000 returns *"Block range limit exceeded. See … docs.chainstack.com/docs/limits"*; 1M returns *"query exceeds max block range 100000"* | none seen (26,846 logs) | 2 years OK. Pre-merge headers return code 4444 *"pruned history unavailable … earliest available 15500000"*, but logs at block 10,000,000 still came back (mixed backends) | yes |
| [ethereum.public.blockpi.network/v1/rpc/public](https://ethereum.public.blockpi.network/v1/rpc/public) | *"eth_getLogs is limited to 5000 block range"* | none seen (26,846 logs) | 2020-05-04 | no (*"historical state … is not available"*) |
| [eth.drpc.org](https://eth.drpc.org) | ≤100 blocks OK; 200 and 500 fail with *"ranges over 10000 blocks are not supported on free plan"*. The message does not match the behaviour. | – | 2020-05-04 | yes |
| [1rpc.io/eth](https://1rpc.io/eth) | *"eth_getLogs is limited to 0 - 50 blocks range"* | – | flaky ("Remote Error", "request timed out"). Its errors mention Nodies and OnFinality | no |
| [eth-mainnet.public.blastapi.io](https://eth-mainnet.public.blastapi.io) | *"up to a 10 block range"* | – | 2020-05-04 | yes |

#### EVM public JSON-RPC, BSC (head 132,750,752; measured ≈0.45 s per block from block timestamps)
- [bsc-dataseed.bnbchain.org](https://bsc-dataseed.bnbchain.org) and [bsc-dataseed1.defibit.io](https://bsc-dataseed1.defibit.io) returned `eth_getLogs` → "limit exceeded" for every range, including 1 block (live). This matches BNB's docs: *"The rate limit of BSC endpoint on Testnet and Mainnet is 10K/5min. eth_getLogs is disabled on below Mainnet endpoints, please use 3rd party endpoints"*. — [BNB docs](https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/)
- [bsc-rpc.publicnode.com](https://bsc-rpc.publicnode.com):
  - Range cap is 50,000 (100,000 → *"exceed maximum block range: 50000"*).
  - A 200-block USDT query returned 13,017 logs.
  - Single-block Transfer logs were present at head−200,000 (≈25 h back).
  - **head−400,000 and head−1,000,000 returned `[]` with no error** (a silent empty result).
  - Blocks about 1 and 2 years back and the 2021/2023 blocks return *"Archive requests require a personal token"*. State is archive-gated at about 1 month.
- [1rpc.io/bnb](https://1rpc.io/bnb) has a 50-block range and returned "header not found" for old blocks. [bsc.drpc.org](https://bsc.drpc.org) returned *"You reached Public endpoint rate limit, please upgrade to paid plan"*. [bsc-mainnet.public.blastapi.io](https://bsc-mainnet.public.blastapi.io) returned *"rate-limited due to unusually high traffic on the Alchemy public API"*. Tenderly's `/public/bsc` returned an empty response (not served). [rpc.ankr.com/bsc](https://rpc.ankr.com/bsc) and [bsc.blockpi.network](https://bsc.blockpi.network/v1/rpc/public) require a key. All are live results.
- No BSC Blockscout instance: [bsc.blockscout.com](https://bsc.blockscout.com/api/v2/stats) returned 404 "default backend" (live).
- Etherscan API V2 with chainid=56, no key: *"Free API access is not supported for this chain. Please upgrade your api plan for full chain coverage"*. So BscScan-via-Etherscan needs a **paid** key. — [live test](https://api.etherscan.io/v2/api?chainid=56&module=proxy&action=eth_blockNumber)

#### EVM public JSON-RPC, Base (head 55,559,046; ≈1.8 s/block) and Arbitrum One (head 522,934,493; ≈0.25 s/block)
- [mainnet.base.org](https://mainnet.base.org) (the official endpoint listed in [Base docs](https://docs.base.org/base-chain/quickstart/connecting-to-base)) returned `eth_getLogs` → "request limit reached" even for 10 blocks (live).
- [base-rpc.publicnode.com](https://base-rpc.publicnode.com): range ≤50,000. Logs are present to head−1,000,000 (≈3 weeks). About 1 and 2 years back is archive-gated (live).
- [gateway.tenderly.co/public/base](https://gateway.tenderly.co/public/base): logs at head−15M (≈10 months) and head−30M (≈21 months). A 100k range → "invalid params" (live).
- [base.drpc.org](https://base.drpc.org): history to block 2,000,000 (2023-07-31), with the same ~100-block range ceiling as on ETH (live).
- [1rpc.io/base](https://1rpc.io/base): *"pruned history unavailable: requested …, earliest available 52000000"* (live).
- [arb1.arbitrum.io/rpc](https://arb1.arbitrum.io/rpc) (official) is the best keyless EVM log source found. It accepted a 1,000,000-block range, logs at block 50,000,000 (2022-12-31) and about 1–2 years back, but no state at about 1 month ("missing trie node") (live). Arbitrum's docs describe it as *"General-purpose read/write endpoint, useful for development and low-volume reads. No uptime, latency, or rate-limit guarantees"* and say *"The Arbitrum public RPC endpoints do not support WebSocket."* — [Arbitrum docs](https://docs.arbitrum.io/build-decentralized-apps/reference/node-providers)
- [arbitrum-one-rpc.publicnode.com](https://arbitrum-one-rpc.publicnode.com): anything older than about 10–100 blocks → *"Archive requests require a personal token"* (live). It is useless for history.
- [gateway.tenderly.co/public/arbitrum](https://gateway.tenderly.co/public/arbitrum): 1M-block range OK; logs at head−120M (≈11 months) (live).
- Tenderly response headers: `x-tdly-limit: 20`, `x-tdly-egress-limit: 1000000000` (live; the docs were not checked).

#### Endpoints that now require a key, are paid, or are dead (live 2026-11-10)
- **Require a key:**
  - [rpc.ankr.com/eth](https://rpc.ankr.com/eth): *"Unauthorized: You must authenticate your request with an API key"*. For Solana: *"API key is not allowed to access blockchain"*.
  - [ethereum.blockpi.network/v1/rpc/public](https://ethereum.blockpi.network/v1/rpc/public): "Apikey not found". The `*.public.blockpi.network` host still works.
  - [eth.api.onfinality.io/public](https://eth.api.onfinality.io/public): *"Too Many Requests, Please apply an OnFinality API key"*.
  - Etherscan API V2: *"Missing/Invalid API Key"* — [live](https://api.etherscan.io/v2/api?chainid=1&module=proxy&action=eth_blockNumber)
  - Envio HyperSync: `/height` is open, but `/query` → *"Your token is malformed. API Tokens can be created at https://app.envio.dev/api-tokens"* — [live](https://eth.hypersync.xyz/query); [docs](https://docs.envio.dev/docs/HyperSync/api-tokens)
  - Blockscout PRO multichain API: [api.blockscout.com](https://api.blockscout.com/api/v2/stats) → 402 *"Proceed with API key or make a X402 payment to continue"*.
  - CoinGecko on-chain endpoints `api.coingecko.com/api/v3/onchain/...` → *"Requests without API key are not allowed for this endpoint"* — [live](https://api.coingecko.com/api/v3/onchain/networks/eth/pools/0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc)
- **Paid:**
  - Base, Arbitrum and Solana on dRPC are paid: *"chain is not available on free plan"* — [solana.drpc.org](https://solana.drpc.org)
  - DefiLlama `bridges.llama.fi/bridges`, `/bridgevolume/{chain}` and `api.llama.fi/inflows/{protocol}/{ts}` → HTTP 402 *"Upgrade to the paid API plan at https://defillama.com/subscription"* — [live](https://bridges.llama.fi/bridges)
- **Dead or unusable:**
  - [cloudflare-eth.com](https://cloudflare-eth.com): "Cannot fulfill request".
  - [eth.llamarpc.com](https://eth.llamarpc.com): HTTP 525 (Base and Arbitrum too).
  - [eth.merkle.io](https://eth.merkle.io): "Rate limit exceeded" on the first call.
  - rpc.payload.de: 502.

#### Ethereum history expiry (why "earliest available 15500000" appears)
- In July 2025 Ethereum clients shipped partial history expiry under EIP-4444. Dropping pre-Merge block data saves 300–500 GB, and every full-node client supports running without it. Reth's flag is `--prune.receipts.before 15537394`. Pre-Merge receipts and logs are therefore missing on many nodes. Mirrors are listed at eth-clients.github.io/history-endpoints. — [EF blog, 2025-07-08](https://blog.ethereum.org/2025/07/08/partial-history-exp)

#### Solana
- [api.mainnet-beta.solana.com](https://api.mainnet-beta.solana.com) is keyless with **full history** (live). `getBlock` and `getTransaction` worked for:
  - slot 100,000,000 (2021-10-06);
  - slot about 1 year back (2025-12-28);
  - slot about 2 years back (2025-01-03).
- `getSignaturesForAddress` maxes out at 1,000 per call (*"Invalid limit; max 1000"*; 1,000 rows ≈ 234 KB, 0.6 s).
- `getTokenLargestAccounts` was rejected on the first call with 429 *"Too many requests for a specific RPC call"*.
- Response headers: `x-ratelimit-tier: free`, `x-ratelimit-rps-limit: 250`, `x-ratelimit-method-limit: 150`, `x-ratelimit-conn-limit: 40`, `x-ratelimit-connrate-limit: 40`, `x-ratelimit-pubsub-limit: 5` (live).
- Official docs, per search snippets (the page returned 429 to direct fetch): *"Maximum number of requests per 10 seconds per IP: 100; … for a single RPC: 40"*. A third party adds 40 concurrent connections and 100 MB per 30 s. The public endpoints are not for production. — [solana.com clusters](https://solana.com/docs/references/clusters); [OrbitFlare](https://orbitflare.com/blog/fundamentals/solana-rpc-rate-limits). The live header numbers differ from the docs, and the header time windows are unknown.
- [solana-rpc.publicnode.com](https://solana-rpc.publicnode.com) has a short ledger only: *"Block … cleaned up, does not exist on node. First available block: 466958568"*, which is about 709k slots or ≈3.3 days. `getTokenLargestAccounts` → 403 "Request blocked" (live).

#### Tron
- TronGrid REST v1, keyless (live):
  - `GET https://api.trongrid.io/v1/contracts/{contract}/events?event_name=Transfer&min_block_timestamp=…&max_block_timestamp=…&limit=200&order_by=block_timestamp,asc` returned 200 events per page, with `meta.fingerprint` for paging. It worked for windows 1, 2 and **4 years back (2022-11-11)**, at 0.6–1.9 s per call. — [live](https://api.trongrid.io/v1/contracts/TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t/events?event_name=Transfer&limit=5)
  - `/v1/accounts/{addr}/transactions/trc20?only_to=true&contract_address=…&min_timestamp=…` worked for 2 years back.
  - `/jsonrpc` `eth_getLogs` accepted 5,000-block ranges.
- TronGrid docs (no fixed numbers):
  - *"Production requests should include TRON-PRO-API-KEY"*.
  - No API key → *"Strict rate limiting or rejection"*.
  - Throttling returns 429/403.
  - *"Do not hard-code fixed limits"*.
  — [TronGrid rate limits](https://developers.tron.network/reference/rate-limits)
- [tron-rpc.publicnode.com/jsonrpc](https://tron-rpc.publicnode.com/jsonrpc): `eth_getLogs` caps at *"exceed max block range: 5000"*. Logs are present at head−1,000,000 (≈35 days). head−5M, −10.5M and −21M returned **0 logs with no error** (probably pruned) (live).
- Tronscan API (keyless parts, live):
  - Works: [`/api/token_trc20/transfers`](https://apilist.tronscanapi.com/api/token_trc20/transfers?limit=20&start=0&contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t). The response showed `"total": 10000`, possibly a paging cap.
  - Works, with labels: [`/api/token_trc20/holders`](https://apilist.tronscanapi.com/api/token_trc20/holders?contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&start=0&limit=20).
  - Needs a key: `/api/accountv2?address=` → 401 "Authorization Required".
  - The Tronscan API-key docs returned 403 to fetch, so official limits are unverified.

#### Blockscout REST v2 and Etherscan-compatible API (keyless)
- `GET https://eth.blockscout.com/api/v2/tokens/{token}/transfers` returns 50 items per page with keyset paging (`next_page_params` = `{index, block_number}`). Items carry `from`, `to`, `total.value` + `total.decimals`, `method`, `timestamp`, `transaction_hash`. Header `x-ratelimit-limit: 180`. — [live](https://eth.blockscout.com/api/v2/tokens/0x6982508145454Ce325dDbE47a25d4ec3d2311933/transfers)
- `/api/v2/tokens/{token}/holders` returns 50 per page, sorted by balance, and **each address carries `metadata.tags`**, for example "Binance: Hot Wallet 20", "Bybit: Hot Wallet 10", "OKX: Cold Wallet". — [live](https://eth.blockscout.com/api/v2/tokens/0x6982508145454Ce325dDbE47a25d4ec3d2311933/holders)
- `/api/v2/addresses/{addr}/token-transfers?type=ERC-20&filter=to` works (live).
- The Etherscan-compatible `GET /api?module=logs&action=getLogs&fromBlock&toBlock&address&topic0` over a 100k-block window 2 years back returned **1,000 results per call** (a cap). Header `x-ratelimit-limit: 10`. — [live](https://eth.blockscout.com/api?module=logs&action=getLogs&fromBlock=21127553&toBlock=21227553&address=0x6982508145454Ce325dDbE47a25d4ec3d2311933&topic0=0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef)
- Instances that answer: base, arbitrum, optimism and polygon.blockscout.com. BSC does not (live).
- Docs:
  - No key: by IP, *"300 requests per minute by default (API_RATE_LIMIT_BY_IP=300)"*.
  - Personal API key: 10 req/s.
  - The multichain PRO API includes "5 rps" on its free plan.
  - The page says per-instance API access will be deprecated, ending "July 1" (no year shown). It still worked keyless on 2026-11-10.
  — [Blockscout requests & limits](https://docs.blockscout.com/devs/apis/requests-and-limits)

#### Bulk and streaming sources (best for 1–2 years)
- **AWS Public Blockchain Data** needs no account: `aws s3 ls --no-sign-request s3://aws-public-blockchain/`, bucket ARN `arn:aws:s3:::aws-public-blockchain`, region us-east-2. It is compressed Parquet partitioned by date and *"New data is delivered daily"*. Maintainers: AWS (BTC, ETH), SonarX (Arbitrum, Base, Aptos, XRP, Provenance), BNB Chain, Cronos, Lighter, Stellar, TON. — [AWS registry](https://registry.opendata.aws/aws-public-blockchain/)
- Live listing of the same bucket over anonymous HTTPS ([listing URL](https://aws-public-blockchain.s3.us-east-2.amazonaws.com/?list-type=2&prefix=v1.0/eth/&delimiter=/)):
  - `v1.0/eth/{blocks,contracts,logs,token_transfers,traces,transactions}`. `token_transfers` runs from 2015-10-27 to **2026-11-09** (1-day lag) at ≈638 MB per day (one file). `logs` is ≈1.37 GB per day.
  - `v1.1/sonarx/{arbitrum,base}/{approvals,blocks,logs,receipts,traces,transactions,transactions_failed,transfers}`. Base starts 2023-06-15 and Arbitrum 2021-05-29; both end **2026-11-03** (≈1 week lag). Base transfers are ≈1.28 GB/day, Arbitrum ≈217 MB/day, Base logs ≈5 GB/day.
  - `v1.1/bnb/` holds **only `blocks` and `transactions`** (2020-08-29 to 2026-11-09, ≈6.6 GB/day). There are no logs or transfers.
  - `v1.1/hyperliquid/mainnet/{asset_ctxs,explorer_blocks,market_data,misc_events_by_block,node_fills,node_fills_by_block,node_trades}`, for example `node_fills_by_block/hourly/20250727/10.lz4`. This is a keyless mirror of data Hyperliquid itself publishes requester-pays.
- **SQD Portal**, public and keyless (live):
  - `GET https://portal.sqd.dev/datasets` lists, among others, ethereum-mainnet, binance-mainnet (BSC), base-mainnet, arbitrum-one, solana-mainnet, hyperliquid-fills and hyperliquid-mainnet.
  - `/datasets/{ds}/metadata` gives `start_block: 0` and `real_time: true` for solana-mainnet and binance-mainnet.
  - `POST /datasets/{ds}/stream` with a JSON query (`type:"evm"`, `fromBlock`, `toBlock`, `fields`, `logs:[{topic0:[…]}]`) returns NDJSON per block.
  - An Ethereum log query at a 2-year-old block succeeded on retry (182 KB). BSC, Base and Arbitrum queries got **HTTP 529 `{"type":"rate_limit_error","code":"overloaded"}`**. A Solana `tokenBalances` query at slot 300,000,000 (2024-11-07) succeeded.
  — [portal.sqd.dev/datasets](https://portal.sqd.dev/datasets)
- SQD docs:
  - *"Public is the shared public Portal at https://portal.sqd.dev. Use it to explore data, prototype… rate-limited"*.
  - *"Portal billing is not live yet… Until billing starts, the public Portal keeps its current limits"*.
  - Plans: Public $0, Testing $0 (key), Starter $99/mo (1 chain, 25 GB/mo, 5 MB/s), Growth $499/mo.
  — [SQD pricing](https://docs.sqd.dev/en/portal/pricing)
- SQD exact public rate limit: older and closed-beta docs say 20 or 50 requests per 10 s, and overload responses carry Retry-After. These figures conflict and are unverified. — [search summary of docs.sqd.ai pages](https://docs.sqd.ai/portal-rate-limited)
- **Blockchair dumps** (`gz.blockchair.com`):
  - `ethereum/erc-20/transactions/` has 3,995 daily TSV.gz files, 2015-10-30 to 2026-11-09 (live listing). Chains: BTC, BCH, DASH, DOGE, ETH, LTC, ZEC only.
  - *"by default the speed is limited to 10 kB/s. You'd need a special key to download without this limit"*. Keyless use is therefore impractical.
  — [Blockchair README](https://gz.blockchair.com/README.html); [listing](https://gz.blockchair.com/ethereum/erc-20/transactions/)
- **Google BigQuery public crypto datasets** need a Google account. The sandbox needs no credit card and gives *"1 TiB of processed query data each month"*, a lifetime *"10 GiB of storage"*, and tables that *"automatically expire after 60 days"*. These are not keyless/no-account sources. — [BigQuery sandbox docs](https://docs.cloud.google.com/bigquery/docs/sandbox)

#### DefiLlama (keyless; free vs paid)
- Free and working (live): [`api.llama.fi/protocol/binance-cex`](https://api.llama.fi/protocol/binance-cex), `/protocols` (8,983 protocols, 84 in category CEX), `stablecoins.llama.fi/stablecoins`, `/stablecoincharts/all`, `api.llama.fi/overview/dexs`, `/summary/dexs/{protocol}`, `/overview/fees`, `yields.llama.fi/pools`, `coins.llama.fi/prices/historical/{ts}/{chain}:{addr}`, `/v2/historicalChainTvl/{chain}`.
- The `binance-cex` object is 45.7 MB of JSON. It has `tokens`, `tokensInUsd` and `tvl` series of **1,459 daily points, 2022-11-12 to 2026-11-10**, and `chainTvls` per chain (Ethereum, Binance/BSC, Tron, Solana, Arbitrum, Base and about 40 more). The Ethereum series held 313 tokens at the last point, and the last points were about 24 h apart. This gives free **per-token, per-chain daily balances** of Binance's tracked wallets. OKX and Bybit have similar series (≈1,420–1,455 points) (live).
- **Upbit and Bithumb exist as CEX entries but have no balance series.** `/protocol/upbit` and `/protocol/bithumb` return metadata only (live).
- Bridges and the `inflows` endpoint are paid (402, see above).

#### DEX market data: GeckoTerminal, DexScreener, CoinGecko
- GeckoTerminal (keyless, live):
  - `GET https://api.geckoterminal.com/api/v2/networks/{net}/pools/{pool}/ohlcv/{day|hour|minute}?limit=1000&before_timestamp=…` works for recent data.
  - **Anything beyond 180 days → 401 *"You can only access data from the past 180 days with Public API"*.** Minute candles 30 days back were available (1,000 rows).
  - `/pools/{pool}/trades` returns **the last 300 trades** with `kind` (buy/sell), `tx_from_address`, `volume_in_usd`, `block_number`.
  — [live](https://api.geckoterminal.com/api/v2/networks/eth/pools/0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc/trades)
- GeckoTerminal rate limit, conflicting:
  - CoinGecko keyless docs: *"GeckoTerminal endpoints: ~5 calls/min (dynamic, varies by server load)"*, and attribution is required. — [CoinGecko keyless API](https://docs.coingecko.com/docs/keyless-public-api)
  - GeckoTerminal FAQ (via search): 30 calls/min, raised from 10 in April 2023. — [GT FAQ](https://apiguide.geckoterminal.com/faq)
- DexScreener (keyless, live):
  - Endpoints: `/latest/dex/tokens/{addr}`, `/token-pairs/v1/{chainId}/{token}`, `/tokens/v1/{chainId}/{addrs}`.
  - The pair object has `txns` counts of buys and sells for the m5, h1, h6 and h24 windows, plus `volume`, `priceChange`, `liquidity`, `pairCreatedAt`.
  - Docs give 60 req/min for profile, boost and meta endpoints. No endpoint provides OHLCV or historical trades. — [DexScreener API reference](https://docs.dexscreener.com/api/reference)
- CoinGecko keyless (live):
  - `/coins/list?include_platform=true` returns 22,875 coins with contract addresses per platform.
  - `/coins/{id}/market_chart` with `days=365` works; `days=730` and older `/range` calls → error 10012 *"Public API users are limited to querying historical data within the [past 365 days]"*.
  - Docs: keyless is ≈5 calls/min. — [live](https://api.coingecko.com/api/v3/coins/list?include_platform=true); [docs](https://docs.coingecko.com/docs/keyless-public-api)

#### Hyperliquid (keyless)
- `POST https://api.hyperliquid.xyz/info` works for **any address**:
  - `{"type":"clearinghouseState","user":…}`: positions, margin, withdrawable.
  - `userFillsByTime` (returned 2,000 fills), `portfolio`, `userNonFundingLedgerUpdates`, `meta`.
  — [live](https://api.hyperliquid.xyz/info)
- Leaderboard, undocumented, used by the web UI: `GET https://stats-data.hyperliquid.xyz/Mainnet/leaderboard` returns 38.6 MB with 48,155 rows of `ethAddress`, `accountValue`, `windowPerformances` (day/week/month/allTime) and `displayName`. — [live](https://stats-data.hyperliquid.xyz/Mainnet/leaderboard)
- Limits:
  - 1,200 weight per minute per IP.
  - Weights: `clearinghouseState` 2; most other info requests 20; extra weight per 20 items for `userFills`/`userFillsByTime` and per 60 items for `candleSnapshot`; explorer 40.
  — [HL rate limits](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits)
- History caps:
  - `userFillsByTime` *"Returns at most 2000 fills per response and only the 10000 most recent fills are available"*.
  - Time-range responses return 500 elements.
  - `candleSnapshot`: *"Only the most recent 5000 candles are available"*.
  — [HL info endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
- Hyperliquid's own S3 buckets `hyperliquid-archive` and `hl-mainnet-node-data` are requester-pays (*"the requester of the data must pay for transfer costs"*), so they need an AWS account. — [HL historical data](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data)

#### Binance public web endpoints (keyless)
- Alpha token list: [`/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list`](https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list)
  - 686 tokens.
  - Fields include `chainId`, `chainName`, `contractAddress`, `decimals`, `alphaId`, `holders`, `listingTime`, `listingCex`, `cexCoinName`, `offline`.
  - By chain: BSC 502, Solana 70, Base 46, Ethereum 38, Sui 13, Robinhood 5, Arbitrum 4, Sonic 4, TRON 3, Linea 1 (live).
- Alpha market data (live):
  - `/bapi/defi/v1/public/alpha-trade/klines?symbol=ALPHA_124USDT&interval=1h&limit=1500` returned 1,500 rows.
  - `1d` with `startTime` set 2 years back returned 486 rows, starting 2025-07-13, although `listingTime` was 2025-03-22.
  - `agg-trades` (limit 1000), `ticker` and `get-exchange-info` also work.
- Official docs exist under developers.binance.com/docs/alpha/market-data: public GET, no authentication, symbol format `ALPHA_175USDT`. — [Binance Alpha docs](https://developers.binance.com/docs/alpha/market-data)
- [`/bapi/capital/v1/public/capital/getNetworkCoinAll`](https://www.binance.com/bapi/capital/v1/public/capital/getNetworkCoinAll): 991 coins. Each has a `networkList` with `network`, `contractAddress`, `depositEnable`, `withdrawEnable`, `depositDesc`, … This shows which contract Binance accepts on each chain (live, undocumented).
- [`/bapi/apex/v1/public/apex/market/por/address`](https://www.binance.com/bapi/apex/v1/public/apex/market/por/address): see Q2.

#### mempool.space
- `https://mempool.space/api/blocks/tip/height` answered keyless (975,280), but it is Bitcoin only, so it is irrelevant for altcoin token flows. — [live](https://mempool.space/api/blocks/tip/height)

### Inferences
- For history deeper than a few days on ETH, BSC, Base and Arbitrum, "public RPC" now effectively means Tenderly's gateway, MEV Blocker, Flashbots/Chainstack, BlockPI-public, dRPC (100-block windows) or Arbitrum's official RPC. PublicNode is only for the real-time tail.
- None of these endpoints publishes SLAs or numeric keyless quotas. Treat them as best-effort: use backoff, rotate endpoints, and validate every chunk against a known non-empty block, because of the silent-empty behaviour seen on PublicNode BSC and Tron.
- For 1–2 years of ERC-20 transfers, AWS Parquet beats any RPC on ETH, Base and Arbitrum. One day of ETH token transfers (≈0.64 GB) replaces tens of thousands of `eth_getLogs` calls.
- On BSC the only keyless full-history log source found is SQD Portal, and it returned 529 "overloaded" in 4 of 5 EVM attempts (ETH first try, BSC, Base, Arbitrum; only the ETH retry succeeded). BSC history therefore needs patience (retry with Retry-After), or one must accept the DefiLlama per-exchange daily balances as a proxy.
- Tron is better than expected: TronGrid's per-contract events API serves at least 4 years keyless, 200 events per page.

### Gaps
- No numeric keyless quotas were found in official docs for PublicNode, Tenderly's public gateway, MEV Blocker, Flashbots, dRPC free or TronGrid (TronGrid explicitly refuses to give fixed numbers).
- Tronscan's official key and limit page was unreachable (403).
- Solana's official limits page returned 429, so its numbers come from search snippets and a third party.
- SQD Portal's exact public rate limit is undocumented or conflicting; observed behaviour was 529 "overloaded".
- The DexScreener rate limit for pair and token endpoints (often quoted as 300/min) is not shown on the fetched docs page.
- Freshness of the AWS Hyperliquid mirror (the latest hourly folder) was not determined. Listing showed files from 2025-07-27.
- Results are a single-day snapshot. Free-tier behaviour changes often (for example, the dRPC error message contradicts its actual limit).

## Q2. Where can one get reasonably reliable free labels for Upbit, Bithumb and Binance wallets on Ethereum, BSC, Solana and Tron?

### Takeaway
**Binance** is well covered:
- its own keyless Proof-of-Reserves endpoint (708 addresses, including ETH 58, BSC 54, TRX 37, SOL 24);
- Dune Spellbook CEX lists (EVM 150, Solana 15, Tron 14);
- eth-labels (ETH 5,102 including "Binance Dep:" deposit entries);
- Blockscout and Tronscan tags.

**Upbit and Bithumb** have usable EVM labels: Spellbook has Upbit 32 and Bithumb 550 on EVM, and eth-labels has 15 and 40 on Ethereum. No open dataset found had Upbit or Bithumb on Solana or Tron, and DefiLlama does not track them. Korean coverage on non-EVM chains must be built in-house with sweep/deposit heuristics seeded from known EVM wallets or explorer tags.

### Cited Findings
- **Binance PoR (official, keyless)**:
  - `GET https://www.binance.com/bapi/apex/v1/public/apex/market/por/address` returns 708 rows of `{network, address, thirdPartyCustodianName, createTime}`.
  - By network: BTC 84, ETH 58, BSC 54, DOGE 45, BCH 37, TRX 37, ARBITRUM 32, XRP 28, LTC 27, MATIC 27, AVAXC 25, SOL 24, NEAR 19, SUI 18, APT 16, BASE 16, OPTIMISM 14, … — [live](https://www.binance.com/bapi/apex/v1/public/apex/market/por/address)
  - DefiLlama's Binance adapter uses exactly this endpoint (`const ENDPOINT = "https://www.binance.com/bapi/apex/v1/public/apex/market/por/address"`). — [DefiLlama-Adapters projects/binance/index.js](https://github.com/DefiLlama/DefiLlama-Adapters/blob/main/projects/binance/index.js)
- **Dune Spellbook** CEX address lists (repo last commit 2026-11-10):
  - `cex_evms_addresses.sql` is one static EVM list of 4,957 rows across 328 exchanges. Counts: Binance 150, Bithumb 550, Upbit 32, OKX 274, Bybit 50, Korbit 36, Coinone 7, Coinbase 287, Kraken 254, HTX 242, KuCoin 81, MEXC 25, Bitget 36. Columns: address, cex_name, distinct_name, added_by, added_date. — [cex_evms_addresses.sql](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/models/_sector/cex/addresses/chains/cex_evms_addresses.sql)
  - Upbit entries are "Upbit 4…9", "Upbit Cold Wallet", "Upbit Wallet Factory Contract", etc. Bithumb entries are 509 "Bithumb N", 7 "Bithumb Gas Supplier", 4 "Bithumb Old Address", a deployer and a contract (same file).
  - Per-chain tables apply the EVM list to each chain through the `cex_evms` macro, which keeps addresses seen receiving token transfers or created on that chain. — [cex_evms macro](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/macros/sector/cex/cex_evms.sql); [ethereum model](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/models/_sector/cex/addresses/chains/ethereum/cex_ethereum_addresses.sql)
  - Solana list: Binance 15, OKX 24, Bybit 2, Coinbase etc.; **no Upbit or Bithumb**. — [cex_solana_addresses.sql](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/models/_sector/cex/addresses/chains/solana/cex_solana_addresses.sql)
  - Tron list: Binance 14, OKX 12, Bybit 8; **no Upbit or Bithumb**. — [cex_tron_addresses.sql](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/models/_sector/cex/addresses/chains/tron/cex_tron_addresses.sql)
  - There are also per-chain `cex_<chain>_deposit_addresses` models (ethereum, bnb, base, arbitrum, optimism, polygon, avalanche_c, …; none for Solana or Tron). These are computed inside Dune, not static files. — [deposit_addresses/chains](https://github.com/duneanalytics/spellbook/tree/main/dbt_subprojects/hourly_spellbook/models/_sector/cex/deposit_addresses/chains)
- **Spellbook license**: Business Source License 1.1. *"You may make use of the Licensed Work, provided that you may not use the Licensed Work for a Data or Analytics Platform"*, with non-production use granted. The Change Date is **Mar 3, 2027**, after which the license becomes GPL v3+. — [LICENSE](https://github.com/duneanalytics/spellbook/blob/main/LICENSE)
- **eth-labels** (dawsbot):
  - MIT license; last commit 2026-09-25; *"A dataset of crypto addresses labeled (Ethereum and MANY more EVM chains)"*. Data is at `data/csv/accounts.csv`, plus JSON, SQLite and an MCP server (*"169k+ labeled addresses and tokens"*).
  - The live CSV has 144,378 account rows: chain 1: 113,194; Base: 11,271; Avalanche: 4,955; World Chain: 4,910; Arbitrum: 3,394; BSC: 3,180; OP: 2,465; Celo: 645; Gnosis: 364.
  - Exchange matches: Upbit on ETH 15 (e.g. "Upbit: Cold Wallet", "Upbit 11"); Bithumb on ETH 40 (e.g. "Bithumb 17", "Bithumb: Deposit Funder 4"); Binance on ETH 5,102 (including entries like "Binance Dep: 0x…") and on BSC 89. **No Upbit or Bithumb on BSC**.
  — [repo](https://github.com/dawsbot/eth-labels); [accounts.csv](https://github.com/dawsbot/eth-labels/blob/v1/data/csv/accounts.csv)
- **brianleect/etherscan-labels** is stale. Its last commit was 2023-10-02, and the README says *"Currently broken due to undetected chromedriver not working"*. It holds 45,198 labels over 7 chains (ETH 29,945; BSC 6,726). — [repo](https://github.com/brianleect/etherscan-labels)
- **Blockscout metadata tags** (keyless):
  - `GET https://metadata.services.blockscout.com/api/v1/metadata?addresses={addr}&chainId=1` returned "Binance: Hot Wallet", "Binance 14", and the generic tags "Exchange" and "HOT WALLET" for 0x28C6…1d60. — [live](https://metadata.services.blockscout.com/api/v1/metadata?addresses=0x28C6c06298d514Db089934071355E5743bf21d60&chainId=1)
  - The same tags appear inline in `/api/v2/tokens/{t}/holders`.
  - `/api/v2/addresses/{addr}` returned `metadata: null` for the same address, which is inconsistent (live).
- **Tronscan holder tags** (keyless): the top USDT holders came back with `addressTag` such as "Tether Treasury", "Binance 3", "Binance-Cold 2" and "Kraken: Hot Wallet". Many large holders had no tag. — [live](https://apilist.tronscanapi.com/api/token_trc20/holders?contract_address=TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t&start=0&limit=20)
- **DefiLlama**:
  - The shared CEX helper `projects/helper/cex.js` has no "upbit" or "bithumb" strings. — [helper/cex.js](https://github.com/DefiLlama/DefiLlama-Adapters/blob/main/projects/helper/cex.js)
  - `/protocol/upbit` and `/protocol/bithumb` have no balance series (live).
- **Market makers**: Spellbook's CEX list contains none of Wintermute, Jump, DWF, GSR, Amber, Cumberland, Flow Traders or B2C2 (grep of cex_evms_addresses.sql). eth-labels coverage is thin: Wintermute 8 on ETH + 2 on OP, DWF Labs 3, GSR 1. — [accounts.csv](https://github.com/dawsbot/eth-labels/blob/v1/data/csv/accounts.csv)

### Inferences
- A practical label stack:
  1. Binance PoR (authoritative for reserve wallets);
  2. the Spellbook EVM, Solana and Tron lists (broad CEX coverage; BSL forbids offering a "data/analytics platform" to third parties, but private research is permitted non-production use);
  3. eth-labels (MIT, but scraped from Etherscan-family label clouds, so redistribution and ToS caveats apply);
  4. Blockscout and Tronscan tags for spot-checks of top holders;
  5. self-detected deposit addresses (Q3).
- For Upbit and Bithumb on Solana and Tron, no free label list was found. The workable route is behavioural:
  - find large wallets that receive sweeps from many single-use addresses;
  - cross-check with Tronscan tags on top-holder lists;
  - confirm with timing against Upbit/Bithumb deposit and withdrawal suspensions or listing events.
  This is unvalidated.
- Bithumb's 550 EVM entries are mostly numbered addresses ("Bithumb N") and may include deposit-related wallets. Treat them as one entity and check how fresh they are (`added_date`) before relying on them.

### Gaps
- No Upbit or Bithumb Proof-of-Reserves address publication was found (not searched exhaustively).
- No open Solana or Tron label list containing Upbit or Bithumb was found.
- How many Upbit/Bithumb labels Blockscout's metadata service holds could not be enumerated: no keyless search-by-tag endpoint was tested.
- Label accuracy and staleness rates were not measured.
- OKX and Bybit official PoR address files were not checked in this session.

## Q3. What is the most efficient keyless way to reconstruct daily or hourly exchange inflows for ~200 altcoins over 1–2 years? (techniques and pitfalls)

### Takeaway
Use bulk Parquet where it exists:
- AWS `v1.0/eth/token_transfers` for ETH;
- AWS SonarX `transfers` for Base and Arbitrum;
- SQD Portal (with retries) for BSC and Solana;
- TronGrid's per-contract events API for Tron.

Filter to the ~200 contracts, then classify each transfer against a label set: known CEX wallets, plus deposit addresses detected by the sweep heuristic (forwarding within ~1 day or ~3,200 blocks, ±10% amount, to exactly one exchange). Aggregate per hour. Use DefiLlama's free daily per-token CEX balances (Binance, OKX, Bybit) as a cross-check and fallback; it has no Korean coverage.

### Cited Findings

#### Data-volume facts (live 2026-11-10)
- AWS ETH `token_transfers` is ≈638 MB per day (2026-11-09; 463 MB on 2026-11-01), as one snappy Parquet file per day. ETH `logs` is ≈1.37 GB per day. — [AWS listing](https://aws-public-blockchain.s3.us-east-2.amazonaws.com/?list-type=2&prefix=v1.0/eth/token_transfers/date=2026-11-09/)
- AWS SonarX Base `transfers` is ≈1.28 GB/day in 14 files, Base `logs` ≈5.04 GB/day, Arbitrum `transfers` ≈217 MB/day. AWS BNB `transactions` is ≈6.6 GB/day. — [AWS listing](https://aws-public-blockchain.s3.us-east-2.amazonaws.com/?list-type=2&prefix=v1.1/sonarx/base/transfers/date=2026-11-03/)
- RPC equivalent: 200 ETH blocks of USDT Transfer logs is 26,846 logs and 16.7 MB of JSON (live test on [publicnode](https://ethereum-rpc.publicnode.com)).
- DefiLlama `protocol/binance-cex` is 45.7 MB of JSON with daily per-token balances since 2022-11-12 (live, [link](https://api.llama.fi/protocol/binance-cex)).

#### Deposit-address detection (sweep pattern)
- **Victor (FC 2020) deposit-address-reuse heuristic**:
  - Pattern: a path user → deposit address → exchange address, where both legs carry the same asset type, the received amount minus the forwarded amount is in [0, a_max], and the time gap is in [0, t_max].
  - Exclude known exchange addresses and miners as users. Require the deposit address to forward to a **single** exchange address.
  - Calibration: initial windows of 10,000 blocks and 1 ETH; empirical 95th percentiles of **0.0083 ETH and 3,185 blocks (~13 h)**; final thresholds **a_max = 0.01 ETH, t_max = 3,200 blocks**. For tokens *"amax is typically 0"*.
  - Results: 13,104,448 forwarding traces found; the clusters cover 17.9% of active EOAs. Kraken uses mass-deployed forwarding contracts as deposit addresses.
  — [Victor, "Address clustering heuristics for Ethereum", FC 2020](https://fc20.ifca.ai/preproceedings/31.pdf)
- **Dune Spellbook `cex_deposit_addresses` macro** (by hildobby). The candidate is the `from` of an "Inflow" flow that meets all of these:
  - it sends to a CEX within **1 day** after the address first received tokens;
  - it is not a system-like address (first 16 bytes not zero);
  - `HAVING COUNT(DISTINCT cex_name) = 1` (it deposits to only one CEX);
  - the deposits precede the consolidation;
  - `amount_consolidated BETWEEN amount_deposited*0.9 AND amount_deposited*1.1` (*"account for older dust test transfers"*);
  - **all** its outgoing transfers in the window go to the same CEX.
  Addresses labelled "Deposit N" are taken directly. On Ethereum, beacon withdrawals into a deposit address count as deposits. Flow types used: 'Inflow', 'Internal', 'Executed', 'Executed Contract'. — [cex_deposit_addresses.sql](https://github.com/duneanalytics/spellbook/blob/main/dbt_subprojects/hourly_spellbook/macros/sector/cex/cex_deposit_addresses.sql)

#### Ready-made exchange balance series (netflow proxy)
- DefiLlama `/protocol/{binance-cex|okx|bybit}` gives free per-chain, per-token daily balances of the exchange's tracked (PoR) wallets. The Binance series runs 2022-11-12 to 2026-11-10, with 313 tokens on Ethereum at the last point. Upbit and Bithumb are empty (live: [binance-cex](https://api.llama.fi/protocol/binance-cex), [upbit](https://api.llama.fi/protocol/upbit)). The precomputed `inflows` endpoint is paid ([402](https://api.llama.fi/inflows/binance-cex/1730000000)).

#### Holder concentration and top-holder changes
- Blockscout `/api/v2/tokens/{t}/holders` gives the current top holders, 50 per page, sorted by balance, with exchange tags. It is a snapshot only. — [live](https://eth.blockscout.com/api/v2/tokens/0x6982508145454Ce325dDbE47a25d4ec3d2311933/holders)
- Tronscan `/api/token_trc20/holders` gives top holders with `addressTag` (live, see Q2).
- Solana `getTokenLargestAccounts` was rate-limited (429) on the official public RPC and blocked (403) on PublicNode (live).

#### DEX buy/sell pressure
- GeckoTerminal `/trades` returns the last 300 trades with a buy/sell `kind` and the trader address. OHLCV goes back at most 180 days keyless (live; [GT](https://api.geckoterminal.com/api/v2/networks/eth/pools/0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc/ohlcv/day?limit=1000)).
- DexScreener gives only rolling-window buy/sell counts (m5–h24) and no history. — [docs](https://docs.dexscreener.com/api/reference)
- History must therefore come from decoding swap events in logs: AWS ETH, Base and Arbitrum `logs` tables or SQD Portal (sources as above).

#### Tracking known wallets (teams, market makers, perp traders)
- Hyperliquid `clearinghouseState` works for any address. The 48,155-row leaderboard gives candidate addresses. Fills history is capped at the 10,000 most recent per user. — [HL info docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint); [leaderboard](https://stats-data.hyperliquid.xyz/Mainnet/leaderboard)
- Keyless historical fills and trades exist on the AWS mirror `v1.1/hyperliquid/mainnet/node_fills_by_block/` and on SQD's `hyperliquid-fills` dataset. — [AWS listing](https://aws-public-blockchain.s3.us-east-2.amazonaws.com/?list-type=2&delimiter=/&prefix=v1.1/hyperliquid/mainnet/); [SQD datasets](https://portal.sqd.dev/datasets)

#### Mapping tickers to contracts and decimals
- Binance `getNetworkCoinAll` gives `contractAddress` per network for 991 coins (live, [link](https://www.binance.com/bapi/capital/v1/public/capital/getNetworkCoinAll)).
- The Binance Alpha list gives `contractAddress`, `chainId` and `decimals` (live, [link](https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list)).
- CoinGecko `coins/list?include_platform=true` covers 22,875 coins (live, [link](https://api.coingecko.com/api/v3/coins/list?include_platform=true)).
- Blockscout transfers include `total.decimals` (live).

#### Pitfalls (observed or documented)
- **Silent empty results beyond node retention**: PublicNode BSC returned `[]` at head−400k and head−1M, and PublicNode Tron returned 0 logs at head−5M and beyond, with no error (live). Elsewhere the error is explicit ("Archive requests require a personal token", "pruned history unavailable", "cleaned up … First available block").
- **History expiry on Ethereum**: pre-Merge (before block 15,537,394) receipts and logs are pruned on many nodes. — [EF blog](https://blog.ethereum.org/2025/07/08/partial-history-exp)
- L2 nodes also prune: 1rpc Base reported "earliest available 52000000" (live).
- **Result caps**, which force adaptive range splitting:
  - Tenderly 20,000 logs; MEV Blocker 10,000; Blockscout Etherscan-compatible API 1,000; Solana signatures 1,000; TronGrid 200 per page (all live);
  - Hyperliquid 2,000 per response and 500 per time range. — [HL docs](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint)
- **Misleading errors**: dRPC rejects 200-block ranges with a message about "ranges over 10000 blocks" (live).
- **History windows on market APIs**: GeckoTerminal 180 days and CoinGecko keyless 365 days (live).
- **Reorgs**: cryo provides `--reorg-buffer` to save blocks only once they are a given number of blocks old. — [cryo README](https://github.com/paradigmxyz/cryo)
- On Arbitrum a sequencer response *"does not mean that the transaction is posted in a batch to the parent chain, or final there"*. — [Arbitrum docs](https://docs.arbitrum.io/build-decentralized-apps/reference/node-providers)
- **BSC bulk gap**: AWS BNB has no logs or transfers, only blocks and transactions (live listing).
- **Label gaps**: no Upbit or Bithumb on Solana or Tron in open lists; DefiLlama has no Korean series (Q2).

### Inferences
- **Recommended pipeline** for about 200 tokens over 1–2 years, keyless:
  1. Build the universe: for each ticker, list (chain, contract, decimals) from Binance `getNetworkCoinAll` plus the Alpha list plus CoinGecko platforms. Keep only contracts that exchanges actually accept.
  2. Pull transfers:
     - ETH: stream daily `token_transfers` Parquet from AWS. Roughly 0.5–0.65 GB per day means ≈200–240 GB per year compressed, read with column projection and anonymous S3/HTTPS access (for example DuckDB or pyarrow; not verified here). Filter by `token_address` in the set.
     - Base and Arbitrum: the SonarX `transfers` tables.
     - BSC: SQD Portal `binance-mainnet` logs with `address`=[contracts] and `topic0`=Transfer, small block windows, honouring Retry-After. Fall back to DefiLlama balances.
     - Tron: TronGrid `/v1/contracts/{c}/events?event_name=Transfer` by time windows.
     - Solana: SQD `solana-mainnet` token balances or transfers, mapping token accounts to owners.
  3. Labels: CEX hot and cold wallets (Binance PoR + Spellbook + eth-labels), then add deposit addresses by applying the Victor/Spellbook rules to the same transfer data.
  4. Inflow per exchange per hour = Σ value of transfers whose `to` ∈ {exchange wallets ∪ its deposit addresses} and whose `from` ∉ that exchange's set.
     - Count only user→deposit legs, or only deposit→hot sweeps, never both, to avoid double counting.
     - Exclude same-exchange internal moves: hot↔cold and deposit→hot when counting at deposit level.
     - Treat cross-exchange flows separately.
  5. Validate against DefiLlama daily balance changes (Binance, OKX, Bybit) and against known events: listings, and deposit suspensions on Upbit and Bithumb.
- Sweep-level counting (to hot wallets only) is cheaper: just `topic2` ∈ hot wallets in `eth_getLogs` or in a Parquet filter. But it lags deposits by up to ~13 h (Victor's 95th-percentile t_max), and it misses exchanges that sweep rarely. Deposit-level counting is needed for hourly signals.
- Further pitfalls (my own inference; no source fetched in this session):
  - Rebasing or fee-on-transfer tokens break "sum of Transfer values = balance change".
  - Bridged or wrapped variants of a ticker on other chains must be treated as separate supply.
  - Mint and burn transfers to and from the zero address distort "inflows" around bridge events.
  - Solana transfers credit token accounts, not wallets, so owner resolution is required.

### Gaps
- End-to-end throughput of SQD Portal for BSC over 1–2 years was not measured (only single requests).
- AWS S3 anonymous egress terms and limits for this bucket were not checked beyond "no account needed".
- No benchmark of the deposit heuristics on BSC, Tron or Solana was found. Victor's calibration is ETH-only (2020); Spellbook runs it on EVM chains.
- No source was fetched on rebasing-token or Solana-ATA handling. Those items are inferences.
- SonarX `transfers` schema and coverage (whether it includes all ERC-20s and native ETH) were not inspected.

## Q4. What open-source tools (Python libraries, ETL tools) help, and what do their docs say about limits?

### Takeaway
- **cryo** (Rust CLI plus Python bindings, Apache-2.0/MIT) is the most practical RPC extractor. It has explicit throttling (`--requests-per-second`, `--max-concurrent-requests`), chunking (`--chunk-size`, `--inner-request-size` for blocks per `eth_getLogs`) and `--reorg-buffer`, and it warns that its defaults will overload third-party RPCs.
- **ethereum-etl** is older. Its `export_token_transfers` needs a local node and is "not supported by Infura". The logs-then-extract route works with providers.
- For bulk history, the "tool" is effectively Parquet readers over AWS, plus the SQD Portal API and SDKs. HyperSync and BigQuery require a token or a Google account.

### Cited Findings
- **cryo** (paradigmxyz):
  - Datasets include `logs`, `erc20_transfers`, `erc20_balances`, `erc20_metadata`, `erc20_supplies`, `transactions`, `traces`, `native_transfers`.
  - Output is Parquet by default, or CSV or JSON. Python DataFrames come via the `cryo` package.
  - Log filters: `--contract`, `--topic0..3`, `--event-signature`, `--inner-request-size` (blocks per `eth_getLogs`, default 1).
  - Rate options: `-l/--requests-per-second`, `--max-concurrent-requests`, `--max-concurrent-chunks`, `--max-retries` (default 5), `--initial-backoff` (default 500 ms).
  - Chunking: `--chunk-size` (default 1,000 blocks); `--reorg-buffer`.
  - The README warns that the defaults will overload a node, especially third-party providers.
  - Licensed Apache-2.0 and MIT.
  — [cryo README](https://github.com/paradigmxyz/cryo)
- **Ethereum ETL**:
  - `export_token_transfers` (`--start-block`, `--end-block`, `--batch-size`, `--max-workers`, `--provider-uri`, `--tokens`) is *"not supported by Infura"*.
  - `export_receipts_and_logs` plus `extract_token_transfers` is the provider-compatible route.
  - `stream` supports `-e log,token_transfer` with `--lag`.
  - The docs state no rate limits.
  — [ethereum-etl commands](https://ethereum-etl.readthedocs.io/en/latest/commands/)
- **SQD Portal** is a keyless public endpoint (rate-limited; paid tiers coming). The live dataset catalog and the stream API are described in Q1. — [SQD pricing](https://docs.sqd.dev/en/portal/pricing); [datasets](https://portal.sqd.dev/datasets)
- **Envio HyperSync** requires an API token for queries (live 401). — [HyperSync api-tokens](https://docs.envio.dev/docs/HyperSync/api-tokens)
- **BigQuery** requires a Google account. The sandbox gives 1 TiB of queries per month, 10 GiB of lifetime storage and 60-day table expiry. — [BigQuery sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox)
- **Dune Spellbook** SQL (BSL 1.1) is a reference implementation of CEX address lists, flow typing and deposit detection, not a runnable keyless tool. Running it needs Dune. — [spellbook](https://github.com/duneanalytics/spellbook); [LICENSE](https://github.com/duneanalytics/spellbook/blob/main/LICENSE)
- **eth-labels** ships labels as CSV, JSON and SQLite, plus a self-hostable API and an MCP server (`npx -y eth-labels-mcp`), under the MIT license. — [eth-labels](https://github.com/dawsbot/eth-labels)

### Inferences
- **Minimal Python stack**: `requests`/`httpx` with retry and backoff for the JSON APIs (TronGrid, Blockscout, Hyperliquid, DefiLlama, Binance); `pyarrow` or `duckdb` for AWS Parquet; cryo with `--requests-per-second 2–5 --inner-request-size 1000–5000` pointed at arb1.arbitrum.io, Tenderly or BlockPI-public for gap-filling; an SQD client for BSC and Solana. web3.py and DuckDB limits were not checked in this session.
- **Validation step**: for every chunk, assert the logs are non-empty on a block known to contain Transfer events. This catches the silent-empty failure seen on PublicNode BSC and Tron.

### Gaps
- No official docs were fetched for web3.py, DuckDB's anonymous S3 access, or the SQD Python/TypeScript SDK specifics.
- Cryo does not document the minimum node type per dataset (archive vs full).
- No tool was found that implements deposit-address clustering offline, outside Dune.
