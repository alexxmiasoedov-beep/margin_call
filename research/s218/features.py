"""s218 — новые измерения к наблюдениям s216 (метод — ВЫВОДЫ.md, записан до расчёта, коммит abc2b8e). Только данные до T.
Итог — s218_feat.pkl в папке данных. Запуск из /home/user/mc_data: python3 <repo>/research/s218/features.py"""
import datetime
import json
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s216", "s171", "s187"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from features import coin_of, live, OUTS  # noqa: E402  (s216)

H, DAY = 3600, 86400


def spot_key(s, S):
    if s in S:
        return s
    c = coin_of(s)
    return c if c in S else None


def window(t, T, a, b):
    """Индексы строк ряда t (отсортирован) в [T − a, T − b)."""
    return int(np.searchsorted(t, T - a, "left")), int(np.searchsorted(t, T - b, "left"))


def spot(F):
    S = pickle.load(open("s23/spot1h.pkl", "rb"))       # монета → [начало часа, оборот, покупки тейкеров, сделок, цена]
    out = {k: np.full(len(F), np.nan) for k in ("sp24", "sptb4", "spx")}
    for s, idx in F.groupby("s").groups.items():
        k = spot_key(s, S)
        if k is None:
            continue
        a = S[k]; t = a[:, 0].astype(np.int64); cq = np.r_[0.0, np.cumsum(a[:, 1])]; cb = np.r_[0.0, np.cumsum(a[:, 2])]
        for j in F.index.get_indexer(idx):
            T = int(F["T"].iat[j]); q24 = F.qv24.iat[j]
            i0, i1 = window(t, T, DAY, 0); sq = cq[i1] - cq[i0]
            if i1 - i0 >= 20 and np.isfinite(q24):
                out["sp24"][j] = sq / (sq + q24) if sq + q24 > 0 else np.nan
                k0, _ = window(t, T, 7 * DAY, 0)
                s7 = (cq[i1] - cq[k0]) / 7
                out["spx"][j] = sq / s7 if s7 > 0 else np.nan
            i0, i1 = window(t, T, 4 * H, 0)
            q4 = cq[i1] - cq[i0]
            if i1 - i0 >= 3 and q4 > 0:
                out["sptb4"][j] = (cb[i1] - cb[i0]) / q4
    return out


def korea(F):
    P = pickle.load(open("s15/kr_panel.pkl", "rb"))     # фьючерс → часы: T (начало часа), kr, bin, prem, …
    out = {k: np.full(len(F), np.nan) for k in ("kr24", "krx", "kprem")}
    for s, idx in F.groupby("s").groups.items():
        g = P.get(s)
        if g is None or not len(g):
            continue
        t = g["T"].to_numpy(np.int64); kr = np.r_[0.0, np.cumsum(g.kr.fillna(0).to_numpy())]
        bn = np.r_[0.0, np.cumsum(g["bin"].fillna(0).to_numpy())]; pr = g.prem.to_numpy(float)
        for j in F.index.get_indexer(idx):
            T = int(F["T"].iat[j])
            i0, i1 = window(t, T, DAY, H - 1)                # часы с началом в [T − 24 ч, T − 1 ч]
            if i1 - i0 < 12:
                continue
            k24, b24 = kr[i1] - kr[i0], bn[i1] - bn[i0]
            out["kr24"][j] = k24 / (k24 + b24) if k24 + b24 > 0 else np.nan
            k0, _ = window(t, T, 7 * DAY, H - 1)
            k7 = (kr[i1] - kr[k0]) / 7
            out["krx"][j] = k24 / k7 if k7 > 0 else np.nan
            if t[i1 - 1] == T - H:
                out["kprem"][j] = pr[i1 - 1]
    return out


def premium(F):
    P = pickle.load(open("s12/prem.pkl", "rb"))         # фьючерс → (время открытия 15-мин свечи, премия к индексу)
    out = {k: np.full(len(F), np.nan) for k in ("pr1", "pr24")}
    for s, idx in F.groupby("s").groups.items():
        if s not in P:
            continue
        t, v = P[s]; t = np.asarray(t, np.int64) + 900; v = np.asarray(v, float)
        for j in F.index.get_indexer(idx):
            T = int(F["T"].iat[j]); i = int(np.searchsorted(t, T, "right"))
            if i >= 96:
                out["pr1"][j] = float(np.nanmean(v[i - 4:i])); out["pr24"][j] = float(np.nanmean(v[i - 96:i]))
    return out


def liquidations(F):
    L = {"Long": {}, "Short": {}}
    for ln in open("s72/liq.jsonl"):
        x = json.loads(ln)
        m = re.search(r"#(\S+) Liquidated (Long|Short): \$([\d.]+)([KMB]?)", x[2])
        if m:
            L[m.group(2)].setdefault(m.group(1), []).append((pd.Timestamp(x[1]).timestamp(),
                                                             float(m.group(3)) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(4)]))
    out = {}
    for side, nm in (("Long", "lqL"), ("Short", "lqS")):
        D = {s: np.array(sorted(v)) for s, v in L[side].items()}
        col = np.full(len(F), np.nan)
        for j, (s, T, q) in enumerate(zip(F.s, F["T"], F.qv24)):
            a = D.get(s)
            v = float(a[(a[:, 0] > T - DAY) & (a[:, 0] <= T), 1].sum()) if a is not None else 0.0
            col[j] = v / q if q and np.isfinite(q) and q > 0 else np.nan
        out[nm] = col
    return out


