"""s268 — проверка Н1–Н4 (ВЫВОДЫ.md, «Полный экспорт») на всех страницах экспорта канала Margin_data_exper.
Входы в список — первые снимки серий (posts.pkl из parse.py по 15 страницам). Выборка проверки — входы после 03.10.2026
17:12 UTC (конец первой страницы); первая страница — для сравнения. Свечи и фандинг — s224/k_d.pkl, s224/fund_d.pkl плюс
докачка s268/k_tail.pkl, f_tail.pkl (tail.py). Хедж — индекс альтов s103 по k_d (после 19.11.2026 — нет).
Запуск из /home/user/mc_data: python3 -I <repo>/research/s268/run_full.py"""
import os
import sys

os.environ.setdefault("MC_K", "s224/k_d.pkl")
os.environ.setdefault("MC_F", "s224/fund_d.pkl")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fastbt as FB  # noqa: E402  (добавляет s15 в путь)
import common as CM  # noqa: E402  (s15: K, FU, trade)

BAR, H, DAY, WEEK = 900, 3600, 86400, 7 * 86400
GAPS = 3600
IDX_END = 0
IS_END = pd.Timestamp("2026-10-03 17:12:09", tz="UTC").timestamp()      # последний пост первой страницы
MD_END = pd.Timestamp("2026-11-16 11:15", tz="UTC").timestamp()          # конец архива MarginData s41


def merge_tail():
    """Свечи и фандинг после 19.11.2026 — к концу рядов k_d (только продолжение сетки без разрыва)."""
    import pickle
    kt = pickle.load(open("s268/k_tail.pkl", "rb")); ft = pickle.load(open("s268/f_tail.pkl", "rb"))
    n = 0
    for p, a in kt.items():
        if p not in CM.K:
            continue
        k = CM.K[p]; last = int(k["t"][-1])
        m = a["t"] > last
        if not m.any() or int(a["t"][m][0]) != last + BAR:
            continue
        CM.K[p] = {c: np.concatenate([k[c], a[c][m].astype(k[c].dtype)]) for c in k}
        n += 1
        f = ft.get(p)
        if f is not None and len(f):
            old = CM.FU.get(p)
            lastf = float(old[:, 0].max()) if old is not None and len(old) else 0.0
            add = f[f[:, 0] > lastf]
            CM.FU[p] = np.vstack([old, add]) if old is not None and len(old) else add
    print("докачка: продолжено рядов", n)


def perp(sym):
    for p in (sym, "1000" + sym, "1000000" + sym, "1M" + sym):
        if p in CM.K and (CM.K[p]["qv"] > 0).any():
            return p
    return None


def series(X):
    rows = []
    for s, g in X.sort_values("hdr").groupby("sym"):
        g = g.drop_duplicates("hdr")
        ts = g.hdr.map(lambda x: x.timestamp()).values
        sid = np.cumsum(np.r_[True, np.diff(ts) > GAPS])
        for k, gg in g.groupby(sid):
            f = gg.iloc[0]
            rows.append(dict(sym=s, t0=gg.hdr.iloc[0].timestamp(), t1=gg.hdr.iloc[-1].timestamp(),
                             post0=f.posted.timestamp(), n=len(gg), empty0=f.pempty, fund=f.fund, p24=f.p24, oi4h=f.oi4h,
                             ls=f.ls, apr=f.apr, br=f.br, bor=f.bor, chng=f.chng, dur_h=(ts[sid == k][-1] - ts[sid == k][0]) / H,
                             first_in_file=gg.hdr.iloc[0] == X.hdr.min()))
    return pd.DataFrame(rows)


def was_listed(S, X, R):
    """Была ли монета в списке за прошлые 24 ч (до начала серии минус час): до 16.11 — архив MarginData, дальше — сам канал."""
    md = {c: np.sort(g.t.values) for c, g in R.groupby("c")}
    ex = {c: np.sort(g.hdr.map(lambda x: x.timestamp()).values) for c, g in X.groupby("sym")}
    out = []
    for r in S.itertuples():
        a, b = r.t0 - 24 * H, r.t0 - 10 * 60
        v = md.get(r.sym) if r.t0 <= MD_END else ex.get(r.sym)
        if v is None:
            out.append(False); continue
        i = np.searchsorted(v, a)
        out.append(bool(i < len(v) and v[i] < b))
    return np.array(out)


