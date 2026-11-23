"""s252 — пилот по выборке окон времени: переводы токенов BNB Chain (перпы без спота Binance) на адреса бирж через SQD Portal.
Портал отдаёт ~1000 блоков на запрос (BNB Chain: 0,45 с на блок с 01.2026 — ~190 запросов на сутки цепи), поэтому весь
период 03.2025–11.2026 одним потоком не собрать; берём два случайных окна по 12 ч в каждом месяце 04.2025–11.2026
(зерно 252, окна записаны в s252/windows.json до сбора) и пересчитываем частоты на месяц. 23.11 в 16:10 UTC портал
замедлился (~3 тыс. блоков в минуту на поток): несобранные окна урезаны до первых 4 ч, начатые — до собранной части
(исходные окна — s252/windows_12h.json); пересчёт на месяц везде идёт по фактическим часам окон.
Фильтр — как collect_cex.py: токены (Alpha в BNB Chain, свой адрес, есть CMC), topic0 = Transfer, topic2 = метки бирж
и адреса сметания (до 3 фильтров по 1000 адресов). Один запрос за раз (study/sqdq.py), продолжение после обрыва.
Итог — s252/rawwin/<окно>.jsonl: [блок, время, токен, от, кому, сумма, tx]; s252/rawwin/done_<окно> — окно собрано.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/collect_win.py [число окон] [часть/частей, напр. 0/2] [extra]
extra — дособор собранных окон только по адресам s252/extra_receivers.json (файлы <окно>_x.jsonl, метки donex_<окно>)."""
import json
import os
import random
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect_cex as C  # noqa: E402
import sqdq  # noqa: E402

H12 = 12 * 3600


def windows():
    f = "s252/windows.json"
    if os.path.exists(f):
        return json.load(open(f))
    rng = random.Random(252)
    out = []
    for m in pd.period_range("2025-04", "2026-11", freq="M"):
        a = pd.Timestamp(m.start_time, tz="UTC").timestamp()
        b = min(pd.Timestamp(m.end_time, tz="UTC").timestamp(), pd.Timestamp("2026-11-15", tz="UTC").timestamp())
        picks = []
        while len(picks) < 2:
            t0 = int(a + rng.random() * (b - a - H12)) // 3600 * 3600
            if all(abs(t0 - p) >= H12 for p in picks):
                picks.append(t0)
        for t0 in sorted(picks):
            out.append({"id": f"{m}_{len(out) % 2}", "t0": t0, "t1": t0 + H12,
                        "b0": sqdq.block_guess(t0), "b1": sqdq.block_guess(t0 + H12)})
    json.dump(out, open(f, "w"), indent=0)
    return out


def main():
    W = windows()
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else len(W)
    part, parts = (int(x) for x in (sys.argv[2].split("/") if len(sys.argv) > 2 else ("0", "1")))
    # порядок: первые окна месяцев от свежих к старым, потом вторые (портал медленный — свежие месяцы важнее); часть part из parts
    order = (sorted(W[::2], key=lambda w: -w["t0"]) + sorted(W[1::2], key=lambda w: -w["t0"]))[:lim][part::parts]
    TB = json.load(open("s252/bsc_tokens.json"))
    TK = json.load(open("s252/tokens.json"))
    dec = {v["contract"]: v["decimals"] for s, v in TB.items() if v.get("cmc") and v.get("decimals") is not None
           and TK[s].get("alpha_chain") == "bsc" and TK[s]["bsc_native"]}
    extra = len(sys.argv) > 3 and sys.argv[3] == "extra"   # дособор уже собранных окон только по новым адресам сметания
    if extra:
        recm = {a.lower(): ex for a, ex in json.load(open("s252/extra_receivers.json")).items()}
    else:
        recm = C.receivers()
        json.dump(recm, open("s252/receivers.json", "w"), indent=0)
    rec = sorted(recm)
    sx = "x" if extra else ""
    flts = [{"address": sorted(dec), "topic0": [C.T], "topic2": [C.pad(x) for x in rec[k:k + 1000]]}
            for k in range(0, len(rec), 1000)]
    fields = {"block": {"number": True, "timestamp": True},
              "log": {"address": True, "topics": True, "data": True, "transactionHash": True}}
    os.makedirs("s252/rawwin", exist_ok=True)
    print(f"окон {len(W)}, собираем {lim}; токенов {len(dec)}, получателей {len(rec)}", flush=True)
    for w in order:
        if extra and (not os.path.exists(f"s252/rawwin/done_{w['id']}") or w["t0"] < 1789430400):
            continue                                       # дособор — собранные окна с 15.09.2026 (Bitget сменил адрес между 08.09 и 17.10.2026)
        done = f"s252/rawwin/done{sx}_{w['id']}"
        if os.path.exists(done):
            continue
        prog = f"s252/rawwin/prog{sx}_{w['id']}.json"
        cur = json.load(open(prog))["next"] if os.path.exists(prog) else w["b0"]
        f = open(f"s252/rawwin/{w['id']}{'_x' if extra else ''}.jsonl", "a")
        n, t1 = 0, time.time()
        while cur <= w["b1"]:
            bl = sqdq.stream({"type": "evm", "fromBlock": cur, "toBlock": w["b1"], "fields": fields, "logs": flts})
            if not bl:
                break
            for blk in bl:
                h = blk["header"]
                for lg in blk.get("logs") or []:
                    tok = lg["address"].lower()
                    amt = int(lg["data"], 16) / 10 ** dec.get(tok, 18) if lg["data"] not in ("0x", "") else 0.0
                    f.write(json.dumps([h["number"], h["timestamp"], tok, "0x" + lg["topics"][1][-40:],
                                        "0x" + lg["topics"][2][-40:], amt, lg.get("transactionHash")]) + "\n")
                    n += 1
            f.flush()
            cur = bl[-1]["header"]["number"] + 1
            json.dump({"next": cur}, open(prog, "w"))
        open(done, "w").write(str(n))
        print(f"{w['id']} {time.strftime('%Y-%m-%d %H:%M', time.gmtime(w['t0']))}: блоков {w['b1'] - w['b0']}, "
              f"переводов {n}, {time.time() - t1:.0f} с, запросов {sqdq.STAT}", flush=True)


if __name__ == "__main__":
    main()
