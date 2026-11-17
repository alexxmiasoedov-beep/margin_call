"""s103 — из чего состоит доход журналов: механизм монеты или общий ход рынка альтов. Для каждой сделки бэктеста
(s96.load() + 🇹🇷 из s102) — ход индекса альтов (равный вес, фьючерсы с оборотом ≥ 5 млн $ за прошлые сутки, без BTC)
и BTC за номинальный срок журнала. Регрессия дохода шорта на ход индекса: бета (у чистого шорта рынка −1) и альфа;
доход «с хеджем» = шорт монеты + лонг индекса той же суммы. Сроки — номинальные (тейк и стоп закрывают раньше, поэтому
доля рынка — оценка сверху). Запуск из папки с данными: python3 <repo>/research/s103/beta.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s96"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K  # noqa: E402
from oi_test import CUT, ct  # noqa: E402
from portfolio import HOLD, load  # noqa: E402

HOLD = dict(HOLD, **{"🇹🇷": 24})


def index():
    syms = [s for s in K if s not in ("BTC",) and len(K[s]["t"]) == len(K["BTC"]["t"])]
    t = K["BTC"]["t"]
    C = np.vstack([K[s]["c"].astype(np.float32) for s in syms])
    Q = np.vstack([K[s]["qv"].astype(np.float32) for s in syms])
    R = np.full(C.shape, np.nan, np.float32)
    R[:, 1:] = C[:, 1:] / C[:, :-1] - 1
    cs = np.cumsum(np.nan_to_num(Q, nan=0.0), axis=1, dtype=np.float64)
    v24 = np.zeros_like(cs); v24[:, 96:] = cs[:, 96:] - cs[:, :-96]
    ok = np.zeros(C.shape, bool); ok[:, 1:] = (v24[:, :-1] >= 5e6) & (Q[:, 1:] > 0)   # отбор по прошлым суткам
    R = np.where(ok, np.clip(R, -0.5, 0.5), np.nan)
    m = np.nanmean(R, axis=0); m = np.nan_to_num(m, nan=0.0)
    I = np.cumprod(1 + m.astype(np.float64))
    b = K["BTC"]["c"].astype(np.float64)
    return t, I, b, ok.sum(axis=0)


def main():
    t, I, B, n = index()
    print(f"индекс альтов: в среднем {n[n > 0].mean():.0f} монет в баре")
    X = load()
    T = pd.read_pickle("s102/trades.pkl"); T = T[T.j == "🇹🇷"]
    X = pd.concat([X, pd.DataFrame({"j": "🇹🇷", "s": T.s, "t": T.t, "r": T.net})], ignore_index=True)
    te = X.t.values.astype(np.int64)
    i0 = np.searchsorted(t + 900, te)                         # свеча, закрывающаяся в момент входа
    i1 = np.minimum(i0 + (X.j.map(HOLD).fillna(48).values * 4).astype(int), len(t) - 1)
    ok = (i0 < len(t)) & (t[np.minimum(i0, len(t) - 1)] + 900 == te)
    X = X[ok].copy(); i0, i1 = i0[ok], i1[ok]
    X["m"] = I[i1] / I[i0] - 1; X["mb"] = B[i1] / B[i0] - 1
    X["h"] = X.r + X.m                                         # шорт монеты + лонг индекса альтов
    print(f"\n{'журнал':6s} {'сделок':>6s} {'доход':>8s} {'t':>5s} | {'рынок за срок':>13s} | {'бета':>5s} {'R²':>4s} |"
          f" {'с хеджем':>8s} {'t':>5s} {'1-я / 2-я половина':>20s}")
    rows = []
    for j, x in X.groupby("j"):
        if len(x) < 30:
            continue
        b, a = np.polyfit(x.m, x.r, 1); r2 = np.corrcoef(x.m, x.r)[0, 1] ** 2
        m, tt, nn = ct(x.r, x.t); mh, th, _ = ct(x.h, x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        rows.append((j, nn, m, tt, x.m.mean(), b, r2, mh, th, ct(h1.h, h1.t)[0], ct(h2.h, h2.t)[0]))
    for j, nn, m, tt, mm, b, r2, mh, th, a1, a2 in sorted(rows, key=lambda z: -z[3]):
        print(f"{j:6s} {nn:6d} {m:+8.2%} {tt:+5.1f} | {-mm:+13.2%} | {b:+5.2f} {r2:4.2f} | {mh:+8.2%} {th:+5.1f}"
              f" {a1:+9.2%} / {a2:+7.2%}")
    print("\n«рынок за срок» — доход шорта индекса альтов за те же окна (что дал бы шорт рынка вместо монеты).")
    X.to_pickle("s103/beta_trades.pkl")


if __name__ == "__main__":
    main()
