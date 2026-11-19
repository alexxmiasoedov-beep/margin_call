"""s198 — «ширина заводов» (Г7 s173): ≥ 2 разных отправителей заводят монету на биржи за 72 ч → шорт перпа 24 ч, стоп 25%.
Запись до расчёта — ВЫВОДЫ.md (коммит ad16ffe).

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F, как в s117):
  python3 run.py 2024–2026 main
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024 main     (и s167)
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022 main   (и s167)
  python3 run.py report
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
W, CD = 72 * 3600, 7 * DAY

# вариант → (источник строк, только Binance, «чистые» отправители, порог отправителей; "one" — ровно один)
VARS = {
    "wide": (False, False, 2),
    "one": (False, False, "one"),
    "wide3": (False, False, 3),
    "bin": (True, False, 2),
    "bin1": (True, False, "one"),
    "clean": (False, True, 2),
}
NAMES = {
    "wide": "основной: ≥ 2 отправителей, все биржи",
    "one": "контроль: один отправитель",
    "wide3": "≥ 3 отправителей",
    "bin": "≥ 2 отправителей, только Binance",
    "bin1": "один отправитель, только Binance",
    "clean": "≥ 2 «чистых» отправителей (from_exch = False)",
}


def rows(src):
    if src == "main":
        X = pd.read_pickle(f"{OUT}/s160_events.pkl")
    else:
        X = pd.read_pickle(f"{OUT}/s167_events.pkl")
    X = X[X.perp.notna() & (X.frac >= 0.005)].copy()
    X["t"] = X.t.astype(np.int64)
    return X.sort_values("t")


def events(X, binance, clean, k):
    if binance:
        X = X[X.exch == "Binance"]
    if clean:
        X = X[X.from_exch == False]  # noqa: E712
    out = []
    for perp, g in X.groupby("perp"):
        tt = g.t.values
        ff = g.frm.values
        last = -10 ** 12
        for i in range(len(g)):
            t = tt[i]
            j0 = np.searchsorted(tt, t - W, "right")
            j1 = np.searchsorted(tt, t, "right")                 # весь блок t целиком
            ns = len(set(ff[j0:j1]))
            hit = (ns == 1) if k == "one" else (ns >= k)
            if hit and t - last >= CD:
                out.append((perp, int(t), ns))
                last = t
    return pd.DataFrame(out, columns=["perp", "tb", "ns"])


def run(per, src):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    X = rows(src)
    vars_ = VARS if src == "main" else {k: VARS[k] for k in ("wide", "one")}
    res = []
    for v, (binance, clean, k) in vars_.items():
        E = events(X, binance, clean, k)
        E["entry"] = (np.ceil((E.tb + 900) / 900) * 900).astype(np.int64)
        E = E[(E.entry >= t0) & (E.entry < t1)]
        for s, g in E.groupby("perp"):
            if s not in K:
                continue
            t = K[s]["t"].astype(np.int64)
            c = K[s]["c"].astype(float)
            lo, _ = FB.live(s)
            g = g.sort_values("entry").copy()
            st = g.entry.values - 900
            I = np.searchsorted(t, st)
            ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
            ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
            g, I = g[ok].copy(), I[ok]
            if not len(g):
                continue
            for hold, sl, suf in ((24, 0.25, ""), (168, 0.50, "7")):
                okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
                g["net" + suf] = np.where(okt, net, np.nan)
                g["stop" + suf] = np.where(okt, stp, False)
                g["hed" + suf] = g["net" + suf].values + FB.alt_mv(t[I] + 900, tend)
                g["pl" + suf] = FB.placebo(s, I, sl, hold, -1)
            g["r24"] = c[I] / c[I - 96] - 1
            g["t"] = g.entry
            g["var"] = v
            res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s198_{src}_{per}.pkl")
    print(per, src, R[R.net.notna()].groupby("var").size().to_dict(), flush=True)


def view(R, v, suf=""):
    x = R[(R["var"] == v)].copy()
    x["net"], x["hed"], x["pl"], x["stop"] = x["net" + suf], x["hed" + suf], x["pl" + suf], x["stop" + suf]
    x = x[x.net.notna()]
    x["why"] = np.where(x.stop.astype(bool), "стоп", "время")
    return x


def report():
    import common182 as C  # noqa: E402
    print("s198 — «ширина заводов»: ≥ 2 разных отправителей за 72 ч → шорт перпа (24 ч стоп 25%; 7 сут стоп 50%)\n")
    pn, ph, pdl, pb = [], [], [], []
    for per in C.PER:
        R = pd.read_pickle(f"{OUT}/s198_main_{per}.pkl")
        print(f"== {per} ==")
        for v in VARS:
            print(f"  {NAMES[v]}: {C.line(view(R, v), per)}")
        print(f"  основной, 7 сут: {C.line(view(R, 'wide', '7'), per)}")
        x = view(R, "wide")
        xc = x[x.r24.abs() <= 0.05]
        print(f"  основной, спокойный рынок ±5%: {C.line(xc, per)}")
        for a, b, name in (("wide", "one", "ширина − один кит"), ("bin", "bin1", "то же, только Binance")):
            y = pd.concat([view(R, a), view(R, b)])
            d, se = C.diff(y.net, y["var"] == a, y.t)
            print(f"  Δ {name}: {d:+.2%} (t {d / se:+.1f})")
            if a == "wide":
                pdl.append((d, se, len(y)))
            else:
                pb.append((d, se, len(y)))
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / C.months(per) >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Три периода, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
    print("  по периодам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " +
          " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Δ ширина − один кит вместе: {d:+.2%} (t {t:+.1f})")
    d, t = C.combine(pb)
    print(f"Δ ширина − один кит, только Binance, вместе: {d:+.2%} (t {t:+.1f})")
    print("\nНезависимые токены s167:")
    ps = []
    for per in ("2020–2022", "2022–2024"):
        p = f"{OUT}/s198_s167_{per}.pkl"
        if not os.path.exists(p):
            continue
        R = pd.read_pickle(p)
        x = view(R, "wide")
        print(f"  {per} основной: {C.line(x, per)}")
        print(f"  {per} один отправитель: {C.line(view(R, 'one'), per)}")
        m, t, n = C.ct(x.net, x.t)
        ps.append((m, abs(m / t) if t else np.nan, n))
    if ps:
        m, t = C.combine(ps)
        print(f"  вместе: {m:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "main")
