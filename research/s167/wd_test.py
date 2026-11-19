"""s167 — тест журнала 🐋 (scanner.whale_deposit_rule) с подменой узлов Ethereum, CoinMarketCap, CoinGecko и Binance:
нет файла меток; список токенов за три прохода (монеты с одинаковым тикером, сверка цены, множитель 1000, стейблкоин,
токен без ERC-20); знаки после запятой (в том числе токен без decimals()); события — порог 0,5%, отправитель-биржа,
кастоди среди адресов Binance, вторая выдача за 48 ч и новая после 48 ч; вход — спокойный и неспокойный рынок, молодой
фьючерс, опоздание больше 30 мин; догон пропущенных блоков; сбой узлов (строка не чаще раза в час); выход через 24 ч."""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

D, H = 86400, 3600
T0 = 1795000000.0 // 900 * 900 + 120          # «сейчас» в начале теста (2 мин после закрытия 15-мин свечи)
CLOCK = [T0]
scanner.time.time = lambda: CLOCK[0]
trader.time.time = lambda: CLOCK[0]
LOG = []
scanner.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
trader.log = lambda *a: LOG.append(" ".join(str(x) for x in a))

# --- метки бирж
B1, B2, BW = "0x" + "b1" * 20, "0x" + "b2" * 20, "0x" + "bf" * 20      # Binance, Binance, «Binance Wintermute Deposit»
CB = "0x" + "cb" * 20                                                  # Coinbase — отправитель-биржа
USER = "0x" + "11" * 20
LAB = os.path.join(TMP, "cex_labels.tsv")
scanner.WD_LABELS = LAB

# --- токены: адрес, тикер CMC, платформа CMC, цена CMC, капитализация, монет в обращении, decimals
AAA, BBB, DDD, DDX, YNG, RRR, CCC, USD, EEE, QQQ = ("0x" + h * 20 for h in ("aa", "bb", "dd", "d0", "ee", "77", "cc", "55", "e0", "99"))
CMC = [
    {"id": 10, "symbol": "ZQZ", "name": "Zqz", "slug": "zqz", "circulatingSupply": 1e8,
     "quotes": [{"price": 1.0, "marketCap": 1e8}], "platform": {"slug": "ethereum", "token_address": QQQ}},       # первый узел —
    # откат decimals(), остальные не отвечают: −1, а не повтор, иначе очередь знаков встала бы
    {"id": 1, "symbol": "AAA", "name": "Aaa", "slug": "aaa", "circulatingSupply": 1e9, "quotes": [{"price": 1.0, "marketCap": 1e9}],
     "platform": {"slug": "ethereum", "token_address": AAA.upper().replace("0X", "0x")}},
    {"id": 2, "symbol": "BBB", "name": "Bbb Token", "slug": "bbb-token", "circulatingSupply": 1e12,
     "quotes": [{"price": 2e-5, "marketCap": 2e7}], "platform": {"slug": "bnb", "token_address": "0xbsc"}},       # адрес — у CoinGecko
    {"id": 3, "symbol": "DDD", "name": "Ddd Big", "slug": "ddd-big", "circulatingSupply": 1e8,
     "quotes": [{"price": 50.0, "marketCap": 5e9}], "platform": {"slug": "ethereum", "token_address": DDX}},     # цена не та
    {"id": 4, "symbol": "DDD", "name": "Ddd", "slug": "ddd", "circulatingSupply": 5e8,
     "quotes": [{"price": 2.0, "marketCap": 1e9}], "platform": {"slug": "ethereum", "token_address": DDD}},
    {"id": 5, "symbol": "YNG", "name": "Young", "slug": "young", "circulatingSupply": 1e8,
     "quotes": [{"price": 1.0, "marketCap": 1e8}], "platform": {"slug": "ethereum", "token_address": YNG}},
    {"id": 6, "symbol": "RRR", "name": "Rrr", "slug": "rrr", "circulatingSupply": 1e8,
     "quotes": [{"price": 1.0, "marketCap": 1e8}], "platform": {"slug": "ethereum", "token_address": RRR}},      # нет decimals()
    {"id": 7, "symbol": "CCC", "name": "Ccc", "slug": "ccc", "circulatingSupply": 1e8,
     "quotes": [{"price": 3.0, "marketCap": 3e8}], "platform": {"slug": "ethereum", "token_address": CCC}},      # цена ×3
    {"id": 8, "symbol": "USDC", "name": "USD Coin", "slug": "usd-coin", "circulatingSupply": 7e10,
     "quotes": [{"price": 1.0, "marketCap": 7e10}], "platform": {"slug": "ethereum", "token_address": USD}},     # стейблкоин
    {"id": 9, "symbol": "EEE", "name": "Eee", "slug": "eee", "circulatingSupply": 1e8,
     "quotes": [{"price": 1.0, "marketCap": 1e8}], "platform": {"slug": "solana", "token_address": "So1"}},      # нет ERC-20
]
CG = [{"id": "bbb-token", "symbol": "bbb", "name": "Bbb Token", "platforms": {"ethereum": BBB, "binance-smart-chain": "0xbsc"}},
      {"id": "eee", "symbol": "eee", "name": "Eee", "platforms": {"solana": "So1"}},
      {"id": "noise", "symbol": "aaa", "name": "Other Aaa", "platforms": {"ethereum": "0x" + "99" * 20}}]
