"""s186 — размер токенов с плечом FTX: выпуск ERC-20 на цепочке (totalSupply на снимках) × цена CMC = оценка AUM.

FTX выпускал BULL/BEAR/HALF/HEDGE как ERC-20 (гибридная модель: создание и погашение на бирже, токен на цепочке).
Полнота выпуска на цепочке не проверена (Rahimian–Clark 2024: у ETCBULL 98,5% выпуска пришлись на 04–10.2022, на кошелёк
FTX) — поэтому AUM здесь — оценка порядка величины.
Снимки — 1-е число каждого месяца 10.2019–11.2022, вызов totalSupply() на исторический блок (архивные узлы без
ключа: Tenderly, MEV Blocker, dRPC — по потоку на узел, пауза между запросами, при 429 — пауза 60 с). Токены — с базовым
активом, у которого есть перп Binance, и BTC/ETH для масштаба.
Итог: /home/user/mc_data/s186/ftx_supply.pkl (снимки), ftx_aum.pkl (дневной AUM по токенам); лог — ftx_supply.log.
Доходы не считаются."""
import json
import os
import pickle
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

import common186 as C

L = C.Log("ftx_supply")
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io", "https://eth.drpc.org"]
_k = [0]


def rpc(method, params, tries=6, k=None):
    for a in range(tries):
        if k is None:
            url = URLS[_k[0] % len(URLS)]
            _k[0] += 1
        else:
            url = URLS[(k + a) % len(URLS)]
        try:
            req = urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                                                "params": params}).encode(),
                                         headers={"User-Agent": "research-script/1.0", "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            time.sleep(0.25)
            if "result" in d:
                return d["result"]
        except urllib.error.HTTPError as e:
            time.sleep(60 if e.code == 429 else 5)
        except Exception:
            time.sleep(5 * (a + 1))
    return None


def block_at(t, cache):
    """Блок с временем ≤ t: интерполяция по опорным блокам и уточнение."""
    if t in cache:
        return cache[t]
    lo, hi = 8_500_000, 16_100_000
    tl = int(rpc("eth_getBlockByNumber", [hex(lo), False])["timestamp"], 16)
    th = int(rpc("eth_getBlockByNumber", [hex(hi), False])["timestamp"], 16)
    for _ in range(30):
        if hi - lo <= 50:
            break
        g = int(lo + (hi - lo) * (t - tl) / max(th - tl, 1))
        g = min(max(g, lo + 1), hi - 1)
        tg = int(rpc("eth_getBlockByNumber", [hex(g), False])["timestamp"], 16)
        if tg <= t:
            lo, tl = g, tg
        else:
            hi, th = g, tg
    cache[t] = lo
    return lo


def main():
    U = pickle.load(open(f"{C.OUT}/lt_universe.pkl", "rb"))
    F = U["F"]
    F = F[F.addr.notna()].reset_index(drop=True)
    days = pickle.load(open(f"{C.OUT}/cmc_lt_daily.pkl", "rb"))["ftx"]
    snaps = []
    for y in range(2019, 2023):
        for m in range(1, 13):
            for d in (1,):
                t = C.ts(f"{y}-{m:02d}-{d:02d}")
                if C.ts("2019-10-01") <= t <= C.ts("2022-11-16"):
                    snaps.append(t)
    bpath = f"{C.OUT}/ftx_blocks.json"
    bc = {int(k): v for k, v in json.load(open(bpath)).items()} if os.path.exists(bpath) else {}
    for t in snaps:
        block_at(t, bc)
    json.dump({str(k): v for k, v in bc.items()}, open(bpath, "w"))
    L("снимков:", len(snaps), "токенов с адресом:", len(F))
    spans = pickle.load(open(f"{C.OUT}/lt_universe.pkl", "rb"))["U"]
    keep = set(spans[(spans.ex == "ftx") & spans.perp].und) | {"BTC", "ETH"}
    F = F[F.und.isin(keep)].reset_index(drop=True)
    L("токенов для снимков (базовый с перпом Binance, BTC, ETH):", len(F))
    spath = f"{C.OUT}/ftx_supply.pkl"
    S = pickle.load(open(spath, "rb")) if os.path.exists(spath) else {}

    def one(arg):
        i, r = arg
        k = i % len(URLS)
        dec = rpc("eth_call", [{"to": r.addr, "data": "0x313ce567"}, "latest"], k=k)
        dec = int(dec, 16) if dec and dec != "0x" else 18
        q = days.get(r.token)
        t_first = (q.index.min() - 31 * C.DAY) if q is not None and len(q) else C.ts("2019-10-01")
        vals = {}
        for t in snaps:
            if t < t_first:
                vals[t] = 0.0
                continue
            v = rpc("eth_call", [{"to": r.addr, "data": "0x18160ddd"}, hex(bc[t])], k=k)
            vals[t] = (int(v, 16) / 10 ** dec) if v and v != "0x" else np.nan
        return r.token, pd.Series(vals)

    todo = [(i, r) for i, r in F.iterrows() if r.token not in S]
    with ThreadPoolExecutor(max_workers=len(URLS)) as ex:
        for n, (tok, ser) in enumerate(ex.map(one, todo)):
            S[tok] = ser
            if n % 10 == 0:
                pickle.dump(S, open(spath, "wb"))
                L(f"  {n + 1}/{len(todo)} {tok}: макс выпуск {np.nanmax(ser.values):.4g}")
    pickle.dump(S, open(spath, "wb"))
    # дневной AUM: выпуск (ступенька от снимка) × цена закрытия CMC
    A = {}
    for tok, s in S.items():
        q = days.get(tok)
        if q is None or not len(q):
            continue
        sup = s.reindex(sorted(set(s.index) | set(q.index))).ffill().reindex(q.index)
        A[tok] = (sup * q.c).rename(tok)
    pickle.dump(A, open(f"{C.OUT}/ftx_aum.pkl", "wb"))
    aum = pd.DataFrame(A).fillna(0.0)
    lev = dict(zip(F.token, F.lev))
    und = dict(zip(F.token, F.und))
    tot = aum.sum(axis=1)
    L("\nсуммарный AUM токенов FTX (по выпуску на цепочке × цена CMC), $ млн, на 1-е число квартала:")
    for t in tot.index:
        d = pd.Timestamp(int(t), unit="s")
        if d.day == 1 and d.month in (1, 4, 7, 10):
            top = aum.loc[t].sort_values(ascending=False).head(6)
            L(f"  {d.date()}: {tot.loc[t] / 1e6:8.1f}; крупнейшие: " +
              ", ".join(f"{k} {v / 1e6:.1f}" for k, v in top.items() if v > 0))
    # множитель ребаланса по базовому активу: M = Σ L(L−1)·AUM (поток $ на единицу дневной доходности)
    M = pd.DataFrame({u: sum(lev[k] * (lev[k] - 1) * aum[k] for k in aum.columns if und[k] == u)
                      for u in sorted(set(und[k] for k in aum.columns))})
    pickle.dump(M, open(f"{C.OUT}/ftx_mult.pkl", "wb"))
    L("\nмножитель ребаланса M = Σ L(L−1)·AUM, $ млн на 100% хода (медиана и максимум за 10.2020–09.2022):")
    t0, t1 = C.ts("2020-10-01"), C.ts("2022-10-01")
    Mp = M[(M.index >= t0) & (M.index < t1)]
    for u in Mp.max().sort_values(ascending=False).index[:30]:
        L(f"  {u:6s} медиана {Mp[u].median() / 1e6:8.2f}, макс {Mp[u].max() / 1e6:8.2f} ({C.iso(Mp[u].idxmax())})")


if __name__ == "__main__":
    main()
