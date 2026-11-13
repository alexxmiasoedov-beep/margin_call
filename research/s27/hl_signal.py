"""s27 — Г1–Г3 по позициям пулов Hyperliquid (s27/pos.pkl, s27/pools.pkl) и часовым закрытиям фьючерсов Binance (s22/grid.pkl).
Г1: событие — за 4 ч не меньше k разных участников пула месяца открыли позицию в одну сторону по монете; вход на закрытии
следующего часа Binance; доход в сторону пула к рынку (медиана простой доходности всех фьючерсов) за 4/24/72 ч, минус 0,1%;
повтор той же монеты и стороны — не раньше чем через 24 ч.
Г2: сделки журналов (s20/trades.pkl и 🌊 из s23/rule_trades.pkl, шорты) — позиции участников топ-пула по монете в момент входа: «за нас» (шортов ≥ 2 и
больше, чем лонгов), «против» (лонгов ≥ 2 и больше, чем шортов), «нет».
Г3: каждые 4 ч чистая позиция пула по монете (лонги − шорты) / (лонги + шорты) при ≥ 5 участниках с позицией → ранговая
корреляция с доходом к рынку за 24 ч; t Ньюи — Уэста. Запуск из папки с данными."""
import pickle
import sys
import numpy as np, pandas as pd

CUT = 1764547200                                       # 01.12.2025 — граница половин
GR = pickle.load(open("s22/grid.pkl", "rb"))
g = GR["grid"]; C = GR["C"].astype(np.float64); ROW = GR["row"]
P = pickle.load(open("s27/pos.pkl", "rb"))
POOLS = pickle.load(open("s27/pools.pkl", "rb"))
MKEY = {int(k.timestamp()): v for k, v in POOLS.items()}
AIDX = {a: i for i, a in enumerate(P["addrs"])}
FIRST = P["first"]
H4 = 4 * 3600


def month_key(t):
    d = pd.Timestamp(int(t), unit="s", tz="UTC")
    return int(pd.Timestamp(year=d.year, month=d.month, day=1, tz="UTC").timestamp())


_mk = {}


def mk(h):
    if h not in _mk:
        with np.errstate(all="ignore"):
            r = C[:, h:] / C[:, :-h] - 1
            _mk[h] = np.r_[np.nanmedian(r, axis=0), np.full(h, np.nan)]
    return _mk[h]


def fwd(s, k, h, d):
    """Доход в сторону d с закрытия часа k на h ч к рынку; NaN, если нет цены."""
    if k + h >= len(g):
        return np.nan
    c = C[ROW[s]]; c0, c1 = c[k], c[k + h]
    if not (np.isfinite(c0) and np.isfinite(c1)):
        return np.nan
    return d * (c1 / c0 - 1) - d * mk(h)[k]


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 10:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), q.mean() / q.std() * np.sqrt(len(q)) if q.std() > 0 else np.nan, len(d)


def g1(pool, k, win=H4, cool=86400):
    O = P["opens"]
    members = {m: {AIDX[a] for a in v[pool] if a in AIDX} for m, v in MKEY.items()}
    mk_of = np.array([month_key(t) for t in O[:, 0]])
    keep = np.array([int(ai) in members.get(m, ()) for (t, ci, d, ai), m in zip(O, mk_of)])
    X = O[keep]
    ev = []
    for (ci, d), grp in pd.DataFrame(X, columns=["t", "ci", "d", "ai"]).groupby(["ci", "d"]):
        grp = grp.sort_values("t"); t = grp.t.values; ai = grp.ai.values
        last_ev = -1e18; j = 0
        for i in range(len(t)):
            while t[j] <= t[i] - win:
                j += 1
            if len(set(ai[j:i + 1])) >= k and t[i] - last_ev >= cool:
                ev.append((t[i], int(ci), int(d))); last_ev = t[i]
    rows = []
    for t, ci, d in ev:
        s = P["coins"][ci]; kk = int(np.searchsorted(g, t, "right"))
        if kk >= len(g):
            continue
        rows.append(dict(t=t, s=s, d=d, **{f"r{h}": fwd(s, kk, h, d) for h in (4, 24, 72)}))
    return pd.DataFrame(rows)


def pos_at(a, s, t):
    """Позиция счёта a по фьючерсу s в момент t; None — неизвестна (до первой доступной сделки счёта)."""
    if FIRST.get(a, np.inf) > t:
        return None
    x = P["series"].get((a, s))
    if x is None:
        return 0.0
    tt, pp = x
    i = int(np.searchsorted(tt, t, "right")) - 1
    return float(pp[max(i, 0)])


def journal_trades():
    """Сделки журналов (все — шорты): s20/trades.pkl (канал, 🇰🇷, 🇰🇷🆕, 🏦, 📢, 🆕) и 🌊 из s23/rule_trades.pkl (вход через 15 мин
    после начисления, стоп +15%)."""
    T = pd.read_pickle("s20/trades.pkl")[["s", "te", "net", "journal"]]
    F = pd.read_pickle("s23/rule_trades.pkl")
    F = pd.DataFrame(dict(s=F.s, te=F["T"] + 900, net=F["net0.15"], journal="🌊"))
    return pd.concat([T, F], ignore_index=True)


