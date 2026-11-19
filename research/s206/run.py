"""s206 — предупреждение Bithumb «скачок цены ≥ +50% за сутки» → шорт перпа Binance 48 ч, стоп 25%; контроль — такой же рост
перпа без флага. Запись до расчёта — ВЫВОДЫ.md (коммит bfc2514).

Запуск из /home/user/mc_data:
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  python3 run.py report
"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
sys.path.insert(0, os.path.join(HERE, "..", "s205"))

DAY, OUT = 86400, "/home/user/mc_data"
S204, S206 = f"{OUT}/s204", f"{OUT}/s206"
GAP = 48 * 3600


def flags():
    """Новые эпизоды флага роста цены Bithumb (тип 01, ступени 10/20/30) и эпизоды Upbit PRICE_FLUCTUATIONS."""
    h = pd.concat([pd.read_csv(f"{S204}/{f}") for f in ("bithumb_hist.csv", "bithumb_hist_L2.csv", "bithumb_hist_L3.csv")])
    h = h.drop_duplicates(["coinType", "warningType", "warningStep", "startDateTime"])
    p = h[(h.warningType == 1) & (h.warningStep.astype(int) % 10 == 0)].copy()
    sym = {c["coinType"]: c["coinSymbol"] for c in json.load(open(f"{S204}/web/bithumb_site/intro.json"))["data"]["coinList"]}
    p["coin"] = p.coinType.map(sym)
    p = p[p.coin.notna()]
    p["ts"] = (pd.to_datetime(p.startDateTime) - pd.Timedelta(hours=9)).map(lambda d: int(d.timestamp()))
    p = p.sort_values("ts")
    keep, last = [], {}
    for r in p.itertuples():
        keep.append(r.coin not in last or r.ts - last[r.coin] > GAP)
        last[r.coin] = r.ts
    B = p[keep][["coin", "ts", "warningStep"]].rename(columns={"warningStep": "step"})
    B["ex"] = "bithumb"
    u = pd.read_csv(f"{S204}/upbit_episodes_P.csv")
    u["ts"] = pd.to_datetime(u.start_utc).map(lambda d: int(d.timestamp()))
    u = u.sort_values("ts")
    keep, last = [], {}
    for r in u.itertuples():
        keep.append(r.coin not in last or r.ts - last[r.coin] > GAP)
        last[r.coin] = r.ts
    U = u[keep][["coin", "ts", "max_level"]].rename(columns={"max_level": "step"})
    U["ex"] = "upbit"
    return pd.concat([B, U], ignore_index=True)


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    import run as R5  # noqa: E402  (s205: сопоставление тикеров и проверка ρ)
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    F = flags()
    F = F[(F.ts >= t0 - 2 * DAY) & (F.ts < t1)].copy()
    F["perp"] = [R5.perp_key(K, c) for c in F.coin]
    F = F[F.perp.notna()].copy()
    rho = {(e, c): R5.corr_check(K, e, c, s) for e, c, s in set(zip(F.ex, F.coin, F.perp))}
    F["rho"] = [rho[(e, c)] for e, c in zip(F.ex, F.coin)]
    F = F[~(F.rho < 0.5)]
    F["kind"] = "flag"
    # контроль: рост перпа ≥ +50% к цене 24 ч назад, первый за 48 ч, без флага Bithumb у монеты в ±6 ч
    fb = {s: np.sort(g.ts.values) for s, g in F[F.ex == "bithumb"].groupby("perp")}
    ctl = []
    for s in K:
        t = K[s]["t"].astype(np.int64)
        c = K[s]["c"].astype(float)
        if len(t) < 200:
            continue
        r = np.full(len(c), np.nan)
        r[96:] = c[96:] / c[:-96] - 1
        idx = np.flatnonzero(r >= 0.5)
        last = -10 ** 12
        ft = fb.get(s, np.zeros(0, np.int64))
        for i in idx:
            te = int(t[i]) + 900
            if te - last < GAP or not (t0 <= te < t1):
                continue
            last = te
            j = np.searchsorted(ft, te - 6 * 3600)
            if j < len(ft) and ft[j] <= te + 6 * 3600:
                continue
            ctl.append(("ctl", s, te - 900, "bithumb", 0))
    Cdf = pd.DataFrame(ctl, columns=["kind", "perp", "ts", "ex", "step"])
    Cdf["coin"] = Cdf.perp
    E = pd.concat([F[["kind", "perp", "ts", "ex", "step", "coin"]], Cdf], ignore_index=True)
    E["entry"] = (np.ceil((E.ts + 900) / 900) * 900).astype(np.int64)
    E = E[(E.entry >= t0) & (E.entry < t1)]
    res = []
    for (kind, ex, s), g in E.groupby(["kind", "ex", "perp"]):
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
        g["r24"] = c[I] / c[I - 96] - 1
        for hold, sl, suf in ((48, 0.25, ""), (24, 0.25, "24"), (168, 0.50, "7")):
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            g["net" + suf] = np.where(okt, net, np.nan)
            g["stop" + suf] = np.where(okt, stp, False)
            g["tend" + suf] = tend
            g["hed" + suf] = g["net" + suf].values + FB.alt_mv(t[I] + 900, tend)
            g["pl" + suf] = FB.placebo(s, I, sl, hold, -1)
        g["t"] = g.entry
        res.append(g)
    X = pd.concat(res, ignore_index=True)
    X["per"] = per
    X.to_pickle(f"{S206}_{per}.pkl")
    print(per, X[X.net.notna()].groupby(["kind", "ex"]).size().to_dict(), flush=True)


def report():
    import common182 as C  # noqa: E402
    import run as R5  # noqa: E402
    print("s206 — предупреждение Bithumb «скачок цены ≥ +50%» → шорт перпа Binance 48 ч, стоп 25%\n")
    win = {"2022–2024": ("2023-07-04", "2024-10-01"), "2024–2026": ("2024-10-01", "2026-10-19")}
    pn, ph, pdl = [], [], []
    for per in ("2022–2024", "2024–2026"):
        X = pd.read_pickle(f"{S206}_{per}.pkl")
        mo = (C.ts(win[per][1]) - C.ts(win[per][0])) / (30.4 * DAY)
        X = X[X.t >= C.ts(win[per][0])]
        fl = (X.kind == "flag") & (X.ex == "bithumb")
        ct = X.kind == "ctl"
        print(f"== {per} (окно {win[per][0]} — {win[per][1]}, {mo:.1f} мес) ==")
        x = R5.view(X, fl)
        print(f"  основной: флаг Bithumb, 48 ч: {R5.line(C, x, per, mo)}")
        print(f"  контроль: рост перпа ≥ +50% без флага: {R5.line(C, R5.view(X, ct), per, mo)}")
        print(f"  ступени 20–30: {R5.line(C, R5.view(X, fl & (X.step.astype(int) >= 20)), per, mo)}")
        print(f"  перп за 24 ч < +20% (корейский памп): {R5.line(C, R5.view(X, fl & (X.r24 < 0.2)), per, mo)}")
        print(f"  перп за 24 ч ≥ +20%: {R5.line(C, R5.view(X, fl & (X.r24 >= 0.2)), per, mo)}")
        print(f"  24 ч: {R5.line(C, R5.view(X, fl, '24'), per, mo)}")
        print(f"  7 сут, стоп 50%: {R5.line(C, R5.view(X, fl, '7'), per, mo)}")
        y = pd.concat([x.assign(g=1), R5.view(X, ct).assign(g=0)])
        d, se = C.diff(y.net, y.g == 1, y.t)
        pdl.append((d, se, len(y)))
        print(f"  Δ флаг − без флага: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            cut = C.ts(C.PER[per][2])
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
            umo = (C.ts("2026-10-19") - C.ts("2026-03-24")) / (30.4 * DAY)
            up = (X.kind == "flag") & (X.ex == "upbit") & (X.r24 >= 0.2)
            print(f"  Upbit 「가격 급등락」 при росте перпа ≥ +20% (03–10.2026): {R5.line(C, R5.view(X, up), per, umo)}")
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Два окна, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
    print("  по окнам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " + " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Δ флаг − без флага вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    os.makedirs(S206, exist_ok=True)
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
