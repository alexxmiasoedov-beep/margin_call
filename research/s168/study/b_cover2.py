"""s167 area B, step 3: event-level coverage with all free label sources. Effective sender = the 7-day upstream source
(s160 hop cache) when the direct sender is an exchange deposit address (Blockscout 'Deposit' tags) — the sweep case.
Classes: cex re-shuffle / deposit-sweep with unknown depositor / team-treasury-vesting / VC-fund / MM-OTC / Safe multisig /
dex-bridge-contract / other label / unlabelled. Prints totals for all years and for 10.2024–10.2026."""
import json, re, collections
SP = "/home/user/mc_data/s168"
ev = json.load(open(f"{SP}/work/b_events.json"))
hop = json.load(open("/home/user/mc_data/s160/cache_hop.json"))
CEX = json.load(open("/home/user/mc_data/s160/sets.json"))["cex"]
BS = json.load(open(f"{SP}/work/bs_meta.json"))
L = {}
def put(a, src, name): L.setdefault(a.lower(), []).append(f"{src}:{name}")
for f in ("/home/user/mc_data/s160/labels/es_accounts.json", f"{SP}/labels/comb.json"):
    for a, v in json.load(open(f)).items():
        put(a, "etherscan", (v.get("name") or "") + " [" + ",".join(v.get("labels") or []) + "]")
for fn, src in (("sb_labels_funds_ethereum.sql", "spellbook_funds"), ("sb_labels_dao_multisig_ethereum.sql", "spellbook_dao_multisig")):
    for a, n in re.findall(r"'ethereum'\s*,\s*(0x[0-9a-fA-F]{40})\s*,\s*'([^']*)'", open(f"{SP}/dl/{fn}").read()):
        put(a, src, n)
for a, ps in json.load(open(f"{SP}/work/llama_treasury.json")).items():
    put(a, "llama_treasury", ",".join(ps[:3]))
for a, tags in BS.items():
    for t in tags: put(a, "blockscout", t)
import csv
for x in csv.DictReader(open(f"{SP}/dl/ethl_accounts.csv", encoding="utf-8", errors="ignore")):
    if x["chainId"] == "1":
        put(x["address"], "ethlabels", (x["label"] or "") + " " + re.sub(r"0x[0-9a-fA-F]{6,}", "", x["nameTag"] or ""))
DEP = re.compile(r"deposit|\bdep\b", re.I)
CAT = [("mm_otc", re.compile(r"wintermute|\bgsr\b|dwf|amber|jump|cumberland|galaxy digital|falconx|\bb2c2\b|auros|alameda|qcp|genesis trading|market ?mak|\botc\b|kairon|gotbit|flowdesk|keyrock", re.I)),
       ("vc_fund", re.compile(r"capital\b|ventures?\b|:fund\b|\[.*fund|a16z|paradigm|polychain|pantera|multicoin|three arrows|dragonfly|spartan|hashed|delphi|1kx|framework|variant|defiance|investment|venture-capital|ngc|signum|kirin|parafi|cms holdings", re.I)),
       ("team_treasury_vesting", re.compile(r"team|treasury|vest|foundation|dao|reserve|ecosystem|token.?sale|company-funds|deployer|unlock|airdrop|distributor|grant|community|incentive|rewards|marketing|llama_treasury|spellbook_dao", re.I)),
       ("safe_multisig", re.compile(r"safe|multisig|gnosis", re.I)),
       ("dex_bridge_contract", re.compile(r"uniswap|sushi|balancer|curve|1inch|bridge|router|pool|dex|aggregator|vault|staking|lending|aave|compound|mev bot|beacon", re.I))]
def cls(a):
    if a in CEX: return "cex"
    ls = L.get(a)
    if not ls: return None
    s = " ".join(ls)
    if DEP.search(s) and "blockscout" in s: return "deposit_addr"
    for c, rx in CAT:
        if rx.search(s): return c
    return "other_label"
def run(sel, title):
    c = collections.Counter(); n = 0
    for e in sel:
        n += 1
        k = cls(e["frm"])
        h = hop.get(f"{e['tok']}:{e['frm']}:{e['block']}")
        if k == "deposit_addr" or k is None:
            if h is None:
                c["sweep/no-hop" if k == "deposit_addr" else "unlabelled(no hop)"] += 1; continue
            src = h[0]
            if src == "":
                c["no 7d inflow"] += 1; continue
            u = cls(src)
            if u in ("cex",):
                c["cex re-shuffle"] += 1
            elif u is None:
                c["unlabelled"] += 1
            elif u == "deposit_addr":
                c["cex re-shuffle"] += 1
            else:
                c["up:" + u] += 1
        else:
            c[k] += 1
    print(f"== {title}: events {n}")
    for k, v in c.most_common():
        print(f"   {k:28s} {v:6d}  {v/n*100:5.1f}%")
    lab = sum(v for k, v in c.items() if re.search(r"team|vc_fund|mm_otc|safe", k))
    print(f"   -> insider-type labelled (team/treasury/vesting, VC, MM/OTC, Safe): {lab} ({lab/n*100:.1f}%)")
run(ev, "all 10.2020–11.2026")
run([e for e in ev if e["date"] >= "2024-10-01"], "10.2024–11.2026")
