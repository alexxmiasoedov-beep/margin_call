"""s196 — расписанные выходы в Ethereum по логам (eth_getLogs на публичных RPC без ключа: Tenderly, MEV Blocker,
publicnode), блоки с 10 950 000 (≈ 28.09.2020):
- veCRV, veFXS, veSTG, veBAL: Deposit(provider, value, locktime↑, type, ts) / Withdraw — дата конца блокировки записана
  в событии (неделя, четверг 00:00 UTC);
- vePENDLE: NewLockPosition(user, amount, expiry) / Withdraw;
- veYFI: ModifyLock(sender, user, amount, locktime, ts);
- API3: ScheduledUnstake(user, amount, shares, scheduledFor, userShares) — вывод через 7 сут, дата в событии;
- stkAAVE: Cooldown(user) (v1, без суммы) / Cooldown(user, amount);
- GRT (L1 до 2024): StakeDelegatedLocked(indexer, delegator, shares, tokens, until) — эпоха конца;
- LPT (L1 до 02.2022): Unbond(delegate, delegator, lockId, amount, withdrawRound).
Итог — /home/user/mc_data/s196/evm/<имя>.json.gz: [блок, tx, topics, data]."""
import gzip
import json
import os
import sys
import time
from common196 import http, OUT

URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io", "https://ethereum-rpc.publicnode.com"]
FIRST = 10_950_000
T = {
    "Deposit": "0x4566dfc29f6f11d13a418c26a02bef7c28bae749d4de47e4e6a7cddea6730d59",
    "Withdraw": "0xf279e6a1f5e320cca91135676d9cb6e44ca8a08c0b88342bcdb1144f6511b568",
    "NewLockPosition": "0xb1a3371956c54dc1d83695b4a006b051c8313ee986e533b6b964e77c9066fc2c",
    "ScheduledUnstake": "0x251830cd12788c7474148132132ab205112e7b9bba739f0e69c8d4a6a54e2159",
    "Cooldown1": "0xf52f50426b32362d3e6bb8cb36b7074756b224622def6352a59eac7f66ebe6e8",
    "Cooldown2": "0x8a05f911d8ab7fc50fec37ef4ba7f9bfcb1a3c191c81dcd824ad0946c4e20d65",
    "StakeDelegatedLocked": "0x0430183f84d9c4502386d499da806543dee1d9de83c08b01e39a6d2116c43b25",
    "Unbond": "0x2d5d98d189bee5496a08db2a5948cb7e5e786f09d17d0c3f228eb41776c24a06",
    "ModifyLock": "0x01affbd18fb24fa23763acc978a6bb9b9cd159b1cc733a15f3ea571d691cabc1",
}
JOBS = {
    "vecrv": ("0x5f3b5DfEb7B28CDbD7FAba78963EE202a494e2a2", ["Deposit", "Withdraw"], 10_950_000),
    "vefxs": ("0xc8418aF6358FFddA74e09Ca9CC3Fe03Ca6aDC5b0", ["Deposit", "Withdraw"], 11_900_000),
    "vestg": ("0x0e42acBD23FAee03249DAFF896b78d7e79fBD58E", ["Deposit", "Withdraw"], 14_400_000),
    "vebal": ("0xC128a9954e6c874eA3d62ce62B468bA073093F25", ["Deposit", "Withdraw"], 14_400_000),
    "vependle": ("0x4f30A9D41B80ecC5B94306AB4364951AE3170210", ["NewLockPosition", "Withdraw2"], 16_000_000),
    "veyfi": ("0x90c1f9220d90d3966FbeE24045EDd73E1d588aD5", ["ModifyLock"], 16_500_000),
    "api3": ("0x6dd655f10d4b9E242aE186D9050B68F725c76d76", ["ScheduledUnstake"], 11_800_000),
    "stkaave": ("0x4da27a545c0c5B758a6BA100e3a049001de870f5", ["Cooldown1", "Cooldown2"], 10_950_000),
    "grt_l1": ("0xF55041E37E12cD407ad00CE2910B8269B01263b9", ["StakeDelegatedLocked"], 11_400_000),
    "lpt_l1": ("0x511Bc4556D823Ae99630aE8de28b9B80Df90eA2e", ["Unbond"], 10_950_000),
}
# vePENDLE Withdraw(address indexed user, uint128 amount)
T["Withdraw2"] = None


def rpc(i, method, params):
    d = http(URLS[i % len(URLS)], data={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=120, tries=1)
    if d is None:
        return None, "net"
    return d.get("result"), d.get("error")


def logs(addr, topics, a, b, k=0, depth=0):
    q = {"fromBlock": hex(a), "toBlock": hex(b), "address": addr, "topics": [topics]}
    err = None
    for attempt in range(6):
        r, e = rpc(k + attempt, "eth_getLogs", [q])
        if isinstance(r, list):
            return r
        err = str(e).lower()
        if any(s in err for s in ("more than", "limit", "too many", "exceed", "range", "size")) and b > a:
            m = (a + b) // 2
            return logs(addr, topics, a, m, k, depth + 1) + logs(addr, topics, m + 1, b, k, depth + 1)
        time.sleep(3 + 3 * attempt)
    if b > a and depth < 12:
        m = (a + b) // 2
        return logs(addr, topics, a, m, k + 1, depth + 1) + logs(addr, topics, m + 1, b, k + 1, depth + 1)
    raise RuntimeError(f"{addr} {a}-{b}: {err}")


def topic_of(name):
    if name == "Withdraw2":
        from Crypto.Hash import keccak
        h = keccak.new(digest_bits=256)
        h.update(b"Withdraw(address,uint128)")
        return "0x" + h.hexdigest()
    return T[name]


def job(name):
    addr, evs, start = JOBS[name]
    os.makedirs(f"{OUT}/evm", exist_ok=True)
    p = f"{OUT}/evm/{name}.json.gz"
    if os.path.exists(p):
        return
    last, _ = rpc(0, "eth_blockNumber", [])
    last = int(last, 16)
    tops = [topic_of(e) for e in evs]
    rows = []
    step = 200_000
    for a in range(start, last + 1, step):
        b = min(a + step - 1, last)
        for x in logs(addr, tops, a, b):
            rows.append([int(x["blockNumber"], 16), x["transactionHash"], x["topics"], x["data"]])
        if (a - start) // step % 10 == 0:
            print(name, "блок", a, "логов", len(rows), flush=True)
    with gzip.open(p, "wt") as f:
        json.dump(rows, f)
    print(name, "готово, логов", len(rows), flush=True)


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(JOBS)):
        try:
            job(n)
        except Exception as e:
            print(n, "ошибка", repr(e)[:300], flush=True)
