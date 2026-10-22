"""Публичные коллы автора по альтам (посты t.me/cryptocoddee за 22.10.2024–21.10.2026): тикеры $XXX, направление по словам поста.
Доход от цены фьючерса на закрытии 15-мин свечи после поста за 1 / 3 / 7 суток, сверх медианы альтов за то же время."""
import pickle, re, datetime
import numpy as np, pandas as pd
P = pickle.load(open("../cc/posts.pkl", "rb")); K = pickle.load(open("s2/k2y.pkl", "rb"))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
sym = {}
for s in K: sym.setdefault(strip(s), s)
SH = re.compile(r"шорт|шортан|в шорт|разгруз|слив|на разгрузку|давить|снижени", re.I)
LO = re.compile(r"лонг|покуп|набира|набор|спот|откуп|подбира|холд|перехай|накоплен|держится|выглядит неплохо|выглядит бодро|рост", re.I)
rows = []
for p in P:
    if not p["dt"] or p["dt"] < "2024-10-22" or p.get("reply"): continue
    txt = p["text"]; tick = sorted({m.upper() for m in re.findall(r"\$([A-Za-z0-9]{2,12})", txt)} - {"BTC", "ETH", "USDT", "USDC"})
    if not tick: continue
    s_ = bool(SH.search(txt)); l_ = bool(LO.search(txt))
    side = 0 if s_ == l_ else (-1 if s_ else 1)
    T = datetime.datetime.fromisoformat(p["dt"]).timestamp()
    for tk in tick:
        k = sym.get(tk) or sym.get(strip(tk))
        if k is None: continue
        rows.append(dict(id=p["id"], t=T, s=k, side=side, txt=txt[:80].replace("\n", " ")))
C = pd.DataFrame(rows).sort_values("t")
keep, last = [], {}
for i, s, t in zip(C.index, C.s, C.t):
    if t - last.get(s, -1e18) >= 3 * 86400: keep.append(i); last[s] = t
C = C.loc[keep]
# индекс альтов (медиана) для поправки
def ret(s, T, h):
    a = K[s]; t = a["t"] + 900; c = a["c"]
    i0 = np.searchsorted(t, T); i1 = np.searchsorted(t, T + h * 3600)
    if i0 >= len(t) or i1 >= len(t) or t[i0] - T > 3600: return np.nan
    return float(c[i1] / c[i0] - 1)
ALTS = [s for s in K if s not in ("BTC", "ETH")]
def alt_med(T, h):
    v = [ret(s, T, h) for s in ALTS[::4]]
    return float(np.nanmedian(v))
for h in (24, 72, 168):
    C[f"r{h}"] = [ret(s, t, h) for s, t in zip(C.s, C.t)]
    C[f"m{h}"] = [alt_med(t, h) for t in C.t]
    C[f"x{h}"] = C.side * (C[f"r{h}"] - C[f"m{h}"])
C.to_pickle("s9/calls.pkl")
print("коллов с тикером на фьючерсе Binance:", len(C), "| лонг", (C.side == 1).sum(), "шорт", (C.side == -1).sum(), "неясно", (C.side == 0).sum())
for sd, nm in ((1, "ЛОНГ"), (-1, "ШОРТ")):
    g = C[C.side == sd]
    print(f"{nm}: n={len(g)} | " + " | ".join(f"{h // 24} сут: цена {g[f'r{h}'].mean()*100:+.1f}%, сверх рынка {g[f'x{h}'].mean()*100:+.1f}% (медиана {g[f'x{h}'].median()*100:+.1f}%, в плюсе {(g[f'x{h}'] > 0).mean():.0%})" for h in (24, 72, 168)))
g = C[C.side == 0]; print(f"неясно: n={len(g)}, цена за 3 сут {g.r72.mean()*100:+.1f}%, рынок {g.m72.mean()*100:+.1f}%")
print(C[C.side != 0].sample(12, random_state=2)[["s", "side", "x72", "txt"]].to_string(index=False))
