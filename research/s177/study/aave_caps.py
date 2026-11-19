"""s177 — «лимиты» займа в DeFi: как часто Aave v3 (Ethereum) меняет потолки займа и предложения, замораживает
резервы, и как часто займ альткоина упирается в потолок. Без доходов и цен.

Данные: логи PoolConfigurator Aave v3 Ethereum через публичные узлы без ключа (eth_getLogs); подписи событий
хешируются узлом (web3_sha3); займ по монетам в ед. токена — DefiLlama (кэш lend_events.py).
Запуск: python3 -I aave_caps.py [папка данных]
"""
import json
import os
import pickle
import sys
import time
import urllib.request
from collections import Counter, defaultdict

import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
OUT = os.path.join(D, "s177", "aave_caps_logs.json")
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
CONFIGURATOR = "0x64b761d848206f447fe2dd461b0c635ec39ebb27"  # Aave v3 Ethereum Core, PoolConfigurator (proxy)
START = 16291000  # развёртывание Aave v3 Ethereum, 01.2023
SIGS = ["BorrowCapChanged(address,uint256,uint256)", "SupplyCapChanged(address,uint256,uint256)",
        "ReserveFrozen(address)", "ReserveUnfrozen(address)", "ReserveBorrowing(address,bool)",
        "SiloedBorrowingChanged(address,bool,bool)", "ReserveInterestRateStrategyChanged(address,address,address)",
        "ReserveInterestRateDataChanged(address,address,bytes)", "ReserveFactorChanged(address,uint256,uint256)",
        "CollateralConfigurationChanged(address,uint256,uint256,uint256)", "ReserveInitialized(address,address,address,address,address)",
        "ReservePaused(address,bool)", "DebtCeilingChanged(address,uint256,uint256)"]


def rpc(method, params, tries=4):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for a in range(tries):
        url = URLS[a % len(URLS)]
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=60))
            if "result" in r:
                return r["result"]
            if method == "eth_call":
                return None  # ошибка EVM повторяется на любом узле
            print("  ошибка узла", url.split("/")[2], str(r.get("error"))[:100], flush=True)
        except Exception as e:  # сеть: пауза и повтор
            print("  сеть", url.split("/")[2], type(e).__name__, str(e)[:60], flush=True)
        time.sleep(3 * (a + 1))
    return None


def sym_of(addr):
    res = rpc("eth_call", [{"to": addr, "data": "0x95d89b41"}, "latest"])  # symbol()
    try:
        b = bytes.fromhex(res[2:])
        if len(b) >= 96:
            n = int.from_bytes(b[32:64], "big")
            return b[64:64 + n].decode(errors="ignore").upper()
        return b.rstrip(b"\0").decode(errors="ignore").upper()
    except Exception:
        return addr[:10]


def dec_of(addr):
    res = rpc("eth_call", [{"to": addr, "data": "0x313ce567"}, "latest"])  # decimals()
    try:
        return int(res, 16)
    except Exception:
        return 18


