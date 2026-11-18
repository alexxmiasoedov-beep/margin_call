import re, sys, html, json, collections, datetime
h = open(sys.argv[1], encoding='utf-8', errors='replace').read()
m = re.search(r'<table[^>]*id="table_16"[^>]*>(.*?)</table>', h, re.S)
rows = re.findall(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.S)
data = collections.defaultdict(list)
for r in rows:
    c = [html.unescape(re.sub(r'<[^>]+>', '', x)).strip() for x in re.findall(r'<td[^>]*>(.*?)</td>', r, re.S)]
    if len(c) < 14 or c[0] == 'Fund Name': continue
    try:
        d = datetime.datetime.strptime(c[13], '%m/%d/%Y').date()
        na = float(c[3].replace(',', '')); so = float(c[4].replace(',', '')); nav = float(c[5].replace(',', ''))
    except Exception: continue
    data[c[1]].append((d, na, so, nav))
out = {}
for t, v in sorted(data.items()):
    v.sort()
    flows = []
    for (d0, na0, so0, nav0), (d1, na1, so1, nav1) in zip(v, v[1:]):
        flows.append((d1.isoformat(), (so1 - so0) * nav1))
    nz = [f for f in flows if abs(f[1]) > 1]
    out[t] = flows
    big = sorted(nz, key=lambda x: -abs(x[1]))[:3]
    print(f"{t:6s} {v[0][0]}..{v[-1][0]} дней {len(v):3d}  AUM ${v[-1][1]/1e6:7.1f}M  дней с потоком {len(nz):3d}  сумма ${sum(f[1] for f in flows)/1e6:7.1f}M  медиана |поток| ${sorted(abs(f[1]) for f in nz)[len(nz)//2]/1e6 if nz else 0:5.2f}M  крупнейшие {[(a, round(b/1e6,1)) for a,b in big]}")
json.dump(out, open(sys.argv[2], 'w'))
