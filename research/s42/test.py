"""s42: Г1–Г3 — режим волатильности (BVOL), всплески BVOL и режим базиса квартальных BTC/ETH против сделок
шорт-журналов (s20/trades.pkl) и рынка альтов (s22/grid.pkl). Запуск из папки данных после fetch.py:
python3 <repo>/research/s42/test.py"""
import pickle

import numpy as np
import pandas as pd

H = 3600
CUT = pd.Timestamp("2025-12-01", tz="UTC").timestamp()
QUARTERS = ["240628", "240927", "241227", "250328", "250627", "250926", "251226", "260327", "260626", "260925",
            "261225", "270326"]
W90, W7 = 90 * 24, 7 * 24
HOURS = np.arange(pd.Timestamp("2024-06-01", tz="UTC").timestamp(), pd.Timestamp("2026-10-20", tz="UTC").timestamp(),
                  H).astype(np.int64)


def on_grid(s, limit=3):
    return s[~s.index.duplicated()].sort_index().reindex(HOURS).ffill(limit=limit)


def basis():
    """Базис в годовых ближайшего квартального контракта (до поставки > 14 сут) к бессрочному; время — закрытие свечи."""
    K = pickle.load(open("s42/q1h.pkl", "rb"))

    def close(sym):
        a = K[sym]
        return pd.Series(a[:, 1], index=a[:, 0].astype(np.int64) + H)[a[:, 2] > 0]

    out = {}
    for b in ("BTC", "ETH"):
        P = on_grid(close(b + "USDT"))
        dl = np.array([pd.Timestamp(f"20{q[:2]}-{q[2:4]}-{q[4:]} 08:00", tz="UTC").timestamp() for q in QUARTERS])
        Q = np.full(len(HOURS), np.nan); D = np.full(len(HOURS), np.nan)
        k = np.searchsorted(dl, HOURS + 14 * 86400, side="right")          # первая поставка позже t + 14 сут
        for j, q in enumerate(QUARTERS):
            m = k == j
            if not m.any() or f"{b}USDT_{q}" not in K:
                continue
            s = close(f"{b}USDT_{q}"); s = on_grid(s[s.index <= dl[j]])
            Q[m] = s.values[m]; D[m] = (dl[j] - HOURS[m]) / 86400
        out[b] = pd.Series((Q / P.values - 1) * 365 / D, index=HOURS)
    out["MKT"] = (out["BTC"] + out["ETH"]) / 2
    return out


def bvol():
    d = pickle.load(open("s42/bvol.pkl", "rb"))
    return on_grid(pd.Series(d, dtype=float))


