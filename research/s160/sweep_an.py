import json, gzip, sys, collections, datetime as dt, glob, os
S=json.load(open('sets.json')); cex=S['cex']; toks=S['toks']
meta=json.load(open('tok_meta.json'))
# CMC snapshots: date -> {sym: (circ, price)}
def cmc(date):
    p=f'/home/user/mc_data/s136/raw/{date}.json'
    if not os.path.exists(p): return {}
    d=json.load(open(p))
    return {r[1].upper():(r[4],r[5]) for r in d}
B={}
for l in open('blocks.txt'):
    ts,d,b=l.split(); B[int(b)]=int(ts)
bk=sorted(B)
def ts_of(b):
    for i in range(len(bk)-1):
        if bk[i]<=b<=bk[i+1]:
            return B[bk[i]]+(b-bk[i])*(B[bk[i+1]]-B[bk[i]])/(bk[i+1]-bk[i])
    return None
def run(path, label):
    rows=json.load(gzip.open(path,'rt'))
    snap=cmc(label+'-15') or {}
    n_all=len(rows); n_ext=0
    ev=collections.defaultdict(list)
    big=[]
    for blk,tok,fr,to,val,tx,li in rows:
        if fr in cex: continue  # inter/intra exchange
        n_ext+=1
        m=meta.get(tok,{}); dec=int(m.get('decimals') or 18)
        sym=(toks[tok]['sym'] or m.get('symbol') or '').upper()
        circ=None; src=''
        if sym in snap and snap[sym][0]: circ=snap[sym][0]; src='cmc'
        elif toks[tok].get('circ'): circ=toks[tok]['circ']; src='cg_now'
        if not circ: continue
        amt=val/10**dec
        frac=amt/circ
        if frac>=0.001:
            t=ts_of(blk)
            big.append((frac, sym, toks[tok]['perp'], amt, dt.datetime.fromtimestamp(t,dt.UTC).strftime('%m-%d %H:%M') if t else '', fr, to, cex.get(to,('?',))[0], tx, src))
    big.sort(reverse=True)
    print(f"== {label}: rows {n_all}, from non-labeled {n_ext}, tokens {len(set(r[1] for r in rows))}")
    for thr in (0.001,0.0025,0.005,0.01):
        sel=[b for b in big if b[0]>=thr]
        tokday=set((b[1],b[4][:5]) for b in sel)
        tok=set(b[1] for b in sel)
        print(f"  >= {thr*100:.2f}% circ: transfers {len(sel)}, token-days {len(tokday)}, tokens {len(tok)}")
    return big
if __name__=="__main__":
    for p in sys.argv[1:]:
        lab=os.path.basename(p).split('.')[0]
        big=run(p, lab)
        json.dump(big, open(p.replace('.json.gz','_big.json'),'w'))
        print('  top:'); 
        for b in big[:15]: print('   ', f"{b[0]*100:.2f}%", b[1], b[4], round(b[3]), b[7], b[5][:10], b[9])
