import pickle, numpy as np, datetime
exec(open("kaia/poscells.py").read().split("def show(")[0])
D = pickle.load(open("kaia/positions.pkl", "rb")); PREM, FUND = D["PREM"], D["FUND"]
src = open("kaia/posfeat.py").read(); exec(src[src.index("OCT1 ="):src.index("def feats(")])      # fund_oct — фандинг октября по премии
def rates(sym, a, b):
    out = []; f = FUND.get(sym)
    if f is not None and len(f): out += [x for t, iv, x in f if a < t <= b]
    if b > OCT1:
        fe = fund_oct(sym); last = f[-1, 0] if f is not None and len(f) else 0
        if fe is not None: out += [x for t, iv, x in fe if a < t <= b and t > last]
    return sum(out)
def trade(sym, te):
    k = K15[sym]; e = int(np.searchsorted(k[:, 0], te)); p = k[e - 1, 4]; seg = k[e:e + 192]
    dn = np.flatnonzero(seg[:, 3] <= p * 0.8); up = np.flatnonzero(seg[:, 2] >= p * 1.2)
    fd = dn[0] if len(dn) else 999; fu = up[0] if len(up) else 999
    if fd < fu: px, xt = 0.2, seg[fd, 0] + 900
    elif fu < fd: px, xt = -0.2, seg[fu, 0] + 900
    else: px, xt = -(seg[-1, 4] / p - 1), te + 48 * 3600
    return px, rates(sym, te, xt)                     # фандинг: + получает шорт, − платит
S = {"премия < −4% и фандинг в упоре": lambda st: st[2] == "премия < −4%" and st[3] == "фандинг в упоре",
     "OI ×2+": lambda st: st[1] == "OI ×2+",
     "цена вверх (все пампы)": lambda st: st[0] == "цена вверх"}
for name, fn in S.items():
    print(f"\n{name} — шорт с выходом по −20% / +20% / через 48 ч, комиссии 0,1%:")
    allp, allf = [], []
    for k in "ABC":
        w = W[k]; ix = dedupe(w, [i for i in range(len(w["S"])) if ST[k][i] is not None and fn(ST[k][i])])
        tr = [trade(SYMS[w["S"][i]], w["TE"][i]) for i in ix]; px = np.array([t[0] for t in tr]); fd = np.array([t[1] for t in tr])
        net = px + fd - 0.001
        print(f"  {k}: {len(ix):4d} | цена {px.mean()*100:+5.1f}% | фандинг {fd.mean()*100:+5.1f}% | итог {net.mean()*100:+5.1f}% на сделку, в плюсе {np.mean(net > 0)*100:.0f}%")
        allp += list(px); allf += list(fd)
    net = np.array(allp) + np.array(allf) - 0.001
    print(f"  ВСЕГО {len(net)}: цена {np.mean(allp)*100:+.1f}%, фандинг {np.mean(allf)*100:+.1f}%, итог {net.mean()*100:+.1f}% ± {net.std()/np.sqrt(len(net))*100:.1f}%")
