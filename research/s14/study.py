"""Предсказывают ли данные монеты её цену: часовые признаки (цена и «рисунок» графика, поток покупок/продаж по рынку,
размер сделок, отпечатки алгоритмов, открытый интерес и соотношения лонгов/шортов, фандинг и премия, толщина стакана,
маржинальный канал) → изменение цены через 1, 4, 24 и 168 ч.

Строгая проверка:
  - признак считается на конец часа и только по прошлому; пороги квинтилей — по первой половине истории монеты;
  - разница «верхний квинтиль − нижний» и её t по Ньюи — Уэсту (доходности перекрываются);
  - поправка на перебор: порог t — 95-й процентиль максимума |t| по всем признакам, когда цены сдвинуты относительно
    признаков на случайное время (связь разрушена, всё остальное сохранено) — 200 сдвигов;
  - найденное на 1-й половине проверяется на 2-й теми же порогами.
Плюс часы суток и дни недели (у алгоритмов бывает расписание) и для GPS — до и после отключения маркетмейкера 09.03.2025.

Запуск из папки с данными (после build.py и fingerprints.py): python3 s14/study.py GPS ONE"""
import datetime
import os
import pickle
import sys
import numpy as np, pandas as pd

UTC = datetime.timezone.utc
HOR = (1, 4, 24, 168)
SHIFTS = 200
rng = np.random.default_rng(14)


def sig(q):
    s = f"{q:.8f}".rstrip("0").rstrip(".")
    return len(s.replace(".", "").lstrip("0")) if "." in s else len(s.lstrip("0").rstrip("0"))


