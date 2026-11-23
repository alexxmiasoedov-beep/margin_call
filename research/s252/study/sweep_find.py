"""s252 — адреса сметания бирж в BNB Chain в прошлом (SQD Portal). Адреса пополнения одной биржи в EVM-сетях общие:
берём адреса пополнения из Ethereum (s195_deposits.pkl: отправители переводов на горячие кошельки биржи) за 90 сут
до даты и смотрим, куда они переводили токены в BNB Chain в окне 6 ч (фильтр topic1 = адреса пополнения). Получатель,
на который сходятся переводы многих адресов пополнения, — адрес сметания биржи. Один запрос к порталу за раз
(study/sqdq.py), окна сохраняются в s252/sweep_raw/<дата>_<кусок>.json — после обрыва продолжает.
Итог — /home/user/mc_data/s252/sweep_find.json: {дата: {биржа: [[получатель, переводов, отправителей, токенов], …]}}.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/sweep_find.py [даты через запятую] [часов окна]"""
import collections
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sqdq  # noqa: E402

T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
EXCH = ["MEXC", "Bitget", "Gate.io", "Bybit", "OKX", "KuCoin", "HTX", "BingX", "CoinEx", "LBank", "BitMart", "XT.com",
        "blockscout-exchange", "Binance", "Coinbase", "Kraken", "Upbit", "Bithumb", "Crypto.com"]
OUT = "s252/sweep_find.json"
RAW = "s252/sweep_raw"


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def main():
    days = (sys.argv[1].split(",") if len(sys.argv) > 1 else ["2025-03-15", "2025-09-15", "2026-03-15", "2026-08-15"])
    hours = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0      # длина окна (ч) с 06:00 UTC
    D = pd.read_pickle("s195_deposits.pkl")
    os.makedirs(RAW, exist_ok=True)
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for day in days:
        t0 = pd.Timestamp(day, tz="UTC").timestamp()
        own = {}
        for ex in EXCH:
            d = D[(D.exch == ex) & (D.t < t0)]
            win = d[d.t >= t0 - 90 * 86400]
            if win.frm.nunique() < 30:                       # мало свежих — последние адреса любой давности
                win = d.sort_values("t").tail(3000)
            for a in win.drop_duplicates("frm", keep="last").frm.tolist()[-300:]:
                own.setdefault(a, ex)
        senders = sorted(own)
        b0 = sqdq.block_guess(t0 + 6 * 3600)                 # с 06:00 UTC, hours часов
        b1 = sqdq.block_guess(t0 + (6 + hours) * 3600)
        L = []
        for k in range(0, len(senders), 800):
            f = f"{RAW}/{day}_{k}.json" if hours == 6.0 else f"{RAW}/{day}_{hours:g}h_{k}.json"
            if os.path.exists(f):
                L += json.load(open(f))
                continue
            t1 = time.time()
            part = sqdq.logs(b0, b1, {"topic0": [T], "topic1": [pad(a) for a in senders[k:k + 800]]},
                             fields={"block": {"number": True}, "log": {"address": True, "topics": True}})
            rows = [[b, lg["address"].lower(), "0x" + lg["topics"][1][-40:], "0x" + lg["topics"][2][-40:]]
                    for b, _, lg in part if len(lg["topics"]) >= 3]
            json.dump(rows, open(f, "w"))
            L += rows
            print(day, f"кусок {k}: логов {len(rows)}, {time.time() - t1:.0f} с, запросов {sqdq.STAT}", flush=True)
        cnt = collections.defaultdict(collections.Counter)
        snd = collections.defaultdict(lambda: collections.defaultdict(set))
        tok = collections.defaultdict(lambda: collections.defaultdict(set))
        for b, tk, fr, to in L:
            ex = own.get(fr)
            if ex is None:
                continue
            cnt[ex][to] += 1
            snd[ex][to].add(fr)
            tok[ex][to].add(tk)
        res[day] = {"blocks": [b0, b1], "n_dep": collections.Counter(own.values())}
        for ex in EXCH:
            top = [[a, n, len(snd[ex][a]), len(tok[ex][a])] for a, n in cnt[ex].most_common(8)]
            res[day][ex] = top
            print(day, ex, "переводов", sum(cnt[ex].values()), top[:3], flush=True)
        json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
