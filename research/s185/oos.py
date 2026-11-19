"""s185 — корейская часть 👀 (пятёрка одной корейской биржи вне 🔝, s73/s83) на 2020–2022 и 2022–2024 гг.: вход монеты
в пятёрку по обороту за 24 ч на Upbit или Bithumb впервые за 7 сут (10 лидеров первой половины не считаются), одно
событие на монету за 7 сут, без входа 🔝 за 7 сут (то же правило по сумме Upbit + Bithumb), шорт 10/25/48 ч и 7 сут
(стоп 50%), плацебо 45/90/135 сут; доля Кореи у монеты за 7 сут — как s184 Г3. Гипотеза — ВЫВОДЫ.md (до расчёта).
Запуск из /home/user/mc_data: MC_K=… MC_F=… python3 <repo>/research/s185/oos.py <период>; сводка: … oos.py report"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
sys.path.insert(0, os.path.join(HERE, "..", "s184"))
import g3 as G3  # noqa: E402  (доля Кореи у монеты на момент входа; тянет s182/common182)

C = G3.C
DAY, OUT = 86400, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01", "s88/oos2020"),
       "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01", "s88/oos")}
STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "PYUSD", "RLUSD", "BUSD", "UST"}
EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_7d": dict(tp=None, sl=0.50, hold_h=168)}


def volumes(per, ex):
    base = f"{OUT}/{PER[per][3]}"
    mp = pd.read_pickle(f"{base}/map.pkl")
    cols = {}
    for f in sorted(os.listdir(f"{base}/kc/{ex}")):
        b = f[4:-4]
        if b in STABLE or b not in mp:
            continue
        x = pickle.load(open(f"{base}/kc/{ex}/{f}", "rb"))
        if x is None or not len(x["t"]):
            continue
        s = mp[b][:-4] if mp[b].endswith("USDT") else mp[b]
        v = pd.Series(np.asarray(x["v"], float), index=np.asarray(x["t"], np.int64) + 3600)    # конец часа
        v = v[~v.index.duplicated()]
        cols[s] = cols[s].add(v, fill_value=0.0) if s in cols else v
    V = pd.DataFrame(cols).sort_index()
    full = np.arange(int(V.index.min()), int(V.index.max()) + 3600, 3600)
    return V.reindex(full).fillna(0.0)


def events(V, per, K, live, idx_at):
    t0, _, cut, _ = PER[per]
    V = V[V.index >= C.ts(t0)]
    V24 = V.rolling(24, min_periods=24).sum().dropna(how="all")
    majors = list(V24[V24.index < C.ts(cut)].median().sort_values(ascending=False).index[:10])
    R = V24.drop(columns=majors).rank(axis=1, ascending=False, method="first")
    top = R <= 5
    in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)
    out, last = [], {}
    for T, row in top.iterrows():
        T = int(T)
        for s in row.index[row.values]:
            if in7.at[T, s] or T - last.get(s, -1e18) < 7 * DAY or s not in K:
                continue
            lo, hi = live(s)
            if not np.isfinite(lo) or T < lo + DAY or T > hi or idx_at(s, T) is None:
                continue
            last[s] = T
            out.append((s, T))
    return out, majors


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    t0, t1 = C.ts(PER[per][0]), C.ts(PER[per][1])
    Vu, Vb = volumes(per, "upbit"), volumes(per, "bithumb")
    ev = []
    for ex, V in (("upbit", Vu), ("bithumb", Vb)):
        e, majors = events(V, per, K, live, idx_at)
        print(f"{per} {ex}: лидеры {majors}; входов в пятёрку {len(e)}", flush=True)
        ev += [(T, s, ex) for s, T in e]
    kt_ev, kmaj = events(Vu.add(Vb, fill_value=0.0).fillna(0.0), per, K, live, idx_at)
    print(f"{per} 🔝 (Upbit + Bithumb): лидеры {kmaj}; входов {len(kt_ev)}", flush=True)
    kt = {}
    for s, T in kt_ev:
        kt.setdefault(s, []).append(T)
    kt = {s: np.array(v) for s, v in kt.items()}
    D = G3.kshare(per)
    ev.sort()
    rows, last = [], {}
    for T, s, ex in ev:
        if not (t0 <= T < t1) or T - last.get(s, -1e18) < 7 * DAY:
            continue
        o = kt.get(s, np.zeros(0))
        if ((o <= T) & (o >= T - 7 * DAY)).any():
            continue
        last[s] = T
        i = idx_at(s, T)
        d = dict(s=s, t=T, ex=ex, ks=G3.ks_at(D, s, T))
        for nm, kw in EXITS.items():
            x = trade(s, i, side=-1, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None
                 and (y := trade(s, j, side=-1, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s185_{per}.pkl")
    print(per, "событий", len(X), "с долей Кореи ≥ 20%", int((X.ks >= 0.2).sum()), flush=True)


def report():
    R = pd.read_pickle(f"{OUT}/s184_g3.pkl")
    R = R[R.j == "👀"]
    T = pd.read_pickle(f"{OUT}/s83/trades.pkl")
    T["s"] = T.s.str.replace("USDT$", "", regex=True)
    R = R.merge(T[["s", "t", "src"]], on=["s", "t"], how="left")
    new = R[R.src == "Корея, одна биржа"].rename(columns={"net": "S_10_25", "pl": "pl_S_10_25"})
    A = {per: pd.read_pickle(f"{OUT}/s185_{per}.pkl") for per in PER}
    A["2024–2026"] = new
    print("s185 — корейская часть 👀 (пятёрка одной биржи вне 🔝): доля Кореи у монеты ≥ 20% против < 20%, шорт 10/25/48 ч\n")
    parts_old, parts_all = [], []
    for per, X in A.items():
        X = X[X.S_10_25.notna()].rename(columns={"S_10_25": "net", "pl_S_10_25": "pl"})
        hi, lo = X[X.ks >= 0.2], X[X.ks < 0.2]
        z = X[X.ks.notna()]
        d, se = C.diff(z.net, z.ks >= 0.2, z.t)
        (parts_old if per != "2024–2026" else []).append((d, se, len(hi)))
        parts_all.append((d, se, len(hi)))
        print(f"{per}: всего {len(X)} ({len(X) / C.months(per):.1f} в месяц), доли нет {int(X.ks.isna().sum())}")
        print(f"  ≥ 20% {C.line(hi, per)}")
        print(f"  < 20% {C.line(lo, per)}")
        print(f"  Δ = {d:+.2%} (t {d / se:+.1f}) | доза < 10 / 10–20 / 20–35 / ≥ 35%: " +
              " / ".join(f"{X[(X.ks >= a) & (X.ks < b)].net.mean():+.2%} ({int(((X.ks >= a) & (X.ks < b)).sum())})"
                         for a, b in ((0, 0.1), (0.1, 0.2), (0.2, 0.35), (0.35, 9))))
        if "ex" in X:
            for ex, g in X.groupby("ex"):
                zz = g[g.ks.notna()]
                if (zz.ks >= 0.2).sum() >= 5 and (zz.ks < 0.2).sum() >= 5:
                    dd, ss = C.diff(zz.net, zz.ks >= 0.2, zz.t)
                    print(f"    {ex}: ≥ 20% n={int((g.ks >= 0.2).sum())} {g[g.ks >= 0.2].net.mean():+.2%}; "
                          f"< 20% n={int((g.ks < 0.2).sum())} {g[g.ks < 0.2].net.mean():+.2%}; Δ {dd:+.2%} (t {dd / ss:+.1f})")
        if "S_7d" in X:
            y = X[X.S_7d.notna() & X.ks.notna()]
            dd, ss = C.diff(y.S_7d, y.ks >= 0.2, y.t)
            print(f"    7 сут, стоп 50%: ≥ 20% {y[y.ks >= 0.2].S_7d.mean():+.2%}, < 20% {y[y.ks < 0.2].S_7d.mean():+.2%}, "
                  f"Δ {dd:+.2%} (t {dd / ss:+.1f})")
    m, t = C.combine(parts_old); ma, ta = C.combine(parts_all)
    print(f"\nдва старых периода вместе: Δ = {m:+.2%} (t {t:+.1f}); три периода: Δ = {ma:+.2%} (t {ta:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
