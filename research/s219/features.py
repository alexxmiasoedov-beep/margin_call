"""s219 — суточные признаки по всем фьючерсам и исходы с хеджем индексом альтов (метод — ВЫВОДЫ.md, записан до расчёта,
коммит 925af12). Решение — на закрытии дня d (T = d + 1 сут), только данные до T.
Запуск из /home/user/mc_data для каждого периода (свечи периода — через MC_K, MC_F, как в s213):
  python3 <repo>/research/s219/features.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 <repo>/research/s219/features.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 <repo>/research/s219/features.py 2020–2022
Итог — s219_feat_<период>.pkl; затем python3 <repo>/research/s219/features.py join → s219_feat.pkl"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
DAY = 86400
# исходы: имя → (сторона, стоп, срок ч); y_* — с хеджем индексом альтов (цель перебора), u_* — без хеджа (для отчёта)
OUTS = {"s24": (-1, 0.25, 24), "s48": (-1, 0.25, 48), "s168": (-1, 0.50, 168),
        "l24": (1, 0.25, 24), "l48": (1, 0.25, 48), "l168": (1, 0.50, 168)}


def per_coin(g):
    """Признаки одной монеты по непрерывному дневному ряду (пропуски дней — NaN)."""
    g = g.set_index("d").reindex(np.arange(g.d.min(), g.d.max() + DAY, DAY))
    c, o, h, l, qv = g.c, g.o, g.h, g.l, g.qv
    r = c / c.shift(1) - 1
    f = pd.DataFrame(index=g.index)
    f["r1"] = c / o - 1
    f["r3"] = c / c.shift(3) - 1; f["r7"] = c / c.shift(7) - 1; f["r28"] = c / c.shift(28) - 1
    f["hi28"] = c / h.rolling(28, min_periods=20).max() - 1; f["lo28"] = c / l.rolling(28, min_periods=20).min() - 1
    f["rng"] = (h - l) / o
    f["vol7"] = r.rolling(7, min_periods=6).std()
    f["rvx"] = g.rv / g.rv.shift(1).rolling(28, min_periods=20).mean()
    f["mx15"] = g.mx15; f["mx15x"] = g.mx15 / g.mx15.shift(1).rolling(28, min_periods=20).median()
    q7 = qv.shift(1).rolling(7, min_periods=6).mean()
    f["qvx"] = qv / q7; f["qv7"] = qv.rolling(7, min_periods=6).mean()
    f["tbs"] = g.tb / qv; f["tbs3"] = g.tb.rolling(3).sum() / qv.rolling(3).sum()
    f["nx"] = g.n / g.n.shift(1).rolling(7, min_periods=6).mean()
    tsz = qv / g.n
    f["tszx"] = tsz / tsz.shift(1).rolling(28, min_periods=20).median()
    f["f1"] = g.fsum; f["f7"] = g.fsum.rolling(7, min_periods=6).sum(); f["fint"] = g.fint
    f["ssh"] = g.sqv / (g.sqv + qv); f["ssx"] = g.sqv / g.sqv.shift(1).rolling(7, min_periods=6).mean()
    f["stbs"] = g.stb / g.sqv
    f["sdiv"] = (g.sc / g.sc.shift(1) - 1) - r
    f["ksh"] = g.krv / (g.krv + qv); f["ksx"] = g.krv / g.krv.shift(1).rolling(7, min_periods=6).mean()
    f["kup"] = g.krv_upbit / g.krv
    f["kdiv"] = (g.krc_upbit / g.krc_upbit.shift(1) - 1) - r
    f["c"] = c
    f["s"] = g.s
    return f[g.qv.notna() & (g.qv > 0)]


def events(F, per):
    """Разлоки 🔑⁺ впереди (s142), заводы и выводы токенов Ethereum (s195, s207), ≥ 0,5% обращения."""
    U = pd.read_pickle(f"s142_{per}.pkl")
    UT = {s: (np.asarray(g["T"], np.int64)[np.argsort(g["T"].to_numpy())], g.share.to_numpy()[np.argsort(g["T"].to_numpy())])
          for s, g in U.groupby("s")}
    X = pd.read_pickle("s195_deposits.pkl")[["perp", "t", "frac", "exch"]]
    tok = set(X.perp.dropna().unique())                                 # токены Ethereum из сбора s160 (иначе — нет данных)
    X = X[X.perp.notna() & (X.frac >= 0.005)]
    DB = {s: np.sort(g.t.to_numpy(np.int64)) for s, g in X[X.exch == "Binance"].groupby("perp")}
    DO = {s: np.sort(g.t.to_numpy(np.int64)) for s, g in X[X.exch != "Binance"].groupby("perp")}
    W = pd.read_pickle("s207_withdrawals.pkl")[["perp", "t", "frac", "kind"]]
    W = W[W.perp.notna() & (W.frac >= 0.005) & (W.kind == "wallet")]
    DW = {s: np.sort(g.t.to_numpy(np.int64)) for s, g in W.groupby("perp")}
    out = {k: np.full(len(F), np.nan) for k in ("unl", "unls", "dep1", "dep3", "depo3", "wdr3")}
    for j, (s, T) in enumerate(zip(F.s, F["T"])):
        T = int(T)
        u = UT.get(s); out["unl"][j], out["unls"][j] = 99.0, 0.0
        if u is not None:
            k = int(np.searchsorted(u[0], T, "right"))
            if k < len(u[0]) and u[0][k] <= T + 30 * DAY:
                out["unl"][j] = (u[0][k] - T) / DAY; out["unls"][j] = u[1][k]
        if s in tok:
            for nm, M, w in (("dep1", DB, DAY), ("dep3", DB, 3 * DAY), ("depo3", DO, 3 * DAY), ("wdr3", DW, 3 * DAY)):
                a = M.get(s)
                out[nm][j] = (np.searchsorted(a, T, "right") - np.searchsorted(a, T - w, "right")) if a is not None else 0.0
    return out


def oi_feats(F, per):
    """OI и позиции счетов — только воскресные отметки (s183/oi_<период>.pkl, конец воскресенья): берём последнее
    воскресенье не позже дня d."""
    p = f"s183/oi_{per}.pkl"
    O = pickle.load(open(p, "rb")) if os.path.exists(p) else {}
    out = {k: np.full(len(F), np.nan) for k in ("oi7", "oiq", "lsr_top", "lsr_acc", "tkr")}
    wd = pd.to_datetime(F.d, unit="s").dt.weekday.to_numpy()
    sun = F.d.to_numpy(np.int64) - ((wd + 1) % 7) * DAY                # последнее воскресенье ≤ d
    for j, (s, k, q7) in enumerate(zip(F.s, sun, F.qv7)):
        v, v0 = O.get((s, int(k))), O.get((s, int(k) - 7 * DAY))
        if not v:
            continue
        out["oi7"][j] = v[0] / v0[0] - 1 if v0 and v0[0] else np.nan
        out["oiq"][j] = v[1] / q7 if q7 and q7 > 0 else np.nan
        out["lsr_top"][j], out["lsr_acc"][j], out["tkr"][j] = v[3], v[4], v[5]
    return out


def outcomes(F):
    import fastbt as FB  # noqa: E402
    out = {}
    for k in OUTS:
        out["y_" + k] = np.full(len(F), np.nan); out["u_" + k] = np.full(len(F), np.nan)
    for s, idx in F.groupby("s").groups.items():
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        pos = F.index.get_indexer(idx)
        st = F.loc[idx, "T"].to_numpy(np.int64) - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
        if not ok.any():
            continue
        for k, (side, sl, hold) in OUTS.items():
            okt, net, stp, bars, tend = FB.trades(s, I[ok], sl, hold, side)
            mv = FB.alt_mv(t[I[ok]] + 900, tend)
            out["u_" + k][pos[ok]] = np.where(okt, net, np.nan)
            out["y_" + k][pos[ok]] = np.where(okt, net + (mv if side < 0 else -mv), np.nan)
    return out


def build(per):
    import fastbt as FB  # noqa: E402
    D = pd.read_pickle(f"s183/daily_{per}.pkl").sort_values(["s", "d"])
    F = pd.concat([per_coin(g) for _, g in D.groupby("s")]).rename_axis("d").reset_index()
    F["T"] = F.d + DAY
    lo = {s: FB.live(s)[0] if s in FB.K else np.nan for s in F.s.unique()}
    F["age"] = [(T - lo[s]) / DAY if np.isfinite(lo[s]) else np.nan for s, T in zip(F.s, F["T"])]
    F = F[F.age >= 7].reset_index(drop=True)
    # рынок: BTC, доля выросших за день, медиана хода за 7 сут; место по обороту за 7 сут
    bk = FB.K["BTC"]; bt = bk["t"].astype(np.int64) + 900; bc = bk["c"].astype(float)   # BTC — по 15-мин свечам периода

    def btc(T):
        i = np.searchsorted(bt, np.asarray(T, np.int64), "right") - 1
        return np.where(i >= 0, bc[np.maximum(i, 0)], np.nan)
    F["btc1"] = btc(F["T"]) / btc(F["T"] - DAY) - 1; F["btc7"] = btc(F["T"]) / btc(F["T"] - 7 * DAY) - 1
    F["brd"] = F.groupby("d").r1.transform(lambda x: (x > 0).mean())
    F["alt7"] = F.groupby("d").r7.transform("median")
    F["qvr"] = F.groupby("d").qv7.rank(pct=True)
    F["wday"] = pd.to_datetime(F.d, unit="s").dt.weekday
    for k, v in oi_feats(F, per).items():
        F[k] = v
    for k, v in events(F, per).items():
        F[k] = v
    for k, v in outcomes(F).items():
        F[k] = v
    F = F[~F.s.isin(["BTC", "ETH"])].drop(columns=["c", "qv7"]).reset_index(drop=True)
    F["per"] = per
    F.to_pickle(f"s219_feat_{per}.pkl")
    print(per, F.shape, "монет", F.s.nunique(), "| заполнено:", F.notna().mean().round(2).to_dict(), flush=True)


def join():
    F = pd.concat([pd.read_pickle(f"s219_feat_{p}.pkl") for p in ("2020–2022", "2022–2024", "2024–2026")], ignore_index=True)
    F = F.drop(columns=["per", "d"])
    F.to_pickle("s219_feat.pkl")
    print("s219_feat.pkl:", F.shape)


if __name__ == "__main__":
    join() if sys.argv[1] == "join" else build(sys.argv[1])
