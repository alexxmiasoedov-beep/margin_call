"""Движок поиска параметров сигнала на таблице кандидатов grid.pkl."""
import pickle, datetime, numpy as np, pandas as pd
from numba import njit
UTC = datetime.timezone.utc
ts = lambda *a: int(datetime.datetime(*a, tzinfo=UTC).timestamp())
G = pickle.load(open("grid.pkl", "rb")); D = G["D"]; CFd = G["CF"]; GRID = G["GRID"]
SYMS = sorted(D.sym.unique()); SC = {s: k for k, s in enumerate(SYMS)}
symc = D.sym.map(SC).values.astype(np.int64); bar = D.bar.values.astype(np.int64)
off = {}; parts = []; o = 0
for s in SYMS:
    off[s] = o; parts.append(CFd[s]); o += len(CFd[s])
CFall = np.concatenate(parts); gidx = (D.sym.map(off).values + D.i.values).astype(np.int64)
N, TAK, MAK, SLIP = 10.0, 0.0005, 0.0002, 0.002
SEG = [("S1 25.02–05.25", ts(2025, 2, 23), ts(2025, 6, 1)), ("S2 06–08.25", ts(2025, 6, 1), ts(2025, 9, 1)),
       ("S3 09–11.25", ts(2025, 9, 1), ts(2025, 12, 1)), ("S4 12.25–01.26", ts(2025, 12, 1), ts(2026, 2, 1)),
       ("T1 02–04.26", ts(2026, 2, 1), ts(2026, 5, 1)), ("T2 05–07.26", ts(2026, 5, 1), ts(2026, 8, 1)), ("T3 08–09.26", ts(2026, 8, 1), ts(2026, 10, 1))]
TRAIN_END = ts(2026, 2, 1)
seg_id = np.zeros(len(D), np.int64)
for k, (_, a, b) in enumerate(SEG): seg_id[(bar >= a) & (bar < b)] = k
_EX = {}
def exits(tp, sl, hold=192):
    key = (tp, sl, hold)
    if key in _EX: return _EX[key]
    av = D.avail.values.astype(np.int64); lim = np.minimum(hold, av)
    js = D[f"jsl{sl}"].values.astype(np.int64); jt = D[f"jtp{tp}"].values.astype(np.int64) if tp else np.full(len(D), 255)
    stop = (js <= lim) & (js <= jt); take = (jt <= lim) & (jt < js) & ~stop; tm = ~stop & ~take
    r = np.where(lim >= 192, D.r48.values, np.where(lim >= 96, np.where(hold == 96, D.r24.values, D.rlast.values), D.rlast.values)).astype(np.float64)
    r = np.where((hold == 96) & (av >= 96), D.r24.values, r)
    j = np.where(stop, js, np.where(take, jt, lim))
    px = np.where(stop, (1 + sl / 100) * (1 + SLIP), np.where(take, 1 - (tp or 0) / 100, r))
    fee = N * TAK + N * px * np.where(take, MAK, TAK)
    fund = N * (CFall[gidx + j] - CFall[gidx])
    pnl = N * (1 - px) - fee + fund
    pnl = np.where(np.isnan(pnl), 0.0, pnl)
    out = (pnl, bar + 900 * (j + 1), stop, take, fund); _EX[key] = out
    return out
@njit(cache=True)
def _select(symc, bar, mask, exit_t, stop, nsym, cooldown, pause):
    nxt = np.full(nsym, -1e18); take = np.zeros(len(mask), np.bool_)
    for k in range(len(mask)):
        if mask[k]:
            s = symc[k]
            if bar[k] >= nxt[s]:
                take[k] = True
                v = max(bar[k] + cooldown, exit_t[k])
                if stop[k]: v = max(v, exit_t[k] + pause)
                nxt[s] = v
    return take
def trades(mask, tp, sl, hold=192, cooldown=86400, pause=172800):
    pnl, et, st, tk, fu = exits(tp, sl, hold)
    sel = _select(symc, bar, mask, et, st, len(SYMS), cooldown, pause)
    return sel, pnl, st, tk, fu
def stats(mask, tp, sl, hold=192, **kw):
    sel, pnl, st, tk, fu = trades(mask, tp, sl, hold, **kw)
    p = pnl[sel]; sg = seg_id[sel]; tr = bar[sel] < TRAIN_END
    segs = np.array([p[sg == k].sum() for k in range(len(SEG))]); segn = np.array([(sg == k).sum() for k in range(len(SEG))])
    def part(m):
        x = p[m]; n = len(x)
        if n < 2: return dict(n=n, sum=x.sum(), mean=np.nan, t=np.nan)
        return dict(n=n, sum=x.sum(), mean=x.mean(), t=x.mean() / (x.std() / np.sqrt(n)))
    eq = np.cumsum(p); dd = (eq - np.maximum.accumulate(eq)).min() if len(p) else 0
    return dict(train=part(tr), test=part(~tr), all=part(np.ones(len(p), bool)), segs=segs, segn=segn, dd=dd,
                stop=st[sel].mean() if sel.any() else np.nan, takep=tk[sel].mean() if sel.any() else np.nan, fund=fu[sel].sum())
def fmt(r):
    s = " ".join(f"{v:+5.1f}" for v in r["segs"])
    return (f"обуч n={r['train']['n']:4d} {r['train']['sum']:+6.1f} ({r['train']['mean']:+.3f}, t={r['train']['t']:+.1f}) | "
            f"проверка n={r['test']['n']:4d} {r['test']['sum']:+6.1f} ({r['test']['mean']:+.3f}, t={r['test']['t']:+.1f}) | "
            f"кварталы [{s}] | стоп {r['stop']*100:.0f}% тейк {r['takep']*100:.0f}% | фанд {r['fund']:+.0f} | просадка {r['dd']:+.1f}")
