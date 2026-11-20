"""s244 — 🐋 в сети Arbitrum (гипотеза — ВЫВОДЫ.md, записана до расчёта, коммит 675e5f2). События — s244/raw (переводы на
адреса Binance от «не бирж», collect_arb.py; время блока у крупных переводов уточняется по узлу), монеты в обращении —
s244/arb_circ.json. Правило сделки — как у 🐋 и s221:
вход на закрытии первой 15-мин свечи не раньше чем через 15 мин после блока, ход фьючерса за 24 ч ±5%, фьючерс старше
суток, шорт 24 ч, стоп 25%. Запуск из /home/user/mc_data: python3 <repo>/research/s244/run.py"""
import glob
import importlib.util
import json
import os
import urllib.request

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("s221run", os.path.join(HERE, "..", "s221", "run.py"))
S221 = importlib.util.module_from_spec(spec); spec.loader.exec_module(S221)
DAY, GAP, BIG, CALM = 86400, 48 * 3600, 0.005, 0.05
G0 = 1686789347
T0, T1 = pd.Timestamp("2024-10-01", tz="UTC").timestamp(), pd.Timestamp("2026-10-19", tz="UTC").timestamp()
RPC = "https://arb1.arbitrum.io/rpc"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}


def decimals(addrs):
    p = "s244/dec.json"
    D = json.load(open(p)) if os.path.exists(p) else {}
    for a in addrs:
        if a in D:
            continue
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": a, "data": "0x313ce567"}, "latest"]})
        req = urllib.request.Request(RPC, data=body.encode(), headers=UA)
        D[a] = int(json.loads(urllib.request.urlopen(req, timeout=30).read())["result"], 16)
    json.dump(D, open(p, "w"))
    return D


def block_ts(blocks):
    p = "s244/blk_ts.json"
    D = json.load(open(p)) if os.path.exists(p) else {}
    for b in blocks:
        if str(b) in D:
            continue
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber", "params": [hex(int(b)), False]})
        req = urllib.request.Request(RPC, data=body.encode(), headers=UA)
        D[str(b)] = int(json.loads(urllib.request.urlopen(req, timeout=30).read())["result"]["timestamp"], 16)
    json.dump(D, open(p, "w"))
    return D


def events():
    C = json.load(open("s244/arb_circ.json"))
    by_addr = {v["addr"]: (fs, v) for fs, v in C.items()}
    rows = []
    for p in sorted(glob.glob("s244/raw/*.json")):
        rows += json.load(open(p))
    X = pd.DataFrame(rows, columns=["block", "t", "tok", "frm", "to", "data", "tx"])
    X = X[X.tok.isin(by_addr)]
    dec = decimals(sorted(set(X.tok)))
    X["perp"] = X.tok.map(lambda a: by_addr[a][0])
    X["amt"] = [int(d, 16) / 10 ** dec[a] for d, a in zip(X.data, X.tok)]
    circ = {}
    for fs, v in C.items():
        circ[fs] = (sorted(d for d, c, _ in v["days"]), {d: c for d, c, _ in v["days"]})
    fr = []
    for fs, t, a in zip(X.perp, X.t, X.amt):
        dd, m = circ[fs]
        d = pd.Timestamp(int(t) - DAY, unit="s").strftime("%Y-%m-%d")
        i = int(np.searchsorted(dd, d, "right")) - 1
        fr.append(a / m[dd[i]] if i >= 0 and m[dd[i]] else np.nan)
    X["frac"] = fr
    X["grp"] = X.perp.map(lambda fs: "B" if C[fs]["eth"] else "A")
    print(f"переводов на Binance от «не бирж»: {len(X)}; ≥ 0,5% обращения: {(X.frac >= BIG).sum()}")
    X = X[(X.frac >= BIG) & (X.t >= T0 - DAY) & (X.t < T1 + DAY)].copy()
    bt = block_ts(sorted(set(X.block)))                    # точное время блока вместо оценки по краям куска
    X["t"] = X.block.map(lambda b: bt[str(b)]).astype(np.int64)
    X = X[(X.t >= T0) & (X.t < T1)].sort_values(["perp", "t"])
    out = []
    for perp, g in X.groupby("perp"):
        last = -10 ** 12
        for r in g.itertuples():
            if r.t - last >= GAP:
                out.append(r._asdict()); last = r.t
    return pd.DataFrame(out)


def main():
    E = events()
    print("событий ≥ 0,5% обращения (первые за 48 ч):", len(E), "монет", E.perp.nunique() if len(E) else 0)
    R = S221.trades(E[["perp", "t", "amt", "frac", "grp", "tok", "frm", "tx"]])
    R.to_pickle("s244_trades.pkl")
    months = (T1 - T0) / (30.44 * DAY)
    x = R[R.net.notna() & (R.r24.abs() <= CALM)]
    print(f"\n🐋 Arbitrum (спокойный рынок ±5%): {S221.line(x, months)}")
    print(f"все события без фильтра рынка: {S221.line(R[R.net.notna()], months)}")
    for g in ("A", "B"):
        if (x.grp == g).sum() >= 5:
            print(f"группа {g}: {S221.line(x[x.grp == g], months)}")
    # группа B без завода той же монеты в Ethereum (≥ 0,5% обращения) за 48 ч до события
    D = pd.read_pickle("s195_deposits.pkl")
    D = D[D.exch.astype(str).str.contains("Binance") & (D.frac >= BIG)]
    eth = {p: np.sort(g.t.values.astype(np.int64)) for p, g in D.groupby("perp")}

    def near(r):
        a = eth.get(r.perp)
        if a is None:
            return False
        i = np.searchsorted(a, r.t, "right")
        return i > 0 and r.t - a[i - 1] <= GAP
    xb = x[x.grp == "B"]
    if len(xb):
        nb = xb[~xb.apply(near, axis=1)]
        if len(nb) >= 5:
            print(f"группа B без завода в Ethereum за 48 ч: {S221.line(nb, months)}")
    if len(x) >= 5:
        print(f"🐋ᵛ Arbitrum (λ ≥ 0,05): {S221.line(x[x.lam >= 0.05], months)}")
    m, t, n = S221.ct(x.net, x.entry); mh, _, _ = S221.ct(x.hed, x.entry); md = (x.net - x.pl).mean()
    print("\nпорог s244: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                      (("среднее > 0 и t ≥ 2", m > 0 and t >= 2), ("с хеджем > 0", mh > 0),
                                       ("сверх плацебо > 0", md > 0))))
    cols = ["perp", "entry", "net", "hed", "pl", "stop"]
    parts = [x[cols]]
    for f in ("s243_trades.pkl", "s221_trades.pkl"):
        if os.path.exists(f):
            S = pd.read_pickle(f); parts.append(S[S.net.notna() & (S.r24.abs() <= CALM)][cols])
    if len(parts) > 1:
        print(f"Arbitrum вместе с Base и Solana (что посчитано): {S221.line(pd.concat(parts), months)}")


if __name__ == "__main__":
    main()
