"""Тест двойника 🐋ᵛ (scanner._wd_enter, _wdv_lambda; research/s213) с подменой узлов Ethereum и Binance: λ = завод по цене
входа / среднесуточный оборот фьючерса за 7 сут до свечи входа ≥ 0,05 — вход вместе с 🐋 одной строкой; окно оборота — ровно
672 свечи перед свечой входа (свеча входа, свечи до окна и после входа не считаются); множитель фьючерса (1000BBB); малый λ;
фьючерс моложе 7 сут; событие без суммы завода (из прежней версии бота); опоздание на 20 мин; Binance не отдал цену — повтор;
мало баланса у 🐋ᵛ; неспокойный рынок; закрытие 🐋ᵛ строкой к сообщению 🐋; блок 🐋ᵛ в /virtual.
Запуск: python3 research/s167/wdv_test.py"""
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

B1 = "0x" + "b1" * 20                          # адрес Binance
USER = "0x" + "11" * 20
LAB = os.path.join(TMP, "cex_labels.tsv")
with open(LAB, "w") as f:
    f.write(f"{B1}\tBinance\tBinance 14\n")
scanner.WD_LABELS = LAB

# токены: адрес → (фьючерс, монета, монет в обращении); цена фьючерса; оборот 15-мин свечи в окне 7 сут
A = {s: "0x" + h * 20 for s, h in (("AAA", "aa"), ("CCC", "cc"), ("YNG", "ee"), ("1000BBB", "bb"), ("EEE", "e0"),
                                   ("FFF", "ff"), ("GGG", "99"), ("HHH", "88"))}
CIRC = {"AAA": 1e9, "CCC": 1e9, "YNG": 1e8, "1000BBB": 1e12, "EEE": 1e9, "FFF": 1e9, "GGG": 1e9, "HHH": 1e9}
PERP = {"AAA": 1.0, "CCC": 1.0, "YNG": 1.0, "1000BBB": 0.02, "EEE": 1.0, "FFF": 1.0, "GGG": 1.0, "HHH": 1.0, "DDD": 2.0,
        "BTC": 90000.0}
QV = {"AAA": 1e6, "CCC": 2e6, "YNG": 1e5, "1000BBB": 3000.0, "EEE": 1e6, "FFF": 1e6, "GGG": 1e6, "HHH": 1e6, "DDD": 1e6}
HUGE = 1e12                                    # оборот свечи входа, свечей до окна и после входа — не должен попасть в λ
R24 = {"HHH": 0.07}                            # ход фьючерса за сутки до входа
ONBOARD = {s: T0 - 400 * D for s in PERP}
ONBOARD["YNG"] = T0 - 3 * D                    # фьючерс старше суток, но моложе 7 сут
TE = {}                                        # фьючерс → закрытие свечи входа (для подмены свечей)
NOPX = set()                                   # фьючерсы, для которых Binance «не отдаёт» марк-цену
HEAD = [20_000_000]
LOGS = []
state = {"wd": {"tok": {A[s]: [s, scanner._wd_base(s)[0], CIRC[s], i] for i, s in enumerate(A)},
                "dec": {a: 18 for a in A.values()}, "tok_t": T0, "block": HEAD[0] - scanner.WD_CONF,
                "sol": {"tok_t": T0}}}                 # список Solana (🐋⁺) уже собран — без запросов CMC в этом тесте


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def fake_http(url, data=None, timeout=30, ctype=None):
    q = json.loads(data)
    m, p = q["method"], q["params"]
    if m == "eth_blockNumber":
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": hex(HEAD[0])})
    if m == "eth_getLogs":
        f = p[0]; lo, hi = int(f["fromBlock"], 16), int(f["toBlock"], 16)
        out = [{"address": x["tok"], "blockNumber": hex(x["block"]), "logIndex": hex(i), "removed": False,
                "blockTimestamp": hex(x["ts"]), "transactionHash": "0x" + format(i, "064x"),
                "topics": [scanner.WD_TRANSFER, pad(USER), pad(B1)], "data": hex(x["raw"])}
               for i, x in enumerate(LOGS) if lo <= x["block"] <= hi and x["tok"] in f["address"]]
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": out})
    raise AssertionError(m)


