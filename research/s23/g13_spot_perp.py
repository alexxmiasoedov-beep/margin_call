"""Г8 (добавлена после первых итогов) — кто ведёт: реальные деньги на споте или плечи на фьючерсе. Спот — часовые свечи
Binance (s23/spot1h.pkl, 436 монет). Окно 24 ч: PHIs — чистые агрессивные покупки на споте в «нормальных часах» спотового
оборота (медиана за 30 суток до окна), PHI — то же на фьючерсе, SH — доля спота в обороте окна к норме монеты, DIV =
ранг(PHI) − ранг(PHIs) (перп покупает, спот продаёт). Поиск — первая половина; --confirm — вторая. Запуск из папки с данными."""
import pickle
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import BASE_H, CUT, MIN_BASE_H, build, days, deciles, fm, fwd_ex, nw_t, report

CONF = "--confirm" in sys.argv
W = 24
F = build(W)
S = pickle.load(open("s23/spot1h.pkl", "rb"))
idx, cols = F["C"].index, F["C"].columns
Qs = pd.DataFrame(np.nan, index=idx, columns=cols); TBs = Qs.copy()
for s, a in S.items():
    if s not in cols:
        continue
    te = a[:, 0].astype(np.int64) + 3600                       # конец часовой свечи
    m = np.isin(te, idx.values)
    k = np.searchsorted(idx.values, te[m])
    Qs.iloc[k, cols.get_loc(s)] = a[m, 1]; TBs.iloc[k, cols.get_loc(s)] = a[m, 2]
Qs = Qs.where(Qs > 0)
fs = 2 * TBs - Qs
Vbs = Qs.rolling(BASE_H, min_periods=MIN_BASE_H).median().shift(W)
F["PHIs"] = fs.rolling(W, min_periods=W).sum() / Vbs
Qp = pd.DataFrame(np.exp(0), index=idx, columns=cols)
qp = F["PHI"] * 0                                               # заглушка для выравнивания
sh = Qs.rolling(W, min_periods=W).sum() / (Qs.rolling(W, min_periods=W).sum() + F["Vb"] * 0 + 1e-9)
# доля спота: спотовый оборот окна к сумме со фьючерсным (фьючерсный оборот окна = A·W·Vb)
perpW = np.exp(F["A"]) * W * F["Vb"]
SH = Qs.rolling(W, min_periods=W).sum() / (Qs.rolling(W, min_periods=W).sum() + perpW)
SHb = SH.rolling(BASE_H, min_periods=MIN_BASE_H).median().shift(W)
F["SH"] = SH - SHb
F["Bs"] = fs.rolling(W, min_periods=W).sum() / Qs.rolling(W, min_periods=W).sum()
D = days(F)
D = D[D >= CUT] if CONF else D[D < CUT]
n_have = F["PHIs"].loc[D].notna().sum(axis=1).mean()
print(f"{'ВТОРАЯ половина' if CONF else 'первая половина'}: срезов {len(D)}, монет со спотом на срезе в среднем {n_have:.0f}")
for h in (24, 72, 168):
    Y = fwd_ex(F["C"], h)
    print(report(fm(F, Y, ["R", "PHIs", "PHI"], D), h, "спот и перп: R, поток спота PHIs, поток перпа PHI"))
    print(report(fm(F, Y, ["R", "PHIs", "PHI", "SH", "VOL", "A"], D), h, "то же + доля спота SH, VOL, A"))
    print(report(fm(F, Y, ["R", "Bs", "B"], D, extra=lambda X: {"R×Bs": X["R"] * X["Bs"] * 4}), h, "доли чистых покупок: спот Bs, перп B"))
    M = deciles(F, Y, "PHIs", D)
    sp = M[9] - M[0]
    print(f"  децили PHIs ({h // 24} сут): " + " ".join(f"{v * 100:+.2f}" for v in M.mean())
          + f" | D10−D1 {sp.mean() * 100:+.2f}% (t {nw_t(sp, max(1, h // 24)):+.1f})", flush=True)
