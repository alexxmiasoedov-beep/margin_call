"""s181 — происхождение токенов у заводов на Binance ≥ 0,5% обращения (события s160_events.pkl, один на перп за 48 ч —
множество, из которого 🐋 берёт входы до фильтра спокойного рынка): шаги назад до 3 по крупнейшему притоку токена
за 7 сут до перевода (шаг 1 — кэш s160/cache_hop.json, шаги 2–3 — eth_getLogs через публичный RPC без ключа).
Класс конца цепочки: биржа (куплено на бирже), DEX/роутер, выпуск (адрес 0x0), казначейство DefiLlama-Adapters
(строгий список), инсайдерская метка (вестинг, команда, фонд, казна, мультисиг проекта, инвестор — метки Etherscan
dawsbot/eth-labels), ММ (s168/work/mm_core.json), долгий держатель (притока не было 7 сут). Частота в месяц по
периодам — «завод не с рынка» как возможный двойник 🐋. Выборка — по 350 событий на период (random_state=181), оценка
в месяц = доля в выборке × частота всех событий периода. Приближение: шаг 2 ищет приток за 7 сут до блока завода
(кэш s160 не хранит блок перевода шага 1). Только частоты; доходы не считаются."""
import csv
import json
import os
import re
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402
import treasury_outflows as T  # noqa: E402

DAY = 86400
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io"]  # MEV Blocker — запасной, куски по 8400 блоков
CACHE = f"{C.OUT}/hop_cache.json"
INS = re.compile(r"vesting|vester|sablier|hedgey|tokentable|token table|llamapay|team|foundation|treasury|multisig|"
                 r"multi-sig|\bdao\b|ecosystem|investor|token-sale|ico-wallet|genesis|deployer|founder|advisor|reserve|"
                 r"timelock|grant|incentive|fund\b", re.I)
DEX = re.compile(r"uniswap|sushi|pool|pair|router|1inch|cow protocol|gpv2|0x[: ]|dex\b|curve|balancer|kyber|bancor|"
                 r"paraswap|odos|openocean|mev", re.I)
MINT = {"0x0000000000000000000000000000000000000000"}


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def rpc(url, q, timeout=90):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=timeout) as r:
            d = json.load(r)
        return d.get("result"), d.get("error")
    except Exception as e:
        return None, str(e)[:80]


def inflows(key, prefer=0):
    """Притоки токена на адрес за 50 400 блоков до блока: Tenderly одним запросом или MEV Blocker кусками по 8400 блоков
    (у него предел 10 тыс.); prefer — с какого узла начинать, второй — запасной."""
    tok, frm, block = key.split(":")
    block = int(block)
    a0 = max(block - 50400, 0)
    q = {"fromBlock": hex(a0), "toBlock": hex(block - 1), "address": tok, "topics": [T0, None, pad(frm)]}
    if prefer == 1:
        r = mev_chunks(q, a0, block)
        if r is not None:
            return r
    for k in range(5):
        r, e = rpc(URLS[0], q)
        if isinstance(r, list):
            time.sleep(0.25)
            return r
        time.sleep(5 + 5 * k)
    return mev_chunks(q, a0, block)


def mev_chunks(q, a0, block):
    out = []
    for s0 in range(a0, block, 8400):
        qq = dict(q, fromBlock=hex(s0), toBlock=hex(min(s0 + 8399, block - 1)))
        for k in range(4):
            r, e = rpc(URLS[1], qq)
            if isinstance(r, list):
                out += r
                break
            time.sleep(2 + 4 * k)
        else:
            return None
    return out


def hop_batch(keys, cache):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(2) as ex:
        res = list(ex.map(lambda kv: inflows(kv[1], kv[0] % 2), enumerate(keys)))
    for key, logs in zip(keys, res):
        if logs is None:
            continue
        tot, blk = {}, {}
        for y in logs:
            a = "0x" + y["topics"][1][-40:]
            tot[a] = tot.get(a, 0) + (int(y["data"], 16) if y["data"] not in ("0x", "") else 0)
            blk[a] = max(blk.get(a, 0), int(y["blockNumber"], 16))
        src = max(tot, key=tot.get) if tot else ""
        cache[key] = [src, blk.get(src, 0), sorted(tot)[:20]]


