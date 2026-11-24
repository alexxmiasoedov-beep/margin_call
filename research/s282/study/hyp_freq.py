"""s282 — ожидаемые частоты гипотез Г1, Г2, Г4, Г5 и дозы (только счёт событий по 15-мин свечам; доходы не считаются).
Г3 и Г5 — до доли из минутной выборки (m1_speed.py): Г3 — доля «прострела», Г5 — доля «есть минута на реакцию».

Общее: перп ≥ 7 сут, обе свечи с оборотом, оборот перпа за прошлые 24 ч ≥ TURN_MIN; sig — медианный размах 15-мин свечи
монеты за 7 сут до начала суток; уровень лимитки L = c[i−1]·(1 − X), X = max(X_FLOOR, K·sig) (или фиксированный X);
исполнение — «проход»: минимум свечи ≤ L·(1 − 0,2%). Позиция одна на монету: не чаще раза в час (выход ≤ 1 ч).
Вселенная Г1–Г4 — до 20 перпов на сутки (количественные правила Binance, s282 «Ограничения биржи»): 20 перпов с наибольшим
числом свечей с dl ≤ −K·sig (у Г4 — dh ≥ K·sig) за 7 сут до начала суток.
Вывод — /home/user/mc_data/s282/hyp_freq.txt.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s282/study/hyp_freq.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common282 import BAR, DAY, H, OUT, PER, TMP, cooldown_mask, months  # noqa: E402

K_SIG, X_FLOOR, THROUGH, TOP = 8, 0.03, 0.002, 20
LINES = []


def out(s=""):
    print(s)
    LINES.append(s)


def universe(E, side, k=K_SIG, x=None, top=TOP):
    """Сутки → множество перпов: top по числу свечей-событий (dl ≤ −k·sig или ≤ −x) за 7 сут до начала суток."""
    d = -E.dl.values if side < 0 else E.dh.values
    m = d >= (x if x is not None else k * E.sig.values)
    F = pd.DataFrame(dict(s=E.s.values[m], day=E.t.values[m] // DAY))
    c = F.groupby(["s", "day"], observed=True).size().rename("n").reset_index()
    if not len(c):
        return {}
    days = np.arange(c.day.min(), c.day.max() + 9)
    tab = c.pivot_table(index="day", columns="s", values="n", aggfunc="sum", observed=True).reindex(days).fillna(0)
    roll = tab.rolling(7, min_periods=1).sum().shift(1)        # окно [d − 7, d), без суток d
    U = {}
    for dd, row in roll.iterrows():
        r = row[row > 0].sort_values(ascending=False, kind="stable")
        U[int(dd)] = set(r.index[:top])
    return U


def fills(E, side, turn_min, x=None, k=K_SIG, U=None):
    d = -E.dl.values if side < 0 else E.dh.values
    X = np.full(len(E), x) if x is not None else np.maximum(X_FLOOR, k * E.sig.values)
    need = 1 - (1 - X) * (1 - THROUGH) if side < 0 else (1 + X) * (1 + THROUGH) - 1
    m = (d >= need) & (E.age.values >= 7) & (E.turn.values >= turn_min) & np.isfinite(X)
    F = E.loc[m, ["s", "t", "dl", "dh", "turn", "sig"]].copy()
    F["X"] = X[m]
    if U is not None:
        day = F.t.values // DAY
        keep = np.array([s in U.get(int(dd), ()) for s, dd in zip(F.s.values, day)], bool)
        F = F[keep]
    keep = cooldown_mask(F.s.cat.codes.values, F.t.values, H)
    return F[keep]


def line(F, cfg, lab):
    t0, t1, mid = cfg["t0"], cfg["t1"], cfg["mid"]
    tt = F.t.values
    h1 = ((tt >= t0) & (tt < mid)).sum() / months(t0, mid)
    h2 = ((tt >= mid) & (tt < t1)).sum() / months(mid, t1)
    wk = pd.Series(1, index=tt // (7 * DAY)).groupby(level=0).sum()
    top10 = pd.Series(1, index=tt // DAY).groupby(level=0).sum().sort_values(ascending=False).iloc[:10].sum() / max(len(F), 1)
    out(f"  {lab:<58} {len(F) / months(t0, t1):7.1f} в мес. (половины {h1:.1f} / {h2:.1f}); недель с событиями "
        f"{len(wk)}; монет {F.s.nunique()}; медиана X {100 * np.median(F.X):.1f}%; в 10 сутках {100 * top10:.0f}%")


def main():
    out("s282 — ожидаемые частоты гипотез (только счёт; см. ВЫВОДЫ.md, «Гипотезы»)")
    for per, cfg in PER.items():
        E = pd.read_pickle(f"{TMP}/ev_{per}.pkl")
        B = dict(np.load(f"{TMP}/bars_{per}.npz"))
        out()
        out(f"=== {per}")
        Ud = universe(E, -1)
        Uu = universe(E, +1)
        for tm in (1e6, 5e6):
            out(f" оборот за 24 ч ≥ {tm / 1e6:.0f} млн $:")
            F1 = fills(E, -1, tm, U=Ud)
            line(F1, cfg, "Г1 лимитка вниз, X = max(3%, 8·sig), 20 «прострельных»")
            gi = ((F1.t.values - cfg["t0"]) // BAR).astype(np.int64)
            btc = B["btc_dl"][gi]
            out(f"    Г2: BTC в той же свече ≤ −1% — {100 * np.mean(btc <= -0.01):.0f}% событий Г1, "
                f"≤ −2% — {100 * np.mean(btc <= -0.02):.0f}%")
            line(F1[btc > -0.01], cfg, "Г2а одиночные (BTC в свече > −1%)")
            line(F1[btc <= -0.01], cfg, "Г2б при падении BTC в свече ≤ −1%")
            line(fills(E, +1, tm, U=Uu), cfg, "Г4 лимитка вверх (шорт), X = max(3%, 8·sig), 20 «прострельных»")
            line(fills(E, -1, tm, U=None), cfg, "Г5 все перпы, X = max(3%, 8·sig) (до доли m1_speed)")
            for x in (0.05, 0.08, 0.10, 0.15):
                Ux = universe(E, -1, x=x)
                line(fills(E, -1, tm, x=x, U=Ux), cfg, f"доза: фикс. X = {100 * x:.0f}%, 20 «прострельных» по X")
            for x in (0.05, 0.10):
                line(fills(E, -1, tm, x=x, U=None), cfg, f"   все перпы, фикс. X = {100 * x:.0f}%")
    open(f"{OUT}/hyp_freq.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
