"""Г10 (добавлена после первых итогов) — переключение интервала фандинга. Когда фандинг упирается в предел, Binance
сокращает интервал начисления (8 ч / 4 ч → 1 ч): платящая сторона теряет деньги каждый час и вынуждена выходить. Событие —
первое начисление с интервалом 1 ч после начислений с интервалом > 1 ч (s2/fund2y.pkl). По знаку ставки: шорты платят
(ставка < 0) или лонги платят (> 0). Доход к рынку (лонг) через 1, 3, 7 суток от часа события и сделка «на стороне
получателя фандинга» (цена + фандинг − комиссия) на 1 и 3 суток. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common23 import CRYPTO, CUT, FU, H, SY, ct, fwd, funding

rows = []
for s, c in zip(SY, CRYPTO):
    f = FU.get(s)
    if not c or f is None or len(f) < 10:
        continue
    f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
    for n in range(3, len(f)):
        if f[n, 1] == 1 and f[n - 1, 1] > 1 and f[n - 2, 1] > 1:
            T = int(f[n, 0] // 3600 * 3600)
            rows.append(dict(s=s, T=T, rate=f[n, 2], prev_ih=f[n - 1, 1], prev_rate=f[n - 1, 2]))
E = pd.DataFrame(rows)
print(f"переключений на 1 ч: {len(E)}, монет {E.s.nunique()}; ставка < 0: {(E.rate < 0).sum()}, > 0: {(E.rate > 0).sum()}")


def fwd_raw(s, T, h):
    x = fwd(s, T, h, net=False)                     # шорт к рынку → лонг к рынку = −x
    return -x if np.isfinite(x) else np.nan


def carry(s, T, h, side):
    """Сделка на стороне получателя: side +1 лонг (ставка < 0), −1 шорт; цена + фандинг − 0,1%."""
    x = fwd(s, T, h, net=True)                      # шорт: цена + фандинг − комиссия
    if not np.isfinite(x):
        return np.nan
    if side < 0:
        return x
    fr = funding(s); px_short = x + 0.001          # снять комиссию, восстановить шорт без неё
    # лонг: цена с обратным знаком и фандинг с обратным знаком
    return -(px_short) - 0.001


for nm, g in (("ставка < 0 (шорты платят)", E[E.rate < 0]), ("ставка > 0 (лонги платят)", E[E.rate > 0])):
    print(f"\n== {nm}: событий {len(g)}, средняя ставка {g.rate.mean() * 100:+.3f}%")
    for h in (24, 72, 168):
        y = np.array([fwd_raw(s, T, h) for s, T in zip(g.s, g["T"])])
        m, t, n = ct(y, g["T"].values)
        h1, h2 = y[g["T"].values < CUT], y[g["T"].values >= CUT]
        print(f"  {h // 24} сут: доход к рынку (лонг) {m * 100:+.2f}% (t {t:+.1f}, n {n}); половины "
              f"{np.nanmean(h1) * 100:+.2f} / {np.nanmean(h2) * 100:+.2f}%; в плюсе {(y[np.isfinite(y)] > 0).mean():.0%}")
    side = 1 if g.rate.mean() < 0 else -1
    for h in (24, 72):
        y = np.array([carry(s, T, h, side) for s, T in zip(g.s, g["T"])])
        m, t, n = ct(y, g["T"].values)
        print(f"  сделка получателя фандинга ({'лонг' if side > 0 else 'шорт'}) {h // 24} сут: {m * 100:+.2f}% (t {t:+.1f}, n {n})")