def returns(S):
    res = []
    for p, g in S.groupby("perp"):
        a = CM.K[p]; t = a["t"].astype(np.int64); c = a["c"].astype(float)
        te = (np.ceil(g.post0.values / BAR) * BAR).astype(np.int64)
        I = np.searchsorted(t, te - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == te - BAR) & (I >= 96)
        g = g[ok].copy(); I = I[ok]; te = te[ok]
        if not len(g):
            continue
        g["entry"] = te
        for h in (4, 24, 48):
            j = I + h * 4
            g[f"r{h}"] = np.where(j < len(t), -(c[np.minimum(j, len(t) - 1)] / c[I] - 1), np.nan)
        okt, net, stp, bars, tend = FB.trades(p, I, 0.25, 24, -1)
        g["net"] = np.where(okt, net, np.nan); g["stop"] = np.where(okt, stp, False)
        g["hed"] = g.net.values + FB.alt_mv(te, np.where(okt, tend, te))
        g.loc[~okt | (tend > IDX_END), "hed"] = np.nan             # индекс альтов кончается с k_d (19.11.2026)
        g["pl"] = FB.placebo(p, I, 0.25, 24, -1)
        b = [CM.trade(p, int(i), tp=0.15, sl=0.25, hold_h=48, side=-1) for i in I]       # как у 📘
        g["blue"] = [x["net"] if x else np.nan for x in b]
        g["pre24"] = c[I] / c[I - 96] - 1
        res.append(g)
    return pd.concat(res, ignore_index=True)


def ct(x, t, unit=DAY):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // unit) * unit; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def line(x, months, mid=None):
    if len(x) < 5:
        return f"n={len(x)}" + (f", сделка {x.net.mean():+.2%}" if len(x) else "")
    m, t, n = ct(x.net, x.entry); _, tw, _ = ct(x.net, x.entry, WEEK)
    mh, th, nh = ct(x.hed, x.entry); md, td, _ = ct(x.net - x.pl, x.entry)
    s = (f"n={n} ({n / months:.0f} в мес.), сделка 24 ч {m:+.2%} (t по дням {t:+.1f}, по неделям {tw:+.1f}; медиана "
         f"{x.net.median():+.2%}); шорт 24 ч без стопа {x.r24.mean():+.2%}; с хеджем {mh:+.2%} (t {th:+.1f}, n={nh}); "
         f"сверх плацебо {md:+.2%} (t {td:+.1f}); как 📘 {x.blue.mean():+.2%}; стопов {x.stop.mean():.0%}")
    if mid is not None:
        s += f"; половины {x[x.entry < mid].net.mean():+.2%} / {x[x.entry >= mid].net.mean():+.2%}"
    return s