def fetch():
    if os.path.exists(OUT):
        return json.load(open(OUT))
    topics = {rpc("web3_sha3", ["0x" + s.encode().hex()]): s for s in SIGS}
    print("подписи:", {v.split("(")[0]: k[:10] for k, v in topics.items()})
    head = int(rpc("eth_blockNumber", []), 16)
    logs, b, step = [], START, 200000
    while b <= head:
        e = min(b + step - 1, head)
        r = rpc("eth_getLogs", [{"address": CONFIGURATOR, "fromBlock": hex(b), "toBlock": hex(e)}])
        if r is None:
            step = max(step // 4, 5000)
            if step == 5000:
                b = e + 1
            continue
        logs += r
        b = e + 1
        time.sleep(0.3)
    ts = {}
    for blk in sorted({l["blockNumber"] for l in logs}):
        h = rpc("eth_getBlockByNumber", [blk, False])
        ts[blk] = int(h["timestamp"], 16) if h else None
        time.sleep(0.1)
    out = {"topics": topics, "logs": logs, "ts": ts}
    json.dump(out, open(OUT, "w"))
    return out


def main():
    d = fetch()
    topics, logs, ts = d["topics"], d["logs"], d["ts"]
    print(f"логов PoolConfigurator: {len(logs)}")
    logs = [l for l in logs if l["topics"][0] in topics]  # только события с индексом «актив»
    print(f"из них известных событий по активам: {len(logs)}")
    assets = sorted({"0x" + l["topics"][1][-40:] for l in logs if len(l["topics"]) > 1})
    sy = {a: sym_of(a) for a in assets}
    dc = {a: dec_of(a) for a in assets}
    stable = {"USDC", "USDT", "DAI", "GHO", "USDE", "SUSDE", "LUSD", "FRAX", "CRVUSD", "PYUSD", "RLUSD", "USDS",
              "SDAI", "EURC", "USDTB", "FDUSD", "TUSD", "USDP", "BUSD", "USD0", "USDG", "EUSDE", "SYRUPUSDC"}
    eth_btc = {"WETH", "WSTETH", "RETH", "CBETH", "WEETH", "OSETH", "ETHX", "RSETH", "EZETH", "WBTC", "CBBTC",
               "TBTC", "LBTC", "SWETH", "EBTC", "FBTC", "SOLVBTC"}
    rows = []
    for l in logs:
        nm = topics.get(l["topics"][0], "?").split("(")[0]
        a = "0x" + l["topics"][1][-40:] if len(l["topics"]) > 1 else None
        t = ts.get(l["blockNumber"])
        data = l["data"][2:]
        old = new = None
        if nm in ("BorrowCapChanged", "SupplyCapChanged") and len(data) >= 128:
            old, new = int(data[:64], 16), int(data[64:128], 16)
        sa = sy.get(a) or ""
        other = sa.startswith(("PT-", "SYRUP")) or sa in {"XAUT", "BTC.B", "CIRBTC", "MUSD", "TETH", "PAXG"}
        cls = "стейбл" if sa in stable else ("ETH/BTC" if sa in eth_btc else ("прочее" if other else "альт"))
        rows.append((pd.to_datetime(t, unit="s"), nm, sy.get(a), cls, old, new))
    e = pd.DataFrame(rows, columns=["t", "ev", "sym", "cls", "old", "new"])
    months = (e.t.max() - e.t.min()).days / 30.44
    print(f"период {e.t.min().date()} – {e.t.max().date()}, месяцев {months:.1f}")
    tab = e.groupby(["ev", "cls"]).size().unstack(fill_value=0)
    print("\nСобытий за весь период (в месяц):")
    for ev, r in tab.iterrows():
        print(f"  {ev:36s} " + ", ".join(f"{c} {v} ({v / months:.2f})" for c, v in r.items()))
    alts = sorted(set(e[e.cls == "альт"].sym))
    print("\nАльты в Aave v3 Ethereum:", ", ".join(alts))
    bc = e[(e.ev == "BorrowCapChanged") & (e.cls == "альт")]
    up = (bc.new > bc.old) | (bc.old == 0)
    print(f"Потолок займа альтов: повышений {up.sum()}, понижений {(~up).sum()}, в месяц {len(bc) / months:.2f}")
    # займ альта к потолку: DefiLlama (ед. токена) против потолка (целые токены) по дням
    panel, _ = pickle.load(open(os.path.join(D, "s177", "lend_panel.pkl"), "rb"))
    a3 = panel[(panel.slug == "aave-v3") & (panel.chain == "Ethereum")]
    caps = defaultdict(list)
    for _, r in bc.sort_values("t").iterrows():
        caps[r.sym].append((r.t.normalize(), r.new))
    hits = []
    for s, ch in caps.items():
        g = a3[a3.sym == s]
        if g.empty:
            continue
        ser = g.set_index(pd.to_datetime(g.day * 86400, unit="s")).bor_u.sort_index()
        capser = pd.Series({t: v for t, v in ch}).sort_index()
        capser = capser[~capser.index.duplicated(keep="last")].reindex(ser.index, method="ffill")
        ratio = ser / capser.replace(0, float("nan"))
        hi = ratio >= 0.9
        first = hi & ~hi.shift(1, fill_value=False)
        for t in ratio.index[first.values]:
            hits.append((s, t, round(float(ratio.loc[t]), 2)))
    print(f"\nДней-входов займа альта в ≥ 90% потолка (Aave v3 Ethereum): {len(hits)} за {months:.0f} мес. "
          f"({len(hits) / months:.2f} в мес.)")
    print("  " + ", ".join(f"{s} {t.date()}" for s, t, _ in hits[:30]))


if __name__ == "__main__":
    main()
