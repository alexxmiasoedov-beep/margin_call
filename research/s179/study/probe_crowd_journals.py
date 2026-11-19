"""s179 — сколько входов действующих шорт-журналов совпадает с «сигналами толпы» на дневке той же монеты (2024–2026).
Только время и монета; доходы журналов не читаются.

Запуск: python3 -I probe_crowd_journals.py <папка данных>   (нужен s179/crowd_events_2024–2026.pkl из probe_crowd_signals.py)
Счёт: число разных «стран» (US, CN, JP, KR, BN), чей бычий дневной сигнал сработал у монеты
  (а) в день входа d (верхняя оценка: сигнал виден только к закрытию дня, на текущей свече — частично),
  (б) в прошлый закрытый день d − 1 (известно на входе).
"""
import os
import sys

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
BULL = {
    "US": ["US RSI14 вверх через 70", "US золотой крест SMA50/200", "US закрытие выше SMA200", "US пробой 20-дн. максимума",
           "US 52-нед. максимум (первый за 30 сут)"],
    "CN": ["CN MACD 金叉", "CN KDJ J > 100", "CN BOLL выше верхней полосы", "CN 均线多头排列 5>10>20>60"],
    "JP": ["JP 三役好転", "JP пробой облака вверх", "JP 乖離率 25 дн. ≥ +20%", "JP RCI(9) вверх через +80"],
    "KR": ["KR 정배열 5>20>60>120", "KR 골든크로스 MA5/MA20", "KR 골든크로스 MA20/MA60", "KR 이격도 20 дн. ≥ 115"],
    "BN": ["BN дневка MA7 через MA25", "BN дневка цена выше MA99"],
}


def main():
    E = pd.read_pickle(os.path.join(D, "s179/crowd_events_2024–2026.pkl"))
    fam = {sig: f for f, sigs in BULL.items() for sig in sigs}
    E = E[E.signal.isin(fam)].copy()
    E["fam"] = E.signal.map(fam)
    E["day"] = E.t // 86400
    byday = E.groupby(["s", "day"]).fam.nunique()
    J = {}
    J["🔝"] = pd.read_pickle(os.path.join(D, "s65/trades.pkl"))[["s", "t"]]
    J["👀"] = pd.read_pickle(os.path.join(D, "s83/trades.pkl"))[["s", "t"]]
    a = pd.read_pickle(os.path.join(D, "s88/trades.pkl"))
    J["⏰"] = a[(a.open9.astype(bool)) & (a.r1 >= 0.05) & (a.share >= 0.20)][["s", "t"]]
    a = pd.read_pickle(os.path.join(D, "s49/trades.pkl"))
    J["🛒"] = a[a.share >= 0.26][["s", "t"]]
    for k, v in J.items():
        v = v.copy()
        v["s"] = v.s.astype(str).str.replace("USDT$", "", regex=True)
        v["t"] = pd.to_numeric(v.t) if np.issubdtype(v.t.dtype, np.number) else pd.to_datetime(v.t, utc=True).astype("int64") // 10 ** 9
        d = (v.t // 86400).astype(np.int64)
        n0 = np.array([byday.get((s, dd), 0) for s, dd in zip(v.s, d)])
        n1 = np.array([byday.get((s, dd - 1), 0) for s, dd in zip(v.s, d)])
        print(f"{k}: входов {len(v)}; день входа — стран ≥ 1: {np.mean(n0 >= 1):.0%}, ≥ 2: {np.mean(n0 >= 2):.0%}, "
              f"≥ 3: {np.mean(n0 >= 3):.0%}; прошлый день — ≥ 1: {np.mean(n1 >= 1):.0%}, ≥ 2: {np.mean(n1 >= 2):.0%}, "
              f"≥ 3: {np.mean(n1 >= 3):.0%}")


if __name__ == "__main__":
    main()
