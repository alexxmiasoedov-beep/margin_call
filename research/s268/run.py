"""s268 — проверка гипотез Г1 («пул пуст — сквиз») и Г2 («вход в список») на снимках канала Margin_data_exper
(posts.pkl из parse.py). Свечи — s224/k_d.pkl, сделки — s187/fastbt. Запуск из /home/user/mc_data:
python3 -I <repo>/research/s268/run.py"""
import os
import sys

os.environ.setdefault("MC_K", "s224/k_d.pkl")
os.environ.setdefault("MC_F", "s224/fund_d.pkl")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fastbt as FB  # noqa: E402

BAR, H, DAY = 900, 3600, 86400
GAPS = 3600                                         # разрыв серии — нет монеты в списке дольше часа


def perp(sym):
    for p in (sym, "1000" + sym, "1000000" + sym, "1M" + sym):
        if p in FB.K and (FB.K[p]["qv"] > 0).any():
            return p
    return None


def fwd(p, t_post):
    """Вход — закрытие первой 15-мин свечи после поста. Шорт: −(c[i+n]/c[i] − 1) за 4/24/48 ч; сделка 24 ч, стоп 25%."""
    a = FB.K[p]
    t = a["t"].astype(np.int64); c = a["c"].astype(float)
    te = int(np.ceil(t_post / BAR) * BAR)                  # закрытие свечи = открытие + 900
    i = int(np.searchsorted(t, te - BAR))
    if i >= len(t) or t[i] != te - BAR:
        return None
    out = {"entry": te}
    for h in (4, 24, 48):
        j = i + h * 4
        out[f"r{h}"] = -(c[j] / c[i] - 1) if j < len(t) else np.nan
    ok, net, stp, bars, tend = FB.trades(p, np.array([i]), 0.25, 24, -1)
    out["net"] = float(net[0]) if ok[0] else np.nan
    out["stop"] = bool(stp[0]) if ok[0] else False
    out["pre24"] = c[i] / c[i - 96] - 1 if i >= 96 else np.nan
    return out


def series(X):
    """Серии монеты: снимки подряд с разрывом не больше часа. → первый снимок серии и первый снимок с меткой «пул пуст»."""
    rows = []
    for s, g in X.sort_values("hdr").groupby("sym"):
        g = g.drop_duplicates("hdr")
        ts = g.hdr.map(lambda x: x.timestamp()).values
        br = np.r_[True, np.diff(ts) > GAPS]
        sid = np.cumsum(br)
        for k, gg in g.groupby(sid):
            f = gg.iloc[0]
            e = gg[gg.pempty.fillna(False).astype(bool)]
            rows.append(dict(sym=s, t0=gg.hdr.iloc[0].timestamp(), t1=gg.hdr.iloc[-1].timestamp(), post0=f.posted.timestamp(),
                             n=len(gg), empty0=bool(f.pempty) if pd.notna(f.pempty) else None, fund=f.fund, p24=f.p24,
                             ser_h=f.ser_h, apr=f.apr, br=f.br, bor=f.bor,
                             t_empty=e.posted.iloc[0].timestamp() if len(e) else np.nan,
                             first_in_file=gg.hdr.iloc[0] == X.hdr.min()))
    return pd.DataFrame(rows)


def prior_md(S, R, hours=24):
    """Была ли монета в MarginData (архив s41) за прошлые hours ч до начала серии."""
    out = []
    by = {c: g.t.values for c, g in R.groupby("c")}
    for r in S.itertuples():
        v = by.get(r.sym)
        out.append(bool(v is not None and ((v >= r.t0 - hours * H) & (v < r.t0 - 10 * 60)).any()))
    return np.array(out)


