"""События маржинального бота CryptoCode (MarginData, посты раз в 5 мин с 20.02.2025) по логике автора канала:
ENTER — монета появилась в списке (B/R ≥ 3) после ≥ 24 ч отсутствия; JUMP — займ за 24 ч (BOR) вырос в ≥ 2 раза за час
(как платный бот B.PREV → B.NOW); REPAY — после ≥ 6 ч в списке отдача (REP) выросла в ≥ 2 раза за час или монета ушла из списка.
Контекст на закрытии 15-мин свечи после поста (вход по закрытию): рост за 4/24/72 ч, размах за 48 ч (флэт), фандинг, доля покупок
тейкеров, объём, BTC. Исходы лонга и шорта: сетка тейк × стоп за 48 ч, стоп первым в общей свече, комиссия 0,1%, фактический фандинг."""
import pickle, re, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], m["PT"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
sym_of = {}
for s in K:
    sym_of.setdefault(strip(s), s)
TP = (3, 5, 7, 10, 15, 20, 30); SL = (5, 7, 10, 15, 20, 25); HOLD = 192
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
def fund_sum(s, a, b):
    fr = F.get(s)
    if fr is None: return 0.0
    ft = fr[:, 0]; k0, k1 = np.searchsorted(ft, a, "right"), np.searchsorted(ft, b, "right"); return float(fr[k0:k1, 2].sum())
def outcomes(s, j):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + HOLD, len(t) - 1)
    if end <= j: return None
    hi = a["h"][j + 1:end + 1].astype(np.float64) / e - 1; lo = a["l"][j + 1:end + 1].astype(np.float64) / e - 1
    out = {}
    for side in ("L", "S"):
        for tp in TP:
            for sl in SL:
                if side == "L": gq = np.flatnonzero(hi >= tp / 100); bq = np.flatnonzero(lo <= -sl / 100)
                else: gq = np.flatnonzero(lo <= -tp / 100); bq = np.flatnonzero(hi >= sl / 100)
                g = gq[0] if len(gq) else 10**9; b = bq[0] if len(bq) else 10**9
                if b <= g and b < 10**9: q = b; px = -sl / 100
                elif g < 10**9: q = g; px = tp / 100
                else: q = end - j - 1; px = (float(a["c"][end]) / e - 1) * (1 if side == "L" else -1)
                fs = fund_sum(s, t[j] + 900, t[j + 1 + q] + 900)
                out[f"{side}_{tp}_{sl}"] = px - 0.001 - (fs if side == "L" else -fs)
    for hh, n in (("r4", 16), ("r24", 96), ("r48", 192)):
        out[hh] = float(a["c"][min(j + n, len(t) - 1)]) / e - 1
    out["mfe48"] = float(hi.max()); out["mae48"] = float(lo.min())
    return out
def ctx(s, j):
    a = K[s]; c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); l = a["l"].astype(np.float64); qv = a["qv"].astype(np.float64)
    tb = a["tb"].astype(np.float64); t = a["t"]
    if j < 300: return None
    r = lambda n: c[j] / c[j - n] - 1
    rng48 = h[j - 191:j + 1].max() / l[j - 191:j + 1].min() - 1
    rng24 = h[j - 95:j + 1].max() / l[j - 95:j + 1].min() - 1
    v24 = qv[j - 95:j + 1].sum(); v7 = qv[max(0, j - 671):j + 1].sum() / 7
    tb4 = tb[j - 15:j + 1].sum() / max(qv[j - 15:j + 1].sum(), 1); tb24 = tb[j - 95:j + 1].sum() / max(v24, 1)
    fr = F.get(s); f_last = np.nan
    if fr is not None:
        k = np.searchsorted(fr[:, 0], t[j] + 900, "right") - 1
        if k >= 0: f_last = float(fr[k, 2])
    hi7 = c[j] / h[max(0, j - 671):j - 95].max() - 1 if j > 96 else np.nan
    return dict(r4=r(16), r24=r(96), r72=r(288), rng24=rng24, rng48=rng48, v24=v24, vr=v24 / max(v7, 1), tb4=tb4, tb24=tb24, f_last=f_last, hi7=hi7)
