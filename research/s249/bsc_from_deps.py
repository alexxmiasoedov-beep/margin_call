"""Куда адреса пополнения Binance (из Ethereum) переводят токены в BNB Chain — это и есть адреса сметания Binance в BNB Chain."""
import collections, json, sys, time
sys.path.insert(0, ".")
import sqd
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
deps = json.load(open("eth_deps.json"))[:600]
pad = lambda a: "0x" + "0" * 24 + a[2:]
h = sqd.head()
t0 = time.time()
L = sqd.logs(h - 200000, h, topic0=[T], topic1=[pad(a) for a in deps])
print("переводов из адресов пополнения в BNB Chain:", len(L), f"({time.time() - t0:.0f} с)")
to_c = collections.Counter(); to_s = collections.defaultdict(set); tok_c = collections.defaultdict(collections.Counter)
for b, ts, l in L:
    fr = "0x" + l["topics"][1][-40:]; to = "0x" + l["topics"][2][-40:]
    to_c[to] += 1; to_s[to].add(fr); tok_c[to][l["address"]] += 1
for a, n in to_c.most_common(12):
    print(a, "переводов", n, "отправителей", len(to_s[a]), "токенов", len(tok_c[a]))
json.dump({a: [n, len(to_s[a]), len(tok_c[a])] for a, n in to_c.most_common(50)}, open("bsc_collectors.json", "w"))
