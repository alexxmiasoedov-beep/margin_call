"""Шорт топ-N по присутствию в канале MarginData за 7 дней: контроль случайным выбором из монет канала (тот же фильтр фандинга),
хедж рынком (лонг всех монет поровну), стопы по 15-мин максимумам за неделю, разные N. Окно 7 дней, объём ≥ 10 (3) млн $."""
import pickle, datetime
import numpy as np, pandas as pd
F = pd.read_pickle("s10/factor3.pkl"); K = pickle.load(open("s2/k2y.pkl", "rb"))
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
F["spnl"] = -F.ret + F.fr - 0.001; F["lpnl"] = F.ret - F.fr - 0.001
def stop_pnl(s, W, sl, tp=None):
    a = K[s]; t0 = int(W + 3600); j = int(np.searchsorted(a["t"], t0))
    e = float(a["o"][j]); n = 672
    hi = a["h"][j:j + n].astype(float) / e - 1; lo = a["l"][j:j + n].astype(float) / e - 1
    b = np.flatnonzero(hi >= sl); g = np.flatnonzero(lo <= -tp) if tp else np.array([], int)
    b = b[0] if len(b) else 10**9; g = g[0] if len(g) else 10**9
    if b <= g and b < 10**9: return -sl - 0.002
    if g < 10**9: return tp - 0.001
    return None
def stats(nm, w):
    w = w.dropna(); eq = w.cumsum(); dd = (eq - eq.cummax()).min(); h = w.index < CUT
    qs = w.groupby(pd.to_datetime(w.index, unit="s").to_period("Q")).sum()
    print(f"{nm:66s} {w.mean()*100:+.2f}%/нед (t {w.mean() / w.std() * np.sqrt(len(w)):.2f}, в плюсе {(w > 0).mean():.0%}, 1-я/2-я {w[h].mean()*100:+.2f}/{w[~h].mean()*100:+.2f}, "
          f"просадка {dd*100:.1f}%, кв. {(qs > 0).sum()}/{len(qs)})")
    return w
rng = np.random.default_rng(5)
for vmin in (10e6, 3e6):
    g = F[(F.look == 7) & (F.v >= vmin)].copy()
    mkt = g.groupby("W").lpnl.mean()
    inn = g[g.sh > 0].copy(); inn["r"] = inn.groupby("W").sh.rank(ascending=False, method="first")
    ok = ~(inn.f0 < -0.001)
    print(f"\n=== объём ≥ {vmin/1e6:.0f} млн $; в канале за неделю — медиана {int(inn.groupby('W').size().median())} монет")
    for N in (5, 10, 20):
        top = inn[ok & (inn.r <= N + (inn[~ok].groupby('W').r.transform('size').reindex(inn.index).fillna(0)))]   # первые N среди допустимых
        top = inn[ok].sort_values(["W", "r"]).groupby("W").head(N)
        w = stats(f"шорт топ-{N} (без фандинга дешевле −0,1%)", top.groupby("W").spnl.mean())
        if N == 10:
            stats("   то же, без фильтра фандинга", inn.sort_values(["W", "r"]).groupby("W").head(N).groupby("W").spnl.mean())
            stats("   то же + лонг рынка (нейтрально)", (w + mkt.reindex(w.index)) / 2)
            pool = inn[ok]
            sims = []
            for _ in range(300):
                pick = pool.groupby("W").apply(lambda d: d.sample(min(N, len(d)), random_state=int(rng.integers(1e9))).spnl.mean(), include_groups=False)
                sims.append(pick.mean())
            sims = np.array(sims)
            print(f"   контроль: 10 случайных монет канала (тот же фильтр) — {sims.mean()*100:+.2f}%/нед, 95-й перцентиль {np.percentile(sims, 95)*100:+.2f}%, "
                  f"максимум {sims.max()*100:+.2f}% | доля симуляций ≥ топ-10: {(sims >= w.mean()).mean():.1%}")
            for sl in (0.20, 0.30):
                pn = []
                for x in top.itertuples():
                    p = stop_pnl(x.s, x.W, sl)
                    pn.append(x.spnl if p is None else p)
                top = top.assign(pst=pn)
                stats(f"   со стопом +{sl*100:.0f}% на позицию", top.groupby("W").pst.mean())
