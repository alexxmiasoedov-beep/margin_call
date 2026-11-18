import json, time, urllib.request, sys
from gl_test import call, pad, T0, toks, cex, S
url=sys.argv[1]; ncex=int(sys.argv[2])
# prioritize spellbook (named) addresses, then blockscout extra
named=[a for a in cex if S['cex'][a][0]!='blockscout-exchange']; extra=[a for a in cex if S['cex'][a][0]=='blockscout-exchange']
sel=(named+extra)[:ncex]
for start,rng in [(16000000,2000),(16000000,10000),(16000000,50000),(11500000,10000)]:
    q={"fromBlock":hex(start),"toBlock":hex(start+rng),"address":toks,"topics":[T0,None,[pad(a) for a in sel]]}
    r,e,dt=call(url,q)
    print(len(toks),len(sel),start,rng, (len(r) if isinstance(r,list) else r), str(e)[:200] if e else '', f"{dt:.1f}s")
    time.sleep(1)
