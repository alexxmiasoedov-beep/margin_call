"""Тест двойника 🐋⁸ (virtual_WD8: те же входы, что у 🐋, шорт 8 ч без тейка, стоп +10%; research/s284) с подменой узлов
Ethereum и Binance (подмена — как в research/s167/wdv_test.py): совместный вход одной строкой к сообщению 🐋 при большом
и малом λ 🐋ᵛ; настройки сделки; мало баланса у 🐋⁸ — отдельное сообщение; неспокойный рынок — без входа; Solana (🐋⁺)
двойник 🐋⁸ не открывает; выход через 8 ч своим сообщением, 🐋 держит; стоп +10% только у 🐋⁸; блок в /virtual; выгрузка.
Запуск из корня репозитория: python3 research/s284/wd8_test.py"""
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



# 1. настройки журнала
cfg = trader.VIRTUALS["virtual_WD8"]
check(cfg["icon"] == "🐋⁸" and cfg["params"](None) == (None, 10.0) and cfg.get("own") and cfg.get("lev") == 1
      and cfg.get("hedge") == "BTC", "🐋⁸: свои входы, без тейка, стоп 10%, плечо ×1, хедж BTC в отчёте")
check(cfg.get("hold_h") == 8.0 and cfg.get("cooldown_h") == 0 and cfg.get("pause_h") == 0.0 and cfg.get("twin") == "virtual_WD",
      "срок 8 ч, одна сделка на монету задаётся правилом (48 ч), без паузы после стопа, близнец 🐋")
keys = list(trader.VIRTUALS)
check(keys.index("virtual_WD8") > keys.index("virtual_WD"), "🐋⁸ идёт после 🐋 — закрытия склеиваются по порядку")

# 2. завод AAA (λ 0,0625): 🐋, 🐋ᵛ, 🐋⁺ и 🐋⁸ — одно сообщение
te = event("AAA", 6e6)
CLOCK[0] = te + 40; m = run()
w8, w = trades("virtual_WD8", "AAA"), trades("virtual_WD", "AAA")
check(len(m) == 1 and m[0].startswith("🐋 сигнал") and "\n🐋⁸ тот же шорт: выход через 8 ч, без тейка, стоп 10%" in m[0]
      and "🐋ᵛ тот же шорт" in m[0] and len(w8) == 1 and len(w) == 1, "AAA: шорт 🐋 и 🐋⁸ (и 🐋ᵛ) — одно сообщение")
t = w8[0]
check(abs(t["sl"] - t["entry"] * 1.10) < 1e-9 and t["tp"] is None and t["lev"] == 1 and t["hold_h"] == 8.0
      and t.get("hedge_sym") == "BTC" and abs(t["opened"] - w[0]["opened"]) < 1 and abs(t["entry"] - w[0]["entry"]) < 1e-12,
      "🐋⁸: стоп +10%, без тейка, плечо ×1, 8 ч, хедж BTC, вход вместе с 🐋 по той же цене")
check("выход через 8 ч" in t["note"] and "выход через 24 ч" not in t["note"] and "выход через 24 ч" in w[0]["note"],
      "в заметке 🐋⁸ — выход через 8 ч, у 🐋 — через 24 ч")
check(any("ЗАВОДЫ" in x and "шорт 🐋⁸" in x for x in LOG), "строка «ЗАВОДЫ» говорит о входе 🐋⁸")
print("   сообщение:", m[0].replace("\n", " | "))
# 3. малый λ (CCC): у 🐋ᵛ «без входа», 🐋⁸ входит той же строкой
te = event("CCC", 6e6)
CLOCK[0] = te + 40; m = run()
check(len(m) == 1 and trades("virtual_WD8", "CCC") and "\n🐋⁸ тот же шорт" in m[0] and "🐋ᵛ без входа" in m[0],
      "CCC: λ 0,031 — 🐋 и 🐋⁸ одной строкой, у 🐋ᵛ «без входа»")
