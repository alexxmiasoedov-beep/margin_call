"""Итоговое правило «отлив после фандинга» (s23): начисление с фактической ставкой ≤ порога (ставка известна сразу после
начисления), интервал фандинга 4–8 ч → шорт по закрытию 15-мин свечи T+15 мин, выход по закрытию T+2 ч 15 мин (до
следующего начисления — фандинг не платим); комиссия 0,1%; стоп — по 15-мин high с проскальзыванием 0,2% (как common.trade).
Плацебо — те же монеты, случайные 15-мин моменты в ±3 сутках, вне окон [начисление со ставкой ≤ −0,5%, +2 ч 15 мин].
Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT
from common23 import CRYPTO, FU, K, SY, ct

FEE = 0.001
rng = np.random.default_rng(11)


def short(cl, hi, op, i, j, sl):
    p0 = cl[i]
    if sl:
        k = np.flatnonzero(hi[i + 1:j + 1] >= p0 * (1 + sl))
        if len(k):
            px = max(p0 * (1 + sl), op[i + 1 + k[0]]) * 1.002
            return 1 - px / p0 - FEE, "стоп"
    return 1 - cl[j] / p0 - FEE, "время"


rows, plac = [], []
for s, c in zip(SY, CRYPTO):
    f = FU.get(s)
    if not c or f is None or len(f) < 3:
        continue
    f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
    a = K[s]; t = a["t"].astype(np.int64); cl, hi, op = (a[x].astype(np.float64) for x in ("c", "h", "o")); live = a["qv"] > 0
    ext = f[f[:, 2] <= -0.005, 0]
    for n in range(len(f) - 1):
        tf, ih, rate = f[n]
        if ih < 4 or rate > -0.01:
            continue
        i = int(np.searchsorted(t, tf)); j = i + 8
        if i < 1 or j >= len(t) or t[i] != tf or not live[i:j + 1].all() or f[n + 1, 0] < t[j] + 1800:
            continue
        row = dict(s=s, T=int(tf), ih=ih, rate=rate, vol=float(a["qv"][i - 4:i].sum()))
        for sl in (None, 0.15, 0.25):
            row[f"net{sl or 0}"], row[f"why{sl or 0}"] = short(cl, hi, op, i, j, sl)
        rows.append(row)
        for _ in range(3):                                   # плацебо
            T2 = tf + int(rng.integers(-288, 288)) * 900
            i2 = int(np.searchsorted(t, T2)); j2 = i2 + 8
            if i2 < 1 or j2 >= len(t) or t[i2] != T2 or not live[i2:j2 + 1].all():
                continue
            if ((ext <= t[i2]) & (ext > t[i2] - 2.25 * 3600 - 900)).any() or ((ext > t[i2]) & (ext <= t[j2] + 900)).any():
                continue                                     # окно задевает начисление со ставкой ≤ −0,5% — не плацебо
            plac.append(dict(s=s, T=int(T2), rate=rate, net=short(cl, hi, op, i2, j2, None)[0]))
R = pd.DataFrame(rows); PL = pd.DataFrame(plac)
R.to_pickle("s23/rule_trades.pkl")


def st(x, T):
    m, t, n = ct(x, T)
    return (f"{m * 100:+.2f}% (t {t:+.1f}, n {n}; половины {x[T < CUT].mean() * 100:+.2f} / {x[T >= CUT].mean() * 100:+.2f}; "
            f"в плюсе {(x > 0).mean():.0%}; медиана {x.median() * 100:+.2f}%)")


for thr in (-0.01, -0.015):
    g = R[R.rate <= thr]; p = PL[PL.rate <= thr]
    print(f"\n== ставка ≤ {thr * 100:.1f}%, интервал 4–8 ч: сделок {len(g)}, монет {g.s.nunique()}, дней "
          f"{pd.to_datetime(g['T'], unit='s').dt.date.nunique()} (≈ {len(g) / 730:.1f} в сутки)")
    for sl in (0, 0.15, 0.25):
        x = g[f"net{sl}"]
        print(f"  стоп {'нет' if not sl else f'+{sl:.0%}'}: {st(x, g['T'])}; стопов {(g[f'why{sl}'] == 'стоп').mean():.0%}")
    print(f"  плацебо (те же монеты, случайные моменты ±3 сут вне окон после начислений ≤ −0,5%): {st(p.net, p['T'])}")
    q = pd.to_datetime(g["T"], unit="s").dt.to_period("Q")
    print("  по кварталам (без стопа): " + " ".join(f"{k}:{v.net0.mean() * 100:+.2f}%({len(v)})" for k, v in g.groupby(q)))
    pn = g.groupby("s").net0.sum().sort_values(ascending=False)
    print(f"  доля 5 лучших монет в сумме: {pn.head(5).sum() / pn.sum() * 100:.0f}% ({', '.join(pn.head(5).index)}); "
          f"без 5 лучших монет: {g[~g.s.isin(pn.head(5).index)].net0.mean() * 100:+.2f}%")
    w = g.sort_values("net0").head(3)
    print("  худшие сделки: " + ", ".join(f"{r.s} {pd.Timestamp(r.T, unit='s'):%d.%m.%Y %H:%M} {r.net0 * 100:+.1f}%" for r in w.itertuples()))
    print(f"  сумма по всем сделкам (без стопа, на 1 единицу маржи, плечо ×1): {g.net0.sum() * 100:+.0f}%")