PERP = {"ZQZ": 1.0, "AAA": 1.0, "1000BBB": 0.02, "DDD": 2.0, "YNG": 1.0, "RRR": 1.0, "CCC": 1.0, "USDC": 1.0, "EEE": 1.0, "BTC": 90000.0}
DEC = {AAA: 18, BBB: 9, DDD: 18, YNG: 6}                  # RRR — decimals() откатывается
ONBOARD = {s: T0 - 400 * D for s in PERP}
R24 = {"AAA": 0.02, "1000BBB": -0.03, "DDD": 0.08, "YNG": 0.0}   # ход фьючерса за сутки до входа
CALLS = {"cmc": 0, "cg": 0, "px": 0, "logs": [], "dec": 0}
FAIL = {"rpc": False}

HEAD = [20_000_000]
LOGS = []                                                  # (блок, время, токен, от, кому, сумма в единицах токена)


def add_log(block, tok, frm, to, amount, ts):
    LOGS.append(dict(block=block, ts=int(ts), tok=tok, frm=frm, to=to, raw=int(round(amount * 10 ** DEC.get(tok, 18)))))


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def fake_http(url, data=None, timeout=30, ctype=None):
    if FAIL["rpc"]:
        raise scanner.urllib.error.URLError("сеть недоступна")
    q = json.loads(data)
    m, p = q["method"], q["params"]
    if m == "eth_blockNumber":
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": hex(HEAD[0])})
    if m == "eth_call":
        CALLS["dec"] += 1
        a = p[0]["to"]
        if a == QQQ and "tenderly" not in url:
            raise scanner.urllib.error.URLError("узел недоступен")
        if a in DEC:
            return json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0x" + format(DEC[a], "064x")})
        return json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": 3, "message": "execution reverted"}})
    if m == "eth_getLogs":
        f = p[0]; lo, hi = int(f["fromBlock"], 16), int(f["toBlock"], 16)
        CALLS["logs"].append((lo, hi, set(f["topics"][2])))
        out = []
        for i, x in enumerate(LOGS):
            if lo <= x["block"] <= hi and x["tok"] in f["address"] and pad(x["to"]) in f["topics"][2]:
                out.append({"address": x["tok"], "blockNumber": hex(x["block"]), "logIndex": hex(i), "removed": False,
                            "blockTimestamp": hex(x["ts"]), "transactionHash": "0x" + format(i, "064x"),
                            "topics": [scanner.WD_TRANSFER, pad(x["frm"]), pad(x["to"])], "data": hex(x["raw"])})
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": out})
    raise AssertionError(m)


def klines(sym, n):
    """15-мин свечи фьючерса: последняя — текущая (не закрыта); закрытие свечи входа (и позже) = база × (1 + R24)."""
    te = state.get("wd", {}).get("pend", {}).get(sym, {}).get("te", 0)
    cur = int(CLOCK[0] // 900 * 900)
    out = []
    for k in range(n - 1, -1, -1):
        o = cur - k * 900
        c = PERP[sym] * ((1 + R24.get(sym, 0.0)) if te and o + 900 >= te else 1.0)
        out.append([o * 1000, c, c, c, c, 1, o * 1000 + 899999, 1000.0])
    return out


def fake_http_json(url, timeout=30):
    if url.startswith("https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing"):
        CALLS["cmc"] += 1
        return {"data": {"cryptoCurrencyList": CMC}}
    if url == scanner.WD_CG:
        CALLS["cg"] += 1
        return CG
    if url == "https://fapi.binance.com/fapi/v1/ticker/price":
        CALLS["px"] += 1
        return [{"symbol": f"{s}USDT", "price": str(p)} for s, p in PERP.items()]
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
        return {"markPrice": str(PERP[s]), "lastFundingRate": "0.0001", "nextFundingTime": int((CLOCK[0] + 3600) * 1000)}
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
state = {}
ALL = []


def run():
    LOG.clear()
    m = scanner.whale_deposit_rule(state)
    ALL.extend(LOG)
    return m


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG)); raise SystemExit(1)


def trades():
    return state.get("virtual_WD", {}).get("trades", [])


