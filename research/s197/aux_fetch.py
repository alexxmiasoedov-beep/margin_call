"""s197 — вспомогательные выгрузки для точного T (без цен): только то, без чего T не восстановить.
- эры Polkadot/Kusama: события staking.EraPaid / EraPayout в Statescan (номер эры и время блока конца эры);
- Tezos: TzKT staking/unstake_requests (unlockTime каждого запроса);
- stkAAVE: COOLDOWN_SECONDS() на прошлых блоках (eth_call, публичные RPC) → даты смен;
- GRT EpochManager и LPT RoundsManager (L1): длина эпохи/раунда и точка отсчёта (eth_call);
- TIA: unbonding_time по высотам (архивный REST) → высота смены 21 сут → 14 сут 1 ч.
Кэш — /home/user/mc_data/s197/aux/. User-Agent research-script/1.0."""
import json
import os
import sys
import time
sys.path.insert(0, "/home/user/margin_call/research/s196/study")
from common196 import http  # noqa: E402

AUX = "/home/user/mc_data/s197/aux"
RPC = ["https://gateway.tenderly.co/public/mainnet", "https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io"]


def save(name, obj):
    json.dump(obj, open(f"{AUX}/{name}.json", "w"))


def have(name):
    return os.path.exists(f"{AUX}/{name}.json")


def eras(net):
    name = f"eras_{net}"
    if have(name):
        return
    out = []
    for method in ("EraPaid", "EraPayout"):
        page = 0
        while True:
            d = http(f"https://{net}-api.statescan.io/events?section=staking&method={method}&page={page}&page_size=100",
                     timeout=60)
            items = (d or {}).get("items") or []
            if not items:
                break
            for it in items:
                args = [x.get("value") for x in it.get("args") or []]
                out.append([int(args[0]), it["indexer"]["blockHeight"], it["indexer"]["blockTime"] // 1000])
            page += 1
            time.sleep(0.1)
    out.sort()
    save(name, out)
    print(net, "эр", len(out), out[0] if out else None, out[-1] if out else None, flush=True)


def tezos_requests():
    if have("tezos_requests"):
        return
    rows, last = [], 0
    while True:
        d = http("https://api.tzkt.io/v1/staking/unstake_requests?limit=10000&sort.asc=id"
                 f"&id.gt={last}&select=id,cycle,baker.address,staker.address,requestedAmount,unlockCycle,unlockTime,"
                 "firstTime,lastTime,status")
        if not d:
            break
        rows += d
        last = d[-1]["id"]
        if len(d) < 10000:
            break
    save("tezos_requests", rows)
    print("tezos запросов", len(rows), flush=True)


def eth_call(to, data, block):
    for url in RPC:
        d = http(url, data={"jsonrpc": "2.0", "id": 1, "method": "eth_call",
                            "params": [{"to": to, "data": data}, hex(block)]}, timeout=40, tries=2)
        r = (d or {}).get("result")
        if r and r != "0x":
            return int(r, 16)
    return None


def sel(sig):
    from Crypto.Hash import keccak
    h = keccak.new(digest_bits=256)
    h.update(sig.encode())
    return "0x" + h.hexdigest()[:8]


def aave_cooldown():
    if have("aave_cooldown"):
        return
    stk = "0x4da27a545c0c5B758a6BA100e3a049001de870f5"
    s = sel("COOLDOWN_SECONDS()")
    grid = list(range(11_000_000, 26_400_001, 250_000))
    vals = {b: eth_call(stk, s, b) for b in grid}
    changes = []
    for a, b in zip(grid[:-1], grid[1:]):
        va, vb = vals[a], vals[b]
        if va is not None and vb is not None and va != vb:
            lo, hi = a, b
            while hi - lo > 1:
                m = (lo + hi) // 2
                vm = eth_call(stk, s, m)
                if vm == va:
                    lo = m
                else:
                    hi = m
            changes.append([hi, va, vb])
            print("stkAAVE cooldown", va / 86400, "→", vb / 86400, "сут на блоке", hi, flush=True)
    save("aave_cooldown", {"grid": vals, "changes": changes})


def grt_lpt():
    if have("grt_lpt"):
        return
    out = {}
    em = "0x64F990Bf16552A693dCB043Bb7bf3866c5E05DdB"          # The Graph EpochManager (L1)
    for b in (11_600_000, 13_000_000, 15_000_000, 17_000_000, 19_000_000, 20_500_000):
        out[f"grt_{b}"] = {k: eth_call(em, sel(f"{k}()"), b) for k in
                           ("epochLength", "lastLengthUpdateEpoch", "lastLengthUpdateBlock", "currentEpoch")}
    rm = "0x3984fC4ceEeF1739135476f625D36d6c35c40dC3"          # Livepeer RoundsManager (L1)
    for b in (11_000_000, 12_000_000, 13_000_000, 14_000_000, 14_200_000):
        out[f"lpt_{b}"] = {k: eth_call(rm, sel(f"{k}()"), b) for k in
                           ("roundLength", "lastRoundLengthUpdateRound", "lastRoundLengthUpdateStartBlock", "currentRound")}
    save("grt_lpt", out)
    print(json.dumps(out, indent=0)[:1500], flush=True)


def tia_unbonding():
    if have("tia_unbonding"):
        return
    base = "https://public-celestia-lcd.numia.xyz"

    def ut(h):
        d = http(f"{base}/cosmos/staking/v1beta1/params", headers={"x-cosmos-block-height": str(h)}, timeout=60, tries=3)
        try:
            return d["params"]["unbonding_time"]
        except Exception:
            return None
    # высоты из снимков s196: 2025-10-15 (21 сут) и 2026-03-15 (14 сут)
    snaps = {}
    for f in os.listdir("/home/user/mc_data/s196/cosmos"):
        if f.startswith("tia_"):
            s = json.load(open(f"/home/user/mc_data/s196/cosmos/{f}"))
            snaps[s["date"]] = (s["height"], s["time"])
    lo, hi = snaps["2025-10-15"][0], snaps["2026-03-15"][0]
    u_lo, u_hi = ut(lo), ut(hi)
    while hi - lo > 1:
        m = (lo + hi) // 2
        if ut(m) == u_lo:
            lo = m
        else:
            hi = m
    d = http(f"{base}/cosmos/base/tendermint/v1beta1/blocks/{hi}", timeout=60)
    t = d["block"]["header"]["time"][:19] if d else None
    save("tia_unbonding", {"before": u_lo, "after": u_hi, "height": hi, "time": t})
    print("TIA unbonding_time", u_lo, "→", u_hi, "на высоте", hi, t, flush=True)


if __name__ == "__main__":
    os.makedirs(AUX, exist_ok=True)
    what = sys.argv[1:] or ["eras", "tezos", "aave", "grtlpt", "tia"]
    if "eras" in what:
        eras("polkadot")
        eras("kusama")
    if "tezos" in what:
        tezos_requests()
    if "aave" in what:
        aave_cooldown()
    if "grtlpt" in what:
        grt_lpt()
    if "tia" in what:
        tia_unbonding()