def hourly(coin):
    X = pickle.load(open(f"s14/{coin}.pkl", "rb"))
    B = X["bars"].copy(); B.index = B.index * 60
    g = B.groupby(B.index // 3600 * 3600)
    H = pd.DataFrame({"o": g.o.first(), "h": g.h.max(), "l": g.l.min(), "c": g.c.last(), "n": g.n.sum(),
                      "fills": g.fills.sum(), "bv": g.buy_v.sum(), "sv": g.sell_v.sum()})
    H = H.reindex(np.arange(H.index.min(), H.index.max() + 1, 3600))
    H["c"] = H.c.ffill()
    for k in ("h", "l"):
        H[k] = H[k].fillna(H.c)
    H[["n", "fills", "bv", "sv"]] = H[["n", "fills", "bv", "sv"]].fillna(0)
    c = np.log(H.c); vol = H.bv + H.sv; F = pd.DataFrame(index=H.index)
    # цена и рисунок графика
    for k in (1, 4, 24, 168):
        F[f"r{k}"] = c.diff(k)
    F["rv24"] = c.diff().rolling(24).std()
    hi, lo = H.h.rolling(168).max(), H.l.rolling(168).min()
    F["pos7"] = (H.c - lo) / (hi - lo)
    F["dd7"] = H.c / hi - 1
    # объём и поток
    F["vol1"] = np.log((vol + 1) / (vol.rolling(168).median() + 1))
    F["vol24"] = np.log((vol.rolling(24).sum() + 1) / (vol.rolling(24).sum().rolling(720).median() + 1))
    for k in (1, 4, 24):
        bv, sv = H.bv.rolling(k).sum(), H.sv.rolling(k).sum()
        F[f"ti{k}"] = (bv - sv) / (bv + sv).replace(0, np.nan)
    avg = vol / H.n.replace(0, np.nan)
    F["tsize"] = np.log(avg / avg.rolling(168).median())
    F["sweep"] = H.fills / H.n.replace(0, np.nan)
    # открытый интерес и соотношения лонгов/шортов (Binance metrics, 5 мин → последнее значение часа)
    M = X["metrics"]
    if len(M):
        m = M.groupby(M.index // 3600 * 3600).last().reindex(H.index)
        oi = np.log(m.oi)
        for k in (1, 4, 24):
            F[f"doi{k}"] = oi.diff(k)
        F["oi_vol"] = np.log(m.oi_usd / vol.rolling(24).sum().replace(0, np.nan))
        for col in ("top_pos", "top_acc", "all_acc"):
            F[col] = np.log(m[col]); F[f"d_{col}24"] = F[col].diff(24)
    # фандинг (ставка на 8 ч) и премия фьючерса к индексу
    Fu = X["funding"]
    if len(Fu):
        rate = (Fu.rate / Fu.iv * 8).sort_index()
        F["fund"] = pd.Series(rate.values, index=rate.index).reindex(H.index + 3600, method="ffill").values
    P = X["premium"]
    if len(P):
        pr = P.c.groupby(P.index // 3600 * 3600).last().reindex(H.index)
        F["prem"] = pr; F["dprem4"] = pr.diff(4)
    # толщина стакана ±1/2/5% ($)
    D = X["depth"]
    if len(D):
        d = D.groupby(D.index // 3600 * 3600).mean().reindex(H.index)
        both1 = d["d-1"] + d["d+1"]
        F["dep1"] = np.log(both1 / both1.rolling(168).median())
        for p in (1, 2, 5):
            F[f"dimb{p}"] = (d[f"d-{p}"] - d[f"d+{p}"]) / (d[f"d-{p}"] + d[f"d+{p}"])
        F["dep_vol"] = np.log((d["d-2"] + d["d+2"]) / vol.rolling(24).mean().replace(0, np.nan))
    # маржинальный канал MarginData: доля постов с монетой за сутки и неделю
    mg = pickle.load(open("s7/margin.pkl", "rb")); PT = np.sort(np.array(mg["PT"]))
    G = mg["G"].get(coin)
    if G is not None:
        ct = np.sort(np.unique(np.asarray(G)[:, 0])); te = H.index.values + 3600
        for L in (24, 168):
            nc = np.searchsorted(ct, te) - np.searchsorted(ct, te - L * 3600)
            na = np.searchsorted(PT, te) - np.searchsorted(PT, te - L * 3600)
            F[f"ch{L}"] = np.where(na > 0, nc / np.maximum(na, 1), np.nan)
    # отпечатки (fingerprints.py, 30 самых частых размеров), три группы:
    #   wash — размеры, где ≥ 15% сделок парные (покупка и продажа того же размера за 5 с: самоторговля или перекладка);
    #   algo — остальные некруглые (≥ 3 значащих цифр);  tiny — мелочь дешевле 5 $ (пробные сделки, «пинг» стакана)
    fp = f"s14/{coin}_fp.pkl"
    if os.path.exists(fp):
        Q = pickle.load(open(fp, "rb")); tab = Q["table"].set_index("q"); px = float(H.c.median())
        groups = {"wash": [q for q in tab.index if tab.loc[q, "pair"] >= 0.15],
                  "algo": [q for q in tab.index if tab.loc[q, "pair"] < 0.15 and sig(q) >= 3],
                  "tiny": [q for q in tab.index if q * px < 5 and tab.loc[q, "pair"] < 0.15]}
        for name, keep in groups.items():
            if not keep:
                continue
            fl = Q["flow"][keep].sum(axis=1); fl.index = fl.index * 60
            sz = Q["flow"][keep].abs().sum(axis=1); sz.index = sz.index * 60
            nn = Q["count"][keep].sum(axis=1); nn.index = nn.index * 60
            fh = fl.groupby(fl.index // 3600 * 3600).sum().reindex(H.index, fill_value=0) * H.c
            ah = sz.groupby(sz.index // 3600 * 3600).sum().reindex(H.index, fill_value=0) * H.c
            ch = nn.groupby(nn.index // 3600 * 3600).sum().reindex(H.index, fill_value=0)
            F[f"{name}_net4"] = fh.rolling(4).sum() / vol.rolling(4).sum().replace(0, np.nan)
            sh = (ch if name == "tiny" else ah).rolling(24).sum() / (H.n if name == "tiny" else vol).rolling(24).sum().replace(0, np.nan)
            F[f"{name}_share24"] = sh - sh.rolling(168).median()
    Y = pd.DataFrame({f"f{h}": c.shift(-h) - c for h in HOR}, index=H.index)
    return H, F, Y


def nw_var(u, L):
    v = u @ u
    for l in range(1, L + 1):
        v += 2 * (1 - l / (L + 1)) * (u[l:] @ u[:-l])
    return v


def spread_t(x, y, edges, L):
    """Разница средних будущих изменений цены: верхний квинтиль признака минус нижний; t по Ньюи — Уэсту."""
    ok = np.isfinite(x) & np.isfinite(y)
    q = np.searchsorted(edges, np.where(ok, x, 0), side="right")
    m5, m1 = ok & (q == 4), ok & (q == 0)
    if m5.sum() < 50 or m1.sum() < 50:
        return np.nan, np.nan
    a = m5 / m5.sum() - m1 / m1.sum()
    yy = np.where(ok, y, 0.0); u = a * (yy - yy[ok].mean()); s = a @ yy
    return s, s / np.sqrt(max(nw_var(u, L), 1e-30))


def study(coin):
    H, F, Y = hourly(coin)
    n = len(H); half = n // 2
    tr, te = slice(0, half), slice(half, n)
    d0, d1, d2 = (datetime.datetime.fromtimestamp(H.index[i], UTC) for i in (0, half, n - 1))
    print(f"\n===== {coin}: часов {n:,} ({d0:%d.%m.%Y} – {d2:%d.%m.%Y}), 1-я половина до {d1:%d.%m.%Y}; признаков {F.shape[1]}")
    edges = {f: np.nanquantile(F[f].values[tr], [0.2, 0.4, 0.6, 0.8]) for f in F.columns
             if np.isfinite(F[f].values[tr]).sum() > 500}
    rows = []
    for h in HOR:
        L = max(h, 24) + 6; y = Y[f"f{h}"].values
        res = {f: spread_t(F[f].values[tr], y[tr], e, L) for f, e in edges.items()}
        null = []
        ytr = y[tr]
        for _ in range(SHIFTS):                       # максимум |t| по всем признакам при сдвинутых ценах
            k = int(rng.integers(720, half - 720))
            ys = np.roll(ytr, k)
            null.append(np.nanmax([abs(spread_t(F[f].values[tr], ys, e, L)[1]) for f, e in edges.items()]))
        thr = np.nanquantile(null, 0.95)
        for f, e in edges.items():
            s1, t1 = res[f]; s2, t2 = spread_t(F[f].values[te], y[te], e, L)
            rows.append(dict(h=h, f=f, s1=s1, t1=t1, s2=s2, t2=t2, thr=thr))
    R = pd.DataFrame(rows)
    R["pass1"] = R.t1.abs() > R.thr
    R["pass2"] = R.pass1 & (np.sign(R.s2) == np.sign(R.s1)) & (R.t2.abs() > 2)
    for h in HOR:
        r = R[R.h == h].sort_values("t1", key=abs, ascending=False)
        print(f"  через {h} ч: порог |t| с поправкой на перебор {r.thr.iloc[0]:.2f}; прошли на 1-й половине "
              f"{int(r.pass1.sum())}, подтвердились на 2-й {int(r.pass2.sum())}. Сильнейшие на 1-й половине "
              "(разница верхний − нижний квинтиль, %; t; на 2-й половине):")
        for _, x in r.head(6).iterrows():
            print(f"    {x.f:12s} {x.s1 * 100:+6.2f}% (t {x.t1:+5.2f}) → {x.s2 * 100:+6.2f}% (t {x.t2:+5.2f})"
                  + ("  ← ПРОШЁЛ ОБЕ" if x.pass2 else "  ← только 1-я" if x.pass1 else ""))
    # расписание: средний ход цены по часам суток и дням недели, 1-я и 2-я половина
    f1 = Y.f1; hr = (H.index // 3600) % 24; wd = pd.to_datetime(H.index, unit="s").dayofweek
    a = f1[:half].groupby(hr[:half]).mean(); b = f1[half:].groupby(hr[half:]).mean()
    print(f"  часы суток (UTC): связь среднего хода цены за час между половинами — корреляция {a.corr(b):+.2f}; "
          f"сильнейшие часы на 1-й: " + ", ".join(f"{int(k)}ч {a[k] * 100:+.3f}% → {b[k] * 100:+.3f}%" for k in a.abs().sort_values().index[-3:]))
    f24 = Y.f24
    a = f24[:half][hr[:half] == 0].groupby(wd[:half][hr[:half] == 0]).mean(); b = f24[half:][hr[half:] == 0].groupby(wd[half:][hr[half:] == 0]).mean()
    print(f"  дни недели (ход за сутки от 00 UTC): корреляция между половинами {a.corr(b):+.2f}; "
          + ", ".join(f"{'пн вт ср чт пт сб вс'.split()[int(k)]} {a[k] * 100:+.2f}%→{b[k] * 100:+.2f}%" for k in a.index))
    R.to_pickle(f"s14/{coin}_study.pkl")
    return H, F, Y, R


def gps_event(H, F):
    """GPS: недели до и после отключения маркетмейкера Binance (09.03.2025)."""
    ban = datetime.datetime(2025, 3, 9, tzinfo=UTC).timestamp()
    wk = (H.index - ban) // (7 * 86400)
    cols = {"объём, млн $/сут": (H.bv + H.sv) * 24 / 1e6, "сделок/час": H.n, "средняя сделка, $": (H.bv + H.sv) / H.n.replace(0, np.nan),
            "волатильность за час, %": np.log(H.c).diff().abs() * 100}
    for k in ("dep1", "fp_share24"):
        if k in F:
            cols[k] = F[k]
    X = pd.DataFrame(cols)
    if "dimb2" in F:
        X["перекос стакана ±2%"] = F.dimb2
    t = X.groupby(wk).mean().loc[-3:5]
    t.index = [f"неделя {int(i):+d}" for i in t.index]
    print("\n===== GPS до и после отключения маркетмейкера (09.03.2025 = начало недели +0):")
    print(t.round(3).to_string())


if __name__ == "__main__":
    for c in sys.argv[1:]:
        H, F, Y, R = study(c)
        if c == "GPS":
            gps_event(H, F)
