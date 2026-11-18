"""s167 area B, step 2: offline label coverage of senders (and their 7-day upstream source from s160 hop cache) for
large transfers to exchanges. Label sets: Etherscan label dumps (brianleect/etherscan-labels style JSON already on disk),
Dune spellbook funds_ethereum + dao multisig_ethereum, DefiLlama treasury owners. Prints coverage by event and by sender."""
import json, re, sys, collections
SP = "/home/user/mc_data/s168"
ev = json.load(open(f"{SP}/work/b_events.json"))
hop = json.load(open("/home/user/mc_data/s160/cache_hop.json"))
CEX = json.load(open("/home/user/mc_data/s160/sets.json"))["cex"]
L = {}
def put(a, src, name):
    L.setdefault(a.lower(), []).append((src, name))
for f in ("/home/user/mc_data/s160/labels/es_accounts.json", f"{SP}/labels/comb.json"):
    for a, v in json.load(open(f)).items():
        put(a, "etherscan", (v.get("name") or "") + " [" + ",".join(v.get("labels") or []) + "]")
for fn, src in (("sb_labels_funds_ethereum.sql", "spellbook_funds"), ("sb_labels_dao_multisig_ethereum.sql", "spellbook_dao_multisig")):
    t = open(f"{SP}/dl/{fn}").read()
    for a, n in re.findall(r"'ethereum'\s*,\s*(0x[0-9a-fA-F]{40})\s*,\s*'([^']*)'", t):
        put(a, src, n)
for a, ps in json.load(open(f"{SP}/work/llama_treasury.json")).items():
    put(a, "llama_treasury", ",".join(ps[:3]))
CAT = [("mm_otc", re.compile(r"wintermute|\bgsr\b|dwf|amber|jump|cumberland|galaxy|falconx|b2c2|auros|alameda|qcp|genesis trading|market ?mak|\botc\b|kairon|gotbit|flowdesk|keyrock", re.I)),
       ("vc_fund", re.compile(r"capital|ventures?|fund\b|\[.*fund|a16z|paradigm|polychain|pantera|multicoin|three arrows|dragonfly|spartan|hashed|delphi|1kx|framework|variant|defiance|investment|venture-capital|ngc|signum|kirin|parafi|cms holdings", re.I)),
       ("team_treasury_vesting", re.compile(r"team|treasury|vest|foundation|dao|multisig|reserve|ecosystem|token.?sale|company-funds|deployer|unlock|airdrop|distributor|grant|community|incentive|rewards|marketing|llama_treasury|spellbook_dao", re.I)),
       ("dex_bridge_contract", re.compile(r"uniswap|sushi|balancer|curve|1inch|0x|bridge|router|pool|dex|aggregator|vault|staking|lending|aave|compound", re.I)),
       ("airdrop_hunter_etc", re.compile(r"airdrop-hunter|blocked|phish|hack|exploit|scam", re.I))]
def classify(a):
    if not a:
        return None
    if a in CEX:
        return "cex"
    ls = L.get(a)
    if not ls:
        return None
    s = " ".join(f"{src} {n}" for src, n in ls)
    for c, rx in CAT:
        if rx.search(s):
            return c
    return "other_label"
ce = collections.Counter(); cs = collections.Counter(); cu = collections.Counter(); n_hop = 0
senders = {}
for e in ev:
    c = classify(e["frm"]); ce[c or "unlabelled"] += 1
    senders.setdefault(e["frm"], c)
    h = hop.get(f"{e['tok']}:{e['frm']}:{e['block']}")
    if h is not None:
        n_hop += 1
        src = h[0]
        cu[classify(src) or ("no_inflow" if src == "" else "unlabelled")] += 1
for s, c in senders.items():
    cs[c or "unlabelled"] += 1
tot = len(ev)
print("label addresses loaded", len(L))
print("events", tot, "- by sender label:", {k: f"{v} ({v/tot*100:.1f}%)" for k, v in ce.most_common()})
print("distinct senders", len(senders), {k: v for k, v in cs.most_common()})
print("events with hop source", n_hop, "- by upstream label:", {k: f"{v} ({v/max(n_hop,1)*100:.1f}%)" for k, v in cu.most_common()})
