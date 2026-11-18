"""s160 — события «крупный завод на биржу» из s160/raw (гипотеза — ВЫВОДЫ.md, записана до расчёта).
1) Строки: получатель — адрес биржи без кастоди и прайм-брокеров; отправитель не помечен как биржа и не нулевой адрес.
2) Доля от обращения: сумма / обращение CMC на дату (дата блока по опорным блокам через каждые 100 тыс.) ≥ 0,5%.
3) Шаг назад: крупнейший приток токена на адрес отправителя за 7 сут (50 400 блоков) до перевода — с адреса биржи → перекладка.
4) Точное время блока; одно событие на монету за 48 ч — отдельно для всех заводов и для чистых.
Итог — s160_events.pkl в папке данных. Запуск из /home/user/mc_data: python3 <repo>/research/s160/events.py"""
import glob
import gzip
import json
import os
import re
import time
import urllib.request

import numpy as np
import pandas as pd

UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io"]
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CUST = re.compile(r"prime|anchorage|falconx|bitcoin suisse|copper|bitgo|fireblocks|cumberland|galaxy|wintermute|amber|matrixport|"
                  r"ceffu|hex trust|komainu|cobo|paxos|custody", re.I)
S = json.load(open("s160/sets.json")); CEX = S["cex"]; TOK = S["toks"]


def post(body, tries=8):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(URLS[k % 2], data=json.dumps(body).encode(), headers=UA),
                                                      timeout=90).read())
        except Exception:
            time.sleep(2 + 3 * k)
    return None


BT_CACHE, HOP_CACHE = "s160/cache_blocktime.json", "s160/cache_hop.json"


def _load(p):
    return json.load(open(p)) if os.path.exists(p) else {}


def block_times(blocks):
    cache = _load(BT_CACHE)
    out = {int(b): cache[str(b)] for b in blocks if str(int(b)) in cache}
    blocks = sorted(set(int(b) for b in blocks) - set(out))
    for i in range(0, len(blocks), 50):
        part = blocks[i:i + 50]
        r = post([{"jsonrpc": "2.0", "id": j, "method": "eth_getBlockByNumber", "params": [hex(b), False]} for j, b in enumerate(part)])
        for x in r or []:
            if x.get("result"):
                out[part[x["id"]]] = int(x["result"]["timestamp"], 16)
    cache.update({str(k): v for k, v in out.items()})
    json.dump(cache, open(BT_CACHE, "w"))
    return out


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def hop_source(tok, frm, block):
    """Крупнейший приток токена на адрес отправителя за 50 400 блоков до перевода: (адрес, биржа ли)."""
    q = {"fromBlock": hex(max(block - 50400, 0)), "toBlock": hex(block - 1), "address": tok, "topics": [T0, None, pad(frm)]}
    r = post({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]})
    logs = (r or {}).get("result")
    if logs is None:
        return None, None
    tot = {}
    for x in logs:
        a = "0x" + x["topics"][1][-40:]
        tot[a] = tot.get(a, 0) + (int(x["data"], 16) if x["data"] not in ("0x", "") else 0)
    if not tot:
        return "", False
    src = max(tot, key=tot.get)
    return src, src in CEX


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
    rows = []
    for p in sorted(glob.glob("s160/raw/b*.json.gz")):
        rows += json.load(gzip.open(p, "rt"))
    X = pd.DataFrame(rows, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    print("строк в сборе", len(X), flush=True)
    lab = {a: " ".join(v) for a, v in CEX.items()}
    X = X[~X.to.map(lambda a: bool(CUST.search(lab.get(a, ""))))]
    X = X[~X.frm.isin(CEX.keys()) & (X.frm != "0x" + "0" * 40)]
    X["exch"] = X.to.map(lambda a: CEX[a][0])
    # опорные блоки → приблизительная дата для обращения
    anchors = list(range(10_900_000, int(X.block.max()) + 100_000, 100_000))
    bt = block_times(anchors); A = np.array(sorted(bt.items()), float)
    X["t_approx"] = np.interp(X.block, A[:, 0], A[:, 1])
    C = circ_table()
    frac = []
    for r in X.itertuples():
        s = C.get(r.tok)
        if s is None:
            frac.append(np.nan); continue
        d = pd.Timestamp(int(r.t_approx), unit="s").normalize()
        k = s.index.searchsorted(d, "right") - 1
        frac.append(r.amt / s.iloc[k] if k >= 0 and s.iloc[k] > 0 else np.nan)
    X["frac"] = frac
    E = X[X.frac >= 0.005].copy()
    print("переводов ≥ 0,5% обращения", len(E), flush=True)
    tm = block_times(E.block.unique()); E["t"] = E.block.map(tm)
    E = E.dropna(subset=["t"]); E["t"] = E.t.astype(np.int64)
    src, fromx = [], []
    hc = _load(HOP_CACHE)
    for k, r in enumerate(E.itertuples()):
        key = f"{r.tok}:{r.frm}:{int(r.block)}"
        if key in hc:
            a, b = hc[key]
        else:
            a, b = hop_source(r.tok, r.frm, int(r.block))
            if a is not None:
                hc[key] = [a, b]
        src.append(a); fromx.append(b)
        if k % 500 == 0:
            print("шаг назад", k, "из", len(E), flush=True)
            json.dump(hc, open(HOP_CACHE, "w"))
    json.dump(hc, open(HOP_CACHE, "w"))
    E["src"], E["from_exch"] = src, fromx
    E["perp"] = E.tok.map(lambda t: TOK[t]["perp"]); E["sym"] = E.tok.map(lambda t: TOK[t]["sym"])
    E = E.sort_values("t").reset_index(drop=True)
    for col, mask in (("first_all", np.ones(len(E), bool)), ("first_clean", (E.from_exch == False).values)):  # noqa: E712
        keep, last = np.zeros(len(E), bool), {}
        for i in np.flatnonzero(mask):
            r = E.iloc[i]
            if r.t - last.get(r.perp, -10 ** 12) >= 48 * 3600:
                keep[i] = True; last[r.perp] = r.t
        E[col] = keep
    E.to_pickle("s160_events.pkl")
    print("событий: все", int(E.first_all.sum()), "чистые", int(E.first_clean.sum()),
          "перекладка", int((E.from_exch == True).sum()), "не определено", int(E.from_exch.isna().sum()), flush=True)  # noqa: E712


if __name__ == "__main__":
    main()
