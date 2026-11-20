"""s246: разовые куски по расписанию Sablier (транш, клифф, начальная выдача) и снятия >= 0,5% / 1% обращения
в месяц; сверка с событиями 🔑⁺ (s142). Доходы не считаются. Выход: sablier_lumps.pkl, sablier_wd.pkl в /home/user/mc_data/s246/."""
import json, collections, datetime, glob, os, bisect
import pandas as pd
D='/home/user/mc_data/s246/'
pm=json.load(open('/home/user/mc_data/s160/perp_map.json'))
a2={}
for p in pm:
    for k in ('eth','bsc','base','arb'):
        a=p.get(k)
        if a and a.startswith('0x'): a2[a.lower()]=p
ex=json.load(open(D+'fapi_exchangeInfo.json'))['symbols']
onb={}
for s in ex:
    if s.get('contractType')=='PERPETUAL' and s['symbol'].endswith('USDT'):
        b=s['symbol'][:-4]; onb[b]=min(onb.get(b,9e18), s['onboardDate']/1000)
cmc=json.load(open('/home/user/mc_data/s160/cmc_ids.json'))
circh={}
for addr,v in cmc.items():
    f=f"/home/user/mc_data/s160/circ/{v['id']}.json"
    if os.path.exists(f):
        rows=[(r[0],r[1]) for r in json.load(open(f)) if r[1] and r[1]>0]
        circh[v['perp']]=(([r[0] for r in rows]),[r[1] for r in rows])
def circ_at(perp, day, fallback):
    if perp in circh:
        ds,vs=circh[perp]; i=bisect.bisect_right(ds,day)-1
        if i>=0: return vs[i], 'cmc'
    return fallback, 'now'
S={s['id']:s for s in json.load(open(D+'sablier_streams.json'))}
T=json.load(open(D+'sablier_tranches.json'))
W=json.load(open(D+'sablier_withdraws.json'))
lumps=collections.defaultdict(float)   # (perp, day) -> tokens
src=collections.defaultdict(set)
for sid,t in T.items():
    s=S[sid]; p=a2[s['asset']['address'].lower()]; dec=int(s['asset']['decimals'])
    if s.get('canceled'): continue
    ev=[]
    if t.get('initialAmount') and int(t['initialAmount'])>0: ev.append((int(s['startTime']),int(t['initialAmount'])))
    if t.get('cliffAmount') and int(t['cliffAmount'])>0 and t.get('cliffTime'): ev.append((int(t['cliffTime']),int(t['cliffAmount'])))
    for tr in t.get('tranches') or []: ev.append((int(tr['endTime']),int(tr['amount'])))
    for ts,amt in ev:
        day=datetime.datetime.fromtimestamp(ts,datetime.UTC).strftime('%Y-%m-%d')
        lumps[(p['perp'],day)]+=amt/10**dec; src[(p['perp'],day)].add(s['chainId'])
rows=[]
for (perp,day),amt in lumps.items():
    p=[x for x in pm if x['perp']==perp][0]
    c,how=circ_at(perp,day,p['circ'])
    ob=onb.get(perp)
    rows.append(dict(perp=perp,day=day,amt=amt,circ=c,how=how,share=amt/c if c else None,perp_live=(ob is not None and ob<=datetime.datetime.strptime(day,'%Y-%m-%d').replace(tzinfo=datetime.UTC).timestamp()-86400),chains=','.join(sorted(src[(perp,day)]))))
L=pd.DataFrame(rows); L['m']=L.day.str[:7]
L.to_pickle(D+'sablier_lumps.pkl')
def per_month(df,lo,hi):
    x=df[(df.day>=lo)&(df.day<hi)]
    n_months=(pd.Timestamp(hi)-pd.Timestamp(lo)).days/30.44
    return len(x), round(len(x)/n_months,2), x.perp.nunique()
for thr in (0.005,0.01):
    x=L[(L.share>=thr)&L.perp_live]
    print(f"lumps >= {thr*100}% circ, perp live: 2020-10..2022-10 {per_month(x,'2020-10-01','2022-10-01')}, 2022-10..2024-10 {per_month(x,'2022-10-01','2024-10-01')}, 2024-10..2026-11 {per_month(x,'2024-10-01','2026-11-20')}, future {per_month(x,'2026-11-20','2027-11-20')}")
x=L[(L.share>=0.005)&L.perp_live&(L.day>='2024-10-01')&(L.day<'2026-11-20')]
print(x.groupby('perp').size().sort_values(ascending=False).head(25).to_dict())
print(x.how.value_counts().to_dict())
# compare with 🔑⁺ (s142) events
k=pd.read_pickle('/home/user/mc_data/s142_2024–2026.pkl')
k['day']=pd.to_datetime(k['T'],unit='s').dt.strftime('%Y-%m-%d')
kk=set(zip(k.s,k.day))
def near(perp,day):
    d0=datetime.datetime.strptime(day,'%Y-%m-%d')
    for dd in range(-3,4):
        if (perp,(d0+datetime.timedelta(days=dd)).strftime('%Y-%m-%d')) in kk: return True
    return False
x=x.copy(); x['in_k']=[near(a,b) for a,b in zip(x.perp,x.day)]
print("overlap with 🔑⁺ s142 (±3d):", x.in_k.sum(), "of", len(x), "| tokens in s142:", len(set(k.s)&set(x.perp)), "of", x.perp.nunique())
print(x[~x.in_k].groupby('perp').size().sort_values(ascending=False).head(25).to_dict())
# withdrawals
wr=[]
for w in W:
    s=S[w['stream_id']]; p=a2[s['asset']['address'].lower()]; dec=int(s['asset']['decimals'])
    day=datetime.datetime.fromtimestamp(int(w['timestamp']),datetime.UTC).strftime('%Y-%m-%d')
    amt=int(w['amountB'])/10**dec; c,how=circ_at(p['perp'],day,p['circ']); ob=onb.get(p['perp'])
    wr.append(dict(perp=p['perp'],day=day,ts=int(w['timestamp']),amt=amt,share=amt/c if c else None,how=how,live=(ob is not None and ob<=int(w['timestamp'])-86400),to=w['addressB'],chain=s['chainId']))
Wd=pd.DataFrame(wr); Wd.to_pickle(D+'sablier_wd.pkl')
for thr in (0.005,0.01):
    x=Wd[(Wd.share>=thr)&Wd.live]
    print(f"withdrawals >= {thr*100}%: 2022-10..2024-10 {per_month(x,'2022-10-01','2024-10-01')}, 2024-10..2026-11 {per_month(x,'2024-10-01','2026-11-20')}")
x=Wd[(Wd.share>=0.005)&Wd.live&(Wd.day>='2024-10-01')]
print(x.groupby('perp').size().sort_values(ascending=False).head(20).to_dict())
print(x.chain.value_counts().to_dict())
