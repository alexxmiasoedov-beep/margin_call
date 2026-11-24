"""s282 — таблицы частот «прострелов» по событиям wicks_build.py (только счёт: доходы, откат после касания,
закрытие свечи против минимума не считаются).

Вывод — /home/user/mc_data/s282/freq.txt, помесячный ряд — /home/user/mc_data/s282/monthly.csv.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s282/study/wicks_report.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common282 import (BAR, DAY, H, K_LEVELS, MONTH, OUT, PER, TMP, TURN_BINS, TURN_LAB, X_LEVELS,  # noqa: E402
                       cooldown_mask, months)

LINES = []


def out(s=""):
    print(s)
    LINES.append(s)


def pct(x):
    return f"{100 * x:.0f}%"


def load(per):
    E = pd.read_pickle(f"{TMP}/ev_{per}.pkl")
    B = dict(np.load(f"{TMP}/bars_{per}.npz"))
    L = json.load(open(f"{TMP}/liq_{per}.json"))
    return E, B, L


def side_frame(E, side, x=None, k=None):
    """События одной стороны: side −1 — минимум вниз, +1 — максимум вверх; порог x (доля) или k (в долях sig)."""
    d = -E.dl.values if side < 0 else E.dh.values
    if x is not None:
        m = d >= x
    else:
        m = np.isfinite(E.sig.values) & (d >= k * E.sig.values)
    F = E.loc[m].copy()
    F["d"] = d[m]
    return F


def main():
    MON = []
    out("s282 — частоты «прострелов» на 15-мин свечах (только счёт событий)")
    out("Событие: минимум свечи ≤ закрытие прошлой × (1 − X) (вниз) или максимум ≥ × (1 + X) (вверх); обе свечи с оборотом;")
    out("перп ≥ 7 сут (если не сказано иное). «Первое за 24 ч» — не чаще раза в сутки на монету и сторону.")
    for per, cfg in PER.items():
        E, B, L = load(per)
        t0, t1, mid = cfg["t0"], cfg["t1"], cfg["mid"]
        mo = months(t0, t1)
        grid = B["grid"]
        out()
        out(f"=== {per}: перпов {L['perps']}, событий в таблице {len(E)}, монето-суток (≥ 7 сут) "
            f"{sum(L['liq']) / 96:.0f}, в среднем живых перпов {np.mean(B['live7']):.0f}")
        E7 = E[E.age >= 7]
        # --- А. по порогам
        out("А. В месяц по порогам: все события / первое у монеты за 1 ч / первое за 24 ч (в скобках — половины, первое за 24 ч)")
        for side, lab in ((-1, "вниз"), (1, "вверх")):
            for x in X_LEVELS:
                F = side_frame(E7, side, x=x)
                c = F.s.cat.codes.values
                tt = F.t.values
                k1 = cooldown_mask(c, tt, H)
                k24 = cooldown_mask(c, tt, DAY)
                h1 = ((tt < mid) & k24).sum() / months(t0, mid)
                h2 = ((tt >= mid) & k24).sum() / months(mid, t1)
                young = side_frame(E[E.age < 7], side, x=x)
                out(f"  {lab} {100 * x:>4.0f}%: {len(F) / mo:8.1f} / {k1.sum() / mo:7.1f} / {k24.sum() / mo:7.1f} "
                    f"({h1:.1f} / {h2:.1f}); монет {F.s.nunique()}; доп. в первые 7 сут перпа — {len(young) / mo:.1f} в мес.")
        # --- Б. по группам оборота
        out("Б. По обороту перпа за прошлые 24 ч: первое за 24 ч в месяц | на 100 монето-суток группы (вероятность за сутки)")
        cd = np.array(L["liq"]) / 96
        out("  группа:            " + " | ".join(f"{g:>14}" for g in TURN_LAB))
        out("  монето-суток:      " + " | ".join(f"{v:>14.0f}" for v in cd))
        for side, lab in ((-1, "вниз"), (1, "вверх")):
            for x in (0.05, 0.10, 0.15):
                F = side_frame(E7, side, x=x)
                k24 = cooldown_mask(F.s.cat.codes.values, F.t.values, DAY)
                F = F[k24]
                g = np.digitize(F.turn.values, TURN_BINS[1:-1])
                n = np.bincount(g, minlength=len(TURN_LAB))
                out(f"  {lab} {100 * x:>3.0f}%:          " + " | ".join(
                    f"{n[q] / mo:6.1f} {100 * n[q] / max(cd[q], 1):5.2f}%" for q in range(len(TURN_LAB))))
        # --- В. в долях собственной волатильности
        out("В. В долях медианного размаха 15-мин свечи монеты за 7 сут (k·sig), первое за 24 ч, в месяц; медиана X этих событий")
        for side, lab in ((-1, "вниз"), (1, "вверх")):
            row = []
            for k in K_LEVELS:
                F = side_frame(E7, side, k=k)
                k24 = cooldown_mask(F.s.cat.codes.values, F.t.values, DAY)
                row.append(f"{k}·sig {k24.sum() / mo:6.1f} (X≈{100 * np.median(F.d[k24]):.1f}%)")
            out(f"  {lab}: " + "; ".join(row))
        out(f"  медиана sig по событиям {100 * np.nanmedian(E7.sig):.2f}%, по монето-суткам ≈ см. sig монет")
        # --- Г. сгруппированность во времени
        out("Г. Сгруппированность: сколько перпов в той же 15-мин свече ушли так же (вся вселенная, перп ≥ 7 сут)")
        out("   классы: одиночный (1) | 2–4 | ≥ 5, но < 10% рынка | ≥ 10% рынка; BTC ≤ −1% (≥ +1%) в той же свече;"
            " доля событий в 10 худших сутках и в 1% свечей с наибольшим числом событий")
        for side, lab, cnt, btc in ((-1, "вниз", B["cnt_dn7"], B["btc_dl"]), (1, "вверх", B["cnt_up7"], B["btc_dh"])):
            for xi, x in enumerate(X_LEVELS):
                F = side_frame(E7, side, x=x)
                gi = ((F.t.values - t0) // BAR).astype(np.int64)
                m = cnt[xi][gi]
                share = m / np.maximum(B["live7"][gi], 1)
                cls = np.select([m <= 1, m <= 4, share < 0.10], [0, 1, 2], 3)
                fr = np.bincount(cls, minlength=4) / len(F)
                bb = (btc[gi] <= -0.01) if side < 0 else (btc[gi] >= 0.01)
                day = F.t.values // DAY
                dc = pd.Series(1, index=day).groupby(level=0).sum().sort_values(ascending=False)
                bc = pd.Series(1, index=gi).groupby(level=0).sum().sort_values(ascending=False)
                top_b = bc.iloc[: max(1, int(round(0.01 * len(bc))))].sum() / len(F)
                out(f"  {lab} {100 * x:>3.0f}%: {pct(fr[0]):>4} | {pct(fr[1]):>4} | {pct(fr[2]):>4} | {pct(fr[3]):>4};"
                    f" BTC {pct(np.mean(bb)):>4}; 10 суток {pct(dc.iloc[:10].sum() / len(F)):>4}; 1% свечей {pct(top_b):>4};"
                    f" свечей с событиями {len(bc)} ({len(bc) / mo:.0f} в мес.)")
        # --- Д. повтор у той же монеты (до события)
        out("Д. Было ли у той же монеты такое же событие раньше: в прошлой свече / за прошлый час / за прошлые 24 ч")
        for side, lab in ((-1, "вниз"), (1, "вверх")):
            for x in (0.05, 0.10):
                F = side_frame(E7, side, x=x)
                c = F.s.cat.codes.values
                tt = F.t.values
                same = np.r_[False, c[1:] == c[:-1]]
                gap = np.r_[np.inf, np.diff(tt).astype(float)]
                gap[~same] = np.inf
                out(f"  {lab} {100 * x:>3.0f}%: {pct(np.mean(gap <= BAR)):>4} / {pct(np.mean(gap <= H)):>4} / "
                    f"{pct(np.mean(gap <= DAY)):>4}")
        # --- Е. как глубоко проходит уровень (распределение минимума у события ≥ X; не «что было после»)
        out("Е. Насколько уровень пройден: среди событий ≥ X доля, где уход < X + 0,2 п. п. / < X + 1 п. п. / ≥ 2X")
        for side, lab in ((-1, "вниз"), (1, "вверх")):
            for x in (0.05, 0.10):
                F = side_frame(E7, side, x=x)
                d = F.d.values
                out(f"  {lab} {100 * x:>3.0f}%: {pct(np.mean(d < x + 0.002)):>4} / {pct(np.mean(d < x + 0.01)):>4} / "
                    f"{pct(np.mean(d >= 2 * x)):>4}; медиана {100 * np.median(d):.1f}%, 90-й перцентиль {100 * np.quantile(d, 0.9):.1f}%")
        # --- Ж. перед событием: ход за час до свечи
        out("Ж. Ход перпа за час до свечи события (r1h): медиана; доля, где за час уже ≤ −3% (≥ +3%)")
        for side, lab in ((-1, "вниз"), (1, "вверх")):
            for x in (0.05, 0.10):
                F = side_frame(E7, side, x=x)
                r = F.r1h.values
                r = r[np.isfinite(r)]
                pre = np.mean(r <= -0.03) if side < 0 else np.mean(r >= 0.03)
                out(f"  {lab} {100 * x:>3.0f}%: медиана {100 * np.median(r):+.2f}%, уже {pct(pre)}")
        # --- З. крайние события (проверка на сбойные свечи)
        F = side_frame(E7, -1, x=0.5)
        out(f"З. Минимум ≤ −50% от прошлого закрытия: {len(F)} событий; крупнейшие:")
        for r in F.sort_values("d", ascending=False).head(12).itertuples():
            out(f"   {r.s:>12} {pd.Timestamp(r.t, unit='s'):%Y-%m-%d %H:%M} {100 * -r.d:+.1f}%  оборот 24 ч {r.turn / 1e6:.1f} млн $")
        # --- помесячный ряд
        for side, lab in ((-1, "dn"), (1, "up")):
            for x in (0.05, 0.10):
                F = side_frame(E7, side, x=x)
                k24 = cooldown_mask(F.s.cat.codes.values, F.t.values, DAY)
                mm = pd.to_datetime(F.t.values, unit="s").to_period("M")
                s_all = pd.Series(1, index=mm).groupby(level=0).sum()
                s_24 = pd.Series(1, index=mm[k24]).groupby(level=0).sum()
                for p_, v in s_all.items():
                    MON.append(dict(per=per, month=str(p_), side=lab, x=x, all=int(v), first24=int(s_24.get(p_, 0))))
        lv = pd.Series(B["live7"], index=pd.to_datetime(grid, unit="s").to_period("M")).groupby(level=0).mean()
        for p_, v in lv.items():
            MON.append(dict(per=per, month=str(p_), side="live", x=0, all=float(v), first24=0))
    M = pd.DataFrame(MON)
    M.to_csv(f"{OUT}/monthly.csv", index=False)
    out()
    out("И. Помесячно, вниз ≥ 5% / ≥ 10%, первое за 24 ч (живых перпов в среднем): мин — медиана — макс по месяцам; 3 месяца с максимумом")
    for per in PER:
        for x in (0.05, 0.10):
            s = M[(M.per == per) & (M.side == "dn") & (M.x == x)].set_index("month").first24
            top = s.sort_values(ascending=False).head(3)
            out(f"  {per} {100 * x:.0f}%: {s.min()} — {s.median():.0f} — {s.max()}; "
                + ", ".join(f"{k} {v}" for k, v in top.items()))
    open(f"{OUT}/freq.txt", "w").write("\n".join(LINES) + "\n")


if __name__ == "__main__":
    main()
