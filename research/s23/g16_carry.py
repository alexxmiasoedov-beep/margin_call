"""Кэрри в режиме экстремального отрицательного фандинга. Событие — начисление с прошлой ставкой ≤ порога (известна
к моменту входа). Лонг входит через 15 мин после начисления (после «отсечки»), держит 8 / 24 / 72 ч; доход = цена +
все полученные выплаты (−ставки начислений в окне) − 0,1%. Одна позиция на монету: следующий вход — не раньше выхода.
Стоп −50%? Нет — сначала без стопа. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common23 import CRYPTO, CUT, FU, K, SY, ct

out = []
for s, c in zip(SY, CRYPTO):
    f = FU.get(s)
    if not c or f is None or len(f) < 5:
        continue
    f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
    a = K[s]; t = a["t"].astype(np.int64); cl = a["c"].astype(np.float64); lo_ = a["l"].astype(np.float64); live = a["qv"] > 0
    for thr in (-0.003, -0.01):
        for hold in (8, 24, 72):
            busy = -1
            for n in range(1, len(f)):
                tf, prev = f[n, 0], f[n - 1, 2]
                if prev > thr or tf < busy:
                    continue
                i = int(np.searchsorted(t, tf))                  # свеча, открытая в момент начисления; вход — её закрытие
                j = i + hold * 4
                if i < 1 or j >= len(t) or t[i] != tf or not live[i:j + 1].all():
                    continue
                t0, t1 = tf + 900, t[j] + 900
                fund = -f[(f[:, 0] > t0) & (f[:, 0] <= t1), 2].sum()     # лонг получает −ставка
                px = cl[j] / cl[i] - 1
                worst = lo_[i + 1:j + 1].min() / cl[i] - 1
                out.append(dict(s=s, T=int(tf), thr=thr, hold=hold, prev=prev, px=px, fund=fund, worst=worst,
                                net=px + fund - 0.001, nset=int(((f[:, 0] > t0) & (f[:, 0] <= t1)).sum())))
                busy = t1
R = pd.DataFrame(out)
for (thr, hold), g in R.groupby(["thr", "hold"]):
    m, t, n = ct(g.net, g["T"])
    h1, h2 = g.net[g["T"] < CUT], g.net[g["T"] >= CUT]
    print(f"порог {thr * 100:.1f}%, держим {hold:2d} ч: сделок {n}, монет {g.s.nunique()}: итог {m * 100:+.2f}% (t {t:+.1f}); "
          f"половины {h1.mean() * 100:+.2f} / {h2.mean() * 100:+.2f}%; цена {g.px.mean() * 100:+.2f}%, выплаты "
          f"{g.fund.mean() * 100:+.2f}% (начислений {g.nset.mean():.1f}); в плюсе {(g.net > 0).mean():.0%}; "
          f"худшая просадка в сделке: медиана {g.worst.median() * 100:.1f}%, 5% хуже {g.worst.quantile(0.05) * 100:.1f}%")
    q = pd.to_datetime(g["T"], unit="s").dt.to_period("Q")
    print("    по кварталам: " + " ".join(f"{p}:{x.net.mean() * 100:+.1f}%({len(x)})" for p, x in g.groupby(q)))
R.to_pickle("s23/carry.pkl")
