"""Г11. Лонг ликвидных монет вне маржинального канала после сильного хода (Boehmer, Huszár & Jordan: активно торгуемые
бумаги с низким short interest дают значимо положительную доходность). В s21 монеты вне канала после хода ±5% за 4 ч
«обгоняли» медиану рынка на 2,0–2,3% за неделю, но часть этого — счётный эффект медианы у волатильных монет. Здесь:
  - события: фьючерс (без стейблкоинов, металлов, акций; торгуется ≥ суток) на закрытии часа с ходом ±5% за 4 ч,
    оборот за 24 ч — в верхней половине всех торгующихся фьючерсов в этот час, монеты 7 суток не было в ленте
    MarginData; одно событие на монету за сутки;
  - исход — лонг на 7 и 30 суток: к среднему (не медиане) рынка, к среднему ликвидных монет той же волатильности
    (квинтиль волатильности за 7 суток), с фандингом и с хеджем BTC (лонг монеты − лонг BTC, обе ноги с фандингом).
Рост и падение — отдельно; t — с кластеризацией по дню; половины. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import BAR, COIN_OF, DAY, FEE, G, GR, H, K, NONCRYPTO, PREF, funding, live, summ, thin

if __name__ == "__main__":
    g, C = GR["grid"], GR["C"]; syms = GR["syms"]; n = len(g)
    print("матрицы оборота и волатильности…", flush=True)
    TV = np.full(C.shape, np.nan, dtype=np.float32)
    for i, s in enumerate(syms):
        a = K[s]; t = a["t"].astype(np.int64) + BAR; cq = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
        j = np.searchsorted(t, g, "right")                       # свечей, закрывшихся не позже часа
        ok = (j >= 96) & (j <= len(t))
        TV[i, ok] = (cq[j[ok]] - cq[j[ok] - 96]).astype(np.float32)
    LR = np.log(C[:, 1:] / C[:, :-1])
    RV = pd.DataFrame(LR.T).rolling(168, min_periods=120).std().values.T
    RV = np.c_[np.full((len(syms), 1), np.nan), RV].astype(np.float32)
    excl = np.array([s in NONCRYPTO for s in syms])
    pres = {}
    for c, a in G.items():
        pres[c] = a[:, 0]
    rows = []
    for i, s in enumerate(syms):
        if excl[i]:
            continue
        lo, hi = live(s); c = C[i]
        k = np.arange(4, n - 1); r4 = c[k] / c[k - 4] - 1
        ok = np.isfinite(r4) & (np.abs(r4) >= 0.05) & (g[k] - 900 >= lo + DAY) & (g[k] <= hi)
        coin = COIN_OF.get(s, PREF.sub("", s)); pt = pres.get(coin)
        for kk in k[ok]:
            T = int(g[kk])
            if pt is not None:
                j = np.searchsorted(pt, T, "right")
                if j > 0 and pt[j - 1] >= T - 7 * DAY:
                    continue                                     # монета была в ленте за 7 суток
            col = TV[:, kk]; live_now = np.isfinite(col) & ~excl
            if not np.isfinite(TV[i, kk]) or TV[i, kk] < np.nanmedian(col[live_now]):
                continue
            rows.append((s, i, T, kk, c[kk] / c[kk - 4] - 1))
    E = thin(pd.DataFrame(rows, columns=["s", "i", "T", "k", "r4"]))
    print(f"событий: {len(E)} (рост {(E.r4 > 0).sum()}, падение {(E.r4 < 0).sum()})", flush=True)
    bi = GR["row"]["BTC"]; frb = funding("BTC")
    out = []
    for e in E.itertuples():
        r = dict(s=e.s, T=e.T, r4=e.r4)
        liq = np.isfinite(TV[:, e.k]) & ~excl
        liq &= TV[:, e.k] >= np.nanmedian(TV[liq, e.k])
        q = pd.Series(RV[liq, e.k]).rank(pct=True).values
        myq = (np.sum(RV[liq, e.k] <= RV[e.i, e.k]) / max(liq.sum(), 1)) if np.isfinite(RV[e.i, e.k]) else np.nan
        fr = funding(e.s)
        for h in (168, 720):
            if e.k + h >= n:
                continue
            R = C[:, e.k + h] / C[:, e.k] - 1
            px = R[e.i]
            if not np.isfinite(px):
                continue
            f = float(fr[(fr[:, 0] > e.T) & (fr[:, 0] <= e.T + h * H), 1].sum()) if len(fr) else 0.0
            fb = float(frb[(frb[:, 0] > e.T) & (frb[:, 0] <= e.T + h * H), 1].sum())
            mkt = np.nanmean(R[~excl & np.isfinite(R)])
            same = liq & np.isfinite(R)
            if np.isfinite(myq):
                qq = np.full(len(syms), np.nan); qq[np.flatnonzero(liq)] = q
                band = same & (np.abs(qq - myq) <= 0.1)
                vb = np.nanmean(R[band]) if band.sum() >= 5 else np.nan
            else:
                vb = np.nan
            r[f"x{h}"] = px - mkt; r[f"v{h}"] = px - vb
            r[f"n{h}"] = px - f - FEE
            r[f"b{h}"] = (px - f) - (R[bi] - fb) - 2 * FEE
        out.append(r)
    O = pd.DataFrame(out)
    for nm, m in (("рост +5%+", O.r4 > 0), ("падение −5%−", O.r4 < 0)):
        d = O[m]
        print(f"\n{nm}: {len(d)} событий")
        for h in (168, 720):
            print(f"  {h // 24:2d} сут, лонг: к среднему рынка {summ(d[f'x{h}'].values, d['T'].values)}")
            print(f"          к монетам той же волатильности {summ(d[f'v{h}'].values, d['T'].values)}")
            print(f"          с фандингом {summ(d[f'n{h}'].values, d['T'].values)}; с хеджем BTC {summ(d[f'b{h}'].values, d['T'].values)}")
    O.to_pickle("s22/h11_events.pkl")
