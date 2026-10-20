import pickle, math, numpy as np
exec(open("kaia/poscells.py").read().split("def show(")[0])
S = {"премия < −4% и фандинг в упоре": lambda st: st[2] == "премия < −4%" and st[3] == "фандинг в упоре",
     "OI ×2+ (любой рисунок)": lambda st: st[1] == "OI ×2+",
     "цена вверх и OI ×2+": lambda st: st[0] == "цена вверх" and st[1] == "OI ×2+",
     "OI ×2+ или (премия < −4% и фандинг в упоре)": lambda st: st[1] == "OI ×2+" or (st[2] == "премия < −4%" and st[3] == "фандинг в упоре"),
     "цена вверх (все пампы, для сравнения)": lambda st: st[0] == "цена вверх"}
for name, fn in S.items():
    print(f"\n{name}:")
    pool = dict(n=0, dn=0, up=0, pn=[], bdn=0.0)
    for k in "ABC":
        w = W[k]; ix = dedupe(w, [i for i in range(len(w["S"])) if ST[k][i] is not None and fn(ST[k][i])])
        if not ix: print(f"  {k}: нет"); continue
        dn = np.mean(w["O"][ix] == -1); up = np.mean(w["O"][ix] == 1); pr = [pnl(w, i, -1) for i in ix]
        print(f"  {k}: {len(ix):4d} случаев | первым −20%: {dn*100:3.0f}% (фон {base[k][-1]*100:.0f}%) | первым +20%: {up*100:3.0f}% (фон {base[k][1]*100:.0f}%) | "
              f"шорт на 48 ч: {np.mean(pr)*100:+5.1f}% на сделку, в плюсе {np.mean(np.array(pr) > 0)*100:.0f}%")
        pool["n"] += len(ix); pool["dn"] += int(round(dn * len(ix))); pool["up"] += int(round(up * len(ix))); pool["pn"] += pr; pool["bdn"] += base[k][-1] * len(ix)
    if pool["n"]:
        p0 = pool["bdn"] / pool["n"]; k_ = pool["dn"]; n_ = pool["n"]
        pv = sum(math.comb(n_, x) * p0 ** x * (1 - p0) ** (n_ - x) for x in range(k_, n_ + 1))
        se = np.std(pool["pn"]) / np.sqrt(n_)
        print(f"  ВСЕГО: {n_} | первым −20%: {k_/n_*100:.0f}% против фона {p0*100:.0f}% (вероятность случайности {pv:.1e}) | первым +20%: {pool['up']/n_*100:.0f}% | "
              f"шорт {np.mean(pool['pn'])*100:+.1f}% ± {se*100:.1f}% на сделку")
