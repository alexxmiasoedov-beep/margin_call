"""Шорт нового фьючерса токена Binance Alpha, запущенного в те же сутки, что и листинг в Alpha (выход токена, TGE), —
разбор: к рынку, плацебо той же монеты через 30–60 суток, кварталы, стопы и сроки, пересечение с 🇰🇷🆕 (листинг к воне
в первые 7 суток) и с «слабым стартом» из research/s3. Нужен s18/launches.pkl (alpha.py).
Запуск из папки с данными: python3 s18/alpha_tge.py"""
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import BAR, K, fut_of, live, trade
from alpha import market

L = pd.read_pickle("s18/launches.pkl")
KR = pickle.load(open("s15/kr_listings.pkl", "rb"))
rng = np.random.default_rng(18)


def kr_within(s, t0, days=7):
    base = s.replace("1000000", "").replace("1000", "") if s.startswith("1000") else s
    return any(x["base"] == base and t0 <= x["t"] <= t0 + days * 86400 for x in KR)


def short_px(s, i, h=168):
    t = K[s]["t"]; c = K[s]["c"]; k = i + 4 * h; lo, hi = live(s)
    if k >= len(t) or t[k] != t[i] + 4 * h * BAR or t[k] > hi or K[s]["qv"][i] <= 0:
        return np.nan
    return 1 - float(c[k]) / float(c[i])


def summary(R, label):
    if not len(R):
        return f"  {label}: нет сделок"
    h = R.t < R.t.median()
    trim = R.net.sort_values().iloc[:-5].mean() if len(R) > 15 else np.nan
    return (f"  {label:44s} n={len(R):3d} | {R.net.mean() * 100:+5.1f}% (медиана {R.net.median() * 100:+5.1f}%, без 5 лучших {trim * 100:+5.1f}%) | "
            f"в плюсе {(R.net > 0).mean():.0%} | стопов {(R.why == 'стоп').mean():.0%} | половины {R.net[h].mean() * 100:+.1f}/{R.net[~h].mean() * 100:+.1f}%")


if __name__ == "__main__":
    G = L[L.alpha & L.crypto & (L.lag_d.abs() <= 1)].copy()
    print(f"токены Alpha с фьючерсом в те же сутки: {len(G)}")
    rows = []
    for r in G.itertuples():
        i = r.i0 + 96
        x = short_px(r.s, i)
        t = K[r.s]["t"]
        mk = x - market(float(t[i]), float(t[i]) + 168 * 3600) if np.isfinite(x) else np.nan
        pl = [short_px(r.s, i + int(d * 96)) for d in rng.uniform(30, 60, 3)]
        c24 = K[r.s]["c"][r.i0:r.i0 + 97].astype(float); h24 = K[r.s]["h"][r.i0:r.i0 + 97].astype(float)
        weak = c24[-1] <= h24.max() * 0.75 if len(c24) == 97 else False
        rows.append(dict(s=r.s, t=r.launch, x=x, mk=mk, pl=np.nanmean(pl) if np.isfinite(pl).any() else np.nan,
                         kr=kr_within(r.s, r.launch), weak=weak))
    D = pd.DataFrame(rows)
    d = D.dropna(subset=["x", "pl"])
    se = (d.x - d.pl).std() / np.sqrt(len(d))
    print(f"шорт 168 ч со входа через 24 ч (только цена): {D.x.mean() * 100:+.1f}% (медиана {D.x.median() * 100:+.1f}%), к рынку {D.mk.mean() * 100:+.1f}%; "
          f"плацебо — та же монета через 30–60 сут: {d.pl.mean() * 100:+.1f}%, разница {(d.x - d.pl).mean() * 100:+.1f}% (t = {(d.x - d.pl).mean() / se:.1f}, n = {len(d)})")
    print(f"листинг к воне в первые 7 суток: {int(D.kr.sum())} из {len(D)}; «слабый старт» (через 24 ч на ≥ 25% ниже максимума суток): {int(D.weak.sum())}")

    print("\nсделка (комиссия и фандинг), вход через 24 ч после запуска:")
    for nm, kw in (("7 сут, стоп 50%", dict(sl=0.5, hold_h=168)), ("7 сут, стоп 25%", dict(sl=0.25, hold_h=168)),
                   ("7 сут, стоп 100%", dict(sl=1.0, hold_h=168)), ("3 сут, стоп 50%", dict(sl=0.5, hold_h=72)),
                   ("14 сут, стоп 50%", dict(sl=0.5, hold_h=336))):
        R = pd.DataFrame([dict(x, t=r.launch, s=r.s) for r in G.itertuples() if (x := trade(r.s, r.i0 + 96, **kw))])
        print(summary(R, nm))
    R = pd.DataFrame([dict(x, t=r.launch, s=r.s) for r in G.itertuples() if (x := trade(r.s, r.i0 + 96, sl=0.5, hold_h=168))])
    R = R.merge(D[["s", "kr", "weak"]], on="s")
    print(summary(R[~R.kr], "без листинга к воне в первые 7 суток"))
    print(summary(R[R.kr], "с листингом к воне в первые 7 суток"))
    print(summary(R[~R.weak], "без «слабого старта» (s3)"))
    q = R.groupby(pd.to_datetime(R.t, unit="s").dt.to_period("Q")).net.agg(["size", "mean"])
    print("  по кварталам (7 сут, стоп 50%): " + ", ".join(f"{k} {v['mean'] * 100:+.1f}% ({int(v['size'])})" for k, v in q.iterrows()))
    m = R.groupby(pd.to_datetime(R.t, unit="s").dt.to_period("M")).net.sum()
    print(f"  месяцев в плюсе {(m > 0).sum()}/{len(m)}; итог при марже 1 USDT ×1: {R.net.sum():+.2f} USDT")
    print("  худшие:", ", ".join(f"{x.s} {x.net * 100:+.0f}%" for x in R.sort_values('net').head(6).itertuples()))
