"""s243 — 🐋 в сети Base (гипотеза — ВЫВОДЫ.md, записана до расчёта, коммит 2f81b11). События — s243/raw (переводы на адреса
Binance от «не бирж», collect_base.py), монеты в обращении — s243/base_circ.json. Правило сделки — как у 🐋 и s221:
вход на закрытии первой 15-мин свечи не раньше чем через 15 мин после блока, ход фьючерса за 24 ч ±5%, фьючерс старше
суток, шорт 24 ч, стоп 25%. Запуск из /home/user/mc_data: python3 <repo>/research/s243/run.py"""
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
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}


def decimals(addrs):
    p = "s243/dec.json"
    D = json.load(open(p)) if os.path.exists(p) else {}
    for a in addrs:
        if a in D:
            continue
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": a, "data": "0x313ce567"}, "latest"]})
        req = urllib.request.Request("https://base.gateway.tenderly.co", data=body.encode(), headers=UA)
        D[a] = int(json.loads(urllib.request.urlopen(req, timeout=30).read())["result"], 16)
    json.dump(D, open(p, "w"))
    return D


def events():
    C = json.load(open("s243/base_circ.json"))
    by_addr = {v["addr"]: (fs, v) for fs, v in C.items()}
    rows = []
    for p in sorted(glob.glob("s243/raw/*.json")):
        rows += json.load(open(p))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "data", "tx"])
    X = X[X.tok.isin(by_addr)]
    dec = decimals(sorted(set(X.tok)))
    X["t"] = G0 + 2 * X.block.astype(np.int64)
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
    X = X[(X.frac >= BIG) & (X.t >= T0) & (X.t < T1)].sort_values(["perp", "t"])
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
    R.to_pickle("s243_trades.pkl")
    months = (T1 - T0) / (30.44 * DAY)
    x = R[R.net.notna() & (R.r24.abs() <= CALM)]
    print(f"\n🐋 Base (спокойный рынок ±5%): {S221.line(x, months)}")
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
        print(f"🐋ᵛ Base (λ ≥ 0,05): {S221.line(x[x.lam >= 0.05], months)}")
    m, t, n = S221.ct(x.net, x.entry); mh, _, _ = S221.ct(x.hed, x.entry); md = (x.net - x.pl).mean()
    print("\nпорог s243: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                                      (("среднее > 0 и t ≥ 2", m > 0 and t >= 2), ("с хеджем > 0", mh > 0),
                                       ("сверх плацебо > 0", md > 0))))
    if os.path.exists("s221_trades.pkl"):
        S = pd.read_pickle("s221_trades.pkl")
        S = S[S.net.notna() & (S.r24.abs() <= CALM)]
        cols = ["perp", "entry", "net", "hed", "pl", "stop"]
        print(f"Base + Solana вместе: {S221.line(pd.concat([x[cols], S[cols]]), months)}")


if __name__ == "__main__":
    main()
