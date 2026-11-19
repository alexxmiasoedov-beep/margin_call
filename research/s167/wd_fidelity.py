"""s167 — сверка правила бота 🐋 (scanner._wd_event) с бэктестом: все переводы архива s160 на адреса Binance (s160/raw,
10.2020–11.2026) подаются в функцию бота по порядку блоков, как ответы eth_getLogs; метки — bot/cex_labels.tsv; монеты
в обращении — CMC на дату (как в бэктесте). События бота сравниваются с событиями «первый завод на Binance за 48 ч»
(live_variant.py, вариант бота) из s160_events.pkl. Запуск из /home/user/mc_data: python3 <repo>/research/s167/wd_fidelity.py"""
import glob
import gzip
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
import scanner  # noqa: E402

scanner.log = lambda *a: None


def circ_table():
    ids = json.load(open("s160/cmc_ids.json")); out = {}
    for tok, v in ids.items():
        p = f"s160/circ/{v['id']}.json"
        if os.path.exists(p):
            s = pd.Series({d: c for d, c, _ in json.load(open(p)) if c})
            if len(s):
                s.index = pd.to_datetime(s.index); out[tok] = s.sort_index()
    return out


def main():
    lab = scanner._wd_labels(); assert lab, "нет bot/cex_labels.tsv"
    S = json.load(open("s160/sets.json")); TOK = S["toks"]
    binance = set(lab["bin"])
    rows = []
    for p in sorted(glob.glob("s160/raw/b*.json.gz")):
        rows += [r for r in json.load(gzip.open(p, "rt")) if r[3] in binance]
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"]).sort_values(["block", "li"]).reset_index(drop=True)
    bt = {int(k): v for k, v in json.load(open("s160/cache_blocktime.json")).items()}
    A = np.array(sorted(bt.items()), float)
    X["t_approx"] = np.interp(X.block, A[:, 0], A[:, 1])
    C = circ_table()
    print("переводов на Binance в архиве", len(X), flush=True)
    w, dec, cache = {}, {a: 0 for a in TOK}, {}
    tok = {a: [v["perp"], v["sym"], 0.0, 0] for a, v in TOK.items()}
    ev = []
    for r in X.itertuples():
        s = C.get(r.tok)
        if s is None:
            continue
        k = s.index.searchsorted(pd.Timestamp(int(r.t_approx), unit="s").normalize(), "right") - 1
        if k < 0 or s.iloc[k] <= 0:
            continue
        tok[r.tok][2] = float(s.iloc[k])                         # монеты в обращении на дату — как в бэктесте
        ts = bt.get(int(r.block))
        x = {"address": r.tok, "topics": [scanner.WD_TRANSFER, "0x" + "0" * 24 + r.frm[2:], "0x" + "0" * 24 + r.to[2:]],
             "data": hex(int(round(r.amt))), "blockNumber": hex(int(r.block)), "logIndex": hex(int(r.li)),
             "transactionHash": r.tx}
        if ts:
            x["blockTimestamp"] = hex(int(ts))
        before = dict(w.get("pend", {}))
        scanner._wd_event(w, lab, tok, dec, x, cache)
        after = w.get("pend", {})
        for fs, pe in after.items():
            if before.get(fs) is not pe:
                ev.append((fs, int(pe["t"])))
        w["pend"] = {}
    B = pd.DataFrame(ev, columns=["perp", "t"]).drop_duplicates()
    E = pd.read_pickle("s160_events.pkl").sort_values("t").reset_index(drop=True)
    E = E[E.exch == "Binance"]
    keep, last = [], {}
    for r in E.itertuples():
        if r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600:
            keep.append((r.perp, int(r.t))); last[r.perp] = r.t
    R = pd.DataFrame(keep, columns=["perp", "t"]).drop_duplicates()
    a, b = set(map(tuple, R.values)), set(map(tuple, B.values))
    print(f"событий бэктеста (первый завод на Binance за 48 ч): {len(a)} | событий правила бота: {len(b)} | общих {len(a & b)} | "
          f"только в бэктесте {len(a - b)} | только у бота {len(b - a)}")
    for nm, d in (("только в бэктесте", sorted(a - b)[:10]), ("только у бота", sorted(b - a)[:10])):
        if d:
            print(" ", nm + ":", [(p, pd.Timestamp(t, unit="s").strftime("%Y-%m-%d %H:%M")) for p, t in d])


if __name__ == "__main__":
    main()
