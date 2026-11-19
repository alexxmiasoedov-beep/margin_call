"""s189 — ребаланс токенов с плечом на одном периоде (гипотезы — ВЫВОДЫ.md, записаны до расчёта): строки панели s186
(монета × сутки × якорь) с |r24| ≥ 10% — шорт после роста, лонг после падения на закрытии свечи [T, T + 15 мин),
выходы 1 / 4 / 24 ч, стоп 15%; «лестница» Г3 — первое пересечение порога режима Gate в окне 24 ч от якоря, вход на
закрытии следующей свечи, шорт 4 ч. Флаги токенов Gate, FTX, BLVT; доза потока (s186 hyp186.gate_mult, ftx_mult);
хедж индексом альтов и плацебо 45/90/135 сут на 4 ч.
Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s189/run.py <период>  → s189_<период>.pkl"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s186", "study"))
sys.path.insert(0, os.path.join(HERE, "..", "s183", "study"))
import fastbt as FB  # noqa: E402  (тянет s15/common: K по MC_K)
import hyp186 as H6  # noqa: E402
import common183 as C3  # noqa: E402

DAY, OUT = 86400, "/home/user/mc_data"
T_SW = int(pd.Timestamp("2025-04-01", tz="UTC").timestamp()) + 16 * 3600
T_BAND = int(pd.Timestamp("2025-07-17", tz="UTC").timestamp()) + 16 * 3600


def best_map(K):
    bad = C3.bad_set()
    best = {}
    for sym, a in K.items():
        b = C3.base(sym)
        if sym in bad or b in bad or b in ("BTC", "ETH"):
            continue
        q = float(np.nansum(np.asarray(a["qv"], np.float64)))
        if q > 0 and (b not in best or q > best[b][1]):
            best[b] = (sym, q)
    return {b: v[0] for b, v in best.items()}


def entry_idx(t, starts):
    j = np.searchsorted(t, starts)
    ok = (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == starts)
    return np.where(ok, j, -1)


def run(per):
    K = FB.K
    cd = pickle.load(open(f"{OUT}/s186/cd_{per}.pkl", "rb"))["cd"]
    UU = pickle.load(open(f"{OUT}/s186/lt_universe.pkl", "rb"))
    U, G = UU["U"], UU["G"]
    gdaily = pickle.load(open(f"{OUT}/s186/gate_daily.pkl", "rb"))
    Mf = pickle.load(open(f"{OUT}/s186/ftx_mult.pkl", "rb"))
    iv_g, iv_f, iv_b = H6.intervals(U, "gate"), H6.intervals(U, "ftx", levs=[3.0, -3.0]), H6.intervals(U, "binance")
    ftx_coins = set(U[(U.ex == "ftx") & U.lev.isin([3.0, -3.0])].und)
    bm = best_map(K)
    # строки якорей с |r24| ≥ 10%
    A = cd[(cd.r24.abs() >= 0.10)].copy()
    A["kind"] = "a"
    A["T"] = A.D.values + A.H.values.astype(np.int64) * 3600
    # лестница Г3: окна от якорей 16 (событие) и 04/08/12 (ложный якорь); порог режима по началу окна
    L3 = cd[cd.H.isin([16, 4, 8, 12])].copy()
    w0 = L3.D.values + L3.H.values.astype(np.int64) * 3600 - DAY
    k = np.where(w0 >= T_BAND, L3.up_12.values, np.where(w0 >= T_SW, L3.up_6_67.values, L3.up_10.values))
    L3 = L3[k >= 0].copy(); k = k[k >= 0]
    L3["kind"] = "g3"
    L3["T"] = L3.D.values + L3.H.values.astype(np.int64) * 3600 - DAY + (k.astype(np.int64) + 1) * 900
    L3w = L3.copy(); L3w["D"] = L3w.D - DAY                      # флаг токена на начало окна
    L3["gate"] = H6.has(L3w, iv_g)
    L3 = L3[L3.gate]
    A["gate"] = H6.has(A, iv_g); A["ftx"] = H6.has(A, iv_f); A["blvt"] = H6.has(A, iv_b)
    A["ftx_coin"] = A.b.astype(str).isin(ftx_coins)
    A["phi_g"] = H6.gate_mult(A, gdaily, G) * 2.0 * A.r24 / A.v7          # K = 1 (в hyp186 K_GATE = 2)
    A["phi_f"] = H6.ftx_mult_rows(A, Mf) * A.r24 / A.q_base
    A["krw"] = H6.krw_flag(per, A)
    R = pd.concat([A, L3], ignore_index=True)
    R["sym"] = R.b.astype(str).map(bm)
    R = R[R.sym.notna()].copy()
    R["side"] = np.where((R.kind == "a") & (R.r24 <= -0.10), 1, -1)
    for c in ("net1", "net4", "net24", "hed4", "pl4"):
        R[c] = np.nan
    R["stop4"] = False
    for sym, g in R.groupby("sym"):
        if sym not in K:
            continue
        t = K[sym]["t"].astype(np.int64)
        lo, hi = FB.live(sym)
        if not np.isfinite(lo):
            continue
        I = entry_idx(t, g["T"].values.astype(np.int64))
        good = (I >= 96) & (g["T"].values >= lo + 30 * DAY)
        for side in (-1, 1):
            m = good & (g.side.values == side)
            if not m.any():
                continue
            ix = g.index[m]; Ii = I[m]
            for h, col in ((1, "net1"), (4, "net4"), (24, "net24")):
                ok, net, stp, bars, tend = FB.trades(sym, Ii, 0.15, h, side)
                R.loc[ix[ok], col] = net[ok]
                if h == 4:
                    R.loc[ix[ok], "stop4"] = stp[ok]
                    mv = FB.alt_mv(t[Ii[ok]] + 900, tend[ok])
                    R.loc[ix[ok], "hed4"] = net[ok] - side * mv        # шорт + лонг индекса, лонг + шорт индекса
            R.loc[ix, "pl4"] = FB.placebo(sym, Ii, 0.15, 4, side)
    keep = ["kind", "b", "sym", "D", "H", "T", "r24", "gate", "ftx", "blvt", "ftx_coin", "phi_g", "phi_f", "krw", "side",
            "net1", "net4", "net24", "stop4", "hed4", "pl4"]
    R = R[keep]
    R["per"] = per
    R.to_pickle(f"{OUT}/s189_{per}.pkl")
    print(per, "строк", len(R), "со сделкой 4 ч", int(R.net4.notna().sum()),
          "| Г1 событий", int(((R.kind == "a") & (R.H == 16) & R.gate & (R.side < 0) & R.net4.notna()).sum()),
          "| Г2", int(((R.kind == "a") & (R.H == 0) & R.ftx & (R.side < 0) & R.net4.notna()).sum()),
          "| Г3", int(((R.kind == "g3") & (R.H == 16) & R.net4.notna()).sum()), flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
