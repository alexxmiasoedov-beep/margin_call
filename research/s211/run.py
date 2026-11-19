"""s211 — давление маркетмейкера HLP (Г1 s209): HLP / OI ≤ −1% за сутки D (новый эпизод, OI ≥ 1 млн $) → шорт перпа Binance
с 00:15 UTC D + 1 на 48 ч, стоп 25%. Зеркало — HLP / OI ≥ +1%. Запись до расчёта — ВЫВОДЫ.md (коммит e241f45).

Запуск из /home/user/mc_data:
  python3 run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 run.py 2022–2024
  python3 run.py report
"""
import gzip
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
sys.path.insert(0, os.path.join(HERE, "..", "s210"))

DAY, OUT = 86400, "/home/user/mc_data"
HL = f"{OUT}/s209/hl"


def load(name):
    d = json.load(gzip.open(f"{HL}/{name}.json.gz", "rt"))
    return pd.DataFrame(d["chart_data"] if isinstance(d, dict) else d)


def events():
    h = load("hlp_positions")[["time", "coin", "daily_ntl"]]
    oi = load("open_interest")
    lq = load("daily_notional_liquidated_by_coin")
    lcol = [c for c in lq.columns if c not in ("time", "coin")][0]
    m = h.merge(oi, on=["time", "coin"]).merge(lq[["time", "coin", lcol]], on=["time", "coin"], how="left")
    m["day"] = pd.to_datetime(m.time).dt.normalize()
    m = m[m.open_interest >= 1e6].copy()
    m["r"] = m.daily_ntl / m.open_interest
    m["liq"] = m[lcol].fillna(0) / m.open_interest
    out = []
    for coin, g in m.sort_values("day").groupby("coin"):
        days = g.day.values
        r = g.r.values
        lq_ = g.liq.values
        for kind, cond in (("short", r <= -0.01), ("long", r >= 0.01), ("flat", np.abs(r) < 0.002)):
            last = None
            for i in np.flatnonzero(cond):
                d = days[i]
                if last is not None and (d - last) / np.timedelta64(1, "D") <= 7:
                    last = d if kind != "flat" else last
                    continue
                out.append((coin, pd.Timestamp(d), kind, float(r[i]), float(lq_[i])))
                last = d
    E = pd.DataFrame(out, columns=["coin", "day", "kind", "r", "liq"])
    E["entry"] = [int(pd.Timestamp(d).tz_localize("UTC").timestamp()) + DAY + 900 for d in E.day]
    return E


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    import run as R10  # noqa: E402  (s210: сопоставление монет Hyperliquid с перпами)
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events()
    E["perp"] = [R10.perp_key(K, c) for c in E.coin]
    E = E[E.perp.notna() & (E.entry >= t0) & (E.entry < t1)]
    res = []
    for (kind, s), g in E.groupby(["kind", "perp"]):
        t = K[s]["t"].astype(np.int64)
        lo, _ = FB.live(s)
        g = g.sort_values("entry").copy()
        st = g.entry.values - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        g, I = g[ok].copy(), I[ok]
        if not len(g):
            continue
        for hold, suf in ((48, ""), (24, "24")):
            okt, net, stp, bars, tend = FB.trades(s, I, 0.25, hold, -1)
            g["net" + suf] = np.where(okt, net, np.nan)
            g["stop" + suf] = np.where(okt, stp, False)
            g["tend" + suf] = tend
            g["hed" + suf] = g["net" + suf].values + FB.alt_mv(t[I] + 900, tend)
            g["pl" + suf] = FB.placebo(s, I, 0.25, hold, -1)
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R["per"] = per
    R.to_pickle(f"{OUT}/s211_{per}.pkl")
    print(per, R[R.net.notna()].groupby("kind").size().to_dict(), flush=True)


def view(R, mask, suf=""):
    import run as R10  # noqa: E402
    x = R[mask].copy()
    x["net"], x["hed"], x["pl"], x["stop"], x["tend"] = (x["net" + suf], x["hed" + suf], x["pl" + suf], x["stop" + suf],
                                                         x["tend" + suf])
    x = x[x.net.notna()]
    return R10.one_per_coin(x)


def report():
    import common182 as C  # noqa: E402
    import run as R10  # noqa: E402
    print("s211 — давление маркетмейкера HLP: HLP / OI ≤ −1% → шорт перпа Binance 48 ч, стоп 25%\n")
    win = {"2022–2024": ("2023-06-21", "2024-10-01", "2024-02-01"), "2024–2026": ("2024-10-01", "2026-04-05", "2025-07-01")}
    pn, ph, pdl = [], [], []
    for per in ("2022–2024", "2024–2026"):
        R = pd.read_pickle(f"{OUT}/s211_{per}.pkl")
        a, b, cut = (C.ts(x) for x in win[per])
        mo = (b - a) / (30.4 * DAY)
        R = R[(R.t >= a) & (R.t < b)]
        sh, lg, fl = R.kind == "short", R.kind == "long", R.kind == "flat"
        x = view(R, sh)
        print(f"== {per} (окно {win[per][0]} — {win[per][1]}, {mo:.1f} мес) ==")
        print(f"  основной: HLP в шорте ≥ 1% OI: {R10.line(C, x, cut, mo)}")
        print(f"  зеркало: HLP в лонге ≥ 1% OI (та же шортовая сделка): {R10.line(C, view(R, lg), cut, mo)}")
        print(f"  фон: |HLP / OI| < 0,2%: {R10.line(C, view(R, fl), cut, mo)}")
        print(f"  доза ≥ 2%: {R10.line(C, view(R, sh & (R.r <= -0.02)), cut, mo)}")
        print(f"  доза ≥ 5%: {R10.line(C, view(R, sh & (R.r <= -0.05)), cut, mo)}")
        print(f"  ликвидации ≥ 10% OI: {R10.line(C, view(R, sh & (R.liq >= 0.10)), cut, mo)}")
        print(f"  24 ч: {R10.line(C, view(R, sh, '24'), cut, mo)}")
        y = pd.concat([x.assign(g=1), view(R, lg).assign(g=0)])
        d, se = C.diff(y.net, y.g == 1, y.t)
        pdl.append((d, se, len(y)))
        print(f"  Δ шорт HLP − лонг HLP: {d:+.2%} (t {d / se:+.1f})")
        m, t, n = C.ct(x.net, x.t)
        mh, th, _ = C.ct(x.hed, x.t)
        pn.append((m, abs(m / t) if t else np.nan, n))
        ph.append((mh, abs(mh / th) if th else np.nan, n))
        if per == "2024–2026":
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            crit = [("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                    ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))
        print()
    m, t = C.combine(pn)
    mh, th = C.combine(ph)
    print(f"Два окна, основной: {m:+.2%} (t {t:+.1f}); с хеджем {mh:+.2%} (t {th:+.1f})")
    print("  по окнам: " + " / ".join(f"{a:+.2%}" for a, _, _ in pn) + "; с хеджем " + " / ".join(f"{a:+.2%}" for a, _, _ in ph))
    d, t = C.combine(pdl)
    print(f"Δ шорт HLP − лонг HLP вместе: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