def g2(pool):
    T = journal_trades()
    out = []
    for r in T.itertuples():
        if r.s not in P["cidx"]:
            continue
        mem = MKEY.get(month_key(r.te), {}).get(pool, [])
        L = S = n = 0
        for a in mem:
            p = pos_at(a, r.s, r.te)
            if p is None:
                continue
            n += 1; L += p > 0; S += p < 0
        cls = "за нас" if S >= 2 and S > L else "против" if L >= 2 and L > S else "нет"
        out.append(dict(j=r.journal, s=r.s, te=r.te, net=r.net, L=L, S=S, n=n, cls=cls))
    return pd.DataFrame(out)


def g3(pool, step=H4, h=24, minpos=5):
    ks = np.flatnonzero(g % step == 0)
    coins = P["coins"]
    L = np.zeros((len(coins), len(ks))); S = np.zeros_like(L)
    tk = g[ks]
    for m, v in MKEY.items():
        nxt = int((pd.Timestamp(m, unit="s", tz="UTC") + pd.offsets.MonthBegin(1)).timestamp())
        sel = np.flatnonzero((tk >= m) & (tk < nxt))
        if not len(sel):
            continue
        for a in v[pool]:
            f = FIRST.get(a)
            if f is None:
                continue
            ok = sel[tk[sel] >= f]
            if not len(ok):
                continue
            for ci, s in enumerate(coins):
                x = P["series"].get((a, s))
                if x is None:
                    continue
                tt, pp = x
                i = np.searchsorted(tt, tk[ok], "right") - 1
                p = pp[np.maximum(i, 0)]
                L[ci, ok] += p > 0; S[ci, ok] += p < 0
    ics, ts = [], []
    for j, k in enumerate(ks):
        n = L[:, j] + S[:, j]
        m = n >= minpos
        if m.sum() < 10:
            continue
        net = (L[m, j] - S[m, j]) / n[m]
        r = np.array([fwd(coins[ci], k, h, 1) for ci in np.flatnonzero(m)])
        ok = np.isfinite(r)
        if ok.sum() < 10:
            continue
        ics.append(pd.Series(net[ok]).rank().corr(pd.Series(r[ok]).rank())); ts.append(tk[j])
    ic = pd.Series(ics, index=ts).dropna()
    return ic


def nw_t(x, lag):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; n = len(x)
    if n < 20:
        return np.nan
    e = x - x.mean(); v = e @ e / n
    for l in range(1, lag + 1):
        v += 2 * (1 - l / (lag + 1)) * (e[l:] @ e[:-l]) / n
    return x.mean() / np.sqrt(v / n)


if __name__ == "__main__":
    pools = ("top", "roi", "rand", "bottom")
    print("=== Г1: k участников пула открыли позицию в одну сторону за 4 ч → вход на следующем часе Binance, доход к рынку")
    for k in (3, 5, 10):
        for pl in pools:
            E = g1(pl, k)
            if E.empty:
                print(f"  k={k:2d} {pl:6s}: событий нет"); continue
            line = f"  k={k:2d} {pl:6s}: событий {len(E):5d} (лонг {np.mean(E.d > 0):.0%})"
            for h in (4, 24, 72):
                m, t, n = ct(E[f"r{h}"].values - 0.001, E.t.values)
                h1 = E[E.t < CUT][f"r{h}"].mean() - 0.001; h2 = E[E.t >= CUT][f"r{h}"].mean() - 0.001
                line += f" | {h}ч {m*100:+.2f}% (t {t:+.1f}; {h1*100:+.2f}/{h2*100:+.2f})"
            print(line)
    print("\n=== Г2: сделки журналов (шорты) по позициям пула в момент входа, чистый доход журнала")
    for pl in ("top", "roi", "rand"):
        D = g2(pl)
        print(f"  пул {pl}: сделок с монетой на Hyperliquid {len(D)} из {len(journal_trades())}")
        for cls, x in D.groupby("cls"):
            m, t, n = ct(x.net.values, x.te.values)
            print(f"    {cls:7s}: n={n:4d} {m*100:+.2f}% (t {t:+.1f}) в плюсе {(x.net > 0).mean():.0%}")
        if pl == "top":
            for j, x in D.groupby("j"):
                parts = []
                for cls in ("за нас", "нет", "против"):
                    y = x[x.cls == cls]
                    parts.append(f"{cls} {len(y)}: {y.net.mean()*100:+.2f}%" if len(y) else f"{cls} 0")
                print(f"      {j}: " + "; ".join(parts))
    print("\n=== Г3: чистая позиция пула → доход к рынку за 24 ч (ранговая корреляция каждые 4 ч)")
    for pl in pools:
        ic = g3(pl)
        if ic.empty:
            print(f"  {pl}: мало данных"); continue
        h1, h2 = ic[ic.index < CUT], ic[ic.index >= CUT]
        print(f"  {pl:6s}: срезов {len(ic)}, IC {ic.mean():+.4f} (t NW {nw_t(ic.values, 6):+.1f}); половины "
              f"{h1.mean():+.4f}/{h2.mean():+.4f}")
