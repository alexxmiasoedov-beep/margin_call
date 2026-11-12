"""Г9 — сделки вокруг начисления фандинга без заглядывания вперёд. Отбор на входе — только по ставке ПРОШЛОГО начисления
(известна в момент входа). Цены — 15-мин закрытия фьючерса (без поправки на рынок). Сделки:
  A_k — лонг за k·15 мин до начисления (при отрицательной прошлой ставке; при положительной — шорт), выход в момент
        начисления (закрытие свечи, кончающейся в момент начисления): цена + полученный фандинг (фактическая ставка
        этого начисления; если она сменила знак — платим) − 0,1%;
  A_k+ — то же, но выход через 15 мин после начисления (худший случай: выйти сразу не удалось);
  B_m — шорт сразу после начисления (по закрытию свечи момента начисления), выход через m·15 мин, раньше следующего
        начисления: −цена − 0,1%.
Разбивка: корзины прошлой ставки, интервал фандинга, половины, кварталы; сколько монет и дней; доля лучших монет.
Кэш событий — s23/fund_events.pkl. Запуск из папки с данными."""
import os
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common23 import CRYPTO, CUT, FU, K, SY, ct

PATH = "s23/fund_events.pkl"
if os.path.exists(PATH):
    E = pd.read_pickle(PATH)
else:
    rows = []
    for s, c in zip(SY, CRYPTO):
        f = FU.get(s)
        if not c or f is None or len(f) < 3:
            continue
        f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
        a = K[s]; t = a["t"].astype(np.int64); cl = a["c"].astype(np.float64); live = a["qv"] > 0
        for n in range(1, len(f)):
            tf, ih, rate = f[n]; prev = f[n - 1, 2]; prev_t = f[n - 1, 0]
            nxt = f[n + 1, 0] if n + 1 < len(f) else tf + ih * 3600
            if prev > -0.0005 and prev < 0.0005:
                continue
            i = int(np.searchsorted(t, tf))
            if i < 9 or i + 8 >= len(t) or t[i] != tf or not live[i - 9:i + 8].all():
                continue
            p_at = cl[i - 1]                                          # цена в момент начисления
            row = dict(s=s, T=int(tf), ih=ih, rate=rate, prev=prev, gap_prev=(tf - prev_t) / 3600, gap_next=(nxt - tf) / 3600,
                       vol_h=float(a["qv"][i - 4:i].sum()))
            for k in (1, 2, 4, 8):
                row[f"pre{k}"] = p_at / cl[i - 1 - k] - 1                  # от закрытия за k свечей до начисления
            for m in (1, 2, 3, 4, 8):
                row[f"post{m}"] = cl[i - 1 + m] / p_at - 1                 # от момента начисления на m свечей вперёд
            rows.append(row)
    E = pd.DataFrame(rows)
    E.to_pickle(PATH)

E = E[E.prev < 0].copy()                                               # лонг-сторона: прошлая ставка отрицательная
E["bucket"] = pd.cut(E.prev * 100, [-100, -1, -0.3, -0.1, -0.05])
print(f"начислений с прошлой ставкой ≤ −0,05%: {len(E)}, монет {E.s.nunique()}; интервалы: {E.ih.value_counts().to_dict()}")
print("связь прошлой и текущей ставки (корреляция):", round(E.prev.corr(E.rate), 3),
      "| доля, где текущая тоже < 0:", round((E.rate < 0).mean(), 3))
FEE = 0.001


def line(g, col_fn):
    x = col_fn(g)
    m, t, n = ct(x, g["T"])
    h1, h2 = x[g["T"] < CUT], x[g["T"] >= CUT]
    return f"{m * 100:+.3f}% (t {t:+.1f}) [{h1.mean() * 100:+.3f} / {h2.mean() * 100:+.3f}]"


for b, g in E.groupby("bucket", observed=True):
    print(f"\n== прошлая ставка {b}: начислений {len(g)}, монет {g.s.nunique()}, дней {pd.to_datetime(g['T'], unit='s').dt.date.nunique()}"
          f"; средняя ставка начисления {g.rate.mean() * 100:+.3f}%, интервал {g.ih.value_counts().to_dict()}")
    for k in (1, 2, 4, 8):
        ok = g.gap_prev * 4 >= k                                       # вход позже прошлого начисления
        print(f"  A{k} (лонг за {k * 15} мин, выход в начисление): {line(g[ok], lambda d: d[f'pre{k}'] - d.rate - FEE)}"
              f" | выход через 15 мин после: {line(g[ok], lambda d: (1 + d[f'pre{k}']) * (1 + d.post1) - 1 - d.rate - FEE)}")
    for m in (1, 2, 3, 4):
        ok = g.gap_next * 4 > m                                        # выход раньше следующего начисления
        print(f"  B{m} (шорт после начисления на {m * 15} мин): {line(g[ok], lambda d: -d[f'post{m}'] - FEE)}  n={ok.sum()}")
    for ih, gg in g.groupby("ih"):
        if len(gg) >= 50:
            print(f"    интервал {ih:g} ч: n={len(gg)}  A4 {line(gg, lambda d: d.pre4 - d.rate - FEE)}  B2 "
                  f"{line(gg[gg.gap_next * 4 > 2], lambda d: -d.post2 - FEE)}")
    q = pd.to_datetime(g["T"], unit="s").dt.to_period("Q")
    print("    по кварталам A4: " + " ".join(f"{str(p)}:{(gg.pre4 - gg.rate - FEE).mean() * 100:+.2f}%({len(gg)})" for p, gg in g.groupby(q)))
    pnl = (g.pre4 - g.rate - FEE).groupby(g.s).sum().sort_values(ascending=False)
    print(f"    доля 5 лучших монет в сумме A4: {pnl.head(5).sum() / pnl.sum() * 100:.0f}% ({', '.join(pnl.head(5).index)})")