# 1. нет файла меток — правило молчит, строка раз в сутки
m = run()
check(not m and any("нет файла меток" in x for x in LOG) and CALLS["cmc"] == 0, "нет файла меток — правило молчит, без запросов")
CLOCK[0] += 60; run()
check(not any("нет файла меток" in x for x in LOG), "строка о файле — не чаще раза в сутки")
with open(LAB, "w") as f:
    f.write("# тест\n")
    for a, ex, nm in ((B1, "Binance", "Binance 14"), (B2, "Binance", "Binance 20"), (BW, "Binance", "Binance Wintermute Deposit 1"),
                      (CB, "Coinbase", "Coinbase 10")):
        f.write(f"{a}\t{ex}\t{nm}\n")
# 2. список токенов: CMC, CoinGecko, цены Binance — по одному запросу за проход
CLOCK[0] += 60; run()
check(CALLS["cmc"] == 1 and CALLS["cg"] == 0 and not state["wd"].get("tok"), "проход 1: список CMC (меньше 5000 монет — одна страница)")
CLOCK[0] += 60; run()
check(CALLS["cg"] == 1 and CALLS["px"] == 0, "проход 2: список CoinGecko")
CLOCK[0] += 60; run()
tok = state["wd"]["tok"]
check(CALLS["px"] == 1 and set(tok) == {QQQ, AAA, BBB, DDD, YNG, RRR}, f"проход 3: цены Binance и список — {sorted(v[0] for v in tok.values())}")
check(tok[BBB][0] == "1000BBB" and tok[DDD][2] == 5e8 and tok[AAA][2] == 1e9,
      "BBB: адрес у CoinGecko, фьючерс 1000BBB; DDD: из двух монет взята та, у которой сходится цена")
check(any("список токенов Ethereum" in x for x in LOG), "строка об обновлении списка")
dec = state["wd"]["dec"]
check(dec == {QQQ: -1, AAA: 18, BBB: 9, DDD: 18, YNG: 6, RRR: -1}, f"знаки после запятой за один проход; RRR без decimals() и QQQ (откат у одного узла, остальные не ответили) — −1: {dec}")
check({pad(B1), pad(B2)} == CALLS["logs"][-1][2] if CALLS["logs"] else False,
      "в запросе переводов — только адреса Binance, без «Wintermute Deposit»")
h0 = HEAD[0]
check(state["wd"]["block"] == h0 - scanner.WD_CONF and CALLS["logs"][-1][0] == h0 - scanner.WD_CONF - 9,
      "первый опрос — последние 10 блоков с отставанием 3 блока")
