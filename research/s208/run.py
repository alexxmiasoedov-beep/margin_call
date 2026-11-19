"""s208 — зеркало 🐋: крупный вывод с Binance (≥ 0,5% обращения на небиржевой адрес, первый за 48 ч) в спокойном рынке ±5%
→ лонг перпа 24 ч, стоп −25%. Контроль — вывод на другую биржу. Запись до расчёта — ВЫВОДЫ.md (коммит 32ed7c4).

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F, как в s117):
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 run.py 2020–2022
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
GAP, BIG = 48 * 3600, 0.005


def events():
    X = pd.read_pickle(f"{OUT}/s207_withdrawals.pkl").sort_values(["t", "block", "li"])
    out = []
    for kind in ("wallet", "exch"):
        W = X[(X.kind == kind) & (X.frac >= BIG)]
        for perp, g in W.groupby("perp"):
            last = -10 ** 12
            for r in g.itertuples():
                if r.t - last >= GAP:
                    out.append((perp, int(r.t), kind, float(r.frac), r.to, r.tok, int(r.block)))
                    last = r.t
    E = pd.DataFrame(out, columns=["perp", "tb", "kind", "frac", "to", "tok", "block"])
    # получатель впервые получает эту монету с Binance (по всему сбору ≥ 0,05%) — до события
    first = X[X.kind == "wallet"].groupby(["to", "tok"]).t.min()
    E["fresh"] = [first.get((a, k), 10 ** 12) >= t for a, k, t in zip(E.to, E.tok, E.tb)]
    return E


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events()
    E["entry"] = (np.ceil((E.tb + 900) / 900) * 900).astype(np.int64)
    E = E[(E.entry >= t0) & (E.entry < t1)]
    res = []
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
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, +1)
            g["net" + suf] = np.where(okt, net, np.nan)
            g["stop" + suf] = np.where(okt, stp, False)
            g["hed" + suf] = g["net" + suf].values - FB.alt_mv(t[I] + 900, tend)
            g["pl" + suf] = FB.placebo(s, I, sl, hold, +1)
        g["r24"] = c[I] / c[I - 96] - 1
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s208_{per}.pkl")
    calm = R.net.notna() & (R.r24.abs() <= 0.05)
    print(per, R[calm].groupby("kind").size().to_dict(), "| без фильтра рынка",
          R[R.net.notna()].groupby("kind").size().to_dict(), flush=True)


def view(R, mask, suf=""):
    x = R[mask].copy()
    x["net"], x["hed"], x["pl"], x["stop"] = x["net" + suf], x["hed" + suf], x["pl" + suf], x["stop" + suf]
    x = x[x.net.notna()]
    x["why"] = np.where(x.stop.astype(bool), "стоп", "время")
    return x


def report():
    import common182 as C  # noqa: E402
    print("s208 — зеркало 🐋: вывод ≥ 0,5% обращения с Binance на кошелёк в спокойном рынке → лонг перпа 24 ч, стоп −25%\n")
    pn, ph, pdl = [], [], []
    for per in C.PER:
        R = pd.read_pickle(f"{OUT}/s208_{per}.pkl")
        calm = R.r24.abs() <= 0.05
        w, e = R.kind == "wallet", R.kind == "exch"
        x = view(R, w & calm)
        print(f"== {per} ==")
        print(f"  основной: вывод на кошелёк, спокойный рынок: {C.line(x, per)}")
        print(f"  контроль: вывод на другую биржу: {C.line(view(R, e & calm), per)}")
        print(f"  вывод ≥ 1%: {C.line(view(R, w & calm & (R.frac >= 0.01)), per)}")
        print(f"  новый получатель: {C.line(view(R, w & calm & R.fresh), per)}")
        print(f"  повторный получатель: {C.line(view(R, w & calm & ~R.fresh), per)}")
        print(f"  без фильтра рынка: {C.line(view(R, w & R.r24.notna()), per)}")
        print(f"  7 сут, стоп −50%: {C.line(view(R, w & calm, '7'), per)}")
        y = pd.concat([x, view(R, e & calm)])
        d, se = C.diff(y.net, y.kind == "wallet", y.t)
        pdl.append((d, se, len(y)))
        print(f"  Δ кошелёк − другая биржа: {d:+.2%} (t {d / se:+.1f})")
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
    print(f"Δ кошелёк − другая биржа вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
