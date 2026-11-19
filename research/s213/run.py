"""s213 — 🐋ᵛ: доза λ = стоимость завода / средний суточный оборот перпа за 7 сут внутри событий 🐋 (одиночный завод
на Binance ≥ 0,5% обращения, первый за 48 ч, спокойный рынок ±5%) → шорт 24 ч, стоп 25%. Запись до расчёта — ВЫВОДЫ.md
(коммит debbd81).

Запуск из /home/user/mc_data:
  python3 run.py deposits                      — сбор s167 с суммами (один раз)
  python3 run.py 2024–2026 main
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024 main     (и s167)
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022 main   (и s167)
  python3 run.py report
"""
import glob
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
GAP, BIG = 48 * 3600, 0.005


def build_s167():
    sys.path.insert(0, os.path.join(HERE, "..", "s167"))
    import test as S  # noqa: E402
    E6 = S.ev_module()
    CEX = E6.CEX
    TK = json.load(open(f"{OUT}/s167/toks.json"))
    rows = []
    for p in sorted(glob.glob(f"{OUT}/s167/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    lab = {a: " ".join(v) for a, v in CEX.items()}
    X = X[~X.to.map(lambda a: bool(E6.CUST.search(lab.get(a, ""))))]
    X = X[~X.frm.isin(CEX.keys()) & (X.frm != "0x" + "0" * 40)].copy()
    X = X[X.to.map(lambda a: CEX[a][0]) == "Binance"].copy()
    bt = json.load(open(f"{OUT}/s160/cache_blocktime.json"))
    A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    X["t"] = np.interp(X.block, A[:, 0], A[:, 1]).astype(np.int64)
    C = S.circ_table(TK)
    fr = np.full(len(X), np.nan)
    for tok, idx in X.groupby("tok").groups.items():
        s = C.get(tok)
        if s is None:
            continue
        d = pd.to_datetime(X.loc[idx, "t"], unit="s").dt.normalize().values
        k = s.index.values.searchsorted(d, "right") - 1
        c = np.where(k >= 0, s.values[np.maximum(k, 0)], np.nan)
        fr[X.index.get_indexer(idx)] = X.loc[idx, "amt"].values / np.where(c > 0, c, np.nan)
    X["frac"] = fr
    X["perp"] = X.tok.map(lambda t: TK[t]["perp"])
    X = X[(X.frac >= BIG) & X.perp.notna()]
    X[["perp", "t", "frm", "frac", "amt", "block", "li"]].reset_index(drop=True).to_pickle(f"{OUT}/s213_dep_s167.pkl")
    print("s167: заводов на Binance ≥ 0,5%:", len(X), flush=True)


def events(src):
    if src == "main":
        X = pd.read_pickle(f"{OUT}/s195_deposits.pkl")
        X = X[(X.exch == "Binance") & X.perp.notna() & (X.frac >= BIG)]
    else:
        X = pd.read_pickle(f"{OUT}/s213_dep_s167.pkl")
    X = X.assign(t=X.t.astype(np.int64)).sort_values(["t", "block", "li"])
    out = []
    for perp, g in X.groupby("perp"):
        last = -10 ** 12
        for r in g.itertuples():
            if r.t - last >= GAP:
                out.append((perp, int(r.t), float(r.frac), float(r.amt)))
                last = r.t
    return pd.DataFrame(out, columns=["perp", "tb", "frac", "amt"])


def mult(s):
    for p, m in (("1000000", 1e6), ("1M", 1e6), ("10000", 1e4), ("1000", 1e3)):
        if s.startswith(p) and len(s) > len(p) and not s[len(p)].isdigit():
            return m
    return 1.0


def run(per, src):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events(src)
    E["entry"] = (np.ceil((E.tb + 900) / 900) * 900).astype(np.int64)
    E = E[(E.entry >= t0) & (E.entry < t1)]
    res = []
    for s, g in E.groupby("perp"):
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        c = K[s]["c"].astype(float)
        qv = K[s]["qv"].astype(float)
        lo, _ = FB.live(s)
        g = g.sort_values("entry").copy()
        st = g.entry.values - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 672)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        g, I = g[ok].copy(), I[ok]
        if not len(g):
            continue
        g["r24"] = c[I] / c[I - 96] - 1
        cs = np.r_[0.0, np.cumsum(qv)]
        vbar = (cs[I] - cs[I - 672]) / 7.0                              # средний суточный оборот за 7 сут до входа
        g["lam"] = g.amt.values * c[I] / mult(s) / np.where(vbar > 0, vbar, np.nan)
        okt, net, stp, bars, tend = FB.trades(s, I, 0.25, 24, -1)
        g["net"] = np.where(okt, net, np.nan)
        g["stop"] = np.where(okt, stp, False)
        g["hed"] = g.net.values + FB.alt_mv(t[I] + 900, tend)
        g["pl"] = FB.placebo(s, I, 0.25, 24, -1)
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s213_{src}_{per}.pkl")
    x = R[R.net.notna() & (R.r24.abs() <= 0.05)]
    print(per, src, "событий 🐋:", len(x), "λ ≥ 0,1:", int((x.lam >= 0.1).sum()), "медиана λ:", round(float(x.lam.median()), 3),
          flush=True)


def wk(t):
    return (np.asarray(t, np.int64) // (7 * DAY)) * (7 * DAY)


def line(C, x, per):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = C.ct(x.net, x.t)
    _, tw, _ = C.ct(x.net, wk(x.t))
    mh, th, _ = C.ct(x.hed, x.t)
    _, thw, _ = C.ct(x.hed, wk(x.t))
    md, td, _ = C.ct(x.net - x.pl, x.t)
    cut = C.ts(C.PER[per][2])
    return (f"n={n:4d} ({n / C.months(per):4.1f}/мес) {m:+.2%} (t {t:+.1f}, по неделям {tw:+.1f}) | половины "
            f"{x[x.t < cut].net.mean():+.2%} / {x[x.t >= cut].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}, {thw:+.1f}) | "
            f"сверх плацебо {md:+.2%} (t {td:+.1f}) | стопов {x.stop.mean():.0%}")


def report():
    import common182 as C  # noqa: E402
    print("s213 — 🐋ᵛ: доза λ = стоимость завода / оборот перпа за сутки внутри событий 🐋 (шорт 24 ч, стоп 25%)\n")
    pn, ph, pdl = [], [], []
    for per in C.PER:
        R = pd.read_pickle(f"{OUT}/s213_main_{per}.pkl")
        R = R[R.net.notna() & (R.r24.abs() <= 0.05) & R.lam.notna()]
        print(f"== {per} ==   λ: медиана {R.lam.median():.3f}, p75 {R.lam.quantile(.75):.3f}, p90 {R.lam.quantile(.9):.3f}")
        print(f"  все 🐋: {line(C, R, per)}")
        for th in (0.05, 0.1, 0.25):
            print(f"  λ ≥ {th}: {line(C, R[R.lam >= th], per)}")
        print(f"  λ < 0,1: {line(C, R[R.lam < 0.1], per)}")
        x = R[R.lam >= 0.1]
        d, se = C.diff(R.net, R.lam >= 0.1, R.t)
        pdl.append((d, se, len(R)))
        print(f"  Δ λ ≥ 0,1 − λ < 0,1: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        _, tw, _ = C.ct(x.net, wk(x.t))
        mh, th, _ = C.ct(x.hed, wk(x.t))
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / C.months(per) >= 20), ("t ≥ 3 по суткам и неделям", t >= 3 and tw >= 3),
                    ("обе половины > 0", h1 > 0 and h2 > 0), ("сверх плацебо > 0", (x.net - x.pl).mean() > 0),
                    ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Три периода, λ ≥ 0,1: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t по неделям {th:+.1f})")
    print("  по периодам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " + " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Доза Δ λ ≥ 0,1 − λ < 0,1 вместе: {d:+.2%} (t {t:+.1f})")
    print("\nНезависимые токены s167:")
    ps = []
    for per in ("2020–2022", "2022–2024"):
        p = f"{OUT}/s213_s167_{per}.pkl"
        if not os.path.exists(p):
            continue
        R = pd.read_pickle(p)
        R = R[R.net.notna() & (R.r24.abs() <= 0.05) & R.lam.notna()]
        x = R[R.lam >= 0.1]
        print(f"  {per}: все 🐋 {line(C, R, per)}")
        print(f"  {per}: λ ≥ 0,1 {line(C, x, per)}")
        m, t, n = C.ct(x.net, x.t)
        ps.append((m, abs(m / t) if t else np.nan, n))
    if ps:
        m, t = C.combine(ps)
        print(f"  вместе λ ≥ 0,1: {m:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    elif sys.argv[1] == "deposits":
        build_s167()
    else:
        run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "main")
