"""s196 — монеты в обращении по дням (CMC data-api без ключа, как s160/cmc_circ.py): список CMC → id по тикеру
(наибольшая капитализация, ручные исключения), история `cryptocurrency/historical` по годам с 01.09.2020.
Итог — /home/user/mc_data/s196/circ/<SYM>.json ([[дата, обращение, цена]]) и cmc_ids.json."""
import json
import os
import sys
import time
from common196 import http, OUT

API = "https://api.coinmarketcap.com/data-api/v3"
SYMS = ("ATOM TIA INJ SEI DYDX OSMO AKT KAVA AXL NTRN DYM SAGA BAND LUNA LUNC FET OM ZETA INIT BABY IP DOT KSM NEAR APT "
        "SUI SOL TRX EGLD ROSE XTZ EOS ICP AVAX STX FIL CKB GRT LPT CRV PENDLE CVX BAL YFI AERO STG FXS RDNT THE CAKE XVS "
        "AAVE API3 SKL T EIGEN JUP PYTH HNT HIVE STEEM FTM S GLMR ASTR ICX ONE THETA ZIL FLOW POL MATIC HYPE STRK KAITO "
        "DRIFT WCT LISTA IOTX SCRT CELO MINA ALGO XRP ADA TON BERA ENA").split()
FIX = {"LUNA": 20314, "LUNC": 4172, "T": 17751, "S": 32684, "THE": 24237, "IP": 35626, "OM": 6536, "STRK": 22691,
       "SEI": 23149, "INIT": 36191, "BABY": 32198, "API3": 7737, "FET": 3773, "FTM": 3513, "MATIC": 3890, "POL": 28321,
       "APT": 21794, "ZETA": 21259, "SAGA": 30372, "DYM": 28932, "NTRN": 26680, "TIA": 22861, "DYDX": 28324,
       "EIGEN": 30494, "HYPE": 32196, "KAITO": 35824, "WCT": 36126, "LISTA": 30297, "JUP": 29210, "PYTH": 28177,
       "AERO": 29270, "DRIFT": 31278, "BERA": 24647}


def ids():
    def f():
        L = []
        for start in (1, 5001):
            d = http(f"{API}/cryptocurrency/listing?start={start}&limit=5000&sortBy=market_cap&sortType=desc&convert=USD"
                     f"&cryptoType=all&tagType=all&audited=false")
            L += (d or {}).get("data", {}).get("cryptoCurrencyList") or []
        by = {}
        for x in L:
            mc = next((q.get("marketCap") for q in x.get("quotes") or [] if q.get("name") == "USD"), 0) or 0
            by.setdefault(x["symbol"].upper(), []).append((mc, x["id"], x["slug"]))
        out = {}
        for s in SYMS:
            if s in FIX:
                out[s] = FIX[s]
            elif by.get(s):
                out[s] = max(by[s])[1]
        return out
    p = f"{OUT}/cmc_ids.json"
    if os.path.exists(p):
        return json.load(open(p))
    v = f()
    json.dump(v, open(p, "w"))
    return v


def hist(sym, cid):
    p = f"{OUT}/circ/{sym}.json"
    if os.path.exists(p):
        return
    out = []
    edges = [1598918400 + k * 31_536_000 for k in range(8)]
    for t0, t1 in zip(edges[:-1], edges[1:]):
        d = http(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={t0}&timeEnd={min(t1, 1795000000)}"
                 f"&interval=1d")
        for q in ((d or {}).get("data") or {}).get("quotes") or []:
            u = q["quote"]
            out.append([q["timeClose"][:10], u.get("circulatingSupply"), u.get("close")])
        time.sleep(0.4)
        if t1 > 1795000000:
            break
    json.dump(out, open(p, "w"))


def circ_series(sym):
    """дата → (обращение, цена) для символа; None — нет файла."""
    p = f"{OUT}/circ/{sym}.json"
    if not os.path.exists(p):
        return None
    return {d: (c, px) for d, c, px in json.load(open(p))}


def main():
    os.makedirs(f"{OUT}/circ", exist_ok=True)
    M = ids()
    print("id найдено", len(M), "из", len(SYMS), "нет:", [s for s in SYMS if s not in M], flush=True)
    for s in (sys.argv[1:] or SYMS):
        if s in M:
            hist(s, M[s])
    for s in SYMS:
        c = circ_series(s)
        if c:
            ks = sorted(k for k, v in c.items() if v[0])
            if ks:
                print(f"{s:7s} id {M[s]:6d} дни {len(ks):5d} {ks[0]} … {ks[-1]} обращение {c[ks[-1]][0]:,.0f}", flush=True)
            else:
                print(f"{s:7s} id {M[s]:6d} — нет обращения", flush=True)


if __name__ == "__main__":
    main()
