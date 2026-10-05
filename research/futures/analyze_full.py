"""Бэктест на всей истории канала (с 23.02.2025) в условиях, сверенных с реальным счётом."""
import os, datetime
os.environ.setdefault("SIGFILE", "signals_full.pkl")
import numpy as np, pandas as pd
import realism as R
from sim import SIG, FUND, summ
pd.set_option("display.width", 250)
print(f"сигналов {len(SIG)} (правило 1 {sum(s['rule']=='1' for s in SIG)}, правило 2 {sum(s['rule']=='2' for s in SIG)}), "
      f"{datetime.datetime.utcfromtimestamp(SIG[0]['ep']):%d.%m.%Y}–{datetime.datetime.utcfromtimestamp(SIG[-1]['ep']):%d.%m.%Y}")
def run_p(params, delay=1, pause_h=48):
    ou, ls, rows = {}, {}, []
    for s in SIG:
        if ou.get(s["sym"], 0) > s["ep"] or s["ep"] - ls.get(s["sym"], -1e18) < pause_h * 3600: continue
        F = FUND.get(s["sym"]); fh = None
        if F is not None and len(F) > 1:
            k = np.searchsorted(F[:, 0], s["te"]) - 1
            if k >= 1: fh = F[k, 1] / max((F[k, 0] - F[k - 1, 0]) / 3600, 1)
        tp, sl = params(fh); r = R.trade2(s, tp, sl, delay=delay, slip_sl=0.002)
        if r is None: continue
        ou[s["sym"]] = r["xt"]
        if r["kind"] == "стоп": ls[s["sym"]] = r["xt"]
        rows.append(dict(ep=s["ep"], sym=s["sym"], rule=s["rule"], **r))
    return pd.DataFrame(rows)
CFG = [("6/20", lambda fh: (6, 20)), ("8/20", lambda fh: (8, 20)), ("10/20", lambda fh: (10, 20)), ("10/25", lambda fh: (10, 25)),
       ("15/25", lambda fh: (15, 25)), ("20/25", lambda fh: (20, 25)), ("📓 без тейка/25", lambda fh: (None, 25)),
       ("📗 по фандингу", lambda fh: (15, 25) if fh is not None and fh * 100 < -0.03 else (6, 20))]
res = {}
for delay in (1, 3):
    print(f"\n===== вход через ~{'0,5' if delay == 1 else '2,5'} мин после поста =====")
    for lab, p in CFG:
        x = run_p(p, delay); res[(lab, delay)] = x
        xs = x.sort_values("ep").reset_index(drop=True); n3 = len(xs) // 3; third = [xs.iloc[:n3], xs.iloc[n3:2 * n3], xs.iloc[2 * n3:]]
        w = x.pnl.rolling(35).sum().dropna()
        print(summ(x, lab) + f" | по третям {' / '.join(f'{t.pnl.sum():+.1f}' for t in third)} | окна 35 в минусе {(w<0).mean()*100:.0f}%")
for lab in ("6/20", "15/25", "📗 по фандингу"):
    x = res[(lab, 1)]
    for r in "12": print("   " + summ(x[x.rule == r], f"{lab} правило {r}"))
print("\nПо месяцам (вход ~0,5 мин):")
cols = {}
for lab in ("6/20", "10/25", "15/25", "📓 без тейка/25", "📗 по фандингу"):
    x = res[(lab, 1)].copy(); x["m"] = pd.to_datetime(x.ep, unit="s").dt.strftime("%Y-%m"); cols[lab] = x.groupby("m").pnl.sum().round(1)
x = res[("6/20", 1)].copy(); x["m"] = pd.to_datetime(x.ep, unit="s").dt.strftime("%Y-%m")
t = pd.DataFrame(cols); t.insert(0, "сделок", x.groupby("m").size()); t.insert(1, "стоп% 6/20", x.groupby("m").kind.apply(lambda k: round((k == "стоп").mean() * 100)))
print(t.to_string()); print("месяцев в плюсе:", {c: f"{(t[c] > 0).sum()}/{len(t)}" for c in cols})
print("\nСетка тейк × стоп (вход ~0,5 мин), итого USDT:")
g = {}
for tp in (4, 6, 8, 10, 15, 20, None):
    for sl in (15, 20, 25, 30):
        g[(tp or "нет", sl)] = round(run_p(lambda fh, tp=tp, sl=sl: (tp, sl)).pnl.sum(), 1)
print(pd.Series(g).unstack().to_string())
