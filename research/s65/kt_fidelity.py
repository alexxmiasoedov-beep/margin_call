"""Сверка журнала 🔝 в боте с бэктестом krtop_test.py: правило бота scanner.kr_top_rule идёт по часам 10.2024–10.2026.
Обороты за 24 ч — суммы часовых оборотов Кореи из s15/kr_panel.pkl (как в бэктесте), контракты и даты запуска фьючерсов —
по свечам s2/k2y.pkl (первая свеча с оборотом), вход — подмена trader.virt_open с кулдауном 7 суток, как у журнала.
Первые 7 суток бот только копит историю, поэтому сравниваются входы после них. Запуск из папки с данными:
python3 <repo>/research/s65/kt_fidelity.py"""
import os
import pickle
import re
import sys
import tempfile

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
import scanner, trader  # noqa: E402
from common import K, live  # noqa: E402

scanner.log = lambda *a: None


def main():
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    V = pd.DataFrame({s: d.set_index("T").kr for s, d in KP.items() if s in K}).sort_index().fillna(0.0)
    V24 = V.rolling(24, min_periods=24).sum().dropna(how="all")
    coin = {s: re.sub(r"^(1000000|100000|10000|1000)", "", s) for s in V24.columns}
    trader._contracts = {f"{s}USDT": {} for s in K}
    trader.contract = lambda sym: {"symbol": sym, "onboard": live(sym)[0] if sym in K else 0}
    state, entries = {}, []

    def fake_open(st, key, sym, rule, note, price=None, hold_h=None):
        if any(e[0] == sym and T - e[1] < 168 * 3600 for e in entries):
            return None
        entries.append((sym, T))
        return "ok"

    trader.virt_open = fake_open
    for T, row in V24.iterrows():
        T = int(T)
        scanner.candle_due = lambda st, key, name, step=3600, T=T: T
        vol = {coin[s]: float(v) for s, v in row.items() if v > 0}
        scanner._kt_volumes = lambda vol=vol: (vol, "")
        scanner.kr_top_rule(state)
    start = int(V24.index[0]) + 168 * 3600
    B = pd.read_pickle("s65/trades.pkl")
    b = {(r.s, int(r.t)) for r in B.itertuples() if r.t >= start}
    m = {(s, int(t)) for s, t in entries if t >= start}
    print(f"После первых 7 суток: бэктест {len(b)} входов, бот {len(m)}; совпали {len(b & m)}")
    only_b, only_m = sorted(b - m, key=lambda x: x[1]), sorted(m - b, key=lambda x: x[1])
    print(f"Только в бэктесте: {len(only_b)}", only_b[:8])
    print(f"Только у бота: {len(only_m)}", only_m[:8])
    stab = [x for x in only_b if coin.get(x[0]) in scanner.KL_STABLE]
    print(f"  из «только в бэктесте» — стейблкоины: {len(stab)}")


if __name__ == "__main__":
    main()
