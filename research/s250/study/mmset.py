"""Собрать открытые метки ММ (Ethereum) из уже скачанных источников: Blockscout (s168 mm_core), eth-labels (s168 dl), yevadrian etherscan-labels."""
import json, csv, re, collections
FIRMS = [("wintermute", r"wintermute"), ("amber", r"amber"), ("jump", r"jump (trading|crypto)"), ("galaxy", r"galaxy digital|^galaxy:"),
         ("dwf", r"dwf ?labs"), ("gsr", r"^gsr"), ("b2c2", r"b2c2"), ("cumberland", r"^cumberland(?!.*(river|council))"), ("falconx", r"falcon ?x"),
         ("auros", r"auros"), ("qcp", r"qcp"), ("genesis", r"genesis trading"), ("alameda", r"alameda"), ("nonco", r"^nonco \d")]
def firm(name):
    n = re.sub(r"0x[0-9a-fA-F]{6,40}", " ", name.lower())  # не искать имена внутри hex-адреса (b2c2!)
    if "endaoment" in n or "charity" in n or "binance dep" in n: return None
    for f, rx in FIRMS:
        if re.search(rx, n): return f
    return None
out = {}
for a, nm in json.load(open("/home/user/mc_data/s168/work/mm_addrs.json")).items():
    f = firm(nm)
    if f: out.setdefault(a.lower(), (f, "blockscout:" + nm))
for r in csv.reader(open("/home/user/mc_data/s168/dl/ethl_accounts.csv", encoding="utf-8", errors="ignore")):
    if len(r) < 4 or r[1] != "1": continue
    f = firm(r[3])
    if f and "fringe" not in r[3].lower() and "avs" not in r[3].lower(): out.setdefault(r[0].lower(), (f, "eth-labels:" + r[3]))
for r in csv.reader(open("dl/yevadrian_etherscan-labels_main_accounts_fund.csv", encoding="utf-8", errors="ignore")):
    if len(r) < 2: continue
    f = firm(r[1])
    if f: out.setdefault(r[0].lower(), (f, "etherscan-labels:" + r[1]))
json.dump(out, open("work/mm_labels_eth.json", "w"))
c = collections.Counter(v[0] for v in out.values()); print(len(out), c.most_common())
src = collections.Counter(v[1].split(":")[0] for v in out.values()); print(src)
