"""Обобщение 🆕: событие — ПЕРВОЕ появление токена в маржинальном канале (займ стал возможен и его берут), для токенов,
у которых есть фьючерс Binance. Только «свежие» маржинальные токены: первый пост позже 15.03.2025 (архив канала с 20.02.2025)
и объявление о спотовом листинге Binance в пределах ±10 сут от первого поста (иначе — старый токен вернулся в канал).
Вход через 1/24/72 ч после первого поста, 14/21/30 сут, стоп +60%, выход при фандинге ≤ −0,5%/8 ч дважды. Когорты 2025/2026,
возраст фьючерса на момент первого поста (фьючерс раньше спота — схема 2026 года)."""
import sys, os, datetime, itertools
sys.path.insert(0, os.getcwd())
from s12.lib import *
import pandas as pd
F0 = datetime.datetime(2025, 3, 15, tzinfo=UTC).timestamp()
def trade_at(s, a, te, hold_d, stop, fexit):
    if te < a["t"][0] or te + hold_d * 86400 > T_END: return None
    e, je = px(a, te); tx = te + hold_d * 86400; f = FU.get(s)
    if f is not None and fexit is not None:
        ff = f[(f[:, 0] > te) & (f[:, 0] <= tx)]; bad = ff[:, 2] / ff[:, 1] * 8 <= fexit
        two = np.flatnonzero(bad[1:] & bad[:-1])
        if len(two): tx = int(ff[two[0] + 1, 0])
    x, jx = px(a, tx); seg = a["h"][je:jx].astype(float) / e - 1 if jx > je else np.array([0.0])
    hit = np.flatnonzero(seg >= stop)
    sp = (-stop - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
    be, _ = px(btc, te); bx, _ = px(btc, tx)
    return sp, sp + bx / be - 1 - 0.001, fnow(s, te)
ev = []
for c, tt in ch.items():
    if tt[0] < F0: continue
    s = next((p + c for p in ("", "1000", "10000", "100000", "1000000") if p + c in K), None)
    if s is None or s in TF: continue
    sa = spot_ann.get(c)
    fresh = sa is not None and abs(sa - tt[0]) <= 10 * 86400
    ev.append((c, s, int(tt[0]), fresh, (tt[0] - K[s]["t"][0]) / 86400))
print(f"токенов с первым постом в канале после 15.03.2025 и фьючерсом: {len(ev)}; из них со свежим спотовым листингом: {sum(e[3] for e in ev)}")
rows = []
for c, s, t1, fresh, age in ev:
    for ent in (1, 24, 72):
        for hold in (14, 21, 30):
            r = trade_at(s, K[s], t1 + ent * 3600, hold, 0.6, -0.005)
            if r: rows.append(dict(c=c, s=s, t1=t1, fresh=fresh, age=age, ent=ent, hold=hold, sp=r[0], h=r[1], f8=r[2]))
E = pd.DataFrame(rows)
y26 = datetime.datetime(2026, 1, 1, tzinfo=UTC).timestamp()
def st(nm, g):
    hh = g.t1 < CUT; v = g.sp
    if len(g) == 0: print(f"   {nm:58s} n=0"); return
    print(f"   {nm:58s} n={len(g):3d} {v.mean()*100:+6.1f}% (медиана {v.median()*100:+6.1f}%, в плюсе {(v > 0).mean():.0%}; 1-я {v[hh].mean()*100:+6.1f} / 2-я {v[~hh].mean()*100:+6.1f}; с хеджем {g.h.mean()*100:+6.1f})")
for ent in (1, 24, 72):
    for hold in (14, 21, 30):
        g = E[(E.ent == ent) & (E.hold == hold)]
        print(f"\nвход через {ent} ч после первого поста, {hold} сут:")
        st("свежий спотовый листинг (±10 сут)", g[g.fresh]); st("старый токен вернулся в канал", g[~g.fresh])
        f = g[g.fresh]
        st("   свежий, 2025", f[f.t1 < y26]); st("   свежий, 2026", f[f.t1 >= y26])
        st("   свежий, фьючерс младше 3 сут (схема 2025)", f[f.age < 3]); st("   свежий, фьючерс старше 3 сут (схема 2026)", f[f.age >= 3])
        st("   свежий, без дорогого фандинга (≥ −0,1%/8 ч)", f[~(f.f8 < -0.001)])
g = E[(E.ent == 24) & (E.hold == 21) & E.fresh].sort_values("t1")
print("\nсделки (24 ч, 21 сут, свежие):", ", ".join(f"{c} {datetime.datetime.utcfromtimestamp(t):%m.%y} {v*100:+.0f}%" for c, t, v in g[["c", "t1", "sp"]].values))
E.to_pickle("s12/firstborrow.pkl")
