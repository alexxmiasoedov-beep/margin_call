"""s248 — тест дубля 🐋⁺ (Ethereum + Solana; scanner._wds_*, _wd_enter) с подменой узлов Solana, Ethereum и Binance:
- адрес горячего кошелька — по сметаниям плательщика; смена адреса — счета заново;
- счета по монетам; монета без счёта;
- остатки одним запросом; скачок остатка → операции счёта → сметание ≥ 0,5% обращения → событие;
- сметание < 0,5%, пополнение кошелька не плательщиком сметаний (перекладка Binance) — не событие;
- второе событие монеты за 48 ч; вход 🐋⁺ на закрытии свечи; неспокойный рынок; 🐋 при событии Solana не входит;
- событие Ethereum — 🐋, 🐋ᵛ и 🐋⁺ одним сообщением; закрытие 🐋⁺ строкой к сообщению 🐋;
- 429 у одного узла (ответ другого); оба узла не отвечают — пауза; лимит расшифровок за проход; устаревший скачок;
- _wds_map: родной токен Solana, токен с адресом в Ethereum, не та цена, стейблкоин; адрес из сетей ввода Binance
  (основная сеть CMC — BNB, id CoinGecko не совпадает со slug CMC), _wds_bnet.
Запуск: python3 research/s248/wds_test.py"""
import json
import os
import sys
import tempfile
import urllib.error

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

D, H = 86400, 3600
T0 = 1795000000.0 // 900 * 900 + 120
CLOCK = [T0]
scanner.time.time = lambda: CLOCK[0]
trader.time.time = lambda: CLOCK[0]
LOG = []
scanner.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
trader.log = lambda *a: LOG.append(" ".join(str(x) for x in a))

# --- Ethereum (как в wdv_test): один токен AAA
B1, USER = "0x" + "b1" * 20, "0x" + "11" * 20
LAB = os.path.join(TMP, "cex_labels.tsv")
with open(LAB, "w") as f:
    f.write(f"{B1}\tBinance\tBinance 14\n")
scanner.WD_LABELS = LAB
AAA = "0x" + "aa" * 20
HEAD = [20_000_000]
ELOGS = []

# --- Solana
PAYER, HOT, HOT2, STORE, DEP = scanner.WDS_PAYER, "Hot1" + "h" * 40, "Hot2" + "g" * 40, "Store" + "s" * 39, "Dep" + "d" * 41
MINT = {"SAA": "SAA" + "a" * 41, "SBB": "SBB" + "b" * 41, "SCC": "SCC" + "c" * 41}
CIRC = {"SAA": 1e9, "SBB": 1e9, "SCC": 1e9}
PERP = {"AAA": 1.0, "SAA": 1.0, "SBB": 1.0, "SCC": 1.0, "BTC": 90000.0}
R24 = {"SBB": 0.08}
ONBOARD = {s: T0 - 400 * D for s in PERP}
TE = {}
SOL = {"down": False, "f429": set(), "calls": [], "txcalls": 0}
PAYER_SIGS = []                                # операции плательщика: [(подпись, время)]
ACC_SIGS = {}                                  # счёт → [(подпись, время)] от новых к старым
TX = {}                                        # подпись → операция
OWN = {}                                       # (владелец, монета) → [(счёт, остаток)]
BAL = {}                                       # счёт → остаток


def mk_tx(signer, mint, deltas, ts):
    """Операция: подписант-плательщик, изменения остатка монеты по владельцам {владелец: (было, стало)}."""
    keys = [{"pubkey": signer, "signer": True}] + [{"pubkey": f"acc_{o}", "signer": False} for o in deltas]
    pre, post = [], []
    for i, (o, (a, b)) in enumerate(deltas.items(), start=1):
        pre.append({"accountIndex": i, "mint": mint, "owner": o, "uiTokenAmount": {"uiAmountString": str(a)}})
        post.append({"accountIndex": i, "mint": mint, "owner": o, "uiTokenAmount": {"uiAmountString": str(b)}})
    return {"blockTime": int(ts), "meta": {"err": None, "preTokenBalances": pre, "postTokenBalances": post},
            "transaction": {"message": {"accountKeys": keys}}}


def sweep(sig, coin, n, ts, signer=PAYER, hot=HOT, acc=None, dep=DEP):
    """Сметание n монет coin с адреса пополнения на горячий кошелёк: операция, подпись на счёте, рост остатка."""
    m = MINT[coin]
    TX[sig] = mk_tx(signer, m, {dep: (n, 0.0), hot: (0.0, n)}, ts)
    acc = acc or f"ata_{hot[:4]}_{coin}"
    ACC_SIGS.setdefault(acc, []).insert(0, (sig, ts))
    BAL[acc] = BAL.get(acc, 0.0) + n


