"""Г9 (добавлена после первых итогов) — цикл начисления фандинга. При сильном фандинге выплата в момент начисления
предсказуема: перед начислением одни закрывают позиции, чтобы не платить, другие открывают, чтобы получить; после — обратно.
Для каждого начисления криптофьючерса (s2/fund2y.pkl: время, интервал, ставка) — путь цены к рынку (медиана 15-мин
доходов всех монет) от −2 ч до +2 ч вокруг начисления по 15-мин свечам, по корзинам ставки. Сделка «за выплатой»:
позиция на стороне получателя фандинга за k свечей до начисления, выход в момент начисления: цена + ставка − 0,1%.
Поиск — первая половина, вторая — для сравнения. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common23 import CRYPTO, CUT, FU, K, SY, ct

BARS = 8                                                   # ±2 ч по 15 мин
sy = [s for s, c in zip(SY, CRYPTO) if c]
t_all = K["BTC"]["t"].astype(np.int64)
# медиана 15-мин дохода всех криптомонет (рынок)
R = np.full((len(sy), len(t_all)), np.nan, np.float32)
for j, s in enumerate(sy):
    a = K[s]
    if len(a["t"]) != len(t_all):
        continue
    c = a["c"].astype(np.float64); live = a["qv"] > 0
    r = np.r_[np.nan, np.log(c[1:] / c[:-1])]; r[~live] = np.nan; r[1:][~live[:-1]] = np.nan
    R[j] = r
MKT = np.nanmedian(R, axis=0)
rows = []
for j, s in enumerate(sy):
    f = FU.get(s)
    if f is None or not len(f):
        continue
    f = np.asarray(f, float)
    for tf, ih, rate in f:
        if abs(rate) < 0.0005:
            continue
        i = int(np.searchsorted(t_all, tf))               # свеча, открытая в момент начисления (первая после)
        if i - BARS < 1 or i + BARS >= len(t_all) or t_all[i] != tf:
            continue
        ex = R[j, i - BARS:i + BARS] - MKT[i - BARS:i + BARS]   # доходы свечей [tf−2ч, tf+2ч)
        if np.isnan(ex).any():
            continue
        rows.append((s, tf, ih, rate, *np.cumsum(ex)))
cols = ["s", "T", "ih", "rate"] + [f"c{k}" for k in range(-BARS + 1, BARS + 1)]
E = pd.DataFrame(rows, columns=cols)
print(f"начислений с |ставкой| ≥ 0,05%: {len(E)}, монет {E.s.nunique()}")
# путь к рынку: накопленный доход от tf−2ч; c0 — к моменту начисления (закрытие свечи tf−15м)
E["pre1h"] = E["c0"] - E["c-4"]; E["pre2h"] = E["c0"]
E["post1h"] = E["c4"] - E["c0"]; E["post2h"] = E["c8"] - E["c0"]
E["bucket"] = pd.cut(E.rate * 100, [-100, -1, -0.3, -0.1, -0.05, 0.05, 0.1, 0.3, 1, 100])
for half, sel in (("первая", E["T"] < CUT), ("вторая", E["T"] >= CUT)):
    print(f"\n== {half} половина: ставка за начисление (%) → доход к рынку, % (до начисления за 2 ч и 1 ч | после за 1 и 2 ч)")
    for b, g in E[sel].groupby("bucket", observed=True):
        if len(g) < 30:
            continue
        pr = []
        for k in ("pre2h", "pre1h", "post1h", "post2h"):
            m, t, n = ct(g[k], g["T"])
            pr.append(f"{m * 100:+.2f} (t {t:+.1f})")
        # сделка на стороне получателя: при ставке < 0 — лонг (получает), > 0 — шорт; вход за 1 ч, выход в момент начисления
        side = -np.sign(g.rate)
        pnl = side * g.pre1h + np.abs(g.rate) - 0.001
        m, t, n = ct(pnl, g["T"])
        print(f"  {str(b):>14} n={len(g):6d}: " + " | ".join(pr) + f" || «за выплатой» 1 ч: {m * 100:+.3f}% (t {t:+.1f})")
