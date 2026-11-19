"""s181 — уточнение классов получателей крупных выходов собственного токена из казны (treasury_outflows.py):
площадки продажи (роутеры DEX и CoW, MEV-боты и решатели, кастоди и ММ, биржи) против пулов ликвидности; для
неизвестных получателей переводов ≥ 0,5% обращения — тип адреса по публичному RPC (eth_getCode; у контракта —
getThreshold() Safe), второй шаг «→ биржа» за 7, 30 и 90 сут по сбору s160. Bancor исключён: его «владельцы» —
контракты протокола (обмен через пулы BNT), а не казна. Только частоты; доходы не считаются."""
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
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io", "https://ethereum.publicnode.com"]
ROUTER = re.compile(r"router|settlement|aggregat|exchange proxy|executor|swap|zap|1inch|0x[: ]|paraswap|odos|"
                    r"openocean|matcha|kyberswap: operator|mev|solver|resolver", re.I)
POOL = re.compile(r"pair|pool|\blp\b|vault|liquidity|token\b|farming|staking|gauge", re.I)
SALE = {"биржа", "кастоди/ММ", "площадка продажи (роутер, CoW, MEV)", "→ биржа за 7 сут"}


def batch(reqs, tries=6):
    for k in range(tries):
        try:
            body = json.dumps(reqs).encode()
            with urllib.request.urlopen(urllib.request.Request(URLS[k % 3], data=body, headers=UA), timeout=120) as r:
                out = json.load(r)
                if isinstance(out, list):
                    return out
        except Exception:
            time.sleep(3 + 5 * k)
    return []


def addr_types(addrs):
    path = f"{C.OUT}/addr_types.json"
    cache = json.load(open(path)) if os.path.exists(path) else {}
    todo = [a for a in addrs if a not in cache]
    for i in range(0, len(todo), 8):
        part = todo[i:i + 8]
        res = batch([{"jsonrpc": "2.0", "id": j, "method": "eth_getCode", "params": [a, "latest"]} for j, a in enumerate(part)])
        code = {part[x["id"]]: x.get("result") for x in res if isinstance(x, dict)}
        cons = [a for a in part if (code.get(a) or "0x") not in ("0x", "0x0", None)]
        thr = {}
        if cons:
            r2 = batch([{"jsonrpc": "2.0", "id": j, "method": "eth_call",
                         "params": [{"to": a, "data": "0xe75235b8"}, "latest"]} for j, a in enumerate(cons)])
            thr = {cons[x["id"]]: x.get("result") for x in r2 if isinstance(x, dict)}
        for a in part:
            c = code.get(a)
            if c is None:
                continue
            if c in ("0x", "0x0"):
                cache[a] = "EOA"
            else:
                t = thr.get(a)
                cache[a] = "Safe" if (t and t != "0x" and len(t) == 66 and 0 < int(t, 16) < 100) else "контракт"
        time.sleep(0.3)
    json.dump(cache, open(path, "w"))
    return cache