def pct90(s):
    """Перцентиль значения среди значений за прошлые 90 сут (включая текущее)."""
    return s.rolling(W90, min_periods=W90 // 2).rank(pct=True)


def at(s, te):
    i = np.searchsorted(HOURS, np.asarray(te), side="right") - 1
    v = s.values[np.clip(i, 0, len(s) - 1)]
    return np.where((i >= 0) & (i < len(s)), v, np.nan)


def cl_t(y, x, g):
    """МНК y = a + b·x с кластерами g: оценка b и её t (поправка G/(G−1))."""
    y, x, g = np.asarray(y, float), np.asarray(x, float), np.asarray(g)
    X = np.c_[np.ones_like(x), x]
    XtXi = np.linalg.pinv(X.T @ X)
    b = XtXi @ X.T @ y
    u = y - X @ b
    S = pd.DataFrame(X * u[:, None]).groupby(g).sum().values
    G = len(S)
    if G < 5:
        return b[1], np.nan
    V = XtXi @ (S.T @ S) @ XtXi * G / (G - 1)
    return b[1], b[1] / np.sqrt(V[1, 1]) if V[1, 1] > 0 else np.nan


def dayt(a, b):
    """Разница средних по сделкам a − b (индекс — время входа) и её t с кластерами по дням и по неделям."""
    if len(a) < 3 or len(b) < 3:
        return a.mean() - b.mean(), np.nan, np.nan
    y = np.r_[a.values, b.values]; x = np.r_[np.ones(len(a)), np.zeros(len(b))]
    t = np.r_[a.index.values, b.index.values].astype(np.int64)
    d, td = cl_t(y, x, t // 86400)
    _, tw = cl_t(y, x, t // (7 * 86400))
    return d, td, tw


def tercile_table(T, col, lab):
    print(f"\n### {lab}: верхняя треть против нижней (перцентиль к прошлым 90 сут)")
    x = T[T[col].notna()]
    top, mid, bot = x[x[col] >= 2 / 3], x[(x[col] >= 1 / 3) & (x[col] < 2 / 3)], x[x[col] < 1 / 3]
    res = {}
    for name, g in [("все журналы", x)] + list(x.groupby("journal", sort=False)):
        t_, b_ = g[g[col] >= 2 / 3], g[g[col] < 1 / 3]
        d, t, tw = dayt(t_.set_index("te").net, b_.set_index("te").net)
        h = []
        for hm in (g.te < CUT, g.te >= CUT):
            gg = g[hm]
            dh, th, _ = dayt(gg[gg[col] >= 2 / 3].set_index("te").net, gg[gg[col] < 1 / 3].set_index("te").net)
            h.append((dh, th, (gg[col] >= 2 / 3).sum(), (gg[col] < 1 / 3).sum()))
        res[name] = (d, t, tw, h)
        m3 = g[(g[col] >= 1 / 3) & (g[col] < 2 / 3)].net.mean()
        print(f"  {name:12s} верх {len(t_):4d} {t_.net.mean():+7.2%} | середина {m3:+7.2%} | низ {len(b_):4d} {b_.net.mean():+7.2%}"
              f" | разница {d:+7.2%} (t {t:+.1f}, по неделям {tw:+.1f}) | половины {h[0][0]:+7.2%} (t {h[0][1]:+.1f}; {h[0][2]}/{h[0][3]})"
              f" / {h[1][0]:+7.2%} (t {h[1][1]:+.1f}; {h[1][2]}/{h[1][3]})")
    return res


def spikes(bv, thr=0.20, gap=72):
    r24 = bv / bv.shift(24) - 1
    ev, last = [], -10 ** 12
    for t, v in r24.items():
        if v >= thr and t - last >= gap * H:
            ev.append(t); last = t
    return np.array(ev, dtype=np.int64), r24


def main():
    T = pd.read_pickle("s20/trades.pkl").sort_values("te").reset_index(drop=True)
    GR = pickle.load(open("s22/grid.pkl", "rb"))
    B = basis(); BV = bvol()
    print(f"Сделок {len(T)}: {pd.to_datetime(T.te.min(), unit='s'):%Y-%m-%d} – {pd.to_datetime(T.te.max(), unit='s'):%Y-%m-%d}; "
          f"BVOL есть в {BV.notna().mean():.0%} часов, базис в {B['MKT'].notna().mean():.0%}")
    for k in ("BTC", "ETH", "MKT"):
        s = B[k].dropna()
        print(f"  базис {k}: медиана {s.median():+.2%} в год, 10–90% {s.quantile(.1):+.2%} … {s.quantile(.9):+.2%}")
    s = BV.dropna()
    print(f"  BVOL: медиана {s.median():.1f}, 10–90% {s.quantile(.1):.1f} … {s.quantile(.9):.1f}, мин {s.min():.1f}, макс {s.max():.1f}")

    F = {"bv_lvl": pct90(BV), "bv_chg": pct90(BV / BV.shift(W7) - 1),
         "bs_lvl": pct90(B["MKT"]), "bs_chg": pct90(B["MKT"] - B["MKT"].shift(W7))}
    for k, s in F.items():
        T[k] = at(s, T.te)
    T["bv"] = at(BV, T.te); T["bs"] = at(B["MKT"], T.te)
    print("\nКорреляция признаков на сделках:\n" + T[list(F)].corr().round(2).to_string())

    print("\n## Г1 — режим волатильности (ожидание: верх лучше низа)")
    R = {"bv_lvl": tercile_table(T, "bv_lvl", "Г1 уровень BVOL"),
         "bv_chg": tercile_table(T, "bv_chg", "Г1 изменение BVOL за 7 сут")}
    print("\n## Г3 — режим плеча, базис (ожидание: верх лучше низа)")
    R["bs_lvl"] = tercile_table(T, "bs_lvl", "Г3 уровень базиса")
    R["bs_chg"] = tercile_table(T, "bs_chg", "Г3 изменение базиса за 7 сут")

    print("\n## Г2 — всплеск BVOL ≥ 20% за 24 ч (ожидание: альты отскакивают, шорты хуже)")
    ev, r24 = spikes(BV)
    ev = ev[ev >= GR["grid"][0]]
    print(f"Всплесков с 10.2024: {len(ev)}; по годам {pd.Series(pd.to_datetime(ev, unit='s').year).value_counts().sort_index().to_dict()}")
    gr = GR["grid"]
    ok = (gr >= ev.min()) & (gr <= T.te.max())
    for h in (24, 72, 168):
        mk = GR["MK"][h]
        k = np.searchsorted(gr, ev)
        k = k[(k < len(gr))]
        e = pd.Series(mk[k], index=gr[k]).dropna()
        base = np.nanmean(mk[ok])
        sd = e.std()
        t = (e.mean() - base) / (sd / np.sqrt(len(e))) if len(e) > 2 else np.nan
        h1, h2 = e[e.index < CUT], e[e.index >= CUT]
        print(f"  рынок альтов (медиана фьючерсов) за {h // 24} сут после всплеска: {e.mean():+.2%} против обычного {base:+.2%}"
              f" — разница {e.mean() - base:+.2%} (t {t:+.1f}, {len(e)} событий) | половины {h1.mean() - base:+.2%} ({len(h1)})"
              f" / {h2.mean() - base:+.2%} ({len(h2)})")
    bvf = (BV.shift(-W7) / BV - 1)
    print(f"  BVOL через 7 сут после всплеска: {np.nanmean(at(bvf, ev)):+.1%} (обычно {bvf.mean():+.1%})")
    j = np.searchsorted(ev, T.te.values, side="right") - 1
    T["post"] = (j >= 0) & (T.te.values - ev[np.clip(j, 0, None)] <= 72 * H) & (T.te.values >= ev[np.clip(j, 0, None)])
    print("  Сделки журналов в 3 сут после всплеска против остальных:")
    g2 = {}
    for name, g in [("все журналы", T)] + list(T.groupby("journal", sort=False)):
        a, b = g[g.post], g[~g.post]
        d, t, tw = dayt(a.set_index("te").net, b.set_index("te").net)
        hh = []
        for hm in (g.te < CUT, g.te >= CUT):
            gg = g[hm]
            hh.append(dayt(gg[gg.post].set_index("te").net, gg[~gg.post].set_index("te").net)[0])
        g2[name] = (d, t, tw, hh)
        print(f"    {name:12s} после всплеска {len(a):4d} {a.net.mean():+7.2%} | остальные {len(b):4d} {b.net.mean():+7.2%}"
              f" | разница {d:+7.2%} (t {t:+.1f}, по неделям {tw:+.1f}) | половины {hh[0]:+7.2%} / {hh[1]:+7.2%}")
    R["spike"] = g2
    T.to_pickle("s42/trades_feat.pkl")
    pickle.dump(dict(R=R, ev=ev, B=B, BV=BV), open("s42/res.pkl", "wb"))


if __name__ == "__main__":
    main()
