"""s160 — разбор варианта «все заводы на Binance» (найден после расчёта, не записанная гипотеза). Для каждого события: ход
монеты за 24 ч и 4 ч до входа, путь шорта (1, 4, 12, 24 ч, без комиссии); база — та же монета во все моменты сетки 6 ч
периода с таким же ходом за 24 ч до момента (корзины), без событий ±48 ч. Запуск в папке периода с MC_K/MC_F/MC_CUT:
python3 <repo>/research/s160/diag.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY, H1 = "/home/user/mc_data", 86400, 3600
BINS = [-1, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10, 0.20, 10]


def run(per):
    from common import K  # noqa: E402
    X = pd.read_pickle(f"{OUT}/s160_{per}.pkl")
    X = X[X["all"] & (X.exch == "Binance")].reset_index(drop=True)
    ev, base = [], []
    for s, g in X.groupby("s"):
        if s not in K:
            continue
        t, c = K[s]["t"].astype(np.int64) + 900, K[s]["c"].astype(float)   # время закрытия свечи

        def px(x):
            i = int(np.searchsorted(t, x, "right")) - 1
            return c[i] if i >= 0 and t[i] > x - 3 * 900 else np.nan

        for r in g.itertuples():
            p0 = px(r.t)
            ev.append(dict(s=s, t=r.t, r24=p0 / px(r.t - DAY) - 1, r4=p0 / px(r.t - 4 * H1) - 1,
                           **{f"f{h}": 1 - px(r.t + h * H1) / p0 for h in (1, 4, 12, 24)}, net=r.net))
        evt = g.t.values
        for x in range(int(t[0] + 2 * DAY) // (6 * H1) * (6 * H1), int(t[-1] - DAY), 6 * H1):
            if np.any(np.abs(evt - x) <= 2 * DAY):
                continue
            p0 = px(x)
            base.append(dict(s=s, t=x, r24=p0 / px(x - DAY) - 1, f24=1 - px(x + DAY) / p0))
    pd.DataFrame(ev).to_pickle(f"{OUT}/s160d_ev_{per}.pkl"); pd.DataFrame(base).to_pickle(f"{OUT}/s160d_base_{per}.pkl")
    print(per, "событий", len(ev), "базовых точек", len(base), flush=True)


def report():
    sys.path.insert(0, os.path.join(HERE, "..", "s43"))
    from oi_test import ct  # noqa: E402
    for per in ("2020–2022", "2022–2024", "2024–2026"):
        E = pd.read_pickle(f"{OUT}/s160d_ev_{per}.pkl").dropna(subset=["r24", "f24"])
        B = pd.read_pickle(f"{OUT}/s160d_base_{per}.pkl").dropna(subset=["r24", "f24"])
        E["b"] = pd.cut(E.r24, BINS); B["b"] = pd.cut(B.r24, BINS)
        mb = B.groupby(["s", "b"], observed=True).f24.mean()           # база той же монеты в той же корзине
        mg = B.groupby("b", observed=True).f24.mean()                  # база всех монет в корзине (если у монеты нет)
        E["base"] = [mb.get((s, b), mg.get(b, np.nan)) for s, b in zip(E.s, E.b)]
        E["ex"] = E.f24 - E.base
        m, t, n = ct(E.f24, E.t); me, te, _ = ct(E.ex.dropna(), E.t[E.ex.notna()])
        print(f"\n{per}: событий {n}; ход за 24 ч до входа: медиана {E.r24.median():+.2%}, доля ≥ +5% {(E.r24 >= 0.05).mean():.0%} "
              f"(база {(B.r24 >= 0.05).mean():.0%}); путь шорта без комиссии: 1 ч {E.f1.mean():+.2%}, 4 ч {E.f4.mean():+.2%}, "
              f"12 ч {E.f12.mean():+.2%}, 24 ч {m:+.2%} (t {t:+.1f}); сверх базы с тем же ходом {me:+.2%} (t {te:+.1f})")
        for b, x in E.groupby("b", observed=True):
            if len(x) >= 20:
                print(f"   ход {str(b):16s} n={len(x):4d} шорт 24 ч {x.f24.mean():+.2%} | база {mg.get(b):+.2%} | сверх базы монеты {x.ex.mean():+.2%}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
