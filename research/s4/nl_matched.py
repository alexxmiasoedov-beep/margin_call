"""Слабый старт листинга против фона в те же даты: для каждой сделки — тот же шорт (тот же вход по времени, те же выходы)
у всех «обычных» монет (возраст > 60 дней, объём за сутки ≥ 3 млн $). Избыток = сделка − среднее по фону."""
import pickle, datetime
import numpy as np, pandas as pd
exec(open("s3/newlist_final.py").read().split("T = []")[0])
TT = pd.read_pickle("s3/newlist_trades.pkl")
def short_at(s, t_in, tp, sl, hold):
    a = K[s]; t = a["t"]; j = np.searchsorted(t, t_in - 900)
    if j >= len(t) or t[j] != t_in - 900: return np.nan
    if j < 60 * 96 or a["qv"][j - 95:j + 1].sum() < 3e6: return np.nan
    return short2(s, j, tp, sl, hold)[0]
for tp, sl, days in ((0.3, 0.3, 14), (0.3, 0.4, 21)):
    ex = []; base = []
    for x in TT.itertuples():
        p = short2(x.s, int(np.searchsorted(K[x.s]["t"], x.t - 900)), tp, sl, days * 96)[0]
        b = [short_at(s, x.t, tp, sl, days * 96) for s in K if s != x.s]; b = np.nanmean(b)
        ex.append(p - b); base.append(b)
    TT["ex"] = ex; TT["base"] = base; TT["p"] = np.array(ex) + np.array(base); y1 = TT.t < CUT; ok = TT.base.notna()
    print(f"  сделок с фоном {ok.sum()}: сделка {TT.p[ok].mean()*100:+.2f}%, фон {TT.base[ok].mean()*100:+.2f}%, ст. откл. избытка {TT.ex[ok].std()*100:.1f}")
    print(f"{tp:.0%}/{sl:.0%}/{days} дн: фон в те же даты {np.nanmean(base)*100:+.2f}% , избыток {np.nanmean(ex)*100:+.2f}% (1-й год {TT.ex[y1].mean()*100:+.2f}, 2-й {TT.ex[~y1].mean()*100:+.2f}), "
          f"избыток > 0 в {(TT.ex > 0).mean():.0%} сделок, t = {TT.ex[ok].mean() / TT.ex[ok].std() * np.sqrt(ok.sum()):.1f}")
    TT[["s", "t", "p", "base", "ex"]].to_pickle(f"s4/nl_matched_{days}.pkl")
    for y, g in ((1, TT[y1 & ok]), (2, TT[~y1 & ok])):
        print(f"  год {y}: {len(g)} сделок, сделка {g.p.mean()*100:+.2f}%, фон в те же даты {g.base.mean()*100:+.2f}%, избыток {g.ex.mean()*100:+.2f}%")
