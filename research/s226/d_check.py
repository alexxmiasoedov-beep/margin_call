"""s226 — проверка семейства «новый займ после рывка цены» на свежем отрезке D (записано в ВЫВОДЫ.md до расчёта).
Правило зафиксировано на A и B: займ ≥ 1 млн $, займ / оборот ≥ 2%, монеты не было в канале неделю (≤ 1 ч за 7 сут),
цена за 4 ч ≥ +5% → шорт 24 ч и 48 ч (стоп 25%). События D — events.py по новой панели (s224/ev_D.pkl), входы с 22.10.2026.
Запуск из /home/user/mc_data: python3 <repo>/research/s226/d_check.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import grid as G  # noqa: E402

D0 = pd.Timestamp("2026-10-22", tz="UTC").timestamp()
RULE = ["займ ≥ 1 млн $", "займ / оборот ≥ 2%", "за 7 сут в канале 0 ч до события", "цена 4 ч ≥ +5%"]


def trades(X, col):
    M, names, _ = G.masks(X); ix = {n: i for i, n in enumerate(names)}
    sel = np.logical_and.reduce([M[ix[r]] for r in RULE]) & X[col].notna().to_numpy()
    return G.honest(sel, X, X["u_x_" + col].to_numpy(float))


def main():
    old = pd.read_pickle("s226_ev.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    new = pd.read_pickle("s224/ev_D.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    new = new[new["T"] >= D0].reset_index(drop=True)
    months_d = (new["T"].max() + 3600 - D0) / (30.44 * 86400)
    print(f"событий D: {len(new)} (новый займ {int((new.ev == 1).sum())}, займ вырос {int((new.ev == 2).sum())}); "
          f"средний шорт всех событий D: 24 ч {new.s24.mean():+.2%}, 48 ч {new.s48.mean():+.2%}")
    for col, hed in (("s24", "y_hs24"), ("s48", "y_hs48")):
        tk = trades(new, col); y = new[col].to_numpy(float)[tk]; T = new["T"].to_numpy()[tk]
        m, t, n = G.ct(y, T); mh, th, _ = G.ct(new[hed].to_numpy(float)[tk], T)
        to = trades(old, col); yo = old[col].to_numpy(float)[to]; To = old["T"].to_numpy()[to]
        ma, ta, na = G.ct(np.r_[yo, y], np.r_[To, T])
        print(f"  шорт {col}: D — {n} сделок ({n / months_d:.1f} в мес.), {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%}; "
              f"монеты: {', '.join(new.s.values[tk])}")
        print(f"    A + B + C + D: {na} сделок, {ma:+.2%} (t {ta:+.1f}); порог D (> 0): {'да' if n and m > 0 else 'нет'}")


if __name__ == "__main__":
    main()