def tok_acc(owner, mint):
    return [{"pubkey": p, "account": {"data": {"parsed": {"info": {"tokenAmount": {"uiAmountString": str(a)}}}}}}
            for p, a in OWN.get((owner, mint), [])]


def solana(url, q):
    m, p = q["method"], q["params"]
    SOL["calls"].append(m)
    if SOL["down"]:
        raise urllib.error.URLError("сеть недоступна")
    if url in SOL["f429"]:
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
    if m == "getSignaturesForAddress":
        lst = [(s, t) for s, t in PAYER_SIGS] if p[0] == PAYER else ACC_SIGS.get(p[0], [])
        res = [{"signature": s, "blockTime": int(t), "err": None, "slot": 1} for s, t in lst[:p[1].get("limit", 1000)]]
    elif m == "getTransaction":
        SOL["txcalls"] += 1
        res = TX.get(p[0])
    elif m == "getTokenAccountsByOwner":
        res = {"value": tok_acc(p[0], p[1]["mint"])}
    elif m == "getMultipleAccounts":
        res = {"value": [{"data": {"parsed": {"info": {"tokenAmount": {"uiAmountString": str(BAL[a])}}}}} if a in BAL else None
                         for a in p[0]]}
    else:
        raise AssertionError(m)
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": res})


def fake_http(url, data=None, timeout=30, ctype=None):
    q = json.loads(data)
    if url in scanner.WDS_RPC:
        return solana(url, q)
    m, p = q["method"], q["params"]
    if m == "eth_blockNumber":
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": hex(HEAD[0])})
    if m == "eth_getLogs":
        f = p[0]; lo, hi = int(f["fromBlock"], 16), int(f["toBlock"], 16)
        out = [{"address": x["tok"], "blockNumber": hex(x["block"]), "logIndex": hex(i), "removed": False,
                "blockTimestamp": hex(x["ts"]), "transactionHash": "0x" + format(i, "064x"),
                "topics": [scanner.WD_TRANSFER, "0x" + "0" * 24 + USER[2:], "0x" + "0" * 24 + B1[2:]], "data": hex(x["raw"])}
               for i, x in enumerate(ELOGS) if lo <= x["block"] <= hi and x["tok"] in f["address"]]
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": out})
    raise AssertionError(m)


def klines(sym, n):
    te = TE.get(sym, 0)
    cur = int(CLOCK[0] // 900 * 900)
    out = []
    for k in range(n - 1, -1, -1):
        o = cur - k * 900
        c = PERP[sym] * ((1 + R24.get(sym, 0.0)) if te and o + 900 >= te else 1.0)
        out.append([o * 1000, c, c, c, c, 1, o * 1000 + 899999, 1e6])
    return out


def fake_http_json(url, timeout=30):
    if url.startswith("https://fapi.binance.com/fapi/v1/klines?"):
        q = dict(x.split("=") for x in url.split("?", 1)[1].split("&"))
        return klines(q["symbol"][:-4], int(q["limit"]))
    raise AssertionError(url)


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int(ONBOARD[s] * 1000), "filters": []} for s in PERP]}
    if path == "/fapi/v1/premiumIndex":
        s = params["symbol"][:-4]
        return {"markPrice": str(PERP[s] * (1 + R24.get(s, 0.0))), "lastFundingRate": "0.0001",
                "nextFundingTime": int((CLOCK[0] + 3600) * 1000)}
    if path == "/fapi/v1/fundingInfo":
        return []
    if path == "/fapi/v1/fundingRate":
        return [{"fundingTime": int(params["startTime"]) + 1000, "fundingRate": "0.0001"}]
    if path in ("/fapi/v1/markPriceKlines", "/fapi/v1/klines"):
        s = params["symbol"][:-4]; st = int(params["startTime"]); n = int(params["limit"]); pr = PERP[s]
        return [[st + i * 60000, pr, pr * 1.01, pr * 0.99, pr, 0, st + i * 60000 + 59999] for i in range(n)
                if st + i * 60000 + 59999 < CLOCK[0] * 1000]
    raise AssertionError(path)


scanner.http = fake_http
scanner.http_json = fake_http_json
trader._request = fake_request

state = {"wd": {"tok": {AAA: ["AAA", "AAA", 1e9, 1]}, "dec": {AAA: 18}, "tok_t": T0, "block": HEAD[0] - scanner.WD_CONF,
                "sol": {"tok": {MINT[c]: [c, c, CIRC[c], i] for i, c in enumerate(MINT)}, "tok_t": T0}}}
