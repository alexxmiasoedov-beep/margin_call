"""s242 — тест правки 🐋 после смены адреса сметания Binance (11.2026) с подменой узлов Ethereum:
- новый горячий кошелёк Binance в метках: пополнение на него — событие; его перекладка на старый адрес Binance — не завод;
- нулевой перевод от «отравителя адресов» — не событие и не в счёте сторожа;
- счёт сторожа за сутки UTC (переводы, похожие на пополнения, и просмотренные блоки) в _wd_poll;
- сторож _wd_watch: нормальные сутки — только строка; мало переводов при полном просмотре — строка и сообщение;
  повтор сообщения не чаще раза в 7 сут; мало блоков просмотрено — без сообщения.
Запуск: python3 research/s242/wd_watch_test.py"""
import json
import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner  # noqa: E402

D = 86400
T0 = 1795219200.0 + 3600                       # 01:00 UTC
CLOCK = [T0]
scanner.time.time = lambda: CLOCK[0]
LOG = []
scanner.log = lambda *a: LOG.append(" ".join(str(x) for x in a))

OLD, NEW, CB = "0x" + "b1" * 20, "0x690c3eebf6ee237f00fc96f9766282f096c191cc", "0x" + "cb" * 20
USER, POISON = "0x" + "11" * 20, "0x690c" + "77" * 16 + "91cc"
AAA, BBB = "0x" + "aa" * 20, "0x" + "bb" * 20
LAB = os.path.join(TMP, "cex_labels.tsv")
with open(LAB, "w") as f:
    f.write("# тест\n")
    for a, ex, nm in ((OLD, "Binance", "Binance 28"), (NEW, "Binance", "Binance (горячий с 11.2026)"), (CB, "Coinbase", "Coinbase 10")):
        f.write(f"{a}\t{ex}\t{nm}\n")
scanner.WD_LABELS = LAB

HEAD = [26_400_000]
LOGS = []


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def add(block, tok, frm, to, amount):
    LOGS.append(dict(block=block, tok=tok, frm=frm, to=to, raw=int(amount * 10 ** 18)))


def fake_http(url, data=None, timeout=30, ctype=None):
    q = json.loads(data); m, p = q["method"], q["params"]
    if m == "eth_blockNumber":
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": hex(HEAD[0])})
    if m == "eth_getLogs":
        f = p[0]; lo, hi = int(f["fromBlock"], 16), int(f["toBlock"], 16)
        out = []
        for i, x in enumerate(LOGS):
            if lo <= x["block"] <= hi and x["tok"] in f["address"] and pad(x["to"]) in f["topics"][2]:
                out.append({"address": x["tok"], "blockNumber": hex(x["block"]), "logIndex": hex(i), "removed": False,
                            "blockTimestamp": hex(int(CLOCK[0]) - 60), "transactionHash": "0x" + format(i, "064x"),
                            "topics": [scanner.WD_TRANSFER, pad(x["frm"]), pad(x["to"])], "data": hex(x["raw"])})
        return json.dumps({"jsonrpc": "2.0", "id": 1, "result": out})
    raise AssertionError(m)


scanner.http = fake_http
state = {"wd": {"tok": {AAA: ["AAA", "AAA", 1e9], BBB: ["BBB", "BBB", 1e9]}, "tok_t": T0, "dec": {AAA: 18, BBB: 18},
                "block": HEAD[0] - 10}}


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG)); raise SystemExit(1)


def run():
    LOG.clear()
    return scanner.whale_deposit_rule(state)


w = state["wd"]
lab = scanner._wd_labels()
check(NEW in lab["bin"] and OLD in lab["bin"] and NEW in lab["cex"], "новый горячий кошелёк — среди адресов Binance и бирж")
# 1. проход: пополнение на новый кошелёк, перекладка нового на старый, нулевой перевод отравителя, мелкий перевод
add(HEAD[0] - 5, AAA, NEW, OLD, 2e7)            # 2% обращения — перекладка внутри Binance
add(HEAD[0] - 4, BBB, USER, NEW, 1e7)           # 1% обращения — завод
add(HEAD[0] - 3, AAA, POISON, NEW, 0)           # отравитель — ноль
add(HEAD[0] - 6, AAA, USER, OLD, 1e3)           # мелкий перевод пользователя на старый адрес — в счёт, не событие
m = run()
pend = w.get("pend", {})
check("BBB" in pend and "AAA" not in pend, f"событие — только завод BBB на новый кошелёк; перекладка AAA — не завод ({sorted(pend)})")
check(w["cnt"]["n"] == 2 and w["cnt"]["blk"] == HEAD[0] - 3 - (HEAD[0] - 10 + 1) + 1,
      f"счёт сторожа: 2 перевода (завод и мелкий), без перекладки и нуля; блоков {w['cnt']['blk']}")
check(not m, "в первые сутки сторож молчит")
# 2. смена суток: прошлые сутки — мало переводов, но и блоков мало — без сообщения
CLOCK[0] += D; HEAD[0] += 600
m = run()
check(not m and any("переводов токенов списка на адреса Binance 2, блоков просмотрено" in x for x in LOG)
      and not any("мало" in x for x in LOG), "сутки с малым просмотром блоков — строка без тревоги и сообщения")
# 3. сутки с полным просмотром и малым числом переводов — строка и сообщение
w["cnt"]["blk"] = 7000; w["cnt"]["n"] = 12
CLOCK[0] += D; HEAD[0] += 600
m = run()
check(len(m) == 1 and "сменил адрес" in m[0] and any("мало: похоже, Binance сменил адрес" in x for x in LOG),
      "мало переводов при полном просмотре — строка и сообщение в чат")
# 4. на следующие сутки снова мало — строка без сообщения (повтор не чаще раза в 7 сут)
w["cnt"]["blk"] = 7100; w["cnt"]["n"] = 8
CLOCK[0] += D; HEAD[0] += 600
m = run()
check(not m and any("мало" in x for x in LOG), "повтор тревоги в те же 7 сут — только строка")
# 5. через 7 сут — снова сообщение
for k in range(6):
    w["cnt"]["blk"] = 7100; w["cnt"]["n"] = 8
    CLOCK[0] += D; HEAD[0] += 600
    m = run()
check(len(m) == 1, "через 7 сут — сообщение снова")
# 6. нормальные сутки — только строка
w["cnt"]["blk"] = 7100; w["cnt"]["n"] = 5600
CLOCK[0] += D; HEAD[0] += 600
m = run()
check(not m and any("5600" in x for x in LOG) and not any("мало" in x for x in LOG), "нормальные сутки — строка без тревоги")
# 7. повреждённый счёт в состоянии не ломает правило
w["cnt"] = "мусор"
CLOCK[0] += 180; HEAD[0] += 5
m = run()
check(isinstance(w["cnt"], dict) and w["cnt"]["d"], "повреждённый счёт заменяется новым")
print("все проверки пройдены")
