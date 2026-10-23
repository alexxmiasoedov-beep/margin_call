"""Шорт новых фьючерсов с ранним займом — без заглядывания вперёд: посты маржинального канала считаются только
с T0 − 48 ч до момента входа. Сетка: вход через 24/48/72 ч; порог постов {1, 5, 10, 20}; держать 7/14/30 сут; стоп
+60% / +100%; доп. условие — цена на входе ниже цены запуска. Выбор по 1-й половине (запуски до 01.10.2025), проверка
на 2-й. Только эпоха канала (запуски с 21.02.2025)."""
import pickle, re, datetime, itertools
import numpy as np, pandas as pd
exec(open("s12/newlist.py").read().split("rows = []")[0])
rows = []
for s, a in K.items():
    T0 = int(a["t"][0])
    if T0 < CH0 or s in TF or s.endswith("USDC"): continue
    o = a["o"].astype(float); h = a["h"].astype(float)
    if len(o) < 96 * 4: continue
    tt = ch.get(strip(s)); tt = tt if tt is not None else np.array([])
    for ent_h in (24, 48, 72):
        te = T0 + ent_h * 3600
        e, je = px(a, te)
        n_posts = int(((tt >= T0 - 48 * 3600) & (tt < te)).sum())
        prior = int((tt < T0 - 48 * 3600).sum())
        for hold_d in (7, 14, 30):
            tx = te + hold_d * 86400
            if tx > T_END: continue
            x, jx = px(a, tx); seg = h[je:jx] / e - 1 if jx > je else np.array([0.0])
            fr = fsum(s, te, tx); be, _ = px(btc, te); bx, _ = px(btc, tx)
            for stop in (0.6, 1.0):
                hit = np.flatnonzero(seg >= stop)
                sp = (-stop - 0.005 if len(hit) else -(x / e - 1)) + fr - 0.001
                rows.append(dict(s=s, T0=T0, ent=ent_h, hold=hold_d, stop=stop, sp=sp, h=sp + bx / be - 1 - 0.001,
                                 posts=n_posts, prior=prior, down=e < o[0], r0=e / o[0] - 1))
E = pd.DataFrame(rows); E.to_pickle("s12/newlist2.pkl")
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
print(f"запусков в эпоху канала: {E.s.nunique()}; с постами до входа через 24 ч: {(E[(E.ent == 24)].groupby('s').posts.max() > 0).sum()}")
res = []
for ent, thr, hold, stop, down in itertools.product((24, 48, 72), (1, 5, 10, 20), (7, 14, 30), (0.6, 1.0), (False, True)):
    g = E[(E.ent == ent) & (E.hold == hold) & (E.stop == stop) & (E.posts >= thr)]
    if down: g = g[g.down]
    h1, h2 = g[g.T0 < CUT], g[g.T0 >= CUT]
    if len(h1) < 8 or len(h2) < 8: continue
    res.append(dict(ent=ent, thr=thr, hold=hold, stop=stop, down=down, n1=len(h1), n2=len(h2), m1=h1.sp.mean(), m2=h2.sp.mean(),
                    md1=h1.sp.median(), md2=h2.sp.median(), w2=(h2.sp > 0).mean(), m2h=h2.h.mean(),
                    t1=h1.sp.mean() / h1.sp.std() * np.sqrt(len(h1))))
R = pd.DataFrame(res)
print(f"вариантов {len(R)}; на 2-й половине в плюсе {(R.m2 > 0).mean():.0%}, медиана {R.m2.median()*100:+.2f}%")
b = R.sort_values("t1", ascending=False).head(8)
print("лучшие по 1-й половине (t) → 2-я половина:")
for _, r in b.iterrows():
    print(f"   вход {r.ent:.0f} ч, постов ≥ {r.thr:.0f}, {r.hold:.0f} сут, стоп +{r.stop*100:.0f}%, {'ниже цены запуска' if r.down else 'любая цена'}: "
          f"1-я {r.m1*100:+.1f}% (n {r.n1:.0f}, t {r.t1:.1f}) → 2-я {r.m2*100:+.1f}% (медиана {r.md2*100:+.1f}%, в плюсе {r.w2:.0%}, n {r.n2:.0f}; с хеджем {r.m2h*100:+.1f}%)")
print("\nсреднее по всем вариантам на 2-й половине по порогу постов:", " ".join(f"≥{k}: {v*100:+.2f}" for k, v in R.groupby("thr").m2.mean().items()))
base = E[(E.ent == 24) & (E.hold == 14) & (E.stop == 0.6)]
for nm, g in (("без постов до входа", base[base.posts == 0]), ("с постами ≥ 1", base[base.posts >= 1]), ("с постами ≥ 10", base[base.posts >= 10])):
    hh = g.T0 < CUT
    print(f"   вход 24 ч, 14 сут, стоп 60%, {nm:22s}: n {len(g):3d}, шорт {g.sp.mean()*100:+.2f}% (медиана {g.sp.median()*100:+.2f}%, в плюсе {(g.sp > 0).mean():.0%}; 1-я {g[hh].sp.mean()*100:+.2f} / 2-я {g[~hh].sp.mean()*100:+.2f})")
