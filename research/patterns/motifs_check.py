"""Детальная проверка на новом месяце C: по направлениям и против простых правил «шорт/лонг на любых бурных сутках»."""
import sys, pickle, math, numpy as np
sys.argv = ["x"]
src = open("kaia/motifs.py").read().split("res = []")[0]            # окна, шаблоны, функции — без повторного перебора
exec(src)
pickle.dump({p: {k: v for k, v in w.items()} for p, w in W.items()}, open("kaia/motif_windows.pkl", "wb"))
D = pickle.load(open("kaia/motifs_B.pkl", "rb")); res = D["res"]
crit = {"ваш критерий": lambda r: r["same"] >= 2 and r["same"] == r["nB"],
        "мягче": lambda r: r["same"] >= 2 and r["same"] >= r["nB"] / 2,
        "строгий": lambda r: r["nB"] >= 6 and r["same"] / r["nB"] >= bB[r["o"]] + 0.25 and binom_p(r["same"], r["nB"], bB[r["o"]]) < 0.05}
allC = dedupe_idx(C, list(range(len(C["S"]))))
def pnl(i, d): return 0.2 if C["O"][i] == d else -0.2 if C["O"][i] == -d else d * C["R48"][i]
print(f"простое правило на всех бурных сутках C ({len(allC)} событий): шорт {np.mean([pnl(i, -1) for i in allC])*100:+.1f}% на сделку, "
      f"лонг {np.mean([pnl(i, 1) for i in allC])*100:+.1f}%")
for name, fn in crit.items():
    conf = [r for r in res if fn(r)]; pred = {}
    for r in conf:
        for i in matches(C, r["j"]): pred.setdefault(i, []).append(r["o"])
    pi = {i: (1 if sum(v) > 0 else -1) for i, v in pred.items() if sum(v) != 0}
    idx = dedupe_idx(C, list(pi))
    for dname, dv in (("вниз", -1), ("вверх", 1)):
        sel = [i for i in idx if pi[i] == dv]
        if not sel: continue
        hit = np.mean([C["O"][i] == dv for i in sel]); opp = np.mean([C["O"][i] == -dv for i in sel])
        same_dir_all = np.mean([pnl(i, dv) for i in allC])
        print(f"[{name}] прогноз «{dname}»: {len(sel)} | сбылось {hit*100:.0f}% (фон {bC[dv]*100:.0f}%), наоборот {opp*100:.0f}% (фон {bC[-dv]*100:.0f}%) | "
              f"итог {np.mean([pnl(i, dv) for i in sel])*100:+.1f}% против {same_dir_all*100:+.1f}% у простого правила «{('шорт' if dv < 0 else 'лонг')} всегда»")
