"""s186 — след ребаланса FTX (00:02 UTC) в обороте перпа Binance по дозе потока (2020–2022): медиана
(оборот свечи [T, T+15 мин) / её медиана за 14 сут) у монет с BULL/BEAR при |r24| ≥ 5% по оценке потока
φ = M·|r24| / оборот свечи (M — множитель из ftx_supply, NAV = выпуск ERC-20 × цена CMC), в 00 UTC против
04/08/12/16/20 UTC с тем же расчётом φ («ложный ребаланс»). Только оборот, без цены и знака.
Лог — ftx_foot.log. Доходы не считаются."""
import pickle

import numpy as np

import common186 as C

L = C.Log("ftx_foot")


def intervals(U, ex, levs):
    out = {}
    for r in U[(U.ex == ex) & U.lev.isin(levs)].itertuples():
        out.setdefault(r.und, []).append((r.t0, r.t1))
    return out


def has(cd, iv):
    T = cd.D.values + cd.H.values.astype(np.int64) * 3600
    m = np.zeros(len(cd), bool)
    bb = cd.b.astype(str).values
    for b, lst in iv.items():
        sel = np.flatnonzero(bb == b)
        for t0, t1 in lst:
            m[sel] |= (T[sel] >= t0) & (T[sel] <= t1)
    return m


def mult_rows(cd, M):
    out = np.full(len(cd), np.nan)
    bb = cd.b.astype(str).values
    for u in M.columns:
        sel = np.flatnonzero(bb == u)
        if len(sel):
            out[sel] = M[u].reindex(cd.D.values[sel] - C.DAY).values
    return out


def main():
    UU = pickle.load(open(f"{C.OUT}/lt_universe.pkl", "rb"))
    M = pickle.load(open(f"{C.OUT}/ftx_mult.pkl", "rb"))
    iv = intervals(UU["U"], "ftx", [3.0, -3.0])
    cd = pickle.load(open(f"{C.OUT}/cd_2020–2022.pkl", "rb"))["cd"]
    cd = cd[has(cd, iv)].copy()
    cd["M"] = mult_rows(cd, M)
    cd["ratio"] = cd.q_slot / cd.q_base
    cd["phi"] = cd.M * cd.r24.abs() / cd.q_base
    x = cd[(cd.r24.abs() >= 0.05) & np.isfinite(cd.ratio) & np.isfinite(cd.phi)]
    L(f"монето-суток FTX с |r24| ≥ 5%: {len(x)} (по якорям {x.groupby('H').size().to_dict()})")
    L("медиана оборота свечи после якоря к её норме, по оценке потока к обороту свечи (φ):")
    for lo, hi in ((0, 0.5), (0.5, 2.0), (2.0, 1e9)):
        a = x[(x.H == 0) & (x.phi >= lo) & (x.phi < hi)]
        b = x[(x.H != 0) & (x.phi >= lo) & (x.phi < hi)]
        L(f"  φ {lo:g}–{hi:g}: 00 UTC {a.ratio.median():.2f} (n {len(a)}), другие якоря {b.ratio.median():.2f} "
          f"(n {len(b)}); предыдущая свеча: 00 UTC {(a.q_pre / a.q_pre_base).median():.2f}, другие "
          f"{(b.q_pre / b.q_pre_base).median():.2f}")
    for sgn, name in ((1, "рост"), (-1, "падение")):
        a = x[(x.H == 0) & (np.sign(x.r24) == sgn)]
        b = x[(x.H != 0) & (np.sign(x.r24) == sgn)]
        L(f"  {name} ≥ 5%: 00 UTC {a.ratio.median():.2f} (n {len(a)}), другие якоря {b.ratio.median():.2f}")


if __name__ == "__main__":
    main()
