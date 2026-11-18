"""s167: extract treasury owner addresses (EVM) from DefiLlama-Adapters registries/treasury.js and projects/treasury/*.js.
Heuristic: every 0x40-hex literal in these files, minus token addresses (ownTokens / token lists are mixed in, so we
drop addresses that are known ERC-20 tokens from s160 sets.json plus coreAssets). Output: {address: [project,...]}"""
import glob, json, re, sys
root, out = sys.argv[1], sys.argv[2]
toks = set(json.load(open("/home/user/mc_data/s160/sets.json"))["toks"])
res = {}
def add(addr, proj):
    a = addr.lower()
    if a in toks:
        return
    res.setdefault(a, set()).add(proj)
txt = open(f"{root}/registries/treasury.js").read()
# split registry into protocol blocks: keys like 'treasury/<name>' or <name>: {
blocks = re.split(r"\n\s*['\"]?([A-Za-z0-9_\-./ ]+?)['\"]?\s*:\s*\{\s*\n", txt)
cur = "registry"
for i, b in enumerate(blocks):
    if i % 2 == 1:
        cur = b.strip(); continue
    for m in re.finditer(r"0x[0-9a-fA-F]{40}", b):
        # skip lines that look like token lists
        line = b[max(0, b.rfind("\n", 0, m.start())):b.find("\n", m.end())]
        if re.search(r"ownTokens|tokens\s*:|ADDRESSES\.|Token|TOKEN", line):
            continue
        add(m.group(0), cur)
for p in glob.glob(f"{root}/projects/treasury/*.js"):
    name = p.split("/")[-1][:-3]
    for line in open(p):
        if re.search(r"ownTokens|tokens\s*:|ADDRESSES\.|[Tt]oken", line):
            continue
        for m in re.finditer(r"0x[0-9a-fA-F]{40}", line):
            add(m.group(0), name)
json.dump({k: sorted(v) for k, v in res.items()}, open(out, "w"))
print("treasury-like addresses", len(res), "projects", len({p for v in res.values() for p in v}))
