"""Фактор «short interest» MarginData — уточнение: фактический фандинг (шорт получает положительный, платит отрицательный),
комиссия 0,1% за круг, вселенная — все фьючерсы с объёмом (монеты вне канала — отдельная группа), окно 3/7/14 дней,
горизонт 3/7 дней. Ранжирование только по доле постов канала с монетой."""
import pickle, re, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], np.array(m["PT"])
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for c, arr in G.items(): ch.setdefault(strip(c), []).append(arr[:, 0])
ch = {k: np.sort(np.concatenate(v)) for k, v in ch.items()}
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
start = datetime.datetime(2025, 3, 10, tzinfo=UTC).timestamp(); end = datetime.datetime(2026, 9, 7, tzinfo=UTC).timestamp()
def px(a, t):
    j = int(np.searchsorted(a["t"], t)); return (float(a["o"][j]), j) if j < len(a["t"]) and a["t"][j] == t else (np.nan, -1)
def fund(s, a, b):
    f = FU.get(s)
    if f is None: return 0.0
    k0, k1 = np.searchsorted(f[:, 0], a, "right"), np.searchsorted(f[:, 0], b, "right"); return float(f[k0:k1, 2].sum())
def run(look, hold, step=7):
    rows = []
    for W in np.arange(start, end, step * 86400):
        n_posts = ((PT >= W - look * 86400) & (PT < W)).sum()
        if n_posts < 100: continue
        for s, a in K.items():
            e, j = px(a, int(W + 3600))
            if j < 700: continue
            x, j2 = px(a, int(W + hold * 86400 + 3600))
            if not np.isfinite(e) or not np.isfinite(x): continue
            v = float(a["qv"][j - 672:j].astype(float).sum()) / 7
            if v < 3e6: continue
            tt = ch.get(strip(s)); sh = 0.0
            if tt is not None: sh = (np.searchsorted(tt, W) - np.searchsorted(tt, W - look * 86400)) / n_posts
            fr = fund(s, W + 3600, W + hold * 86400 + 3600)
            rows.append(dict(W=W, s=s, sh=sh, ret=x / e - 1, fr=fr))
    return pd.DataFrame(rows)
for look, hold in ((7, 7), (3, 3), (14, 7), (7, 3)):
    F = run(look, hold, step=hold)
    F["short_pnl"] = -F.ret + F.fr - 0.001                       # шорт: −доходность + фандинг (положительный фандинг шорт получает) − комиссия
    zero = F[F.sh == 0].groupby("W").ret.mean()
    inn = F[F.sh > 0].copy()
    inn["q"] = inn.groupby("W").sh.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False) if len(x) >= 10 else np.nan)
    tab = inn.groupby(["W", "q"]).ret.mean().unstack(); sp = (tab[0] - tab[4]).dropna()
    q4 = inn[inn.q == 4].groupby("W")
    short4 = q4.short_pnl.mean(); fr4 = q4.fr.mean()
    mkt = F.groupby("W").ret.mean()
    hedged = (short4 + mkt.reindex(short4.index)).dropna()        # шорт Q4 + лонг «рынка» (все монеты поровну)
    h = sp.index < CUT
    print(f"окно {look} дн, удержание {hold} дн: монет вне канала {int(F[F.sh == 0].groupby('W').size().median())}, в канале {int(inn.groupby('W').size().median())} (медианы)")
    print(f"   доходность: вне канала {zero.mean()*100:+.2f}% | Q0…Q4: " + " ".join(f"{tab[q].mean()*100:+.2f}" for q in range(5)) + f" | рынок {mkt.mean()*100:+.2f}%")
    print(f"   спред Q0−Q4 {sp.mean()*100:+.2f}% (t {sp.mean() / sp.std() * np.sqrt(len(sp)):.2f}, в плюсе {(sp > 0).mean():.0%}, 1-я/2-я {sp[h].mean()*100:+.2f}/{sp[~h].mean()*100:+.2f})")
    hh = short4.index < CUT
    print(f"   шорт Q4 с фандингом и комиссией: {short4.mean()*100:+.2f}% за период (фандинг {fr4.mean()*100:+.2f}%), в плюсе {(short4 > 0).mean():.0%}, 1-я/2-я {short4[hh].mean()*100:+.2f}/{short4[~hh].mean()*100:+.2f}")
    print(f"   шорт Q4 + лонг рынка (нейтрально): {hedged.mean()*100:+.2f}% (t {hedged.mean() / hedged.std() * np.sqrt(len(hedged)):.2f}, в плюсе {(hedged > 0).mean():.0%})")
    F.to_pickle(f"s10/factor_{look}_{hold}.pkl")
