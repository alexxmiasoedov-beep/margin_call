"""s259, вопрос 1 (продолжение) — кто закрывает разрыв перп/индекс и насколько индекс (а через него марк-цена) повторяет
ход перпа. Индекс восстановлен по свече перпа и премии: idx = c / (1 + p) (проверка check_index.py: медиана ошибки
0,06–0,16%, корреляция доходностей 15 мин 0,98–0,99). Механика, не сделки: регрессии без отбора событий.
- error-correction (15 мин): r_перп(t) = a + α_п·g(t−1), r_индекс(t) = a + α_и·g(t−1), g = ln(1 + p); скорость схождения
  α_и − α_п за свечу, доля индекса α_и / (α_и − α_п);
- одновременный отклик индекса: β = cov(r_и, r_п) / var(r_п); у крупных ходов перпа за свечу (|r_п| ≥ 3%) — медиана
  доли хода, которую индекс прошёл в ту же свечу и за 1 ч (накопленно).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/leadlag.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import BAR, DAY, MID, T1  # noqa: E402
from premium import SNAP0, panel  # noqa: E402

EDGES = [2.3e6, 5.3e6, 12.4e6, 41.5e6]


def prep(P):
    for s, d in P.items():
        t = d["t"]; c = d["c"]; p = d["p"]
        g = np.log1p(p)
        ok = np.r_[False, np.diff(t) == BAR]
        rc = np.r_[np.nan, np.diff(np.log(c))]
        ri = rc - np.r_[np.nan, np.diff(g)]
        d.update(g=g, ok=ok, rc=rc, ri=ri, g1=np.r_[np.nan, g[:-1]], bk=np.searchsorted(EDGES, d["to7"]))
        # накопленные доходности за 4 свечи вперёд (для доли хода, пройденной индексом за 1 ч)
        lc, li = np.log(c), np.log(c) - g
        n = len(t)
        j4 = np.minimum(np.arange(n) + 3, n - 1)
        cont4 = (t[j4] - t == 3 * BAR)
        d["rc4"] = np.where(cont4, lc[j4] - np.r_[np.nan, lc[:-1]], np.nan)      # от закрытия t−1 до закрытия t+3
        d["ri4"] = np.where(cont4, li[j4] - np.r_[np.nan, li[:-1]], np.nan)
    return P


def ols(y, x, w):
    """y = a + b·x; t по неделям (кластеры)."""
    X = np.c_[np.ones_like(x), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    XtX_inv = np.linalg.inv(X.T @ X)
    S = pd.DataFrame(X * e[:, None]).groupby(w).sum().values
    V = XtX_inv @ (S.T @ S) @ XtX_inv
    return b[1], b[1] / np.sqrt(V[1, 1])


def block(P, sel, name, gmin=0.0):
    ys_c, ys_i, xs, ws, rc_all, ri_all, big = [], [], [], [], [], [], []
    for s, d in P.items():
        m = sel(s, d) & d["ok"] & np.isfinite(d["g1"]) & np.isfinite(d["rc"])
        if gmin:
            m &= np.abs(d["g1"]) >= gmin
        if not m.any():
            continue
        ys_c.append(d["rc"][m]); ys_i.append(d["ri"][m]); xs.append(d["g1"][m]); ws.append(d["t"][m] // (7 * DAY))
        m0 = sel(s, d) & d["ok"] & np.isfinite(d["rc"])
        rc_all.append(d["rc"][m0]); ri_all.append(d["ri"][m0])
        mb = m0 & (np.abs(d["rc"]) >= 0.03) & np.isfinite(d["ri4"])
        big += list(zip(d["rc"][mb], d["ri"][mb], d["rc4"][mb], d["ri4"][mb]))
    if not xs:
        print(f"  {name}: нет данных"); return
    yc, yi, x, w = (np.concatenate(v) for v in (ys_c, ys_i, xs, ws))
    a_c, t_c = ols(yc, x, w); a_i, t_i = ols(yi, x, w)
    sp = a_i - a_c
    rc, ri = np.concatenate(rc_all), np.concatenate(ri_all)
    beta = np.cov(ri, rc)[0, 1] / np.var(rc)
    B = np.array(big) if big else np.zeros((0, 4))
    s0 = np.median(B[:, 1] / B[:, 0]) if len(B) else np.nan
    s1 = np.median(B[:, 3] / B[:, 0]) if len(B) else np.nan
    up, dn = B[B[:, 0] > 0], B[B[:, 0] < 0]
    print(f"  {name}{' (|g| ≥ ' + format(gmin, '.1%') + ')' if gmin else ''}: свечей {len(x):,}; схождение за 15 мин "
          f"{sp:.1%} разрыва (перп α {a_c:+.3f}, t {t_c:+.1f}; индекс α {a_i:+.3f}, t {t_i:+.1f}); доля индекса "
          f"{a_i / sp if sp else np.nan:.0%}; β индекса к ходу перпа в ту же свечу {beta:.2f}; ходов перпа ≥ 3% за свечу "
          f"{len(B)} ({len(B) / max(len(rc) / 96, 1) * 100:.2f} на 100 монето-суток): индекс прошёл медиану {s0:.0%} в ту же "
          f"свечу, {s1:.0%} хода перпа — к концу часа (вверх {np.median(up[:, 1] / up[:, 0]) if len(up) else np.nan:.0%}/"
          f"{np.median(up[:, 3] / up[:, 0]) if len(up) else np.nan:.0%}, вниз {np.median(dn[:, 1] / dn[:, 0]) if len(dn) else np.nan:.0%}/"
          f"{np.median(dn[:, 3] / dn[:, 0]) if len(dn) else np.nan:.0%})")


def main():
    P = prep(panel())
    nos = lambda s, d: d["ns"]  # noqa: E731
    spt = lambda s, d: ~d["ns"]  # noqa: E731
    print("### все свечи / только при |g(t−1)| ≥ 0,5% и ≥ 1%")
    for gm in (0.0, 0.005, 0.01):
        block(P, nos, "без спота", gm); block(P, spt, "со спотом", gm)
    print("\n### половины")
    for h, (lo, hi) in (("1-я", (0, MID)), ("2-я", (MID, T1))):
        block(P, lambda s, d, lo=lo, hi=hi: d["ns"] & (d["t"] >= lo) & (d["t"] < hi), f"без спота, {h} половина", 0.005)
        block(P, lambda s, d, lo=lo, hi=hi: ~d["ns"] & (d["t"] >= lo) & (d["t"] < hi), f"со спотом, {h} половина", 0.005)
    print("\n### пятые доли оборота (|g| ≥ 0,5%)")
    for b in range(5):
        block(P, lambda s, d, b=b: d["ns"] & (d["bk"] == b), f"без спота, оборот {b + 1}", 0.005)
        block(P, lambda s, d, b=b: ~d["ns"] & (d["bk"] == b), f"со спотом, оборот {b + 1}", 0.005)
    print("\n### самоссылка (снимок, 07–10.2026)")
    late = lambda d: d["ns"] & (d["t"] >= SNAP0) & d["snap"]  # noqa: E731
    for gm in (0.0, 0.005):
        block(P, lambda s, d: late(d) & (d["self"] > 0), "сам перп в индексе", gm)
        block(P, lambda s, d: late(d) & (d["self"] == 0), "перпа в индексе нет", gm)
        block(P, lambda s, d: late(d) & (d["self"] >= 0.25), "вес перпа ≥ 0,25", gm)
        block(P, lambda s, d: late(d) & (d["alpha"] > 0) & (d["self"] == 0), "Alpha есть, перпа нет", gm)
        block(P, lambda s, d: late(d) & (d["alpha"] == 0) & (d["self"] == 0), "ни Alpha, ни перпа", gm)
        block(P, lambda s, d: late(d) & (d["ext_max"] >= 0.5), "внешняя биржа ≥ 0,5", gm)
    for b in range(5):
        block(P, lambda s, d, b=b: late(d) & (d["self"] > 0) & (d["bk"] == b), f"самоссылка, оборот {b + 1}")
        block(P, lambda s, d, b=b: late(d) & (d["self"] == 0) & (d["bk"] == b), f"без самоссылки, оборот {b + 1}")
    print("\n### до и после листинга спота (±30 сут, без 3 сут вокруг)")
    tr = {s for s, d in P.items() if d["spot0"] and d["t"][0] + 30 * DAY < d["spot0"] < d["t"][-1] - 30 * DAY}
    for gm in (0.0, 0.005):
        block(P, lambda s, d: (s in tr) & (d["t"] >= (d["spot0"] or 0) - 30 * DAY) & (d["t"] < (d["spot0"] or 0) - 3 * DAY), "до спота", gm)
        block(P, lambda s, d: (s in tr) & (d["t"] >= (d["spot0"] or 0) + 3 * DAY) & (d["t"] < (d["spot0"] or 0) + 30 * DAY), "после спота", gm)


if __name__ == "__main__":
    main()
