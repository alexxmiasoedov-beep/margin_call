"""Фактор «short interest» по MarginData: раз в неделю (понедельник 00:00 UTC) монеты фьючерсов ранжируются по доле постов канала,
где монета была, за прошлые 7 дней (и по займу к объёму); доходность за следующие 7 дней (вход 01:00, выход через 7 суток).
Портфели по квинтилям (среди монет, бывших в канале), спред «мало займа − много займа», нейтрально к рынку."""
import pickle, re, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], np.array(m["PT"])
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
fut = {}
for s in K: fut.setdefault(strip(s), s)
UTC = datetime.timezone.utc
start = datetime.datetime(2025, 3, 3, tzinfo=UTC).timestamp(); end = datetime.datetime(2026, 9, 14, tzinfo=UTC).timestamp()
weeks = np.arange(start, end, 7 * 86400)
def price_at(s, t):
    a = K[s]; j = int(np.searchsorted(a["t"], t))
    return float(a["o"][j]) if j < len(a["t"]) and a["t"][j] == t else np.nan
def vol7(s, t):
    a = K[s]; j = int(np.searchsorted(a["t"], t)); return float(a["qv"][max(0, j - 672):j].astype(float).sum()) / 7
rows = []
for W in weeks:
    n_posts = ((PT >= W - 7 * 86400) & (PT < W)).sum()
    if n_posts < 100: continue
    for c, arr in G.items():
        s = fut.get(c)
        if s is None: continue
        mm = (arr[:, 0] >= W - 7 * 86400) & (arr[:, 0] < W)
        sh = mm.sum() / n_posts
        if sh == 0: continue
        e = price_at(s, int(W + 3600)); x = price_at(s, int(W + 7 * 86400 + 3600))
        if not (np.isfinite(e) and np.isfinite(x)): continue
        v = vol7(s, W)
        rows.append(dict(W=W, s=s, sh=sh, bor=np.nanmean(arr[mm, 1]), borv=np.nanmean(arr[mm, 1]) / max(v, 1), ret=x / e - 1, v=v))
F = pd.DataFrame(rows); print("наблюдений:", len(F), "недель:", F.W.nunique(), "монет в неделю (медиана):", int(F.groupby("W").size().median()))
F = F[F.v >= 2e6]                                                     # хоть какая-то ликвидность фьючерса
btc = {W: price_at("BTC", int(W + 7 * 86400 + 3600)) / price_at("BTC", int(W + 3600)) - 1 for W in F.W.unique()}
for key in ("sh", "borv"):
    F["q"] = F.groupby("W")[key].transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False) if len(x) >= 10 else np.nan)
    tab = F.groupby(["W", "q"]).ret.mean().unstack()
    spread = tab[0] - tab[4]                                          # мало займа − много займа
    half = tab.index < datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
    print(f"\nранжирование по {key}: средняя недельная доходность квинтилей (0 — мало займа, 4 — много):",
          " ".join(f"{q}: {tab[q].mean()*100:+.2f}%" for q in range(5)))
    print(f"   спред Q0 − Q4: {spread.mean()*100:+.2f}% в неделю, t = {spread.mean() / spread.std() * np.sqrt(len(spread)):.2f}, недель в плюсе {(spread > 0).mean():.0%} "
          f"| 1-я половина {spread[half].mean()*100:+.2f}%, 2-я {spread[~half].mean()*100:+.2f}%")
    print(f"   Q4 (много займа) против BTC: {np.mean([tab[4][W] - btc[W] for W in tab.index])*100:+.2f}% в неделю")
F.to_pickle("s10/factor.pkl")
