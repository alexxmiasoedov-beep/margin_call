"""s168 — завод токена в прайм-брокера или кастоди → шорт (гипотеза — ВЫВОДЫ.md, записана до расчёта). Переводы — сбор s160
(s160/raw), метки — s160/sets.json; доля — к обращению CMC на дату (s160/circ); точное время блока — RPC с кэшем
s160/cache_blocktime.json. Шаги: events (из /home/user/mc_data) → run <период> (в папке периода с MC_K/MC_F/MC_CUT) → report.
Запуск: python3 <repo>/research/s168/custody_test.py events | <период> | report"""
import glob
import gzip
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
NAMES = {"Coinbase Prime", "FalconX", "Ceffu", "BitGo", "Copper", "Anchorage Digital", "Cobo", "Bitcoin Suisse"}
NOSYM = {"PAXG", "XAUT", "USDC", "USDT", "FDUSD", "TUSD", "DAI", "USDP", "BUSD", "USDE", "USD1", "PYUSD", "EUR", "EURI"}
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def ev_module():
    spec = importlib.util.spec_from_file_location("s160_events", os.path.join(HERE, "..", "s160", "events.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def events():
    E6 = ev_module(); CEX = E6.CEX; TOK = E6.TOK
    rows = []
    for p in sorted(glob.glob(f"{OUT}/s160/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    X = X[X.to.map(lambda a: a in CEX and CEX[a][0] in NAMES)]
    X = X[~X.frm.isin(CEX.keys()) & (X.frm != "0x" + "0" * 40)].copy()
    X["perp"] = X.tok.map(lambda t: TOK[t]["perp"]); X["sym"] = X.tok.map(lambda t: str(TOK[t]["sym"]).upper())
    X = X[~X.sym.isin(NOSYM)]
    X["cust"] = X.to.map(lambda a: CEX[a][0])
    bt = json.load(open(f"{OUT}/s160/cache_blocktime.json")); A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    X["t_approx"] = np.interp(X.block, A[:, 0], A[:, 1])
    C = E6.circ_table(); fr = []
    for r in X.itertuples():
        s = C.get(r.tok)
        if s is None:
            fr.append(np.nan); continue
        k = s.index.searchsorted(pd.Timestamp(int(r.t_approx), unit="s").normalize(), "right") - 1
        fr.append(r.amt / s.iloc[k] if k >= 0 and s.iloc[k] > 0 else np.nan)
    X["frac"] = fr
    E = X[X.frac >= 0.005].copy()
    print("заводов в кастоди ≥ 0,5%", len(E), E.cust.value_counts().to_dict(), flush=True)
    tm = E6.block_times(E.block.unique()); E["t"] = E.block.map(tm)
    E = E.dropna(subset=["t"]); E["t"] = E.t.astype(np.int64)
    E = E.sort_values("t").reset_index(drop=True)
    keep, last, first30, last30 = np.zeros(len(E), bool), {}, np.zeros(len(E), bool), {}
    for i, r in enumerate(E.itertuples()):
        if r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600:
            keep[i] = True; last[r.perp] = r.t
            if r.t - last30.get(r.perp, -10 ** 12) >= 30 * DAY:
                first30[i] = True
            last30[r.perp] = r.t
    E["first"], E["first30"] = keep, first30
    B = pd.read_pickle(f"{OUT}/s160_events.pkl"); B = B[B.exch == "Binance"]
    bx = {p: np.sort(g.t.values.astype(np.int64)) for p, g in B.groupby("perp")}
    E["bin2d"] = [bool(np.any(np.abs(bx.get(p, np.array([], np.int64)) - t) <= 2 * DAY)) for p, t in zip(E.perp, E.t)]
    E.to_pickle(f"{OUT}/s168_events.pkl")
    F = E[E.first]
    print("событий (одно на монету за 48 ч)", len(F), "монет", F.perp.nunique(), F.cust.value_counts().to_dict(), flush=True)


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    E = pd.read_pickle(f"{OUT}/s168_events.pkl"); E = E[E.first]
    rows = []
    for r in E.itertuples():
        te = int(-(-(int(r.t) + 900) // 900) * 900)
        if not (t0 <= te < t1) or r.perp not in K:
            continue
        lo, hi = live(r.perp)
        if not np.isfinite(lo) or te < lo + DAY:
            continue
        i = idx_at(r.perp, te)
        if i is None or int(K[r.perp]["t"][i]) + 900 != te:
            continue
        x = trade(r.perp, i, tp=None, sl=0.25, hold_h=24, side=-1)
        if not x:
            continue
        y = trade(r.perp, i, tp=None, sl=0.25, hold_h=48, side=-1)
        z = trade(r.perp, i, tp=None, sl=0.25, hold_h=168, side=-1)
        t_end = int(K[r.perp]["t"][i]) + 900 + int(x["bars"]) * 900
        pl = []
        for back in (45, 90, 135):
            j = idx_at(r.perp, te - back * DAY)
            w = trade(r.perp, j, tp=None, sl=0.25, hold_h=24, side=-1) if j is not None else None
            if w:
                pl.append(w["net"])
        rows.append(dict(s=r.perp, t=te, frac=r.frac, cust=r.cust, first30=bool(r.first30), bin2d=bool(r.bin2d), net=x["net"],
                         why=x["why"], n48=y["net"] if y else np.nan, n7=z["net"] if z else np.nan, hed=x["net"] + mv(te, t_end),
                         pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s168_{per}.pkl")
    print(per, "сделок", len(X), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s168_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for name, x in (("все (основная)", X), ("Coinbase Prime", X[X.cust == "Coinbase Prime"]), ("FalconX", X[X.cust == "FalconX"]),
                        ("≥ 1%", X[X.frac >= 0.01]), ("первое за 30 сут", X[X.first30]), ("без завода на Binance ±2 сут", X[~X.bin2d])):
            if len(x) < 8:
                print(f"  {name:30s} n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
            m48, t48, _ = ct(x.n48.dropna(), x.t[x.n48.notna()]); m7, t7, _ = ct(x.n7.dropna(), x.t[x.n7.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {name:30s} n={n:4d} ({n / months:5.1f}/мес) 24 ч {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | 48 ч {m48:+.2%} (t {t48:+.1f}) | 7 сут {m7:+.2%} "
                  f"(t {t7:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | стопов {(x.why == 'стоп').mean():.0%}")
    A = pd.concat(A, ignore_index=True)
    m, t, n = ct(A.net, A.t); mh, th, _ = ct(A.hed.dropna(), A.t[A.hed.notna()])
    print(f"\nшесть лет: n={n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    a = sys.argv[1]
    events() if a == "events" else (report() if a == "report" else run(a))
