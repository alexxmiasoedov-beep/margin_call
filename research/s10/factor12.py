"""Аварийный стоп для шортов фактора займа: закрытие при росте цены на +40/+60/+100% от входа (по 15-мин максимумам),
проскальзывание стопа 0,5%. Лесенка, хедж рынком."""
import pickle, datetime
import numpy as np, pandas as pd
exec(open("s10/factor11.py").read().split("sets = top")[0])
K = pickle.load(open("s2/k2y.pkl", "rb"))
def lad(w):
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = D.groupby("wk")["T"].min().reindex(s.index).values; return s
def hit(s, T, sl):
    a = K[s]; j = int(np.searchsorted(a["t"], T)); e = float(a["o"][j])
    hi = a["h"][j:j + 672].astype(float) / e - 1; b = np.flatnonzero(hi >= sl)
    return b[0] if len(b) else -1
mk = d.groupby("T").y7.mean() - 0.001
for sl in (0.4, 0.6, 1.0):
    k = np.array([hit(s, T, sl) for s, T in zip(top.s, top["T"])])
    # при стопе: убыток −sl − 0,5% проскальзывания − комиссия, фандинг до стопа не считаем (консервативно — без него)
    sp = np.where(k >= 0, -sl - 0.005 - 0.001, top.sp)
    S = pd.Series(sp, index=top.index).groupby(top["T"]).mean()
    w = lad((S + mk.reindex(S.index)) / 2); ws = lad(S)
    eq = w.cumsum(); eqs = ws.cumsum()
    print(f"стоп +{sl*100:.0f}%: сработал у {(k >= 0).mean():.1%} позиций | шорт+рынок {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}, просадка {(eq-eq.cummax()).min()*100:.1f}%, худшая неделя {w.min()*100:+.1f}%) | "
          f"только шорт {ws.mean()*100:+.2f}%/нед (просадка {(eqs-eqs.cummax()).min()*100:.1f}%, худшая {ws.min()*100:+.1f}%)")
S = top.groupby("T").sp.mean(); w = lad((S + mk.reindex(S.index)) / 2); ws = lad(S); eq = w.cumsum(); eqs = ws.cumsum()
print(f"без стопа: шорт+рынок {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}, просадка {(eq-eq.cummax()).min()*100:.1f}%, худшая неделя {w.min()*100:+.1f}%) | только шорт {ws.mean()*100:+.2f}%/нед (просадка {(eqs-eqs.cummax()).min()*100:.1f}%, худшая {ws.min()*100:+.1f}%)")
print(f"доля позиций, выросших против шорта за 7 дн больше чем на 40/60/100%: {(top.y7 > 0.4).mean():.1%} / {(top.y7 > 0.6).mean():.1%} / {(top.y7 > 1).mean():.1%}")
