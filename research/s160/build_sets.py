import json, re
s=open('labels/cex_evms.sql').read()
rows=re.findall(r"\(\s*(0x[0-9a-fA-F]{40})\s*,\s*'([^']*)'\s*,\s*'([^']*)'", s)
cex={a.lower():(n,d) for a,n,d in rows}
bs=json.load(open('labels/exchange_1.json'))
for a in bs:
    cex.setdefault(a.lower(),('blockscout-exchange',''))
print('cex addresses (eth+evm union)', len(cex))
pm=json.load(open('perp_map.json'))
toks={r['eth'].lower():r for r in pm if r.get('eth') and r['eth'].startswith('0x')}
print('eth tokens', len(toks))
json.dump({'cex':cex,'toks':toks},open('sets.json','w'))
