"""Г7 (добавлена после первых итогов) — перетекание денег внутри «секторов». Сектор монеты строится по данным: на срезе T
(00:00 UTC) — корреляции часовых доходов к рынку за 30 суток до T среди ликвидных монет; соседи монеты — 10 самых
коррелированных (корреляция ≥ 0,3). PR — средний доход соседей к рынку за 24 ч; GAP = PR − R (насколько монета отстала от
соседей). Ожидание: отставшая от своего сектора монета догоняет — коэффициент при PR (при равном R) положителен.
Поиск — первая половина; --confirm — вторая. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT, build, days, deciles, fm, fwd_ex, nw_t, report, universe

CONF = "--confirm" in sys.argv
F = build(24)
e, R = F["e"], F["R"]
D = days(F)
D = D[D >= CUT] if CONF else D[D < CUT]
PR, NC = {}, {}
for T in D:
    idx = universe(F, T)
    E = e.loc[T - 720 * 3600 + 3600:T, idx]
    E = E.loc[:, E.notna().mean() > 0.9]
    if E.shape[1] < 50:
        continue
    Cm = E.fillna(0).corr().values.copy()
    np.fill_diagonal(Cm, np.nan)
    cols = E.columns
    r = R.loc[T, cols].values
    pr, nc = np.full(len(cols), np.nan), np.zeros(len(cols))
    order = np.argsort(-np.nan_to_num(Cm, nan=-9), axis=1)[:, :10]
    for i in range(len(cols)):
        nb = order[i][Cm[i, order[i]] >= 0.3]
        nb = nb[np.isfinite(r[nb])]
        nc[i] = len(nb)
        if len(nb) >= 3:
            pr[i] = np.mean(r[nb])
    PR[T] = pd.Series(pr, index=cols); NC[T] = pd.Series(nc, index=cols)
F["PR"] = pd.DataFrame(PR).T.reindex(index=F["C"].index, columns=F["C"].columns)
F["GAP"] = F["PR"] - F["R"]
cover = pd.DataFrame(NC).T
print(f"{'ВТОРАЯ половина' if CONF else 'первая половина'}: срезов {len(PR)}; монет с ≥ 3 соседями в среднем "
      f"{(cover >= 3).sum(axis=1).mean():.0f}")
for h in (24, 72, 168):
    Y = fwd_ex(F["C"], h)
    print(report(fm(F, Y, ["R", "PR"], D), h, "Г7: свой доход R и доход соседей PR"))
    print(report(fm(F, Y, ["R", "PR", "VOL", "A"], D), h, "Г7 с контролем VOL, A"))
    M = deciles(F, Y, "GAP", D)
    sp = M[9] - M[0]
    print(f"  децили GAP ({h // 24} сут): " + " ".join(f"{v * 100:+.2f}" for v in M.mean())
          + f" | D10−D1 {sp.mean() * 100:+.2f}% (t {nw_t(sp, max(1, h // 24)):+.1f})", flush=True)
