"""s177 — кто занимает альт в DeFi: доля «арбитражного» займа (займ монеты под шорт спота против лонга перпа при
сильно отрицательном фандинге) среди событий «сдвиг спроса» и «закрытие». Без доходов и цен после события:
берётся только фандинг Binance за 72 ч ДО дня события.

Классы по среднему фандингу за 72 ч до события (в пересчёте на 8 ч):
  ≤ −0,05%  — займ, скорее всего, нога арбитража фандинга (не направленный шорт);
  −0,05…0   — умеренно отрицательный;
  > 0       — займ при положительном фандинге: шорт через DeFi дороже перпа, скорее направленный или хедж.
Запуск: python3 -I lend_funding.py [папка данных]  (нужен lend_ev.pkl из lend_events.py)
"""
import os
import pickle
import re
import sys
from collections import Counter

import numpy as np

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"


def load_funding():
    out = {}
    for f in ("s117/fund_2020.pkl", "s117/fund_oos.pkl", "s2/fund2y.pkl"):
        d = pickle.load(open(os.path.join(D, f), "rb"))
        for k, a in d.items():
            m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", k)
            b = m.group(2) if m else k
            b = "POL" if b == "MATIC" else b
            a = np.asarray(a, float)
            if a.ndim != 2 or a.shape[1] < 3:
                continue
            out.setdefault(b, []).append(a)
    for b in out:
        a = np.vstack(out[b])
        a = a[np.argsort(a[:, 0])]
        _, i = np.unique(a[:, 0], return_index=True)
        out[b] = a[i]
    return out


def main():
    ev = pickle.load(open(os.path.join(D, "s177", "lend_ev.pkl"), "rb"))
    F = load_funding()
    for nm, lab in (("D", "сдвиг спроса"), ("C", "закрытие"), ("U90", "загрузка ≥ 90%")):
        cls = Counter()
        for sym, day, nat in ev.get(nm, []):
            if nat:
                continue
            a = F.get(sym)
            if a is None:
                cls["нет перпа/фандинга"] += 1
                continue
            t1 = day * 86400
            m = (a[:, 0] >= t1 - 72 * 3600) & (a[:, 0] < t1)
            if not m.any():
                cls["нет перпа/фандинга"] += 1
                continue
            per8 = np.sum(a[m, 2]) / (72 / 8)  # сумма начислений за 72 ч → средняя на 8 ч
            cls["≤ −0,05%" if per8 <= -0.0005 else ("−0,05…0" if per8 <= 0 else "> 0")] += 1
        n = sum(cls.values())
        print(f"{lab}: {n} событий (не родные) — " + ", ".join(f"{k} {v} ({v / max(n, 1):.0%})"
                                                            for k, v in cls.most_common()))


if __name__ == "__main__":
    main()
