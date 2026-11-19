"""s215 — разлоки CoinMarketCap сверх DefiLlama: cliff ≥ 1% обращения (CMC, s28) без события 🔑⁺ у того же перпа в ±3 сут →
шорт перпа T − 7 → T + 1, стоп 50%. Запись до расчёта — ВЫВОДЫ.md (коммит 09d228e). Сборка событий повторяет
research/s28/unlock_study.py: build() и px_ok() без загрузки сетки s22.

Запуск из /home/user/mc_data: python3 run.py 2024–2026 && python3 run.py report
"""
import datetime
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s182", "s213"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, OUT = 86400, "/home/user/mc_data"
H = 3600


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def hist(cid):
    p = f"{OUT}/s28/hist/{cid}.json"
    if not os.path.exists(p):
        return None
    h = pd.DataFrame(json.load(open(p)), columns=["d", "px", "vol", "mcap", "circ"])
    if h.empty:
        return None
    h["t"] = pd.to_datetime(h.d).map(lambda d: int(d.timestamp())) + DAY          # закрытие дня d — 00:00 d+1
    return h.sort_values("t").reset_index(drop=True)


def tokens():
    keys = set(json.load(open(f"{OUT}/s205/keys_s2_k2y.pkl.json")))
    out = []
    for r in json.load(open(f"{OUT}/s28/unlock_listing.json")):
        for p in ("", "1000", "1000000"):
            if p + r["symbol"] in keys:
                out.append((r["cryptoId"], r["symbol"], p + r["symbol"]))
                break
    return out


def build():
    rows = []
    for cid, sym, fut in tokens():
        p = f"{OUT}/s28/ev/{cid}_past.json"
        if not os.path.exists(p):
            continue
        ev = sorted(json.load(open(p)), key=lambda e: e["time"])
        h = hist(cid)
        grp = []
        for e in ev:
            t = ts(e["time"])
            if t < 1727740800 or t > 1792368000:
                continue
            if grp and t - grp[-1]["t"] <= 2 * DAY:
                grp[-1]["amount"] += e["amount"]
                grp[-1]["pct_total"] += e["percentage"] or 0
                grp[-1]["alloc"] += e["allocations"]
            else:
                grp.append(dict(t=t, amount=e["amount"], pct_total=e["percentage"] or 0, alloc=list(e["allocations"])))
        for x in grp:
            circ = px = np.nan
            if h is not None:
                b = h[h.t < x["t"] - 6 * H]
                if len(b):
                    circ, px = b.circ.iloc[-1], b.px.iloc[-1]
            vt = {a["vestingType"] for a in x["alloc"]}
            rows.append(dict(cid=cid, sym=sym, s=fut, T=int(x["t"]), amount=x["amount"], pct_total=x["pct_total"],
                             pct_circ=x["amount"] / circ * 100 if circ and circ > 0 else np.nan, px=px, cliff="cliff" in vt))
    E = pd.DataFrame(rows)
    E["size"] = E.pct_circ.where(E.pct_circ.notna(), E.pct_total)
    return E


def run(per):
    import fastbt as FB  # noqa: E402
    from run import mult  # noqa: E402  (s213)
    K = FB.K
    E = build()
    E = E[E.cliff & (E["size"] >= 1.0) & E.s.isin(K.keys())].copy()
    U = pd.read_pickle(f"{OUT}/s142_{per}.pkl")
    ut = {s: np.sort(g["T"].values.astype(np.int64)) for s, g in U.groupby("s")}

    def near(s, T):
        a = ut.get(s)
        return a is not None and len(a) and bool(np.any(np.abs(a - T) <= 3 * DAY))
    E["dl"] = [near(s, T) for s, T in zip(E.s, E["T"])]
    E["entry"] = (np.ceil((E["T"] - 7 * DAY) / 900) * 900).astype(np.int64)
    res = []
    for s, g in E.groupby("s"):
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
        # сверка тикера: цена CMC за день до разлока против перпа на входе (±25%, с поправкой на множитель)
        ratio = g.px.values / (c[I] / mult(s))
        g["px_ok"] = (ratio > 0.75) & (ratio < 1.25)
        okt, net, stp, bars, tend = FB.trades(s, I, 0.50, 192, -1)
        g["net"] = np.where(okt, net, np.nan)
        g["why"] = np.where(stp, "стоп", "время")
        g["tend"] = tend
        g["hed"] = g.net.values + FB.alt_mv(t[I] + 900, tend)
        g["pl"] = FB.placebo(s, I, 0.50, 192, -1)
        g["t"] = g.entry
        res.append(g)
    R = pd.concat(res, ignore_index=True)
    R.to_pickle(f"{OUT}/s215_{per}.pkl")
    x = R[R.net.notna() & R.px_ok]
    print(per, "событий CMC ≥ 1% cliff:", len(x), "из них сверх DefiLlama:", int((~x.dl).sum()), flush=True)


def one_per_coin(x):
    keep = []
    for s, g in x.sort_values("t").groupby("s"):
        last = -1
        for i, r in zip(g.index, g.itertuples()):
            if r.t >= last:
                keep.append(i)
                last = r.tend
    return x.loc[keep]


def wk(t, days=7):
    return (np.asarray(t, np.int64) // (days * DAY)) * (days * DAY)


def line(C, x, per):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = C.ct(x.net, wk(x.t))
    _, tm, _ = C.ct(x.net, wk(x.t, 30))
    mh, th, _ = C.ct(x.hed, wk(x.t))
    md, td, _ = C.ct(x.net - x.pl, wk(x.t))
    cut = C.ts(C.PER[per][2])
    return (f"n={n:4d} ({n / C.months(per):4.1f}/мес) {m:+.2%} (t по неделям {t:+.1f}, по месяцам {tm:+.1f}) | половины "
            f"{x[x.t < cut].net.mean():+.2%} / {x[x.t >= cut].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | "
            f"сверх плацебо {md:+.2%} (t {td:+.1f}) | стопов {(x.why == 'стоп').mean():.0%}")


def report():
    import common182 as C  # noqa: E402
    per = "2024–2026"
    R = pd.read_pickle(f"{OUT}/s215_{per}.pkl")
    R = R[R.net.notna() & R.px_ok]
    print("s215 — разлоки CMC (cliff ≥ 1% обращения) сверх DefiLlama → шорт T − 7 → T + 1, стоп 50% (10.2024–10.2026)\n")
    x = one_per_coin(R[~R.dl])
    print(f"основной: сверх DefiLlama: {line(C, x, per)}")
    print(f"пересечение с 🔑⁺: {line(C, one_per_coin(R[R.dl]), per)}")
    print(f"все события CMC: {line(C, one_per_coin(R), per)}")
    print(f"сверх DefiLlama, доля ≥ 5%: {line(C, one_per_coin(R[~R.dl & (R['size'] >= 5)]), per)}")
    m, t, n = C.ct(x.net, wk(x.t))
    mh, _, _ = C.ct(x.hed, wk(x.t))
    cut = C.ts(C.PER[per][2])
    h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
    crit = [("≥ 20 в месяц", n / C.months(per) >= 20), ("t ≥ 3 по неделям", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
            ("сверх плацебо > 0", (x.net - x.pl).mean() > 0), ("с хеджем > 0", mh > 0)]
    print("правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in crit))


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