# 4. мало баланса у 🐋⁸ — его отдельное сообщение, 🐋 входит
state["virtual_WD8"]["balance"] = 0.5
te = event("EEE", 6e6)
CLOCK[0] = te + 40; m = run()
check(trades("virtual_WD", "EEE") and not trades("virtual_WD8", "EEE") and m[0].startswith("🐋 сигнал")
      and "🐋⁸ тот же шорт" not in m[0] and any(x.startswith("🐋⁸ EEE: сигнал WD, но на виртуальном балансе") for x in m)
      and any("🐋⁸ не открыта" in x for x in LOG), "мало баланса у 🐋⁸ — сообщение 🐋 и отдельное сообщение 🐋⁸")
state["virtual_WD8"]["balance"] = 20.0
# 5. неспокойный рынок — ни 🐋, ни 🐋⁸
te = event("HHH", 6e6)
CLOCK[0] = te + 40; m = run()
check(not m and not trades("virtual_WD", "HHH") and not trades("virtual_WD8", "HHH"), "HHH: +7% за сутки — сделок нет")
# 6. Solana (🐋⁺) двойник 🐋⁸ не открывает: в _wds_enter нет virtual_WD8
import inspect  # noqa: E402
check("virtual_WD8" not in inspect.getsource(scanner._wds_enter) and "virtual_WD8" in inspect.getsource(scanner._wd_enter),
      "🐋⁸ входит только по заводам в Ethereum (_wd_enter), не по Solana (_wds_enter)")
# 7. через 8 ч: 🐋⁸ закрыта по времени своим сообщением, 🐋 держит
CLOCK[0] = trades("virtual_WD", "AAA")[0]["opened"] + 8 * H + 120
msgs = trader.virt_manage(state)
a8, aw = trades("virtual_WD8", "AAA")[0], trades("virtual_WD", "AAA")[0]
check(a8.get("closed") and a8.get("reason") == "выход по времени (8 ч)" and not aw.get("closed"),
      f"через 8 ч: 🐋⁸ закрыта ({a8.get('reason')}), 🐋 ещё открыта")
check(any(x.startswith("🐋⁸ ") and "AAA" in x for x in msgs) and not any(x.startswith("🐋 ") and "AAA" in x for x in msgs),
      "закрытие 🐋⁸ — своим сообщением")
print("   закрытие:", next(x for x in msgs if x.startswith("🐋⁸ ") and "AAA" in x).replace("\n", " | "))
# 8. стоп +10% только у 🐋⁸ (стоп 🐋 — +25%)
st2 = {}
trader.virt_open(st2, "virtual_WD", "AAA", "WD", "тест", price=1.0)
trader.virt_open(st2, "virtual_WD8", "AAA", "WD", "тест", price=1.0)
scan0 = trader._virt_scan
trader._virt_scan = lambda tr: "стоп" if tr.get("sl_pct") == 10.0 else None
for tr in st2["virtual_WD"]["trades"] + st2["virtual_WD8"]["trades"]:
    tr["v_chk"] = 0
msgs = trader.virt_manage(st2)
t8, tw = st2["virtual_WD8"]["trades"][0], st2["virtual_WD"]["trades"][0]
check(t8.get("reason") == "стоп" and abs(t8["exit"] - t8["entry"] * 1.10) < 1e-9 and not tw.get("closed")
      and len(msgs) == 1 and msgs[0].startswith("🐋⁸"), "стоп +10% у 🐋⁸ — его сообщение, 🐋 держит")
trader._virt_scan = scan0
# 9. /virtual и выгрузка
txt = trader.virt_text(state)
check("🐋⁸ заводы на Binance, выход внутри дня" in txt and "для сравнения 🐋 по сделкам" in txt, "/virtual: блок 🐋⁸ и итог 🐋")
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "export_signals.py")).read()
check('("virtual_WD8", "🐋⁸")' in src, "tools/export_signals.py выгружает 🐋⁸")
print("все проверки пройдены")