def diff(a, b):
    """Разница средних сделок a − b с t по дням (кластеры — сутки входа по обеим группам)."""
    A = pd.DataFrame({"x": a.net.values, "g": 1, "d": a.entry.values // DAY}); B = pd.DataFrame({"x": b.net.values, "g": 0, "d": b.entry.values // DAY})
    Z = pd.concat([A, B]).dropna()
    if Z.g.sum() < 5 or (1 - Z.g).sum() < 5:
        return "мало"
    ma, mb = Z[Z.g == 1].x.mean(), Z[Z.g == 0].x.mean()
    na, nb = (Z.g == 1).sum(), (Z.g == 0).sum()
    u = np.where(Z.g == 1, (Z.x - ma) / na, -(Z.x - mb) / nb)
    se = np.sqrt(pd.Series(u).groupby(Z.d.values).sum().pow(2).sum())
    return f"разница {ma - mb:+.2%} (t по дням {(ma - mb) / se:+.1f})"


def main():
    global IDX_END
    FB.alt_mv(np.array([0]), np.array([0]))                   # индекс альтов — по k_d до докачки
    IDX_END = int(FB._IDX["T"][-1]) + BAR
    T_, I_ = FB._IDX["T"], FB._IDX["I"]
    for d in ("2026-09-30", "2026-10-03", "2026-10-15", "2026-11-01", "2026-11-15", "2026-11-19 23:00"):
        k = int(np.searchsorted(T_, pd.Timestamp(d, tz="UTC").timestamp()))
        print(f"индекс альтов {d}: {I_[min(k, len(I_) - 1)] / I_[int(np.searchsorted(T_, pd.Timestamp('2026-09-30', tz='UTC').timestamp()))]:.3f}")
    merge_tail()
    X = pd.read_pickle("s268/posts.pkl").rename(columns={"empty": "pempty"})
    R = pd.read_pickle("s41/rows.pkl")
    S = series(X)
    S["perp"] = S.sym.map(perp)
    print(f"серий {len(S)}, монет {S.sym.nunique()}; с перпом — серий {S.perp.notna().sum()}, монет {S[S.perp.notna()].sym.nunique()}")
    S = S[S.perp.notna() & ~S.first_in_file].copy()
    S["ret24"] = was_listed(S, X, R)
    T = returns(S)
    T.to_pickle("s268/entries_full.pkl")
    print("входов с ценами:", len(T), "; последний вход", pd.Timestamp(T.entry.max(), unit="s"))
    for name, P in (("первая страница (до 03.10 17:12)", T[T.post0 <= IS_END]), ("ПРОВЕРКА — страницы 2–15", T[T.post0 > IS_END])):
        mo = max((P.entry.max() - P.entry.min()) / (30.44 * DAY), 0.1)
        mid = float(np.median(P.entry))
        print(f"\n===== {name}: {len(P)} входов, {P.sym.nunique()} монет, {mo:.2f} мес.; середина {pd.Timestamp(mid, unit='s')}")
        print("все входы:", line(P, mo, mid))
        e1, e0 = P[P.empty0 == True], P[P.empty0 == False]          # noqa: E712
        print("Н1 пул пуст на входе:", line(e1, mo, mid)); print("   пул не пуст:", line(e0, mo, mid))
        print("   Н1:", diff(e1, e0)); print("   нет данных о пуле:", line(P[P.empty0.isna()], mo))
        big = P.p24 >= 10
        print("Н2 ход за 24 ч ≥ 10%:", line(P[big], mo, mid)); print("   ход < 10%:", line(P[P.p24 < 10], mo, mid))
        print("Н3 пул пуст и ход ≥ 10%:", line(P[big & (P.empty0 == True)], mo, mid))   # noqa: E712
        print("   пул не пуст и ход ≥ 10%:", line(P[big & (P.empty0 == False)], mo, mid))  # noqa: E712
        print("   Н3:", diff(P[big & (P.empty0 == True)], P[big & (P.empty0 == False)]))   # noqa: E712
        print("   пул пуст и ход < 10%:", line(P[(P.p24 < 10) & (P.empty0 == True)], mo))   # noqa: E712
        print("Н4 возврат (в списке за 24 ч):", line(P[P.ret24], mo, mid)); print("   новые:", line(P[~P.ret24], mo, mid))
        print("   Н4:", diff(P[P.ret24], P[~P.ret24]))
        print("-- для отчёта")
        print("фандинг < 0:", line(P[P.fund < 0], mo)); print("фандинг ≥ 0:", line(P[P.fund >= 0], mo))
        ma = P.apr.median()
        print(f"APR ≥ медианы ({ma:.0f}%):", line(P[P.apr >= ma], mo)); print("APR < медианы:", line(P[P.apr < ma], mo))
        print("серия ≥ 6 ч (по факту, не знали на входе):", line(P[P.dur_h >= 6], mo))
    return T


if __name__ == "__main__":
    main()