def main():
    X = pd.read_pickle(f"{C.OUT}/treasury_out.pkl")
    X = X[~X.protos.map(lambda s: "bancor" in s)]
    L = T.labels()
    lab = X.to.map(lambda a: L.get(a, ""))
    X["dst2"] = X.dst
    X.loc[(X.dst == "DEX/агрегатор") & lab.str.contains(ROUTER) , "dst2"] = "площадка продажи (роутер, CoW, MEV)"
    X.loc[(X.dst == "DEX/агрегатор") & ~lab.str.contains(ROUTER), "dst2"] = "пул ликвидности/прочее DeFi"
    X.loc[(X.dst == "другая метка") & lab.str.contains(r"mev", case=False), "dst2"] = "площадка продажи (роутер, CoW, MEV)"
    G = X.groupby(["tok", "perp", "frm", "to", "dst2", "day"]).agg(t=("t", "min"), amt=("amt", "sum"),
                                                                  frac=("frac", "sum")).reset_index()
    big = G[(G.frac >= 0.005) & ~G.dst2.isin(["та же казна/другая казна", "сжигание"])].copy()
    unk = sorted(set(big[big.dst2.isin(["неизвестный адрес", "другая метка"])].to))
    print(f"переводов ≥ 0,5% обращения (без перекладки и сжигания): {len(big)}; неизвестных получателей {len(unk)}", flush=True)
    ty = addr_types(unk)
    big["atype"] = big.to.map(lambda a: ty.get(a, ""))
    # второй шаг по сбору s160 для неизвестных получателей
    S = json.load(open(f"{C.D}/s160/sets.json"))
    CEX = S["cex"]
    import glob
    import gzip
    raw = []
    for p in sorted(glob.glob(f"{C.D}/s160/raw/b*.json.gz")):
        raw += json.load(gzip.open(p, "rt"))
    R = pd.DataFrame(raw, columns=["block", "tok", "frm", "to", "amt", "tx", "li"])
    R = R[R.frm.isin(set(big.to)) & R.to.isin(CEX.keys())]
    R["t"] = T.block_time()(R.block.values)
    R["exch"] = R.to.map(lambda a: CEX[a][0])
    for w in (7, 30, 90):
        hit = []
        for r in big.itertuples():
            y = R[(R.frm == r.to) & (R.tok == r.tok) & (R.t >= r.t) & (R.t <= r.t + w * DAY)]
            hit.append(float(y.amt.sum()) / r.amt if len(y) else 0.0)
        big[f"cex{w}"] = hit
    big["cls"] = big.dst2
    m = big.dst2.isin(["неизвестный адрес", "другая метка"])
    big.loc[m, "cls"] = "неизвестный: " + big.loc[m, "atype"].replace("", "?")
    big.loc[m & (big.cex7 >= 0.25), "cls"] = "→ биржа за 7 сут"
    big.to_pickle(f"{C.OUT}/treasury_big.pkl")
    print("\nКрупные выходы из казны (≥ 0,5% обращения за сутки одному получателю), по классам, в месяц:")
    for c, y in big.groupby("cls"):
        print(f"  {c:40s} {len(y):4d}  " + " / ".join(f"{C.month_counts(y.t, p):5.2f}" for p in C.PER) +
              f"   медиана {y.frac.median():.2%}; доля дошедших до биржи за 30 / 90 сут "
              f"{(y.cex30 >= 0.25).mean():.0%} / {(y.cex90 >= 0.25).mean():.0%}")
    sale = big[big.cls.isin(SALE)]
    z = T.one_per(sale, "perp", 7 * DAY)
    print(f"\n«Продажа видна» (биржа, кастоди/ММ, роутер/CoW/MEV, или посредник → биржа за 7 сут), 1 на перп за 7 сут: " +
          " / ".join(f"{C.month_counts(z.t, p):5.2f}" for p in C.PER) + f"  (всего {len(z)}, перпов {z.perp.nunique()})")
    z2 = T.one_per(big, "perp", 7 * DAY)
    print("все крупные выходы, 1 на перп за 7 сут: " + " / ".join(f"{C.month_counts(z2.t, p):5.2f}" for p in C.PER))
    dla = json.load(open(f"{C.OUT}/dla_treasury.json"))
    own = {}
    for r in dla:
        for a in r["owners"]:
            own.setdefault(a, set()).add(r["proto"])
    big["proto"] = big.frm.map(lambda a: ",".join(sorted(own.get(a, []))))
    print("\nпротоколы крупных выходов:", big.groupby("proto").size().sort_values(ascending=False).head(15).to_dict())
    print("протоколы «продажа видна»:", sale.groupby(sale.frm.map(lambda a: ",".join(sorted(own.get(a, []))))).size()
          .sort_values(ascending=False).to_dict())


if __name__ == "__main__":
    main()
