"""s199 — крупный завод на другие биржи (не Binance) в спокойном рынке → шорт перпа 24 ч, стоп 25%.
Запись до расчёта — ВЫВОДЫ.md (коммит b552457).

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
GAP = 48 * 3600


def rows(src):
    X = pd.read_pickle(f"{OUT}/s160_events.pkl" if src == "main" else f"{OUT}/s167_events.pkl")
    X = X[X.perp.notna() & (X.frac >= 0.005)].copy()
    X["t"] = X.t.astype(np.int64)
    return X.sort_values("t")


def events(X):
    """Первый за 48 ч завод монеты на другую биржу; на Binance за 48 ч до него заводов не было."""
    B = X[X.exch == "Binance"]
    O = X[X.exch != "Binance"]
    bt = {p: np.sort(g.t.values) for p, g in B.groupby("perp")}
    out = []
    for perp, g in O.groupby("perp"):
        tt = g.t.values
        b = bt.get(perp, np.zeros(0, np.int64))
        prev = -10 ** 12
        for i in range(len(g)):
            t = tt[i]
            if t == prev:                                   # тот же блок — то же событие
                continue
            fresh = t - prev >= GAP
            prev = t
            j = np.searchsorted(b, t, "right")
            nob = not (j > 0 and b[j - 1] > t - GAP)
            if fresh and nob:
                r = g.iloc[i]
                out.append((perp, int(t), r.exch, float(r.frac)))
    return pd.DataFrame(out, columns=["perp", "tb", "exch", "frac"])


def run(per, src):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events(rows(src))
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
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            g["net" + suf] = np.where(okt, net, np.nan)
            g["stop" + suf] = np.where(okt, stp, False)
            g["hed" + suf] = g["net" + suf].values + FB.alt_mv(t[I] + 900, tend)
            g["pl" + suf] = FB.placebo(s, I, sl, hold, -1)
        g["r24"] = c[I] / c[I - 96] - 1
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s199_{src}_{per}.pkl")
    calm = R[R.net.notna() & (R.r24.abs() <= 0.05)]
    print(per, src, "сделок", int(R.net.notna().sum()), "в спокойном рынке", len(calm), flush=True)


def view(R, mask, suf=""):
    x = R[mask].copy()
    x["net"], x["hed"], x["pl"], x["stop"] = x["net" + suf], x["hed" + suf], x["pl" + suf], x["stop" + suf]
    x = x[x.net.notna()]
    x["why"] = np.where(x.stop.astype(bool), "стоп", "время")
    return x


def report():
    import common182 as C  # noqa: E402
    print("s199 — завод ≥ 0,5% обращения на другую биржу (не Binance) в спокойном рынке → шорт перпа 24 ч, стоп 25%\n")
    pn, ph = [], []
    for per in C.PER:
        R = pd.read_pickle(f"{OUT}/s199_main_{per}.pkl")
        calm = R.r24.abs() <= 0.05
        x = view(R, calm)
        print(f"== {per} ==")
        print(f"  основной (спокойный рынок): {C.line(x, per)}")
        print(f"  без фильтра рынка: {C.line(view(R, R.r24.notna()), per)}")
        print(f"  Coinbase: {C.line(view(R, calm & (R.exch == 'Coinbase')), per)}")
        print(f"  остальные биржи: {C.line(view(R, calm & (R.exch != 'Coinbase')), per)}")
        print(f"  перевод ≥ 1%: {C.line(view(R, calm & (R.frac >= 0.01)), per)}")
        print(f"  7 сут, стоп 50%: {C.line(view(R, calm, '7'), per)}")
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
    print("\nНезависимые токены s167:")
    ps = []
    for per in ("2020–2022", "2022–2024"):
        p = f"{OUT}/s199_s167_{per}.pkl"
        if not os.path.exists(p):
            continue
        R = pd.read_pickle(p)
        x = view(R, R.r24.abs() <= 0.05)
        print(f"  {per} основной: {C.line(x, per)}")
        print(f"  {per} без фильтра рынка: {C.line(view(R, R.r24.notna()), per)}")
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
