"""s181 — прямые переводы с адресов казначейств DefiLlama-Adapters на адреса бирж в сборе s160 (s160/raw: все переводы
≥ 0,05% обращения 261 ERC-20 токена с перпом на 5331 адрес бирж, 10.2020–11.2026). Владельцы — dla_parse.py (строгий
список owners/ownTokenOwners) и, для сравнения, широкий список s168 (work/llama_treasury.json). Доля от обращения — CMC
на дату (s160/circ). Только число переводов и событий в месяц по периодам; доходы не считаются."""
import glob
import gzip
import json
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|"
                  r"matrixport|ceffu|hex trust|komainu|cobo|paxos|custody", re.I)


def load_raw():
    rows = []
    for p in sorted(glob.glob(f"{C.D}/s160/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    bt = json.load(open(f"{C.D}/s160/cache_blocktime.json"))
    A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    X["t"] = np.interp(X.block, A[:, 0], A[:, 1])
    return X


def circ_table():
    ids = json.load(open(f"{C.D}/s160/cmc_ids.json"))
    out = {}
    for tok, v in ids.items():
        p = f"{C.D}/s160/circ/{v['id']}.json"
        if os.path.exists(p):
            s = pd.Series({d: c for d, c, _ in json.load(open(p)) if c})
            if len(s):
                s.index = pd.to_datetime(s.index)
                out[tok] = s.sort_index()
    return out


def frac_col(X, Ct):
    fr = np.full(len(X), np.nan)
    for tok, idx in X.groupby("tok").groups.items():
        s = Ct.get(tok)
        if s is None:
            continue
        d = pd.to_datetime(X.loc[idx, "t"], unit="s").dt.normalize().values
        k = np.searchsorted(s.index.values, d, "right") - 1
        v = np.where(k >= 0, s.values[np.clip(k, 0, None)], np.nan)
        fr[X.index.get_indexer(idx)] = X.loc[idx, "amt"].values / v
    return fr


def per_month(t, per):
    return C.month_counts(t, per)


def main():
    S = json.load(open(f"{C.D}/s160/sets.json"))
    CEX, TOK = S["cex"], S["toks"]
    dla = json.load(open(f"{C.OUT}/dla_treasury.json"))
    own_by = {}
    for r in dla:
        for a in r["owners"]:
            if a in CEX or a in TOK:
                continue
            own_by.setdefault(a, set()).add(r["proto"])
    ptok = {}
    for r in dla:
        ptok.setdefault(r["proto"], set()).update(r["ownTokens"])
    loose = json.load(open(f"{C.D}/s168/work/llama_treasury.json"))
    loose = {a: set(v) for a, v in loose.items() if a not in CEX and a not in TOK}
    X = load_raw()
    print("строк в сборе s160", len(X), flush=True)
    X = X[~X.to.map(lambda a: bool(CUST.search(" ".join(CEX.get(a, [])))))]
    X["exch"] = X.to.map(lambda a: CEX[a][0])
    X["frac"] = frac_col(X, circ_table())
    X["perp"] = X.tok.map(lambda t: TOK[t]["perp"])
    for lab, owners in (("строгий список (owners)", own_by), ("широкий список s168", loose)):
        Y = X[X.frm.isin(owners.keys())].copy()
        Y["proto"] = Y.frm.map(lambda a: ",".join(sorted(owners[a])))
        Y["own"] = [bool(ptok.get(p, set()) & {tok}) or any(TOK[tok]["sym"].lower() in q.lower() or q.lower() in TOK[tok]["id"]
                                                         for q in pr.split(","))
                    for tok, p, pr in zip(Y.tok, Y.proto.str.split(",").str[0], Y.proto)]
        print(f"\n{lab}: адресов {len(owners)}; переводов на биржи (≥ 0,05% обращения) {len(Y)}; отправителей {Y.frm.nunique()}; "
              f"протоколов {Y.proto.nunique()}; собственный токен — {int(Y.own.sum())}")
        for thr in (0.0005, 0.001, 0.005):
            y = Y[Y.frac >= thr].sort_values("t")
            keep, last = [], {}
            for r in y.itertuples():
                if r.t - last.get(r.perp, -1e12) >= 48 * 3600:
                    keep.append(r.Index); last[r.perp] = r.t
            z = y.loc[keep]
            fr = [per_month(z.t, p) for p in C.PER]
            fo = [per_month(z[z.own].t, p) for p in C.PER]
            print(f"  ≥ {thr:.2%}: событий (1 на перп за 48 ч) в месяц " + " / ".join(f"{v:5.2f}" for v in fr) +
                  f"; собственный токен " + " / ".join(f"{v:5.2f}" for v in fo) + f"; всего {len(z)}")
        z = Y[Y.frac >= 0.0005]
        mon = pd.to_datetime(z.t, unit="s").dt.strftime("%Y-%m").value_counts().sort_index()
        print("  переводов ≥ 0,05% по месяцам (только месяцы с переводами):", mon.to_dict())
        print("  биржи:", z.exch.value_counts().head(6).to_dict())
        print("  протоколы (переводов):", z.groupby("proto").size().sort_values(ascending=False).head(12).to_dict())
        print("  монеты:", z.groupby("perp").size().sort_values(ascending=False).head(12).to_dict())
        Y.to_pickle(f"{C.OUT}/treasury_cex_{'strict' if 'строгий' in lab else 'loose'}.pkl")
    # для сравнения: все заводы s160 ≥ 0,5% (не биржа → биржа), 1 на перп за 48 ч
    W = X[(X.frac >= 0.005) & ~X.frm.isin(CEX.keys())].sort_values("t")
    keep, last = [], {}
    for r in W.itertuples():
        if r.t - last.get(r.perp, -1e12) >= 48 * 3600:
            keep.append(r.Index); last[r.perp] = r.t
    W = W.loc[keep]
    print("\nдля сравнения — все заводы ≥ 0,5% от небирж (1 на перп за 48 ч), в месяц: " +
          " / ".join(f"{per_month(W.t, p):5.1f}" for p in C.PER))


if __name__ == "__main__":
    main()
