"""s275 — пересечение событий Г1–Г3 (freq.py, 2024–2026) с входами действующих журналов: 🔑⁺ (s142: активная сделка
T − 7 → T + 1 сут), 🐋 (s213: вход за прошлые 24 ч), пампы 🛒/🇰🇷 (s49/trades.pkl: памп за прошлые 24 ч с долей спота
≥ 26% или долей Кореи ≥ 20%). Используются только моменты событий (столбцы доходов не читаются).
Запуск: из /home/user/mc_data после freq.py — python3 -I <repo>/research/s275/study/overlap.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common275 import DAY, OUT, TMP, base  # noqa: E402

LINES = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    LINES.append(s)


def main():
    ev = pickle.load(open(f"{TMP}/freq_events_2024–2026.pkl", "rb"))
    U = pd.read_pickle("s142_2024–2026.pkl")[["s", "T", "t"]]
    W = pd.read_pickle("s213_main_2024–2026.pkl")[["perp", "t"]]
    Pm = pd.read_pickle("s49/trades.pkl")[["s", "t", "share", "kr"]]
    Pm = Pm[(Pm.share >= 0.26) | (Pm.kr >= 0.20)]
    ul = {}
    for r in U.itertuples():
        ul.setdefault(base(r.s), []).append((int(r.t), int(r.T) + DAY))
    wd = {}
    for r in W.itertuples():
        wd.setdefault(base(r.perp), []).append(int(r.t))
    pm = {}
    for r in Pm.itertuples():
        pm.setdefault(base(r.s), []).append(int(r.t))
    say("s275 — пересечение событий с журналами, 2024–2026 (доля событий гипотезы)")
    for key, nm in (("g1", "Г1 провал ≤ −2σ"), ("g2", "Г2 рост 31–100 ≥ +3σ"), ("g3_oi3", "Г3 перелёт с OI ≤ −3%")):
        rows = ev.get(key, [])
        n = len(rows)
        if not n:
            continue
        a = b = c = 0
        for t, p, _ in rows:
            k = base(p)
            if any(t0 <= t <= t1 for t0, t1 in ul.get(k, ())):
                a += 1
            if any(t - DAY <= x <= t for x in wd.get(k, ())):
                b += 1
            if any(t - DAY <= x <= t for x in pm.get(k, ())):
                c += 1
        say(f"  {nm}: событий {n}; в окне 🔑⁺ {a / n:.1%}, после 🐋 за 24 ч {b / n:.1%}, после пампа 🛒/🇰🇷 за 24 ч {c / n:.1%}")
    open(f"{OUT}/overlap.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
