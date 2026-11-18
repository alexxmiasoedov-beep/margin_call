"""s161 — заводы токена на биржи перед входом журнала (гипотезы — ВЫВОДЫ.md, записаны до расчёта). Переводы — s160/raw
(≥ 0,05% обращения, получатель — адрес биржи); без кастоди и прайм-брокеров, отправитель не биржа и не нулевой адрес; время
блока — по опорным блокам (s160/cache_blocktime.json); доля — к обращению CMC на дату (s160/circ). К2а: разлоки s142, заводы на
любые биржи за 72 ч ≥ 0,25%. К2б: пампы со спотом ≥ 26% (s154b) и ⏰ (s88), заводы на Upbit и Bithumb за 6 ч ≥ 0,1%.
Запуск из /home/user/mc_data: python3 <repo>/research/s161/filter_test.py"""
import glob
import gzip
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s157"))
from opt_test import wdiff  # noqa: E402

CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|matrixport|"
                  r"ceffu|hex trust|komainu|cobo|paxos|custody", re.I)
PER = ("2020–2022", "2022–2024", "2024–2026")
O9 = {"2020–2022": "s88/oos2020_trades.pkl", "2022–2024": "s88/oos_trades.pkl", "2024–2026": "s88/trades.pkl"}


def deposits():
    S = json.load(open("s160/sets.json")); CEX = S["cex"]
    rows = []
    for p in sorted(glob.glob("s160/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    lab = {a: " ".join(v) for a, v in CEX.items()}
    X = X[~X.to.map(lambda a: bool(CUST.search(lab.get(a, "")))) & ~X.frm.isin(CEX.keys()) & (X.frm != "0x" + "0" * 40)].copy()
    X["kr"] = X.to.map(lambda a: CEX[a][0] in ("Upbit", "Bithumb"))
    bt = {int(k): v for k, v in json.load(open("s160/cache_blocktime.json")).items()}
    A = np.array(sorted(bt.items()), float)
    X["t"] = np.interp(X.block, A[:, 0], A[:, 1]).astype(np.int64)
    ids = json.load(open("s160/cmc_ids.json")); circ = {}
    for tok, v in ids.items():
        p = f"s160/circ/{v['id']}.json"
        if os.path.exists(p):
            s = pd.Series({d: c for d, c, _ in json.load(open(p)) if c})
            if len(s):
                s.index = pd.to_datetime(s.index); circ[tok] = s.sort_index()
    fr = []
    for r in X.itertuples():
        s = circ.get(r.tok)
        if s is None:
            fr.append(np.nan); continue
        k = s.index.searchsorted(pd.Timestamp(int(r.t), unit="s").normalize(), "right") - 1
        fr.append(r.amt / s.iloc[k] if k >= 0 and s.iloc[k] > 0 else np.nan)
    X["frac"] = fr
    X["perp"] = X.tok.map(lambda t: S["toks"][t]["perp"])
    return X.dropna(subset=["frac"])


def window_sum(D, perp, t, h, kr_only):
    d = D.get(perp)
    if d is None:
        return 0.0
    m = (d.t.values > t - h * 3600) & (d.t.values <= t)
    if kr_only:
        m &= d.kr.values
    return float(d.frac.values[m].sum())


def main():
    X = deposits()
    perps = set(X.perp)
    D = {p: g.sort_values("t") for p, g in X.groupby("perp")}
    print("заводов", len(X), "монет", len(perps), flush=True)
    out = []
    for per in PER:
        U = pd.read_pickle(f"s142_{per}.pkl"); U = U[U.s.isin(perps)]
        for r in U.itertuples():
            out.append(dict(test="К2а разлоки", per=per, te=int(r.t), net=r.net, dep=window_sum(D, r.s, int(r.t), 72, False)))
        P = pd.read_pickle(f"s154_pumps_{per}.pkl"); P = P[(P.share >= 0.26) & P.s.isin(perps)]
        for r in P.itertuples():
            out.append(dict(test="К2б пампы со спотом", per=per, te=int(r.t), net=r.net, dep=window_sum(D, r.s, int(r.t), 6, True)))
        O = pd.read_pickle(O9[per])
        O["s"] = O.s.map(lambda x: x[:-4] if x.endswith("USDT") and x not in perps else x)   # в старых выгрузках s88 — «…USDT»
        O = O[O.open9 & (O.share >= 0.2) & (O.r1 >= 0.05) & O.s.isin(perps)]
        for r in O.itertuples():
            out.append(dict(test="К2б ⏰", per=per, te=int(r.t), net=r.S_10_25, dep=window_sum(D, r.s, int(r.t), 6, True)))
    R = pd.DataFrame(out).dropna(subset=["net"])
    for test, thr in (("К2а разлоки", 0.0025), ("К2б пампы со спотом", 0.001), ("К2б ⏰", 0.001)):
        print(f"\n{test} (метка — заводы ≥ {thr:.2%} обращения):")
        T = R[R.test == test]
        for per in PER:
            x = T[T.per == per]; a, b = x[x.dep >= thr], x[x.dep < thr]; d, t = wdiff(a, b)
            print(f"  {per}: с меткой {len(a)} {a.net.mean():+.2%} | без {len(b)} {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")
        a, b = T[T.dep >= thr], T[T.dep < thr]; d, t = wdiff(a, b)
        print(f"  шесть лет: с меткой {len(a)} {a.net.mean():+.2%} | без {len(b)} {b.net.mean():+.2%} | разница {d:+.2%} (t {t:+.1f})")
    R.to_pickle("s161.pkl")


if __name__ == "__main__":
    main()
