"""s195 — частота «серийных заводов» (без доходов): один отправитель (не биржа, не чеканка) несколько раз заводит токен
на адреса Binance (сбор s160/raw, переводы ≥ 0,05% нынешнего обращения), доля каждого перевода — к обращению CMC на дату.
Серия: ≥ k переводов одного отправителя одного токена за 14 сут, каждый ≥ f обращения, между переводами ≥ 1 ч;
«новый» отправитель — без заводов этого токена на любые биржи за 90 сут до первого перевода серии.
Событие — момент k-го перевода. Только частоты. Запуск из /home/user/mc_data."""
import glob
import gzip
import json
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s160")
DAY = 86400


def load():
    import events as EV  # noqa: E402  (s160/events.py: CEX, CUST, circ_table, block_times)
    rows = []
    for p in sorted(glob.glob("s160/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    lab = {a: " ".join(v) for a, v in EV.CEX.items()}
    X = X[~X.to.map(lambda a: bool(EV.CUST.search(lab.get(a, ""))))]
    X = X[~X.frm.isin(EV.CEX.keys()) & (X.frm != "0x" + "0" * 40)]
    X["exch"] = X.to.map(lambda a: EV.CEX[a][0])
    anchors = list(range(10_900_000, int(X.block.max()) + 100_000, 100_000))
    bt = EV.block_times(anchors)
    A = np.array(sorted(bt.items()), float)
    X["t"] = np.interp(X.block, A[:, 0], A[:, 1])
    C = EV.circ_table()
    fr = np.full(len(X), np.nan)
    for tok, g in X.groupby("tok"):
        s = C.get(tok)
        if s is None:
            continue
        d = pd.to_datetime(g.t.values.astype(np.int64), unit="s").normalize()
        k = s.index.searchsorted(d, "right") - 1
        v = np.where(k >= 0, s.values[np.maximum(k, 0)], np.nan)
        fr[X.index.get_indexer(g.index)] = g.amt.values / np.where(v > 0, v, np.nan)
    X["frac"] = fr
    X["perp"] = X.tok.map(lambda t: EV.TOK[t]["perp"])
    return X.reset_index(drop=True)


def series(X, f, k=3, win=14 * DAY, new=90 * DAY):
    B = X[(X.exch == "Binance") & (X.frac >= f)].sort_values("t")
    cand = {}
    for (frm, tok), g in B.groupby(["frm", "tok"], sort=False):
        if len(g) >= k:
            cand[(frm, tok)] = g
    if not cand:
        return pd.DataFrame()
    keys = set(cand)
    A = X[[(a, b) in keys for a, b in zip(X.frm, X.tok)]]
    allt = {key: np.sort(g.t.values) for key, g in A.groupby(["frm", "tok"], sort=False)}
    ev = []
    for key, g in cand.items():
        tt = g.t.values
        keep = np.r_[True, np.diff(tt) >= 3600]          # отдельные переводы: ≥ 1 ч между соседними
        tt, fr = tt[keep], g.frac.values[keep]
        if len(tt) < k:
            continue
        a = allt[key]
        for j in range(k - 1, len(tt)):
            if tt[j] - tt[j - k + 1] <= win:
                st = tt[j - k + 1]
                prior = a[(a < st) & (a >= st - new)]
                ev.append(dict(frm=key[0], tok=key[1], perp=g.perp.iloc[0], t=tt[j], start=st, n=k,
                               newdep=len(prior) == 0, cum=fr[j - k + 1:j + 1].sum()))
                break                                    # одно событие на серию (первое k-е)
    return pd.DataFrame(ev)


if __name__ == "__main__":
    import os
    P = "/home/user/mc_data/s195_deposits.pkl"
    if os.path.exists(P):
        X = pd.read_pickle(P)
    else:
        X = load()
        X.to_pickle(P)
    print("заводов (не биржа → биржа, без кастоди):", len(X), "| на Binance:", int((X.exch == "Binance").sum()))
    per = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
           "2024–2026": ("2024-10-01", "2026-10-19")}
    for f in (0.0005, 0.001, 0.002):
        E = series(X, f)
        if not len(E):
            continue
        cells = []
        for p, (a, b) in per.items():
            a, b = pd.Timestamp(a, tz="UTC").timestamp(), pd.Timestamp(b, tz="UTC").timestamp()
            e = E[(E.t >= a) & (E.t < b)]
            mo = (b - a) / (30.4 * DAY)
            cells.append(f"{p}: {len(e) / mo:.1f}/мес (новые {e.newdep.sum() / mo:.1f}; монет {e.perp.nunique()})")
        print(f"f ≥ {f:.2%}, k = 3 за 14 сут: " + "; ".join(cells))