# 15-мин сетка постов канала: для каждой монеты последнее значение в каждой 15-мин свече
rows = []
BT = K["BTC"]; bt_t = BT["t"]; bt_c = BT["c"].astype(np.float64)
for c0, arr in G.items():
    s = sym_of.get(c0) or sym_of.get(strip(c0))
    if s is None or s not in K: continue
    a = K[s]; t = a["t"]
    tt = arr[:, 0]; bor = arr[:, 1]; rep = arr[:, 2]; br = arr[:, 3]
    # индекс 15-мин свечи, в которую попадает пост (свеча открыта в t, закрыта в t+900): вход на закрытии этой свечи
    jb = np.searchsorted(t, tt, "right") - 1
    ok = (jb >= 0) & (jb < len(t)); tt, bor, rep, br, jb = tt[ok], bor[ok], rep[ok], br[ok], jb[ok]
    if not len(tt): continue
    last_seen = -1e18; run_start = None; prev = None; hist = []  # история (t, bor, rep) последних постов
    i = 0; n = len(tt)
    # сгруппировать посты по свечам
    ub, first_idx = np.unique(jb, return_index=True)
    last_idx = np.r_[first_idx[1:] - 1, n - 1]
    for u, i0, i1 in zip(ub, first_idx, last_idx):
        T = tt[i1]; B = bor[i1]; R = rep[i1]; Q = br[i1]
        gap = tt[i0] - last_seen
        ev = []
        if gap > 24 * 3600: ev.append("ENTER"); run_start = tt[i0]
        elif gap > 30 * 60: run_start = tt[i0]
        # значения час назад (последний пост в окне [T-75 мин, T-45 мин])
        hist = [x for x in hist if x[0] >= T - 2 * 3600]
        past = [x for x in hist if T - 75 * 60 <= x[0] <= T - 45 * 60]
        if past:
            pb, pr = past[-1][1], past[-1][2]
            if B >= 2 * pb and B - pb >= 50e3: ev.append("JUMP")
            if run_start is not None and T - run_start >= 6 * 3600 and R >= 2 * max(pr, 1) and R - pr >= 20e3: ev.append("REPAY")
        hist.append((T, B, R)); last_seen = tt[i1]
        for e in ev:
            rows.append(dict(s=s, ev=e, t=float(T), j=int(u), bor=B, rep=R, br=Q, run_h=(T - run_start) / 3600 if run_start else 0.0))
    # выход из списка после ≥ 6 ч непрерывно (следующий пост монеты через > 2 ч или нет вовсе)
    gaps = np.diff(tt); idx = np.flatnonzero(gaps > 2 * 3600)
    starts = np.r_[0, idx + 1]; ends = np.r_[idx, len(tt) - 1]
    for st, en in zip(starts, ends):
        if tt[en] - tt[st] >= 6 * 3600 and tt[en] < PT[-1] - 3 * 3600:
            j = int(np.searchsorted(t, tt[en] + 3600, "right") - 1)   # через час после последнего поста — монета точно вышла
            rows.append(dict(s=s, ev="EXIT", t=float(tt[en] + 3600), j=j, bor=bor[en], rep=rep[en], br=br[en], run_h=(tt[en] - tt[st]) / 3600))
E = pd.DataFrame(rows); print(E.ev.value_counts().to_dict())
out = []
for x in E.itertuples():
    c = ctx(x.s, x.j)
    if c is None: continue
    o = outcomes(x.s, x.j)
    if o is None: continue
    kb = np.searchsorted(bt_t, K[x.s]["t"][x.j]); btc24 = bt_c[kb] / bt_c[kb - 96] - 1 if kb >= 96 and kb < len(bt_c) else np.nan
    out.append({**x._asdict(), **{f"c_{k}": v for k, v in c.items()}, **o, "btc24": btc24})
D = pd.DataFrame(out).drop(columns=["Index"]); D["half"] = np.where(D.t < CUT, 1, 2)
D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
D.to_pickle("s9/md_events.pkl"); print(len(D), "событий с исходами;", D.groupby("ev").size().to_dict())
