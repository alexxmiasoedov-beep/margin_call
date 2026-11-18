"""s167 — проверка варианта s160 «все заводы ≥ 0,5% обращения на адреса Binance → шорт 24 ч» на токенах, снятых с фьючерсов
Binance до 10.2024 (гипотеза и порог — ВЫВОДЫ.md, записаны до сбора). Переводы — s167/raw (collect.py), метки и фильтры — как
в s160/events.py; доля — к обращению CMC на дату (s167/circ); точное время блока — RPC с кэшем s160/cache_blocktime.json.
Шаги: events (из /home/user/mc_data) → run <период> (в папке периода с MC_K/MC_F/MC_CUT) → report (из /home/user/mc_data)."""
import glob
import gzip
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141", "s157"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def ev_module():
    spec = importlib.util.spec_from_file_location("s160_events", os.path.join(HERE, "..", "s160", "events.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def circ_table(TK):
    out = {}
    for tok, v in TK.items():
        s = pd.Series({d: c for d, c, _ in json.load(open(f"{OUT}/s167/circ/{v['cmc']}.json")) if c})
        if len(s):
            s.index = pd.to_datetime(s.index); out[tok] = s.sort_index()
    return out


def events():
    E6 = ev_module(); CEX = E6.CEX
    TK = json.load(open(f"{OUT}/s167/toks.json"))
    rows = []
    for p in sorted(glob.glob(f"{OUT}/s167/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    print("строк в сборе", len(X), flush=True)
    lab = {a: " ".join(v) for a, v in CEX.items()}
    X = X[~X.to.map(lambda a: bool(E6.CUST.search(lab.get(a, ""))))]
    X = X[~X.frm.isin(CEX.keys()) & (X.frm != "0x" + "0" * 40)].copy()
    X["exch"] = X.to.map(lambda a: CEX[a][0])
    bt = json.load(open(f"{OUT}/s160/cache_blocktime.json")); A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    X["t_approx"] = np.interp(X.block, A[:, 0], A[:, 1])
    C = circ_table(TK); fr = []
    for r in X.itertuples():
        s = C.get(r.tok)
        if s is None:
            fr.append(np.nan); continue
        k = s.index.searchsorted(pd.Timestamp(int(r.t_approx), unit="s").normalize(), "right") - 1
        fr.append(r.amt / s.iloc[k] if k >= 0 and s.iloc[k] > 0 else np.nan)
    X["frac"] = fr
    E = X[X.frac >= 0.005].copy()
    print("переводов ≥ 0,5% обращения", len(E), flush=True)
    tm = E6.block_times(E.block.unique()); E["t"] = E.block.map(tm)
    E = E.dropna(subset=["t"]); E["t"] = E.t.astype(np.int64)
    E["perp"] = E.tok.map(lambda t: TK[t]["perp"])
    E = E.sort_values("t").reset_index(drop=True)
    keep, last = np.zeros(len(E), bool), {}
    for i, r in enumerate(E.itertuples()):
        if r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600:
            keep[i] = True; last[r.perp] = r.t
    E["first_all"] = keep
    E.to_pickle(f"{OUT}/s167_events.pkl")
    F = E[E.first_all]
    print("событий", len(F), "из них на Binance", int((F.exch == "Binance").sum()), "монет", F.perp.nunique(), flush=True)


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    E = pd.read_pickle(f"{OUT}/s167_events.pkl"); E = E[E.first_all]
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
        t_end = int(K[r.perp]["t"][i]) + 900 + int(x["bars"]) * 900
        pl = []
        for back in (45, 90, 135):
            j = idx_at(r.perp, te - back * DAY)
            w = trade(r.perp, j, tp=None, sl=0.25, hold_h=24, side=-1) if j is not None else None
            if w:
                pl.append(w["net"])
        rows.append(dict(s=r.perp, t=te, frac=r.frac, exch=r.exch, net=x["net"], why=x["why"], hed=x["net"] + mv(te, t_end),
                         pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s167_{per}.pkl")
    print(per, "сделок", len(X), "на Binance", int((X.exch == "Binance").sum()) if len(X) else 0, flush=True)


def line(x, months, c, ct):
    if len(x) < 8:
        return f"n={len(x)}" + (f" {x.net.mean():+.2%}" if len(x) else "")
    m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
    dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
    return (f"n={n:4d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / {x[x.t >= c].net.mean():+.2%} | "
            f"с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | в плюсе {(x.net > 0).mean():.0%} | "
            f"стопов {(x.why == 'стоп').mean():.0%}")


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s167_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        print("  на Binance (проверка):     " + line(X[X.exch == "Binance"], months, c, ct))
        print("  на другие биржи (отчёт):   " + line(X[X.exch != "Binance"], months, c, ct))
    A = pd.concat(A, ignore_index=True); B = A[A.exch == "Binance"]
    m, t, n = ct(B.net, B.t); mh, th, _ = ct(B.hed.dropna(), B.t[B.hed.notna()])
    dp = (B.net - B.pl).dropna(); md, td, _ = ct(dp, B.t[(B.net - B.pl).notna()])
    print(f"\nдва периода, Binance: n={n} {m:+.2%} (t {t:+.1f}) | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f})")
    print("монеты:", B.groupby("s").net.agg(["count", "mean"]).sort_values("count", ascending=False).head(15).round(4).to_dict("index"))


if __name__ == "__main__":
    a = sys.argv[1]
    events() if a == "events" else (report() if a == "report" else run(a))
