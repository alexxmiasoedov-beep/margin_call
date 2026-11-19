"""s184 — Г1 (доля корейской розницы) и Г2/Г4 (OI) на одном периоде: недельные корзины на понедельник 00:00 UTC по признакам
s183 (feat2_<период>.pkl), шорт с закрытия свечи 00:00–00:15 на 168 ч, стоп +25%, хедж — индекс альтов s103 на фактический
срок, плацебо — та же монета за 45/90/135 сут. Гипотезы и пороги — ВЫВОДЫ.md (записаны до расчёта).
Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s184/run.py <период>  → s184_<период>.pkl"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s183", "study"))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import common183 as C3  # noqa: E402
from hyp_freq import KJ, recent_journal  # noqa: E402

DAY, OUT, N = 86400, "/home/user/mc_data", 5
L10, L15, L85, L90, L75, L95, L105 = (np.log(x) for x in (1.10, 1.15, 0.85, 0.90, 0.75, 0.95, 1.05))


def baskets(X, per):
    """{группа: [(d0, s, k)]} — k — место в корзине (для пар Г1)."""
    G = {}
    rng = np.random.default_rng(184)

    def add(name, d0, ss):
        G.setdefault(name, []).extend((d0, s, k) for k, s in enumerate(ss))

    for d0, g in X.groupby("d0"):
        g = g.copy()
        g["rq"] = g.qv7.rank(pct=True); g["rv"] = g.vol28.rank(pct=True)
        ok = ~g.kj7 & (g.f7 > -0.003)
        # Г1 и разрезы
        for name, cond in (("g1", (g.kshare7 >= 0.15) & ok), ("g1_t20", (g.kshare7 >= 0.20) & ok),
                           ("g1_t25", (g.kshare7 >= 0.25) & ok), ("g1_noveto", (g.kshare7 >= 0.15) & ~g.kj7),
                           ("g1_withj", (g.kshare7 >= 0.15) & (g.f7 > -0.003))):
            add(name, d0, list(g[cond].sort_values("kshare7", ascending=False).s.head(N)))
        add("g1_spot", d0, list(g[ok & g.sshare7.notna()].sort_values("sshare7", ascending=False).s.head(N)))
        # контроль (а): пары по рангам оборота и волатильности
        b = g[(g.kshare7 >= 0.15) & ok].sort_values("kshare7", ascending=False).head(N)
        pool = g[(g.kshare7 <= 0.03) & g.kshare7.notna() & ok & g.rv.notna()].copy()
        used = set()
        for k, r in enumerate(b.itertuples()):
            if not np.isfinite(r.rv) or not len(pool):
                continue
            q = pool[~pool.s.isin(used)]
            if not len(q):
                continue
            dist = np.hypot(q.rq - r.rq, q.rv - r.rv)
            s = q.s.iloc[int(np.argmin(dist.values))]
            used.add(s)
            G.setdefault("g1_ctl", []).append((d0, s, k))
        # Г2, Г4 — только срезы с OI
        h = g[g.oi_g7.notna()].copy()
        if not len(h):
            continue
        flat = h.r7.abs() <= L10
        add("g2_fall", d0, list(h[flat & (h.oi_g7 <= L85)].sort_values("oi_g7").s.head(N)))
        add("g2_grow", d0, list(h[flat & (h.oi_g7 >= L15)].sort_values("oi_g7", ascending=False).s.head(N)))
        add("g2_fall10", d0, list(h[flat & (h.oi_g7 <= L90)].sort_values("oi_g7").s.head(N)))
        add("g2_fall25", d0, list(h[flat & (h.oi_g7 <= L75)].sort_values("oi_g7").s.head(N)))
        u = h.oi_g7 + h.r7
        add("g2_usd", d0, list(h[flat & (u <= L85)].assign(u=u).sort_values("u").s.head(N)))
        fl = h[flat]
        if len(fl):
            add("g2_rand", d0, list(fl.s.iloc[rng.permutation(len(fl))[:N]]))
        h["r7_rk"] = h.r7.rank(pct=True); h["oi_rk"] = h.oi_g7.rank(pct=True)
        c = h[(h.r7 >= L10) & (h.oi_g7 <= L95)]
        add("g4_cover", d0, list(c.assign(sc=c.r7_rk - c.oi_rk).sort_values("sc", ascending=False).s.head(N)))
        c = h[(h.r7 >= L10) & (h.oi_g7 >= L105)]
        add("g4_build", d0, list(c.assign(sc=c.r7_rk + c.oi_rk).sort_values("sc", ascending=False).s.head(N)))
    return G


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

    X = pd.read_pickle(f"{OUT}/s183/feat2_{per}.pkl")
    X = X[X.liq5.astype(bool) & ~X.s.isin(["BTC", "ETH"]) & ~X.s.isin(C3.bad_set())]
    X = X.replace([np.inf, -np.inf], np.nan).copy()
    J = C3.journals(per)
    rj = recent_journal(J, KJ)
    X["kj7"] = [(d, s) in rj for d, s in zip(X.d0, X.s)]
    G = baskets(X, per)
    # доли Upbit и Bithumb за 7 сут до среза — для разреза Г1
    P = pd.read_pickle(f"{OUT}/s183/daily_{per}.pkl")[["d", "s", "krv_upbit", "krv_bithumb"]]
    need = {(d0, s) for d0, s, _ in G.get("g1", [])}
    Ps = {s: y for s, y in P[P.s.isin({s for _, s in need})].groupby("s")}
    ub = {}
    for (d0, s) in need:
        y = Ps.get(s)
        if y is None:
            continue
        y = y[(y.d >= d0 - 7 * DAY) & (y.d < d0)]
        ub[(d0, s)] = (y.krv_upbit.fillna(0).sum(), y.krv_bithumb.fillna(0).sum())
    feats = X.set_index(["d0", "s"])[["kshare7", "kprem7", "kabn", "f7", "oi_qv", "qv7", "sshare7", "oi_g7", "r7"]]
    med_oiqv = X.groupby("d0").oi_qv.median()
    cache, rows = {}, []
    for name, lst in G.items():
        for d0, s, k in lst:
            key = (int(d0), s)
            if key not in cache:
                cache[key] = None
                if s in K:
                    te = int(d0) + 900
                    lo, hi = live(s)
                    i = idx_at(s, te)
                    if np.isfinite(lo) and te >= lo + DAY and i is not None and int(K[s]["t"][i]) == int(d0):
                        x = trade(s, i, tp=None, sl=0.25, hold_h=168, side=-1)
                        if x:
                            t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
                            pl = []
                            for dd in (45, 90, 135):
                                j = idx_at(s, te - dd * DAY)
                                y = trade(s, j, tp=None, sl=0.25, hold_h=168, side=-1) if j is not None else None
                                if y:
                                    pl.append(y["net"])
                            cache[key] = dict(net=x["net"], why=x["why"], hed=x["net"] + mv(te, t_end),
                                              pl=np.mean(pl) if pl else np.nan)
            r = cache[key]
            if r is None:
                continue
            f = feats.loc[(d0, s)] if (d0, s) in feats.index else None
            u, b = ub.get((d0, s), (np.nan, np.nan))
            rows.append(dict(grp=name, d0=int(d0), t=int(d0) + 900, s=s, k=k, **r,
                             **({c: float(f[c]) for c in feats.columns} if f is not None else {}),
                             upbit=u, bithumb=b, oiqv_hi=bool(f is not None and f["oi_qv"] > med_oiqv.get(d0, np.nan))))
    R = pd.DataFrame(rows)
    R["per"] = per
    R.to_pickle(f"{OUT}/s184_{per}.pkl")
    print(per, R.groupby("grp").size().to_dict(), flush=True)


if __name__ == "__main__":
    run(sys.argv[1])