def klines(sym, n):
    """15-мин свечи фьючерса: последняя — текущая (не закрыта); оборот в окне 7 сут перед свечой входа — QV, иначе HUGE;
    закрытие свечи входа и позже = цена × (1 + R24); свечи — только после запуска фьючерса."""
    te = TE.get(sym, 0)
    cur = int(CLOCK[0] // 900 * 900)
    out = []
    for k in range(n - 1, -1, -1):
        o = cur - k * 900
        if o < ONBOARD[sym]:
            continue
        c = PERP[sym] * ((1 + R24.get(sym, 0.0)) if te and o + 900 >= te else 1.0)
        qv = QV[sym] if te - 900 - 7 * D <= o < te - 900 else HUGE
        out.append([o * 1000, c, c, c, c, 1, o * 1000 + 899999, qv])
    return out


def fake_http_json(url, timeout=30):
    if url.startswith("https://fapi.binance.com/fapi/v1/klines?"):
        q = dict(x.split("=") for x in url.split("?", 1)[1].split("&"))
        CALLS.append(int(q["limit"]))
        return klines(q["symbol"][:-4], int(q["limit"]))
    raise AssertionError(url)


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int(ONBOARD[s] * 1000), "filters": []} for s in PERP]}
    if path == "/fapi/v1/premiumIndex":
        s = params["symbol"][:-4]
        if s in NOPX:
            return {}
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


CALLS = []
scanner.http = fake_http
scanner.http_json = fake_http_json
trader._request = fake_request


def run():
    LOG.clear()
    return scanner.whale_deposit_rule(state)


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG)); raise SystemExit(1)


def trades(key, sym=None):
    return [t for t in state.get(key, {}).get("trades", []) if sym is None or t["sym"] == sym]


def event(sym, tokens, dt=60):
    """Завод sym на Binance через dt с; прогон, пока событие не встанет в очередь. → закрытие свечи входа."""
    ts = CLOCK[0] + dt
    HEAD[0] += 5
    LOGS.append(dict(block=HEAD[0] - scanner.WD_CONF, ts=int(ts), tok=A[sym], raw=int(round(tokens * 10 ** 18))))
    CLOCK[0] += scanner.WD_EVERY; run()
    p = state["wd"]["pend"][sym]
    TE[sym] = p["te"]
    return p["te"]


def lam(sym, tokens):
    return tokens * PERP[sym] / scanner._wd_base(sym)[1] / (QV[sym] * 672 / 7)


# 1. крупный к обороту завод AAA: λ = 6 млн $ / 96 млн $ = 0,0625 → 🐋 и 🐋ᵛ одной строкой
te = event("AAA", 6e6)
check(abs(state["wd"]["pend"]["AAA"]["n"] - 6e6) < 1e-3, "в событии записана сумма завода в монетах")
CLOCK[0] = te + 40; m = run()
check(CALLS[-1] == scanner.WDV_K, f"свечи входа — одним запросом на {scanner.WDV_K} свечей (7 сут и запас)")
w, v = trades("virtual_WD", "AAA"), trades("virtual_WDV", "AAA")
check(len(m) == 1 and m[0].startswith("🐋 сигнал") and "\n🐋ᵛ тот же шорт: завод 6.00 млн $ — 6.2% среднесуточного оборота "
      "фьючерса за 7 сут (96.00 млн $)" in m[0] and len(w) == 1 and len(v) == 1,
      f"AAA: λ {lam('AAA', 6e6):.4f} — шорт 🐋 и 🐋ᵛ, одно сообщение")
t = v[0]
check(abs(t["sl"] - 1.25) < 1e-9 and t["tp"] is None and t["lev"] == 1 and t["hold_h"] == 24.0 and t.get("hedge_sym") == "BTC"
      and abs(t["opened"] - w[0]["opened"]) < 1, "🐋ᵛ: стоп +25%, без тейка, плечо ×1, 24 ч, хедж BTC, вход вместе с 🐋")
check("AAA" not in state["wd"]["pend"] and any("→ шорт 🐋ᵛ" in x for x in LOG), "событие снято, строка «ЗАВОДЫ» о двойнике")
print("   сообщение:", m[0].replace("\n", " | "))
# 2. малый λ: CCC — 6 млн $ к 192 млн $ в сутки = 3,1%
te = event("CCC", 6e6)
CLOCK[0] = te + 40; m = run()
check(len(m) == 1 and trades("virtual_WD", "CCC") and not trades("virtual_WDV", "CCC")
      and "\n🐋ᵛ без входа: завод 6.00 млн $ — 3.1% среднесуточного оборота фьючерса за 7 сут (192.00 млн $) — меньше 5%" in m[0],
      "CCC: λ 0,031 — шорт 🐋, у 🐋ᵛ строка «без входа»")