def events(F):
    """Разлоки 🔑⁺ впереди; заводы на Binance и другие биржи; выводы с Binance на кошельки (≥ 0,5% обращения, 72 ч)."""
    U = pd.concat([pd.read_pickle(f"s142_{p}.pkl") for p in ("2022–2024", "2024–2026")])
    UT = {s: (np.asarray(g["T"], np.int64)[np.argsort(g["T"].to_numpy())], g.share.to_numpy()[np.argsort(g["T"].to_numpy())])
          for s, g in U.groupby("s")}
    X = pd.read_pickle("s195_deposits.pkl")[["perp", "t", "frac", "exch"]]
    X = X[X.perp.notna() & (X.frac >= 0.005)]
    DB = {s: (g.t.to_numpy(np.int64)[np.argsort(g.t.to_numpy())], g.frac.to_numpy()[np.argsort(g.t.to_numpy())])
          for s, g in X[X.exch == "Binance"].groupby("perp")}
    DO = {s: np.sort(g.t.to_numpy(np.int64)) for s, g in X[X.exch != "Binance"].groupby("perp")}
    W = pd.read_pickle("s207_withdrawals.pkl")[["perp", "t", "frac", "kind"]]
    W = W[W.perp.notna() & (W.frac >= 0.005) & (W.kind == "wallet")]
    DW = {s: np.sort(g.t.to_numpy(np.int64)) for s, g in W.groupby("perp")}
    out = {k: np.full(len(F), np.nan) for k in ("unl", "unls", "dep", "depf", "depo", "wdr")}
    for j, (s, T) in enumerate(zip(F.s, F["T"])):
        T = int(T)
        u = UT.get(s)
        out["unl"][j], out["unls"][j] = 99.0, 0.0
        if u is not None:
            k = int(np.searchsorted(u[0], T, "right"))
            if k < len(u[0]) and u[0][k] <= T + 30 * DAY:
                out["unl"][j] = (u[0][k] - T) / DAY; out["unls"][j] = u[1][k]
        d = DB.get(s)
        if d is not None:
            i0, i1 = np.searchsorted(d[0], T - 3 * DAY, "right"), np.searchsorted(d[0], T, "right")
            out["dep"][j] = i1 - i0; out["depf"][j] = float(d[1][i0:i1].max()) if i1 > i0 else 0.0
        else:
            out["dep"][j] = 0.0; out["depf"][j] = 0.0
        for nm, M in (("depo", DO), ("wdr", DW)):
            a = M.get(s)
            out[nm][j] = (np.searchsorted(a, T, "right") - np.searchsorted(a, T - 3 * DAY, "right")) if a is not None else 0.0
    return out


def chng(F):
    R = pd.read_pickle("s41/rows.pkl")[["c", "t", "chng"]]
    CH = {c: (g.t.to_numpy(float), g.chng.to_numpy(float)) for c, g in R.groupby("c")}
    col = np.full(len(F), np.nan)
    t_first = R.t.min()
    for j, (s, T) in enumerate(zip(F.s, F["T"])):
        if T < t_first + 6 * H:
            continue
        c = s if s in CH else coin_of(s)
        if c not in CH:
            col[j] = 0.0; continue
        t, v = CH[c]; i0, i1 = np.searchsorted(t, T - 6 * H, "right"), np.searchsorted(t, T, "right")
        col[j] = float(np.nanmax(v[i0:i1])) if i1 > i0 else 0.0
    return col


def main():
    F = pd.read_pickle("s216_feat.pkl").sort_values(["T", "s"]).reset_index(drop=True)
    for fn in (spot, korea, premium, liquidations, events):
        for k, v in fn(F).items():
            F[k] = v
        print(fn.__name__, "готово", flush=True)
    F["chng"] = chng(F)
    lo = {s: live(s)[0] for s in F.s.unique()}
    F["age"] = [(T - lo[s]) / DAY if np.isfinite(lo[s]) else np.nan for s, T in zip(F.s, F["T"])]
    F["mcap"] = F.bor / F.bmc.where(F.bmc > 0)
    F["oimc"] = F.oiq * F.qv24 / F.mcap
    F["hour"] = (F["T"] % DAY) // H
    F["wday"] = pd.to_datetime(F["T"], unit="s").dt.weekday
    cols = [c for c in F.columns if c not in OUTS] + list(OUTS)          # исходы — в конце
    F = F[cols]
    F.to_pickle("s218_feat.pkl")
    new = ["sp24", "sptb4", "spx", "kr24", "krx", "kprem", "pr1", "pr24", "lqL", "lqS", "unl", "unls", "dep", "depf", "depo",
           "wdr", "chng", "age", "mcap", "oimc", "hour", "wday"]
    print("готово:", F.shape, "\nзаполнено новых:", F[new].notna().mean().round(2).to_dict(), flush=True)
    print("медианы:", F[new].median().round(4).to_dict(), flush=True)


if __name__ == "__main__":
    main()
