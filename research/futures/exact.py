"""Точная перепроверка сделок грубой модели: вход по open минуты на закрытии 15-мин свечи, путь по минутным свечам
цены (тейк) и марк-цены (стоп +0,2%), фандинг Binance от текущей стоимости позиции, комиссии maker/taker."""
import datetime, numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv, search as S
UTC = datetime.timezone.utc
N, TAK, MAK, SLIP = 10.0, 0.0005, 0.0002, 0.002
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
MONTHS = [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
_F = {}
def fund(sym):
    if sym not in _F: _F[sym] = bv.funding(sym, MONTHS)
    return _F[sym]
def path(sym, t0):
    days = sorted({day(t) for t in range(t0, t0 + 49 * 3600, 3600)})
    a = bv.klines(sym, "klines", "1m", (), days); m = bv.klines(sym, "markPriceKlines", "1m", (), days)
    return a, m
def sim_one(sym, t0, tp, sl, hold=48):
    a, m = path(sym, t0)
    if a is None: return None
    sel = (a[:, 0] >= t0) & (a[:, 0] < t0 + hold * 3600); A = a[sel]
    if len(A) < 10: return None
    mm = dict(zip(m[:, 0].astype(int), m[:, 2])) if m is not None else {}
    t, o, h, l, c = A[:, 0].astype(int), A[:, 1], A[:, 2], A[:, 3], A[:, 4]
    mh = np.array([mm.get(x, y) for x, y in zip(t, h)])
    e = o[0]; slp = e * (1 + sl / 100); tpp = e * (1 - tp / 100) if tp else None
    js = np.nonzero(mh >= slp)[0]; js = js[0] if len(js) else len(t)
    jt = np.nonzero(l < tpp)[0] if tpp else []; jt = jt[0] if len(jt) else len(t)
    j = min(js, jt)
    if j == len(t): j = len(t) - 1; px = c[j]; kind = "время"; fx = TAK
    elif j == js: px = slp * (1 + SLIP); kind = "стоп"; fx = TAK
    else: px = tpp; kind = "тейк"; fx = MAK
    xt = t[j] + 60; F = fund(sym); fu = 0.0
    if F is not None:
        for ft, r in F[(F[:, 0] > t0) & (F[:, 0] <= xt)]:
            k = min(np.searchsorted(t, ft), len(c) - 1); fu += r * N * c[k] / e
    return dict(kind=kind, pnl=N * (1 - px / e) - N * TAK - N * (px / e) * fx + fu, fund=fu)
def run(mask, tp, sl, label=""):
    sel, pnl, st, tk, fu = S.trades(mask, tp, sl)
    T = S.D[sel][["sym", "bar"]].copy(); T["coarse"] = pnl[sel]; T["seg"] = S.seg_id[sel]
    jobs = list(zip(T.sym, (T.bar + 900).astype(int)))
    with ThreadPoolExecutor(16) as ex:
        R = list(ex.map(lambda x: sim_one(x[0], x[1], tp, sl), jobs))
    T["exact"] = [r["pnl"] if r else np.nan for r in R]; T["kind"] = [r["kind"] if r else None for r in R]
    T = T[T.exact.notna()]
    segs_c = T.groupby("seg").coarse.sum().reindex(range(7), fill_value=0); segs_e = T.groupby("seg").exact.sum().reindex(range(7), fill_value=0)
    eq = T.exact.cumsum(); dd = (eq - eq.cummax()).min()
    print(f"{label:50s} {tp}/{sl}: сделок {len(T)} | грубо {T.coarse.sum():+6.1f} | ТОЧНО {T.exact.sum():+6.1f} ({T.exact.mean():+.3f}/сд, стопов {(T.kind == 'стоп').mean()*100:.0f}%) "
          f"| точно по кварталам [{' '.join(f'{x:+5.1f}' for x in segs_e)}] в плюсе {(segs_e > 0).sum()}/7 | просадка {dd:+.1f}", flush=True)
    return T
if __name__ == "__main__":
    v = {c: S.D[c].values for c in S.D.columns if S.D[c].dtype != object}
    n0 = lambda x: np.nan_to_num(x, nan=-1e9)
    r1 = (v["run_h"] >= 4) & (v["ch_4h"] >= 8) & (v["ch_4h"] <= 17)
    r2 = (v["run_h"] >= 4) & (v["ch_4h"] <= -8) & (v["ch_4h"] >= -17) & (v["br"] >= 5)
    Dst = (v["run_h"] >= 2) & (v["ch_12h"] <= -4) & (n0(v["btc_24h"]) > 0) & (n0(v["qv24_m"]) >= 20) & (v["br"] >= 30)
    Pst = (v["run_h"] >= 1) & (v["ch_12h"] >= 2) & (n0(-v["btc_30d"]) > 0) & (n0(v["qv24_m"]) >= 20)
    import pickle
    out = {}
    for lab, m, ex in (("текущие правила 1+2", r1 | r2, ((6, 20), (15, 25))), ("D*", Dst, ((10, 20), (15, 25))), ("P*+объём", Pst, ((10, 20), (15, 25)))):
        for tp, sl in ex: out[(lab, tp, sl)] = run(m, tp, sl, lab)
    pickle.dump(out, open("exact_out.pkl", "wb"))