# 3. множитель фьючерса: 1000BBB — 1e10 монет × 0,02 / 1000 = 200 тыс. $ к 288 тыс. $ в сутки
te = event("1000BBB", 1e10)
CLOCK[0] = te + 40; m = run()
v = trades("virtual_WDV", "1000BBB")
check(len(m) == 1 and len(v) == 1 and "завод 200 тыс. $ — 69.4% среднесуточного оборота фьючерса за 7 сут (288 тыс. $)" in m[0],
      f"1000BBB: поправка на множитель, λ {lam('1000BBB', 1e10):.3f}")
# 4. фьючерс моложе 7 сут (свечей меньше) — 🐋 входит, 🐋ᵛ нет
te = event("YNG", 1e6)
CLOCK[0] = te + 40; m = run()
check(len(m) == 1 and trades("virtual_WD", "YNG") and not trades("virtual_WDV", "YNG")
      and "🐋ᵛ без входа: оборот фьючерса за 7 сут не посчитан" in m[0], "YNG: фьючерсу 3 сут — у 🐋ᵛ «не посчитан», без входа")
# 5. событие из прежней версии бота (без суммы завода)
TE["DDD"] = te_d = int(CLOCK[0] // 900 * 900) + 900
state["wd"]["pend"]["DDD"] = {"t": te_d - 900, "te": te_d, "share": 1.0, "what": "DDD: тест"}
CLOCK[0] = te_d + 40; m = run()
check(len(m) == 1 and trades("virtual_WD", "DDD") and not trades("virtual_WDV", "DDD") and "не посчитан" in m[0],
      "событие без суммы завода — 🐋 входит, 🐋ᵛ нет")
# 6. опоздание на 20 мин: свечи после входа (огромный оборот) в окно не попадают
te = event("EEE", 6e6)
CLOCK[0] = te + 20 * 60 + 40; m = run()
check(len(m) == 1 and trades("virtual_WDV", "EEE") and "6.2% среднесуточного оборота" in m[0], "вход с опозданием 20 мин — λ тот же")
# 7. Binance не отдал цену — повтор в следующем проходе, потом вход обоих
te = event("FFF", 6e6)
NOPX.add("FFF"); CLOCK[0] = te + 40; m = run()
check(not m and not trades("virtual_WD", "FFF") and not trades("virtual_WDV", "FFF") and "FFF" in state["wd"]["pend"],
      "нет цены — ни 🐋, ни 🐋ᵛ, событие ждёт")
NOPX.clear(); CLOCK[0] += 60; m = run()
check(len(m) == 1 and trades("virtual_WD", "FFF") and trades("virtual_WDV", "FFF") and "🐋ᵛ тот же шорт" in m[0],
      "следующий проход — вход обоих одной строкой")
# 8. у 🐋ᵛ мало баланса — два сообщения
state["virtual_WDV"]["balance"] = 0.5
te = event("GGG", 6e6)
CLOCK[0] = te + 40; m = run()
check(len(m) == 2 and m[0].startswith("🐋 сигнал") and m[1].startswith("🐋ᵛ GGG: сигнал WD, но на виртуальном балансе")
      and not trades("virtual_WDV", "GGG"), "мало баланса у 🐋ᵛ — сообщение 🐋 и отдельное сообщение 🐋ᵛ")
state["virtual_WDV"]["balance"] = 20.0
# 9. неспокойный рынок — ни 🐋, ни 🐋ᵛ
te = event("HHH", 6e6)
CLOCK[0] = te + 40; m = run()
check(not m and not trades("virtual_WD", "HHH") and not trades("virtual_WDV", "HHH") and "HHH" not in state["wd"]["pend"],
      "HHH: фьючерс +7% за сутки — сделок нет")
# 10. выход через 24 ч: закрытие 🐋ᵛ — строкой к сообщению 🐋
CLOCK[0] = trades("virtual_WD", "AAA")[0]["opened"] + 24 * H + 120
msgs = trader.virt_manage(state)
aaa = [x for x in msgs if "AAA" in x]
check(len(aaa) == 1 and aaa[0].startswith("🐋 ") and "\n🐋ᵛ выход по времени (24 ч): итого" in aaa[0]
      and trades("virtual_WDV", "AAA")[0].get("closed"), "через 24 ч: 🐋ᵛ закрыта строкой к сообщению 🐋")
print("   закрытие:", aaa[0].replace("\n", " | "))
# 11. /virtual
txt = trader.virt_text(state)
check("🐋ᵛ заводы на Binance, крупные к обороту" in txt and "для сравнения 🐋 по сделкам" in txt, "/virtual: блок 🐋ᵛ и итог 🐋")
print("все проверки пройдены")
