"""«Прилив» перед начислением фандинга с прогнозной ставкой. Binance: ставка = средняя премия за интервал с линейно
растущими весами (свежие значения весят больше) + clamp(процент − премия, ±0,05%), процент 0,01% за 8 ч. Прогноз на момент
T − X — то же по 15-мин закрытиям премии (s12/prem.pkl) от начала интервала до T − X (известно боту в реальном времени из
premiumIndex). Проверка: связь прогноза с фактической ставкой; сделки «лонг с T − X до T − 15 мин» (до начисления —
фандинг не участвует) по корзинам прогноза; половины. Запуск из папки с данными."""
import pickle
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s23")
from common23 import CRYPTO, CUT, FU, K, SY, ct                 # noqa: E402

PR = pickle.load(open("s12/prem.pkl", "rb"))
FEE = 0.001
rows = []
for s, c in zip(SY, CRYPTO):
    f = FU.get(s); p = PR.get(s)
    if not c or f is None or len(f) < 3 or p is None:
        continue
    f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
    f = f[f[:, 1] >= 4]
    if not len(f):
        continue
    pt = p[0].astype(np.int64) + 900; pv = p[1].astype(np.float64)        # премия на закрытии 15-мин свечи
    o = np.argsort(pt); pt, pv = pt[o], pv[o]
    cs_v = np.r_[0, np.cumsum(pv)]; cs_tv = np.r_[0, np.cumsum(pt * pv)]; cs_t = np.r_[0, np.cumsum(pt.astype(np.float64))]
    a = K[s]; t = a["t"].astype(np.int64); cl = a["c"].astype(np.float64); live = a["qv"] > 0
    T = f[:, 0].astype(np.int64); ih = f[:, 1]; rate = f[:, 2]; T0 = T - (ih * 3600).astype(np.int64)
    lo = np.searchsorted(pt, T0, "right")                                    # pt > T0
    D = dict(s=s, T=T, ih=ih, rate=rate)
    full = np.searchsorted(pt, T, "right") - lo
    D["cover"] = full / (ih * 4)
    I = 0.0001 * ih / 8
    for X in (60, 45, 30):
        hi = np.searchsorted(pt, T - X * 60, "right")                        # pt <= T − X
        cnt = hi - lo
        sv = cs_v[hi] - cs_v[lo]; stv = cs_tv[hi] - cs_tv[lo]; st_ = cs_t[hi] - cs_t[lo]
        sw = st_ - T0 * cnt                                                   # Σ (t − T0)
        swv = stv - T0 * sv                                                   # Σ (t − T0)·v
        P = np.where((cnt >= 4) & (sw > 0), swv / np.where(sw > 0, sw, 1), np.nan)
        D[f"pred{X}"] = P + np.clip(I - P, -0.0005, 0.0005)
        i0 = np.searchsorted(t, T - X * 60 - 900); i1 = np.searchsorted(t, T - 900 - 900)
        ok = (i0 > 0) & (i1 < len(t)) & (i0 < i1)
        L = np.full(len(T), np.nan)
        for q in np.flatnonzero(ok):
            if t[i0[q]] + 900 == T[q] - X * 60 and t[i1[q]] + 900 == T[q] - 900 and live[i0[q]:i1[q] + 1].all():
                L[q] = cl[i1[q]] / cl[i0[q]] - 1 - FEE
        D[f"L{X}"] = L
    df = pd.DataFrame(D)
    rows.append(df[df.cover >= 0.9])
R = pd.concat(rows, ignore_index=True)
R.to_pickle("s24/tide.pkl")
for X in (60, 30):
    ok = R[f"pred{X}"].notna()
    print(f"прогноз за {X} мин: корреляция с фактической ставкой {R.loc[ok, f'pred{X}'].corr(R.loc[ok, 'rate']):.3f}; "
          f"среди факт ≤ −1% прогноз ≤ −1% у {((R[f'pred{X}'] <= -0.01) & (R.rate <= -0.01)).sum() / max(1, (R.rate <= -0.01).sum()):.0%}")
for X in (60, 45, 30):
    print(f"\nлонг с T − {X} мин до T − 15 мин, по корзинам прогнозной ставки (интервал 4–8 ч):")
    b = pd.cut(R[f"pred{X}"] * 100, [-100, -1.5, -1, -0.5, -0.3, -0.1, 0.1, 100])
    for k, g in R.groupby(b, observed=True):
        x = g[f"L{X}"].dropna()
        if len(x) < 30:
            continue
        m, t, n = ct(x, g.loc[x.index, "T"])
        T = g.loc[x.index, "T"]
        print(f"  прогноз {str(k):>14}: n={n:6d}, лонг {m * 100:+.3f}% (t {t:+.1f}; половины {x[T < CUT].mean() * 100:+.3f} / "
              f"{x[T >= CUT].mean() * 100:+.3f}); без комиссии {(x + FEE).mean() * 100:+.3f}%; в плюсе {(x > 0).mean():.0%}")