s = state["wd"]["sol"]


def run():
    LOG.clear()
    state["wd"]["tok_t"] = CLOCK[0]                          # суточное обновление списков токенов — не в этом тесте
    return scanner.whale_deposit_rule(state)


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG)); raise SystemExit(1)


def opened(key, sym):
    return [t for t in state.get(key, {}).get("trades", []) if t["sym"] == sym]


# 0. _wds_map: родной токен Solana — да; с адресом в Ethereum, не та цена, стейблкоин — нет
cmc = [{"id": 1, "symbol": "SAA", "name": "Saa", "slug": "saa", "circulatingSupply": 5e8, "quotes": [{"price": 1.0, "marketCap": 5e8}]},
       {"id": 2, "symbol": "SEE", "name": "See", "slug": "see", "circulatingSupply": 1e9, "quotes": [{"price": 1.0, "marketCap": 1e9}]},
       {"id": 3, "symbol": "SPP", "name": "Spp", "slug": "spp", "circulatingSupply": 1e9, "quotes": [{"price": 9.0, "marketCap": 9e9}]},
       {"id": 4, "symbol": "USDC", "name": "USD Coin", "slug": "usd-coin", "circulatingSupply": 7e10,
        "quotes": [{"price": 1.0, "marketCap": 7e10}]}]
cg = [{"id": "saa", "name": "Saa", "platforms": {"solana": MINT["SAA"]}},
      {"id": "see", "name": "See", "platforms": {"solana": "SEE" + "e" * 41, "ethereum": "0x" + "ee" * 20}},
      {"id": "spp", "name": "Spp", "platforms": {"solana": "SPP" + "p" * 41}},
      {"id": "usd-coin", "name": "USD Coin", "platforms": {"solana": "USDC" + "u" * 40}}]
cmc += [{"id": 5, "symbol": "SRR", "name": "Srr Sol", "slug": "srr-sol", "circulatingSupply": 2e9,
         "quotes": [{"price": 1.0, "marketCap": 2e9}], "platform": {"slug": "solana", "token_address": "SRR" + "r" * 41}},
        {"id": 6, "symbol": "SXX", "name": "Sxx", "slug": "sxx-sol", "circulatingSupply": 2e9,
         "quotes": [{"price": 1.0, "marketCap": 2e9}], "platform": {"slug": "solana", "token_address": "SXX" + "x" * 41}}]
cg += [{"id": "srr", "name": "Srr", "platforms": {"solana": "SRR" + "r" * 41}},               # slug CMC ≠ id CoinGecko
       {"id": "sxx", "name": "Sxx", "platforms": {"solana": "SXX" + "x" * 41, "ethereum": "0x" + "cd" * 20}}]
mp = scanner._wds_map(cmc, cg, {"SAA": 1.0, "SEE": 1.0, "SPP": 1.0, "USDC": 1.0, "SRR": 1.0, "SXX": 1.0})
check(set(mp) == {MINT["SAA"], "SRR" + "r" * 41} and mp[MINT["SAA"]][:3] == ["SAA", "SAA", 5e8],
      "_wds_map: родные токены Solana (адрес — у CMC или CoinGecko); с адресом в Ethereum, не та цена, стейблкоин — нет")
bj = {"code": "000000", "data": [
    {"coin": "SHH", "networkList": [{"network": "BSC", "contractAddress": "0x" + "ab" * 20},
                                    {"network": "SOL", "contractAddress": "SHH" + "h" * 41}]},
    {"coin": "SXX", "networkList": [{"network": "SOL", "contractAddress": "SXX" + "x" * 41}]},
    {"coin": "SOL", "networkList": [{"network": "SOL", "contractAddress": ""}]},
    {"coin": "SKK", "networkList": None}, "мусор"]}
bnet = scanner._wds_bnet(bj)
check(bnet == {"SHH": "SHH" + "h" * 41, "SXX": "SXX" + "x" * 41} and scanner._wds_bnet(None) == {}
      and scanner._wds_bnet({"data": "сбой"}) == {}, "_wds_bnet: адреса в Solana из сетей ввода Binance; сбой ответа — пусто")
cmc += [{"id": 7, "symbol": "SHH", "name": "Shh App", "slug": "shh-app", "circulatingSupply": 3e9,   # основная сеть CMC — BNB
         "quotes": [{"price": 1.0, "marketCap": 3e9}], "platform": {"slug": "bnb", "token_address": "0x" + "ab" * 20}}]
