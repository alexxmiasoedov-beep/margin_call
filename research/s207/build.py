"""s207 — таблица выводов с Binance из сбора collect_wd.py: доля к обращению CMC на дату, тип получателя (небиржевой
адрес, другая биржа, кастоди, сжигание), перп. Только суммы и время, без цен после события.
Запуск из /home/user/mc_data: python3 <repo>/research/s207/build.py → /home/user/mc_data/s207_withdrawals.pkl"""
import glob
import gzip
import importlib.util
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "/home/user/mc_data"


def ev_module():
    spec = importlib.util.spec_from_file_location("s160_events", os.path.join(HERE, "..", "s160", "events.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    os.chdir(OUT)
    E6 = ev_module()
    CEX, TOK = E6.CEX, E6.TOK
    rows = []
    for p in sorted(glob.glob("s207/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    print("строк в сборе", len(X), flush=True)
    lab = {a: " ".join(v) for a, v in CEX.items()}
    zero = "0x" + "0" * 40
    X["kind"] = "wallet"
    X.loc[X.to.isin(CEX.keys()), "kind"] = "exch"
    X.loc[X.to.map(lambda a: bool(E6.CUST.search(lab.get(a, "")))), "kind"] = "custody"
    X.loc[X.to.isin(CEX.keys()) & X.to.map(lambda a: CEX.get(a, [""])[0] == "Binance"), "kind"] = "internal"
    X.loc[X.to == zero, "kind"] = "burn"
    X["to_exch"] = X.to.map(lambda a: CEX[a][0] if a in CEX else "")
    bt = json.load(open("s160/cache_blocktime.json"))
    A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
    X["t"] = np.interp(X.block, A[:, 0], A[:, 1]).astype(np.int64)
    C = E6.circ_table()
    fr = np.full(len(X), np.nan)
    for tok, idx in X.groupby("tok").groups.items():
        s = C.get(tok)
        if s is None:
            continue
        d = pd.to_datetime(X.loc[idx, "t"], unit="s").dt.normalize().values
        k = s.index.values.searchsorted(d, "right") - 1
        c = np.where(k >= 0, s.values[np.maximum(k, 0)], np.nan)
        fr[X.index.get_indexer(idx)] = X.loc[idx, "amt"].values / np.where(c > 0, c, np.nan)
    X["frac"] = fr
    X["perp"] = X.tok.map(lambda t: (TOK.get(t) or {}).get("perp"))
    X = X[(X.frac >= 0.0005) & X.perp.notna()].reset_index(drop=True)
    X.to_pickle(f"{OUT}/s207_withdrawals.pkl")
    print("выводов ≥ 0,05% с перпом:", len(X), "| по типу получателя:", X.kind.value_counts().to_dict(), flush=True)
    w = X[(X.kind == "wallet") & (X.frac >= 0.005)].sort_values("t")
    keep, last = [], {}
    for r in w.itertuples():
        keep.append(r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600)
        if keep[-1]:
            last[r.perp] = r.t
    w = w[keep]
    w["y"] = pd.to_datetime(w.t, unit="s").dt.year
    print("выводы ≥ 0,5% на небиржевой адрес, первый у монеты за 48 ч, по годам:", w.groupby("y").size().to_dict(), flush=True)


if __name__ == "__main__":
    main()
