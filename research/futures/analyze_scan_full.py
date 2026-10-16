"""Бэктест текущих правил на всей истории: сигналы на каждом опросе (как в боте) против прежних — по постам.
Условия сверены с реальным счётом: вход рыночным (taker), стоп по марк-цене с проскальзыванием 0,2%, тейк лимитный (maker),
фандинг Binance по факту (октябрь 2026 — оценка), пауза 48 ч после стопа по монете, одна позиция на монету, выход через 48 ч."""
import os, sys, datetime, pickle
os.environ["SIGFILE"] = sys.argv[1] if len(sys.argv) > 1 else "signals_scan_full.pkl"
import numpy as np, pandas as pd
import realism as R
from sim import SIG, FUND, summ
UTC = datetime.timezone.utc
CUT = datetime.datetime(2026, 9, 28, tzinfo=UTC).timestamp()      # прежний бэктест кончался 27.09 — для честного сравнения
def run_p(params, delay=1, pause_h=48, sig=None, t_from=None, t_to=None):
    ou, ls, rows = {}, {}, []
    for s in (sig or SIG):
        if t_from and s["ep"] < t_from or t_to and s["ep"] >= t_to: continue
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
q = lambda ep: f"{datetime.datetime.fromtimestamp(ep, UTC).year}Q{(datetime.datetime.fromtimestamp(ep, UTC).month - 1) // 3 + 1}"
print(f"файл {os.environ['SIGFILE']}: сигналов {len(SIG)} (правило 1 {sum(s['rule']=='1' for s in SIG)}, правило 2 {sum(s['rule']=='2' for s in SIG)}), "
      f"{datetime.datetime.fromtimestamp(SIG[0]['ep'], UTC):%d.%m.%Y}–{datetime.datetime.fromtimestamp(SIG[-1]['ep'], UTC):%d.%m.%Y}")
out = {}
for delay in (1, 2):
    print(f"\n===== вход {'в минуту сигнала' if delay == 1 else 'через минуту после сигнала'}; до 27.09.2026 =====")
    for lab, p in CFG:
        x = run_p(p, delay, t_to=CUT); out[(lab, delay)] = x
        qs = x.groupby(x.ep.map(q)).pnl.sum()
        print(summ(x, lab) + f" | кварталов в плюсе {(qs > 0).sum()}/{len(qs)}")
print("\nПо кварталам (вход в минуту сигнала):")
print(pd.DataFrame({lab: out[(lab, 1)].groupby(out[(lab, 1)].ep.map(q)).pnl.sum().round(1) for lab, _ in CFG}).to_string())
print("\nСетка тейк × стоп (вход в минуту сигнала, до 27.09.2026), итого USDT:")
g = {}
for tp in (4, 6, 8, 10, 15, 20, None):
    for sl in (15, 20, 25, 30):
        g[(tp or "нет", sl)] = round(run_p(lambda fh, tp=tp, sl=sl: (tp, sl), t_to=CUT).pnl.sum(), 1)
print(pd.Series(g).unstack().to_string())
oct0 = datetime.datetime(2026, 9, 28, tzinfo=UTC).timestamp()
print("\nОктябрь 2026 (28.09–15.10), вход в минуту сигнала:")
for lab, p in CFG:
    print("  " + summ(run_p(p, 1, t_from=oct0), lab))
pickle.dump({k: v for k, v in out.items()}, open(os.environ["SIGFILE"].replace(".pkl", "_res.pkl"), "wb"))