def show(name, x):
    if len(x) == 0:
        print(f"{name}: нет событий"); return
    s = f"{name}: n={len(x)}, монет {x.sym.nunique()}"
    for h in (4, 24, 48):
        v = x[f"r{h}"].dropna()
        if len(v):
            se = v.std(ddof=1) / np.sqrt(len(v)) if len(v) > 1 else np.nan
            s += f"; шорт {h} ч {v.mean():+.2%} (медиана {v.median():+.2%}, t {v.mean() / se if se else np.nan:+.1f})"
    v = x.net.dropna()
    if len(v):
        s += f"; сделка 24 ч стоп 25% {v.mean():+.2%}, стопов {x.stop.mean():.0%}"
    print(s)


def main():
    X = pd.read_pickle("s268/posts.pkl").rename(columns={"empty": "pempty"})
    R = pd.read_pickle("s41/rows.pkl")
    S = series(X)
    S["perp"] = S.sym.map(perp)
    print(f"серий {len(S)}, монет {S.sym.nunique()}, без перпа: {sorted(S[S.perp.isna()].sym.unique())}")
    S = S[S.perp.notna()].copy()
    S["md24"] = prior_md(S, R)
    f = [fwd(r.perp, r.post0) for r in S.itertuples()]
    F = pd.DataFrame([z or {} for z in f], index=S.index)
    S = S.join(F)
    S.to_pickle("s268/series.pkl")
    entries = S[~S.first_in_file]
    print("\n— Г2: вход в список (серия началась внутри файла)")
    show("все входы", entries)
    show("  новые: не было в MarginData 24 ч (Г2)", entries[~entries.md24])
    show("  возврат: был в MarginData за 24 ч", entries[entries.md24])
    print("\n— Г1: метка «ПУЛ ПУСТ» на входе (все серии внутри файла)")
    show("  пул пуст на входе", entries[entries.empty0 == True])   # noqa: E712
    show("  пул не пуст на входе", entries[entries.empty0 == False])  # noqa: E712
    show("  нет данных о пуле", entries[entries.empty0.isna()])
    # Г1, вариант: первый снимок с меткой в серии (в том числе позже входа и в сериях с начала файла)
    E = S[S.t_empty.notna()].copy()
    f = [fwd(r.perp, r.t_empty) for r in E.itertuples()]
    E = E.drop(columns=[c for c in ("entry", "r4", "r24", "r48", "net", "stop", "pre24") if c in E]).join(
        pd.DataFrame([z or {} for z in f], index=E.index))
    show("  первая метка «пул пуст» в серии", E)
    print("\n— разрезы входов (для отчёта)")
    show("  фандинг < 0", entries[entries.fund < 0])
    show("  фандинг ≥ 0", entries[entries.fund >= 0])
    show("  ход за 24 ч > 10%", entries[entries.p24 > 10])
    show("  ход за 24 ч ≤ 10%", entries[entries.p24 <= 10])
    # все монето-часы списка: первый снимок монеты в каждом часе (сильно пересекаются — только для картины)
    X["perp"] = X.sym.map(perp)
    Y = X[X.perp.notna()].copy()
    Y["hour"] = Y.hdr.map(lambda x: int(x.timestamp()) // H)
    Y = Y.sort_values("hdr").drop_duplicates(["sym", "hour"])
    f = [fwd(r.perp, r.posted.timestamp()) for r in Y.itertuples()]
    Y = Y.join(pd.DataFrame([z or {} for z in f], index=Y.index))
    print("\n— монето-часы списка (пересекаются; по монетам)")
    for k, g in (("пул пуст", Y[Y.pempty == True]), ("пул не пуст", Y[Y.pempty == False])):  # noqa: E712
        m = g.groupby("sym").r24.mean()
        print(f"  {k}: монето-часов {len(g)}, монет {g.sym.nunique()}; шорт 24 ч в среднем по монетам {m.mean():+.2%} "
              f"(медиана {m.median():+.2%}), по часам {g.r24.mean():+.2%}")
    Y.to_pickle("s268/hours.pkl")


if __name__ == "__main__":
    main()