cg += [{"id": "shh", "name": "Shh", "platforms": {"solana": "SHH" + "h" * 41}}]                    # id и название не совпадают
px6 = {"SAA": 1.0, "SEE": 1.0, "SPP": 1.0, "USDC": 1.0, "SRR": 1.0, "SXX": 1.0, "SHH": 1.0}
mp0, mp1 = scanner._wds_map(cmc, cg, px6), scanner._wds_map(cmc, cg, px6, bnet)
check("SHH" + "h" * 41 not in mp0 and mp1.get("SHH" + "h" * 41) == ["SHH", "SHH", 3e9, 7] and "SXX" + "x" * 41 not in mp1
      and set(mp1) - {"SHH" + "h" * 41} == set(mp0),
      "_wds_map: адрес из сетей ввода Binance находит монету с основной сетью BNB; токен с адресом в Ethereum — всё равно нет")

# 1. первый проход: адрес кошелька по сметаниям плательщика, счета, первые остатки
for i, c in enumerate(("SAA", "SBB", "SAA")):
    sig = f"payer{i}"
    TX[sig] = mk_tx(PAYER, MINT[c], {DEP: (5.0, 0.0), HOT: (0.0, 5.0)}, T0 - 100 - i)
    PAYER_SIGS.append((sig, T0 - 100 - i))
OWN[(HOT, MINT["SAA"])] = [("ata_Hot1_SAA", 1000.0)]
OWN[(HOT, MINT["SBB"])] = [("ata_Hot1_SBB", 5000.0)]
BAL.update({"ata_Hot1_SAA": 1000.0, "ata_Hot1_SBB": 5000.0})
m = run()
check(s.get("hot") == HOT and s["acc"] == {MINT["SAA"]: "ata_Hot1_SAA", MINT["SBB"]: "ata_Hot1_SBB", MINT["SCC"]: ""},
      "адрес горячего кошелька найден по сметаниям плательщика; счета по монетам, у SCC счёта нет")
check(s["bal"] == {"ata_Hot1_SAA": 1000.0, "ata_Hot1_SBB": 5000.0} and not s.get("cand") and not m,
      "первые остатки записаны, скачков нет, сообщений нет")

# 2. скачки: SAA — сметание 1,2% обращения; SBB — сметание 0,3% (< 0,5%); пополнение кошелька самой Binance — не событие
CLOCK[0] += 130
sweep("sigA", "SAA", 12e6, CLOCK[0] - 60)
sweep("sigB", "SBB", 3e6, CLOCK[0] - 50)
m = run()
check("SAA" in s.get("pend", {}) and "SBB" not in s.get("pend", {}),
      f"сметание SAA 1,2% — событие; сметание SBB 0,3% — нет (в ожидании: {sorted(s.get('pend', {}))})")
check(any("событие 🐋⁺" in x and "SAA" in x for x in LOG) and not s.get("cand"), "строка о событии, кандидаты разобраны")
te = s["pend"]["SAA"]["te"]; TE["SAA"] = te; ta = s["pend"]["SAA"]["t"]
CLOCK[0] += 130
TX["refill"] = mk_tx(STORE, MINT["SAA"], {STORE: (5e7, 0.0), HOT: (0.0, 5e7)}, CLOCK[0] - 30)
ACC_SIGS["ata_Hot1_SAA"].insert(0, ("refill", CLOCK[0] - 30)); BAL["ata_Hot1_SAA"] += 5e7
m = run()
check(s["pend"]["SAA"]["t"] == ta and "refill" in s["seen"],
      "пополнение кошелька не плательщиком сметаний (перекладка Binance) разобрано, но события нет")

# 3. вход 🐋⁺ на закрытии свечи: сделка только 🐋⁺, у 🐋 сделки нет
CLOCK[0] = te + 60
m = run()
check(len(opened("virtual_WDS", "SAA")) == 1 and not opened("virtual_WD", "SAA"),
      "событие Solana: шорт 🐋⁺, у 🐋 сделки нет")
check(any("🐋⁺" in x and "Solana" in x for x in m), "сообщение 🐋⁺ о заводе в Solana")

# 4. второе сметание SAA за 48 ч — без события; SBB 0,8% при неспокойном рынке — без сделки
CLOCK[0] += 600
sweep("sigA2", "SAA", 9e6, CLOCK[0] - 60)
sweep("sigB2", "SBB", 8e6, CLOCK[0] - 50)
run()
check("SAA" not in s.get("pend", {}) and any("событие монеты в Solana было" in x for x in LOG),
      "второе сметание SAA за 48 ч — без события")
