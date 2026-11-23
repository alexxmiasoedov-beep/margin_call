"""Куда в BNB Chain переводили токены адреса пополнения Binance (из Ethereum, s195) в разные месяцы 2021–2024 гг. (для проверки на старых периодах)"""
import collections, json, sys, time
sys.path.insert(0, ".")
import pandas as pd
import sqd
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
pad = lambda a: "0x" + "0" * 24 + a[2:]
D = pd.read_pickle("/home/user/mc_data/s195_deposits.pkl")
D = D[D.exch == "Binance"]
res = {}
for day in ("2021-03-15", "2021-09-15", "2022-03-15", "2022-09-15", "2023-03-15", "2023-09-15", "2024-03-15", "2024-07-15"):
    t0 = pd.Timestamp(day, tz="UTC").timestamp()
    deps = D[(D.t >= t0 - 30 * 86400) & (D.t < t0)].frm.drop_duplicates().tolist()[:600]
    b0 = sqd.block_guess(t0); b1 = sqd.block_guess(t0 + 86400)
    L = sqd.logs(b0, b1, topic0=[T], topic1=[pad(a) for a in deps])
    c = collections.Counter(); s = collections.defaultdict(set); k = collections.defaultdict(set)
    for b, ts, l in L:
        to = "0x" + l["topics"][2][-40:]; c[to] += 1; s[to].add(l["topics"][1]); k[to].add(l["address"])
    print(day, f"блоки {b0}–{b1}, адресов {len(deps)}, переводов {len(L)}", flush=True)
    for a, n in c.most_common(5):
        print("   ", a, "переводов", n, "отправителей", len(s[a]), "токенов", len(k[a]), flush=True)
    res[day] = [(a, n, len(s[a]), len(k[a])) for a, n in c.most_common(10)]
json.dump(res, open("hist_coll_old.json", "w"), indent=1)