def main():
    S = json.load(open(f"{C.D}/s160/sets.json"))
    CEX = S["cex"]
    dla = json.load(open(f"{C.OUT}/dla_treasury.json"))
    TRE = {a for r in dla for a in r["owners"]}
    MM = {a.lower() for a in json.load(open(f"{C.D}/s168/work/mm_core.json"))}
    L = T.labels()
    E = pd.read_pickle(f"{C.D}/s160_events.pkl")
    E = E[(E.exch == "Binance") & (E.frac >= 0.005)].sort_values("t")
    E = T.one_per(E, "perp", 2 * DAY)
    ALL = E.copy()
    parts = []
    for p, (a, b) in C.PER.items():
        a, b = (pd.Timestamp(x, tz="UTC").timestamp() for x in (a, b))
        y = E[(E.t >= a) & (E.t < b)]
        parts.append(y.sample(min(len(y), 350), random_state=181))
    E = pd.concat(parts).sort_values("t")
    hc0 = json.load(open(f"{C.D}/s160/cache_hop.json"))
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}

    def cls(a):
        if not a:
            return "долгий держатель (нет притока 7 сут)"
        if a in MINT:
            return "выпуск (0x0)"
        if a in CEX:
            return "биржа"
        if a in TRE:
            return "казначейство DefiLlama"
        if a in MM:
            return "ММ"
        lab = L.get(a, "")
        if lab and DEX.search(lab):
            return "DEX/роутер"
        if lab and INS.search(lab):
            return "инсайдерская метка"
        return None

    # шаг 1 — из кэша s160; цепочки шагов 2–3
    state = []
    for r in E.itertuples():
        k = f"{r.tok}:{r.frm}:{int(r.block)}"
        h = hc0.get(k)
        state.append(dict(t=r.t, perp=r.perp, tok=r.tok, frm=r.frm, block=int(r.block), src1=(h or [None])[0],
                          path=[r.frm]))
    print(f"событий (Binance, ≥ 0,5%, 1 на перп за 48 ч): {len(ALL)}; в выборке (до 350 на период): {len(state)}",
          flush=True)
    for s in state:
        s["end"] = None
        if s["src1"] is None:
            s["end"] = "не определено"
            continue
        c1 = cls(s["src1"])
        s["hops"] = 1
        if c1:
            s["end"] = c1
    # шаги 2 и 3
    for hop in (2, 3):
        todo = []
        for s in state:
            if s["end"] is None:
                prev = s["src1"] if hop == 2 else s["src2"]
                pb = s["block"] if hop == 2 else s["b2"]
                key = f"{s['tok']}:{prev}:{max(pb, 1)}"
                s[f"key{hop}"] = key
                if key not in cache:
                    todo.append(key)
        todo = sorted(set(todo))
        print(f"шаг {hop}: запросов {len(todo)}", flush=True)
        for i in range(0, len(todo), 10):
            hop_batch(todo[i:i + 10], cache)
            if i % 100 == 0:
                json.dump(cache, open(CACHE, "w"))
                print(f"  {i}/{len(todo)}", flush=True)
            time.sleep(0.2)
        json.dump(cache, open(CACHE, "w"))
        for s in state:
            if s["end"] is None:
                h = cache.get(s.get(f"key{hop}"))
                if h is None:
                    s["end"] = "не определено"
                    continue
                s[f"src{hop}"], s[f"b{hop}"] = h[0], h[1] if h[1] else s["block"]
                s["hops"] = hop
                c = cls(h[0])
                if c:
                    s["end"] = c
        # для шага 2 нужен блок притока шага 1: берём блок события (окно 7 сут назад от него) — приближение
        if hop == 2:
            for s in state:
                s.setdefault("b2", s["block"])
    for s in state:
        if s["end"] is None:
            s["end"] = "безымянный адрес после 3 шагов"
    X = pd.DataFrame(state)
    X.to_pickle(f"{C.OUT}/whale_origin.pkl")
    print("\nКлассы происхождения (доля событий по периодам):")
    for p in C.PER:
        a, b = (pd.Timestamp(x, tz="UTC").timestamp() for x in C.PER[p])
        y = X[(X.t >= a) & (X.t < b)]
        print(f"  {p} (событий {len(y)}, {C.month_counts(y.t, p):.1f} в месяц): " +
              "; ".join(f"{k} {v:.0%}" for k, v in y.end.value_counts(normalize=True).items()))
    groups = {"«не с рынка» (выпуск, казначейство, инсайдерская метка, ММ)":
              ["выпуск (0x0)", "казначейство DefiLlama", "инсайдерская метка", "ММ"],
              "…и долгие держатели": ["выпуск (0x0)", "казначейство DefiLlama", "инсайдерская метка", "ММ",
                                     "долгий держатель (нет притока 7 сут)"],
              "только казначейство или инсайдерская метка": ["казначейство DefiLlama", "инсайдерская метка"],
              "«с рынка» (биржа, DEX/роутер)": ["биржа", "DEX/роутер"]}
    print("\nОценка в месяц = доля в выборке × все события периода:")
    for lab, cl in groups.items():
        out = []
        for p, (a, b) in C.PER.items():
            a, b = (pd.Timestamp(x, tz="UTC").timestamp() for x in (a, b))
            y = X[(X.t >= a) & (X.t < b)]
            share = y.end.isin(cl).mean() if len(y) else float("nan")
            out.append(f"{share * C.month_counts(ALL.t, p):5.2f} ({share:.0%})")
        print(f"  {lab:60s} " + " / ".join(out))
    print("шагов до класса:", X.hops.value_counts().to_dict())


if __name__ == "__main__":
    main()
