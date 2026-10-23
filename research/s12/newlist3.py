"""Разбор находки «новый токен в маржинальном канале → шорт»: список сделок, сравнение со спотовым листингом Binance
(объявления «Binance Will List …», HODLer/Launchpool), время входа 1/6/24/72 ч, хедж, вклад отдельных монет."""
import pickle, re, datetime
import numpy as np, pandas as pd
exec(open("s12/newlist.py").read().split("rows = []")[0])
A = pickle.load(open("s10/ann.pkl", "rb"))
spot_ann = {}
for a in A.values():
    if not a["ts"]: continue
    m = re.search(r"Binance Will List (.+?)\s*\(([A-Z0-9]+)\)", a["title"]) or re.search(r"Introducing .*?\(([A-Z0-9]+)\) on Binance (?:HODLer|Launchpool|Megadrop)", a["title"])
    if m:
        sym = m.group(m.lastindex); spot_ann.setdefault(sym, a["ts"] // 1000)
rows = []
for s, a in K.items():
    T0 = int(a["t"][0])
    if T0 < CH0 or s in TF or s.endswith("USDC"): continue
    o = a["o"].astype(float); h = a["h"].astype(float)
    if len(o) < 96 * 4: continue
    tt = ch.get(strip(s)); tt = tt if tt is not None else np.array([])
    sa = spot_ann.get(strip(s)) or spot_ann.get(s)
    for ent_h in (1, 6, 24, 72):
        te = T0 + ent_h * 3600; e, je = px(a, te)
        posts = int(((tt >= T0 - 48 * 3600) & (tt < te)).sum())
        for hold_d in (14, 30):
            tx = te + hold_d * 86400
            if tx > T_END: continue
            x, jx = px(a, tx); seg = h[je:jx] / e - 1 if jx > je else np.array([0.0])
            hit = np.flatnonzero(seg >= 1.0)
            sp = (-1.0 - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
            be, _ = px(btc, te); bx, _ = px(btc, tx)
            rows.append(dict(s=s, T0=T0, ent=ent_h, hold=hold_d, sp=sp, h=sp + bx / be - 1 - 0.001, posts=posts,
                             spot=sa is not None and abs(sa - T0) <= 10 * 86400))
E = pd.DataFrame(rows)
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def st(nm, g):
    hh = g.T0 < CUT; v = g.sp
    print(f"   {nm:56s} n={len(g):3d} {v.mean()*100:+6.1f}% (медиана {v.median()*100:+6.1f}%, в плюсе {(v > 0).mean():.0%}; "
          f"1-я {v[hh].mean()*100:+6.1f} / 2-я {v[~hh].mean()*100:+6.1f}; с хеджем {g.h.mean()*100:+6.1f})")
for ent in (1, 6, 24, 72):
    for hold in (14, 30):
        g = E[(E.ent == ent) & (E.hold == hold)]
        print(f"\nвход через {ent} ч, держать {hold} сут, стоп +100%:")
        st("в канале займов до входа", g[g.posts > 0]); st("нет в канале", g[g.posts == 0])
        st("спотовый листинг Binance (±10 сут) и в канале", g[g.spot & (g.posts > 0)]); st("спотовый листинг, но не в канале", g[g.spot & (g.posts == 0)])
        st("в канале, без объявления спотового листинга", g[~g.spot & (g.posts > 0)])
g = E[(E.ent == 24) & (E.hold == 14) & (E.posts > 0)].sort_values("T0")
print("\nсделки (вход 24 ч, 14 сут):", ", ".join(f"{s} {datetime.datetime.utcfromtimestamp(t):%m.%y} {v*100:+.0f}%" for s, t, v in g[["s", "T0", "sp"]].values))
print("вклад: без 5 лучших", f"{g.sp.drop(g.sp.nlargest(5).index).mean()*100:+.1f}%", "| без 10 лучших", f"{g.sp.drop(g.sp.nlargest(10).index).mean()*100:+.1f}%",
      "| сделок хуже −50%:", (g.sp < -0.5).sum())
