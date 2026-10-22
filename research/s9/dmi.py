"""DMI-подобный индекс (логика автора: «крупный объём в покупку не двигает цену → разворот вниз», и наоборот) на BTC и ETH,
15-мин и 1-ч свечи. Дельта тейкеров D = (покупки − продажи) за окно; «неэффективность» = z(D) − z(ΔP) — остаток регрессии цены
на дельту в скользящем окне 30 дней; сигнал, когда |z| ≥ порог. Исход — доход за 4 / 24 ч, сделка по тейку/стопу."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb"))
CUT = datetime.datetime(2025, 10, 15, tzinfo=datetime.timezone.utc).timestamp()
def run(sym, agg):
    a = K[sym]; n = len(a["t"]) // agg * agg
    t = a["t"][:n].reshape(-1, agg)[:, 0] + 900 * agg
    c = a["c"][:n].astype(np.float64).reshape(-1, agg)[:, -1]; o = a["o"][:n].astype(np.float64).reshape(-1, agg)[:, 0]
    qv = a["qv"][:n].astype(np.float64).reshape(-1, agg).sum(1); tb = a["tb"][:n].astype(np.float64).reshape(-1, agg).sum(1)
    d = (2 * tb - qv); r = np.log(c / o)
    W = int(30 * 96 / agg)
    s = pd.DataFrame(dict(d=d, r=r, qv=qv))
    # нормируем дельту на средний объём, регрессия r ~ d в скользящем окне (до текущей свечи, без неё)
    dn = s.d / s.qv.rolling(W, min_periods=W // 2).mean().shift(1)
    cov = (dn * s.r).rolling(W, min_periods=W // 2).mean().shift(1) - dn.rolling(W, min_periods=W // 2).mean().shift(1) * s.r.rolling(W, min_periods=W // 2).mean().shift(1)
    var = dn.rolling(W, min_periods=W // 2).var().shift(1); beta = cov / var
    res = s.r - beta * dn                                      # что сделала цена сверх «положенного» по дельте
    zres = (res - res.rolling(W, min_periods=W // 2).mean().shift(1)) / res.rolling(W, min_periods=W // 2).std().shift(1)
    zd = (dn - dn.rolling(W, min_periods=W // 2).mean().shift(1)) / dn.rolling(W, min_periods=W // 2).std().shift(1)
    f4 = pd.Series(c).shift(-int(16 / agg)) / c - 1; f24 = pd.Series(c).shift(-int(96 / agg)) / c - 1
    return pd.DataFrame(dict(t=t, zd=zd, zres=zres, f4=f4, f24=f24))
for sym in ("BTC", "ETH"):
    for agg in (1, 4):
        X = run(sym, agg); X["half"] = np.where(X.t < CUT, 1, 2)
        print(f"===== {sym}, свеча {15 * agg} мин")
        for thr in (2, 3, 4):
            for nm, m in ((f"покупки z(D) ≥ {thr}, цена отстала (z остатка ≤ −1)", (X.zd >= thr) & (X.zres <= -1)),
                          (f"продажи z(D) ≤ −{thr}, цена отстала (z остатка ≥ +1)", (X.zd <= -thr) & (X.zres >= 1)),
                          (f"покупки z(D) ≥ {thr} (любые)", X.zd >= thr), (f"продажи z(D) ≤ −{thr} (любые)", X.zd <= -thr)):
                g = X[m]
                if len(g) < 20: continue
                h1, h2 = g[g.half == 1], g[g.half == 2]
                print(f"  {nm:52s} n={len(g):5d} за 4 ч {g.f4.mean()*100:+.3f}% ({h1.f4.mean()*100:+.3f}/{h2.f4.mean()*100:+.3f}) за 24 ч {g.f24.mean()*100:+.3f}% ({h1.f24.mean()*100:+.3f}/{h2.f24.mean()*100:+.3f})")
        print(f"  {'все свечи':52s} n={len(X):5d} за 4 ч {X.f4.mean()*100:+.3f}% за 24 ч {X.f24.mean()*100:+.3f}%")
