"""Рыночно-нейтральная пара по фактору займа: лонг монет вне канала MarginData, шорт монет, дольше всех бывших в канале.
Фандинг по обеим ногам (лонг платит положительный, шорт получает положительный), комиссия 0,1% за круг на каждую ногу.
Раз в неделю: вход понедельник 01:00 UTC, выход через 7 дней. Портфели поровну."""
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
def fnow(s, t):
    f = FU.get(s)
    if f is None: return np.nan
    k = np.searchsorted(f[:, 0], t, "right") - 1; return float(f[k, 2] / f[k, 1] * 8) if k >= 0 else np.nan   # к 8 ч
rows = []
for W in np.arange(start, end, 7 * 86400):
    for look in (7, 14, 21):
        n_posts = ((PT >= W - look * 86400) & (PT < W)).sum()
        if n_posts < 100: continue
        for s, a in K.items():
            e, j = px(a, int(W + 3600))
            if j < 700: continue
            x, _ = px(a, int(W + 7 * 86400 + 3600))
            if not (np.isfinite(e) and np.isfinite(x)): continue
            v = float(a["qv"][j - 672:j].astype(float).sum()) / 7
            if v < 3e6: continue
            tt = ch.get(strip(s)); sh = 0.0
            if tt is not None: sh = (np.searchsorted(tt, W) - np.searchsorted(tt, W - look * 86400)) / n_posts
            rows.append(dict(W=W, look=look, s=s, sh=sh, v=v, ret=x / e - 1, fr=fund(s, W + 3600, W + 7 * 86400 + 3600), f0=fnow(s, W)))
F = pd.DataFrame(rows); F.to_pickle("s10/factor3.pkl")
F["lpnl"] = F.ret - F.fr - 0.001; F["spnl"] = -F.ret + F.fr - 0.001
def stats(nm, w):
    w = w.dropna(); eq = w.cumsum(); dd = (eq - eq.cummax()).min(); h = w.index < CUT
    qs = w.groupby(pd.to_datetime(w.index, unit="s").to_period("Q")).sum()
    print(f"{nm:62s} {w.mean()*100:+.2f}%/нед (t {w.mean() / w.std() * np.sqrt(len(w)):.2f}, в плюсе {(w > 0).mean():.0%}, 1-я/2-я {w[h].mean()*100:+.2f}/{w[~h].mean()*100:+.2f}, "
          f"просадка {dd*100:.1f}%, кварталов в плюсе {(qs > 0).sum()}/{len(qs)})")
for look in (7, 14, 21):
    g = F[F.look == look]
    for vmin in (3e6, 10e6):
        gg = g[g.v >= vmin]
        L = gg[gg.sh == 0].groupby("W").lpnl.mean()
        inn = gg[gg.sh > 0].copy(); inn["r"] = inn.groupby("W").sh.rank(ascending=False, method="first")
        inn["q"] = inn.groupby("W").sh.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False) if len(x) >= 10 else np.nan)
        S5 = inn[inn.q == 4].groupby("W").spnl.mean(); S10 = inn[inn.r <= 10].groupby("W").spnl.mean()
        S10c = inn[(inn.r <= 10) & ~(inn.f0 < -0.001)].groupby("W").spnl.mean()      # без шортов с фандингом дешевле −0,1%/8 ч
        L10 = gg[gg.sh == 0].assign(rr=lambda d: d.groupby("W").v.rank(ascending=False)).query("rr <= 10").groupby("W").lpnl.mean()
        tag = f"окно {look} дн, объём ≥ {vmin/1e6:.0f} млн $"
        stats(f"{tag}: пара лонг вне канала / шорт Q4", (L + S5) / 2)
        stats(f"{tag}: пара лонг 10 ликвидных вне канала / шорт топ-10", (L10 + S10) / 2)
        stats(f"{tag}: шорт топ-10 (без дорогого фандинга)", S10c)