teb = s["pend"]["SBB"]["te"]; TE["SBB"] = teb
CLOCK[0] = teb + 60
run()
check(not opened("virtual_WDS", "SBB") and any("рынок не спокойный, 🐋⁺ без сделки" in x for x in LOG),
      "SBB: фьючерс за сутки +8% — 🐋⁺ без сделки")

# 5. событие Ethereum: 🐋, 🐋ᵛ и 🐋⁺ одним сообщением
CLOCK[0] += 120
ELOGS.append({"block": HEAD[0] + 1, "ts": int(CLOCK[0] - 60), "tok": AAA, "raw": int(2e7 * 10 ** 18)})   # 2% обращения
HEAD[0] += 10
state["wd"]["poll_t"] = 0
run()
pe = state["wd"]["pend"]["AAA"]; TE["AAA"] = pe["te"]
CLOCK[0] = pe["te"] + 60
m = run()
check(opened("virtual_WD", "AAA") and opened("virtual_WDS", "AAA"), "событие Ethereum: шорт 🐋 и 🐋⁺")
check(len([x for x in m if "AAA" in x]) == 1 and any("🐋⁺ тот же шорт" in x for x in m),
      "🐋⁺ — строкой к сообщению 🐋")

# 6. закрытие через 24 ч: 🐋⁺ по AAA — строкой к сообщению 🐋, по SAA — отдельно
CLOCK[0] = pe["te"] + 24 * H + 120
out = trader.virt_manage(state)
txt = "\n".join(out)
check(any("🐋" in x and "AAA" in x and "\n🐋⁺" in x for x in out), "закрытие 🐋⁺ по AAA — строкой к сообщению 🐋")
check(opened("virtual_WDS", "SAA")[0].get("closed"), "сделка 🐋⁺ по SAA закрыта по времени")

# 7. 429 у одного узла — отвечает другой; оба не отвечают — пауза и строка
SOL["f429"] = {scanner.WDS_RPC[0]}
s["poll_t"] = 0
run()
check(not s.get("rpc_next"), "429 у одного узла Solana — ответ другого, паузы нет")
SOL["f429"] = set(); SOL["down"] = True; s["poll_t"] = 0
run()
check(s.get("rpc_next", 0) > CLOCK[0] and any("Solana:" in x and "повтор через" in x for x in LOG),
      "узлы Solana не отвечают — пауза и строка «ЗАВОДЫ»")
SOL["down"] = False
CLOCK[0] = s["rpc_next"] + 1

# 8. лимит расшифровок за проход: 8 новых операций на счёте — 6 в одном проходе, остальные — в следующем
s["poll_t"] = 0
for i in range(8):
    sweep(f"small{i}", "SAA", 1e5, CLOCK[0] - 80 + i)
BAL["ata_Hot1_SAA"] += 3e6                               # общий скачок ≥ 0,2% обращения
SOL["txcalls"] = 0
run()
first = SOL["txcalls"]
s["poll_t"] = CLOCK[0]                                   # следующий проход — без нового опроса остатков
CLOCK[0] += 30
run()
check(first == scanner.WDS_TX and SOL["txcalls"] == 8 and not s.get("cand"),
      f"расшифровок за проход не больше {scanner.WDS_TX}, остальные — в следующем ({first} + {SOL['txcalls'] - first})")

# 9. скачок, не разобранный вовремя (> 30 мин), — пропуск со строкой
s["cand"] = {"ata_Hot1_SBB": {"m": MINT["SBB"], "since": CLOCK[0] - 3 * H}}
run()
check(not s.get("cand") and any("не разобран вовремя" in x for x in LOG), "устаревший скачок — пропуск со строкой")

# 10. смена горячего кошелька через сутки: адрес по свежим сметаниям, счета заново
CLOCK[0] += D
PAYER_SIGS[:0] = [(f"p2_{i}", CLOCK[0] - 10 - i) for i in range(3)]
for i in range(3):
    TX[f"p2_{i}"] = mk_tx(PAYER, MINT["SAA"], {DEP: (1.0, 0.0), HOT2: (0.0, 1.0)}, CLOCK[0] - 10 - i)
OWN[(HOT2, MINT["SAA"])] = [("ata_Hot2_SAA", 10.0)]
BAL["ata_Hot2_SAA"] = 10.0
run()
check(s["hot"] == HOT2 and s["acc"].get(MINT["SAA"]) == "ata_Hot2_SAA" and any("сменился" in x for x in LOG),
      "горячий кошелёк сменился — строка, счета собраны заново")
print("все проверки пройдены")
