"""s271 — частота дней крупной чеканки стейблкоинов (для отказа от гипотезы «чеканка → лонг BTC»): суточный прирост
суммарного предложения стейблкоинов в Ethereum и Tron (DefiLlama, кэш `s177/chains/sc/<сеть>.json.gz`) ≥ 250 / 500 /
1000 млн $. Доходы не считаются. Запуск из /home/user/mc_data."""
import gzip
import json

import numpy as np

WIN = {"2022–2024": (1664582400, 1727740800), "2024–2026": (1727740800, 1792368000)}


def main():
    tot = {}
    for ch in ("Tron", "Ethereum"):
        d = json.load(gzip.open(f"s177/chains/sc/{ch}.json.gz"))
        t = np.array([int(x["date"]) for x in d])
        v = np.array([x["totalCirculatingUSD"].get("peggedUSD", 0) for x in d], float)
        dv, td = np.diff(v), t[1:]
        for per, (a, b) in WIN.items():
            m = (td >= a) & (td < b)
            months = (min(b, td[-1]) - a) / 86400 / 30.44
            for thr in (2.5e8, 5e8, 1e9):
                k = int((dv[m] >= thr).sum())
                tot[(per, thr)] = tot.get((per, thr), 0) + k / months
                print(f"{ch} {per}: суточный прирост ≥ {thr / 1e6:.0f} млн $ — {k} сут, {k / months:.1f} в мес.")
    for (per, thr), x in sorted(tot.items()):
        print(f"вместе {per}, ≥ {thr / 1e6:.0f} млн $: {x:.1f} дня в мес. (дни сетей складываются)")


if __name__ == "__main__":
    main()