# 3. переводы
t_a = CLOCK[0] + 60
HEAD[0] += 10; b = HEAD[0] - scanner.WD_CONF
add_log(b, AAA, USER, B1, 6e6, t_a)                      # 0,6% → событие
add_log(b, BBB, USER, B1, 4e9, t_a)                      # 0,4% → мимо
add_log(b, BBB, CB, B2, 9e9, t_a)                        # с Coinbase → перекладка, мимо
add_log(b, DDD, USER, B2, 1e7, t_a)                      # 2% → событие, но фьючерс +8%
add_log(b, YNG, USER, B1, 1e6, t_a)                      # 1% → событие, но фьючерс моложе суток
add_log(b, RRR, USER, B1, 1e7, t_a)                      # без decimals() → мимо
add_log(b, AAA, USER, BW, 9e7, t_a)                      # на «Wintermute Deposit» — не в запросе
ONBOARD["YNG"] = t_a - 12 * H
trader._contracts.clear()
CLOCK[0] += scanner.WD_EVERY; m = run()
pend = state["wd"]["pend"]
check(set(pend) == {"AAA", "DDD", "YNG"} and not m, f"события AAA, DDD, YNG ждут входа: {sorted(pend)}")
te = pend["AAA"]["te"]
check(te == -(-(int(t_a) + 900) // 900) * 900, "вход — закрытие первой 15-мин свечи не раньше чем через 15 мин после блока")
check(not any("BBB" in x for x in LOG), "BBB: 0,4% и перевод с Coinbase — без строк")
print("   журнал:", *[x for x in LOG if "ЗАВОДЫ" in x], sep="\n   ")
# повторный завод AAA через 10 ч — без события
HEAD[0] += 5; add_log(HEAD[0] - scanner.WD_CONF, AAA, USER, B2, 2e7, t_a + 10 * H)
CLOCK[0] += scanner.WD_EVERY; run()
check(any("AAA" in x and "было 10 ч назад" in x for x in LOG) and pend["AAA"]["te"] == te, "второй завод AAA через 10 ч — без события")
# 4. вход
CLOCK[0] = te - 60; m = run()
check(not m and not trades(), "за минуту до свечи входа сделок нет")
CLOCK[0] = te + 40; m = run()
tr = trades()
check(len(m) == 1 and m[0].startswith("🐋") and len(tr) == 1 and tr[0]["sym"] == "AAA", "AAA: шорт 🐋, сообщение в чат")
t = tr[0]
check(abs(t["sl"] - 1.25) < 1e-9 and t["tp"] is None and t["lev"] == 1 and t["hold_h"] == 24.0 and t.get("hedge_sym") == "BTC",
      "стоп +25%, без тейка, плечо ×1, 24 ч, хедж BTC")
check(any("DDD" in x and "+8.0%" in x and "не спокойный" in x for x in LOG) and "DDD" not in pend, "DDD: фьючерс +8% — сделки нет")
check(any("YNG" in x and "моложе суток" in x for x in LOG) and "YNG" not in pend, "YNG: фьючерс моложе суток — сделки нет")
print("   сообщение:", m[0].replace("\n", " | "))
# 5. опоздание больше 30 мин
t_b = CLOCK[0] + 60
HEAD[0] += 5; add_log(HEAD[0] - scanner.WD_CONF, BBB, USER, B1, 1e10, t_b)     # 1% → событие
CLOCK[0] += scanner.WD_EVERY; run()
te_b = state["wd"]["pend"]["1000BBB"]["te"]
CLOCK[0] = te_b + scanner.WD_LATE + 60; m = run()
check(not m and "1000BBB" not in state["wd"]["pend"] and any("опоздал" in x for x in LOG), "1000BBB: вход опоздал больше 30 мин — сделки нет")
# 6. новое событие AAA через 48 ч — снова вход (сделка закрыта по времени)
CLOCK[0] = trades()[0]["opened"] + 24 * H + 120
trader.virt_manage(state)
check(trades()[0].get("closed") and str(trades()[0].get("reason")).startswith("выход по времени (24 ч)"), "через 24 ч сделка AAA закрыта по времени")
t_c = t_a + 49 * H
CLOCK[0] = t_c - 60
HEAD[0] += 5; add_log(HEAD[0] - scanner.WD_CONF, AAA, USER, B1, 8e6, t_c)
CLOCK[0] += scanner.WD_EVERY; run()
check("AAA" in state["wd"]["pend"], "AAA через 49 ч после первого события — новое событие")
CLOCK[0] = state["wd"]["pend"]["AAA"]["te"] + 30; m = run()
check(len(m) == 1 and len(trades()) == 2, "вход по новому событию AAA")
# 7. догон блоков: бот не работал — не больше WD_BACK блоков
state["wd"]["block"] = HEAD[0] - 5000; HEAD[0] += 1; n0 = len(CALLS["logs"])
CLOCK[0] += scanner.WD_EVERY; run()
lo = min(x[0] for x in CALLS["logs"][n0:])
check(any("пропущено" in x for x in LOG) and lo == HEAD[0] - scanner.WD_CONF - scanner.WD_BACK + 1
      and state["wd"]["block"] == HEAD[0] - scanner.WD_CONF, f"догон — последние {scanner.WD_BACK} блоков, кусками по {scanner.WD_STEP}")
# 8. сбой узлов — строка не чаще раза в час, блоки не теряются
blk = state["wd"]["block"]; FAIL["rpc"] = True
CLOCK[0] += scanner.WD_EVERY; run()
check(any("не отдали номер блока" in x for x in LOG) and state["wd"]["block"] == blk, "сбой узлов — строка в журнале, позиция не сдвинулась")
CLOCK[0] += scanner.WD_EVERY; run()
check(not any("не отдали" in x for x in LOG) and state["wd"]["rpc_wait"] == 2 * scanner.WD_EVERY,
      "второй сбой в течение часа — без строки, пауза выросла до 4 мин")
FAIL["rpc"] = False; HEAD[0] += 2; n0 = len(CALLS["logs"])
CLOCK[0] += scanner.WD_EVERY; run()
check(len(CALLS["logs"]) == n0 and state["wd"]["block"] == blk, "во время паузы узлы не опрашиваются")
CLOCK[0] += scanner.WD_EVERY; run()
check(state["wd"]["block"] == HEAD[0] - scanner.WD_CONF and CALLS["logs"][-1][0] == blk + 1 and "rpc_wait" not in state["wd"],
      "после паузы — продолжение с того же блока, пауза сброшена")
# 9. список токенов — раз в сутки
n = CALLS["cmc"]; CLOCK[0] += 3600; run()
check(CALLS["cmc"] == n, "список токенов не перезапрашивается раньше суток")
CLOCK[0] += scanner.WD_LIST_EVERY; run()
check(CALLS["cmc"] == n + 1, "через сутки — новый список")
print("все проверки пройдены")
