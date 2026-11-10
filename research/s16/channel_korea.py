"""Доля Кореи как фильтр для действующих журналов (часовая панель research/s15/kr_panel.py; доля — за последний полный час
до сигнала, Upbit + Bithumb вместе с фьючерсом Binance):
 (а) 🇰🇷 — даёт ли порог 30–40–60% вместо 20% больше на сделку (выход как у 🇰🇷: тейк 10 / стоп 25 / 48 ч);
 (б) основное правило маржинального канала — монета в канале ≥ 4 ч (разрывы ≤ 30 мин), рост за 4 ч +8…+17% → шорт
     (scanner.rule_for, правило pump; 15-мин свечи, кулдаун 24 ч; архив канала 20.02.2025–21.10.2026, s7/margin.pkl):
     как результат зависит от доли Кореи в момент сигнала. Выходы — как у реальной торговли по умолчанию (тейк 10 /
     стоп 18 / 24 ч) и как у 📘 (15 / 25 / 24 ч).
Запуск из папки с данными: python3 s16/channel_korea.py"""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import K, fut_of, live, trade
from kr_raid import P, kr_signals, line

M = pickle.load(open("s7/margin.pkl", "rb")); G = M["G"]
GAP = 1800


def share_at(s, T):
    """Доля Кореи за последний полный час до T; 0 — монеты нет на Upbit/Bithumb; NaN — нет данных за этот час."""
    d = P.get(s)
    if d is None:
        return 0.0
    Tv = d["T"].values; k = int(np.searchsorted(Tv, T, side="right")) - 1
    return float(d["share"].values[k]) if k >= 0 and T - Tv[k] < 3600 else np.nan


def channel_signals():
    out = []
    for coin, g in G.items():
        s, _ = fut_of(coin)
        if s is None:
            continue
        tp = g[:, 0]
        gaps = np.diff(tp) > GAP
        start = tp[np.r_[0, np.flatnonzero(gaps) + 1]][np.r_[0, np.cumsum(gaps)]]   # начало серии для каждого поста
        a = K[s]; t = a["t"]; c = a["c"].astype(float); lo, hi = live(s)
        j = np.arange(16, len(t)); T = t[j] + 900
        k = np.searchsorted(tp, T, side="right") - 1; kk = np.maximum(k, 0)
        present = (k >= 0) & (T - tp[kk] <= GAP)
        run_h = (T - start[kk]) / 3600
        b4h = c[j] / c[j - 16] - 1
        ok = present & (run_h >= 4) & (b4h >= 0.08) & (b4h <= 0.17) & (a["qv"][j] > 0) & (t[j] >= lo + 86400) & (t[j] <= hi)
        last = -1e18
        for jj, TT in zip(j[ok], T[ok]):
            if TT - last >= 24 * 3600:
                out.append(dict(s=s, j=int(jj), T=int(TT))); last = TT
    E = pd.DataFrame(out)
    E["share"] = [share_at(s, T) for s, T in zip(E.s, E["T"])]
    E["korea"] = E.s.isin(P)
    return E


def with_trades(E, **kw):
    return pd.DataFrame([dict(e._asdict(), **x) for e in E.itertuples() if (x := trade(e.s, e.j, **kw))])


if __name__ == "__main__":
    allT = np.concatenate([d["T"].values for d in P.values()]); cut = float(np.median(allT))
    print("(а) 🇰🇷: пампы монет из Кореи по доле Кореи за прошлый час (тейк 10 / стоп 25 / 48 ч)")
    S = kr_signals()
    R = with_trades(S, tp=0.10, sl=0.25, hold_h=48)
    for nm, m in (("доля < 5%", R.share < 0.05), ("5–20%", (R.share >= 0.05) & (R.share < 0.2)), ("20–30%", (R.share >= 0.2) & (R.share < 0.3)),
                  ("30–40%", (R.share >= 0.3) & (R.share < 0.4)), ("40–60%", (R.share >= 0.4) & (R.share < 0.6)), ("≥ 60%", R.share >= 0.6),
                  ("порог 20% (как в боте)", R.share >= 0.2), ("порог 30%", R.share >= 0.3), ("порог 40%", R.share >= 0.4)):
        print(f"  {nm:24s} {line(R[m.values], cut)}")

    E = channel_signals()
    cut2 = float(E["T"].median())
    print(f"\n(б) основное правило канала: сигналов {len(E)} у {E.s.nunique()} монет, "
          f"{pd.to_datetime(E['T'].min(), unit='s'):%d.%m.%Y}–{pd.to_datetime(E['T'].max(), unit='s'):%d.%m.%Y}")
    for nm, kw in (("тейк 10 / стоп 18 / 24 ч", dict(tp=0.10, sl=0.18, hold_h=24)), ("тейк 15 / стоп 25 / 24 ч", dict(tp=0.15, sl=0.25, hold_h=24))):
        r = with_trades(E, **kw)
        print(f"  — {nm}")
        for g, m in (("все", np.ones(len(r), bool)), ("монеты нет на Upbit/Bithumb", ~r.korea), ("в Корее, доля < 5%", r.korea & (r.share < 0.05)),
                     ("доля 5–20%", (r.share >= 0.05) & (r.share < 0.2)), ("доля 20–40%", (r.share >= 0.2) & (r.share < 0.4)),
                     ("доля ≥ 40%", r.share >= 0.4), ("доля ≥ 20%", r.share >= 0.2), ("без корейцев (нет в Корее или < 5%)", ~r.korea | (r.share < 0.05))):
            print(f"    {g:38s} {line(r[np.asarray(m)], cut2)}")
