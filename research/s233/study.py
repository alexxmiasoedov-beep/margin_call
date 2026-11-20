"""s233 — изучение: повторяет ли часовая ставка займа маржи Binance «момент займа» канала MarginData.
Часовая сетка 01.03.2025 – 18.10.2026, монеты со ставкой в s11/rates и фьючерсом. Метка — монета в канале в отметке
часа (пост не старше 30 мин, s7/margin.pkl, как панель s216/s225). Признаки ставки на момент T (запись не позже T,
ряд записей «при изменении» продлевается вперёд):
  j1, j4, j24 — ln(ставка T / ставка T − 1, 4, 24 ч); z30 — ln(ставка T / медиана 30 сут); fl — ставка ≤ 1,05 × 5-й
  перцентиль за 30 сут («на полу»).
Итог: доля часов в канале, ROC AUC каждого признака, точность и полнота порогов скачка, связь размера займа в посте
со скачком ставки. Запуск из /home/user/mc_data: python3 <repo>/research/s233/study.py"""
import os
import pickle
import time

import numpy as np
import pandas as pd

H, DAY = 3600, 86400
T0 = int(pd.Timestamp("2025-03-01", tz="UTC").timestamp())
T1 = int(pd.Timestamp("2026-10-18", tz="UTC").timestamp())


def auc(score, lab):
    """ROC AUC через ранги (связи — средний ранг)."""
    s = pd.Series(score); ok = s.notna().to_numpy() & np.isfinite(lab)
    s, y = s[ok].rank().to_numpy(), lab[ok].astype(bool)
    n1, n0 = y.sum(), (~y).sum()
    return (s[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan


def main():
    G = pickle.load(open("s7/margin.pkl", "rb"))["G"]
    hours = np.arange(T0, T1, H)
    rows = []
    t_start = time.time()
    for coin, g in G.items():
        p = f"s11/rates/{coin}.csv"
        if not os.path.exists(p):
            continue
        a = np.loadtxt(p, delimiter=",", ndmin=2)
        if len(a) < 100:
            continue
        rt, rv = a[:, 0].astype(np.int64), a[:, 1]
        g = np.asarray(g, float); pt = g[:, 0]; pb = g[:, 1]
        o = np.argsort(pt); pt, pb = pt[o], pb[o]
        # метка: последний пост монеты в (T − 1800, T]
        j = np.searchsorted(pt, hours, "right") - 1
        inch = (j >= 0) & (hours - pt[np.maximum(j, 0)] <= 1800)
        bor = np.where(inch, pb[np.maximum(j, 0)], np.nan)
        # ставка на момент T и раньше (запись не позже момента, продлевается вперёд)

        def at(ts):
            k = np.searchsorted(rt, ts, "right") - 1
            return np.where(k >= 0, rv[np.maximum(k, 0)], np.nan)
        r0, r1, r4, r24 = at(hours), at(hours - H), at(hours - 4 * H), at(hours - DAY)
        live = (hours >= rt[0] + 30 * DAY)
        # медиана и 5-й перцентиль ставки за 30 сут — по часовой сетке
        s = pd.Series(at(np.arange(T0 - 30 * DAY, T1, H)))
        med = s.rolling(30 * 24, min_periods=24 * 7).median().to_numpy()[30 * 24:]
        p05 = s.rolling(30 * 24, min_periods=24 * 7).quantile(0.05).to_numpy()[30 * 24:]
        with np.errstate(divide="ignore", invalid="ignore"):
            d = pd.DataFrame({"c": coin, "T": hours, "inch": inch, "bor": bor,
                              "j1": np.log(r0 / r1), "j4": np.log(r0 / r4), "j24": np.log(r0 / r24),
                              "z30": np.log(r0 / med), "fl": (r0 <= 1.05 * p05).astype(float)})
        d = d[live & np.isfinite(r0) & (r0 > 0)]
        if len(d):
            rows.append(d)
    D = pd.concat(rows, ignore_index=True)
    D.to_pickle("s233_study.pkl")
    lab = D.inch.to_numpy(float)
    print(f"монет {D.c.nunique()}, монето-часов {len(D)}, в канале {lab.mean():.2%}; {time.time() - t_start:.0f} с")
    for f in ("j1", "j4", "j24", "z30"):
        print(f"  AUC {f}: {auc(D[f], lab):.3f}")
    print(f"  «на полу»: в канале {D.inch[D.fl == 1].mean():.2%} против {D.inch[D.fl == 0].mean():.2%} не на полу")
    base = lab.mean()
    for f in ("j1", "j4", "z30"):
        x = D[f].to_numpy(float)
        for q in (0.9, 0.98, 0.995):
            thr = np.nanquantile(x, q); m = x >= thr
            prec = lab[m].mean(); rec = lab[m].sum() / lab.sum()
            print(f"  {f} ≥ {thr:+.3f} (верхние {1 - q:.1%}): в канале {prec:.1%} (база {base:.1%}, ×{prec / base:.1f}), "
                  f"полнота {rec:.1%}")
    C = D[D.inch]
    for f in ("j1", "j4", "z30"):
        print(f"  ранговая корреляция займа в посте и {f} (часы в канале): "
              f"{C['bor'].corr(C[f], method='spearman'):+.3f}")
    # вход в канал: первый час монеты в канале после ≥ 24 ч без канала — как ставка ведёт себя вокруг него
    D = D.sort_values(["c", "T"])
    prev = D.groupby("c").inch.shift(1).fillna(False).astype(bool)
    first = D.inch & ~prev
    print(f"  входов в канал (час в канале, прошлый час — нет): {int(first.sum())}; j1 у них медиана "
          f"{D.j1[first].median():+.4f}, у прочих часов {D.j1[~first].median():+.4f}; доля j1 > 0: "
          f"{(D.j1[first] > 0).mean():.0%} против {(D.j1[~first] > 0).mean():.0%}")


if __name__ == "__main__":
    main()
