"""Признаки каждого пампа (только данные до момента T — закрытия свечи, где впервые достигнуто +15%) и исходы сделок
с барьерами (тейк / стоп / 48 ч, стоп первым в общей свече, комиссия 0,1%, фактический фандинг) для шорта и лонга."""
import pickle, re, os, glob, datetime
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
UTC = datetime.timezone.utc
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]
P = pd.read_pickle("s2/pump_TRY.pkl"); assert len(P) == len(EV) and all(P.s.values == [e["s"] for e in EV])
key = lambda d: {(s, int(t)): r for s, t, r in zip(d.s, d.t, d.to_dict("records"))}
SPOT = key(pd.read_pickle("s5/pump_spot.pkl")); THB = key(pd.read_pickle("s4/pump_THB.pkl"))
VEN = {v: key(pd.read_pickle(f"s5/pump_{v}.pkl")) for v in ("cb", "okx", "ku", "bg")}
MET = key(pd.read_pickle("s6/ev_metrics.pkl")) if os.path.exists("s6/ev_metrics.pkl") else {}
# курс KRW-USDT для корейских окон
FX = {}
for ex in ("upbit", "bithumb"):
    a = np.vstack([np.load(f) for f in glob.glob(f"mm2/korea2y/{ex}_USDT_*.npy") if os.path.getsize(f) > 200])
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True); FX[ex] = a[u]
# сетка времени для ширины рынка
GT = np.load("s4/T.npy"); GC = np.load("s4/G_c.npy"); GSYM = pickle.load(open("s4/syms.pkl", "rb"))
B = K["BTC"]; bt_ix = {int(t): i for i, t in enumerate(B["t"])}; bc = B["c"].astype(np.float64)
evt = np.array([e["t_in"] for e in EV]); order = np.argsort(evt); evt_sorted = evt[order]
FC = {s: (fr[:, 0].astype(np.float64), np.concatenate([[0.0], np.cumsum(fr[:, 2].astype(np.float64))]), fr[:, 1], fr[:, 2].astype(np.float64)) for s, fr in F.items()}
def fsum(s, a, b):
    f = FC.get(s)
    if f is None: return 0.0
    return float(f[1][np.searchsorted(f[0], b, "right")] - f[1][np.searchsorted(f[0], a, "right")])
TPS = (0.03, 0.05, 0.07, 0.1, 0.15, 0.2, 0.3); SLS = (0.05, 0.07, 0.1, 0.15, 0.2, 0.25, 0.3)
def outcomes(s, j, hold=192):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64) / e - 1; lo = a["l"][j + 1:end + 1].astype(np.float64) / e - 1
    out = {"mfe_s24": -lo[:96].min() if len(lo) else np.nan, "mae_s24": hi[:96].max() if len(hi) else np.nan,
           "mfe_s48": -lo.min() if len(lo) else np.nan, "mae_s48": hi.max() if len(hi) else np.nan, "ret48": float(a["c"][end]) / e - 1,
           "ret24": float(a["c"][min(j + 96, len(t) - 1)]) / e - 1, "ret4": float(a["c"][min(j + 16, len(t) - 1)]) / e - 1, "full": end == j + hold}
    if not len(hi): return out
    t_in = t[j] + 900
    for side in (-1, 1):
        for tp in TPS:
            for sl in SLS:
                if side < 0: bad = np.flatnonzero(hi >= sl); good = np.flatnonzero(lo <= -tp)
                else: bad = np.flatnonzero(lo <= -sl); good = np.flatnonzero(hi >= tp)
                q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
                if q1 <= q2 and q1 < 10**9: q = q1; px = -sl
                elif q2 < 10**9: q = q2; px = tp
                else: q = len(hi) - 1; px = side * out["ret48"]
                fd = fsum(s, t_in, t[j + 1 + q] + 900)                    # для шорта: >0 получил
                out[f"{'S' if side < 0 else 'L'}_{int(tp * 100)}_{int(sl * 100)}"] = px - 0.001 + (fd if side < 0 else -fd)
    return out
def kr_arrays(e, w):
    n = len(w); vol = np.zeros(n); close = np.full(n, np.nan); listed = []
    for ex in ("upbit", "bithumb"):
        fn = f"mm2/korea2y/{ex}_{strip(e['s'])}_{int(e['t_in'] + 26 * 3600)}.npy"
        if not os.path.exists(fn): continue
        a = np.load(fn)
        if not len(a): continue
        listed.append(ex)
        idx = np.searchsorted(w[:, 0], a[:, 0]); ok = idx < n; ok[ok] &= w[idx[ok], 0] == a[ok, 0]
        fxv = np.interp(a[:, 0], FX[ex][:, 0], FX[ex][:, 4]); np.add.at(vol, idx[ok], a[ok, 5] / fxv[ok])
        sel = idx[ok]; fill = np.isnan(close[sel]); close[sel[fill]] = (a[ok, 4] / fxv[ok])[fill]
    return (vol, close) if listed else None
prev = {}   # монета → [(t, pnl_short_10_25, kshare)]
rows = []
LIMIT = int(os.environ.get("LIMIT", "0")) or len(EV)
for n_, (e, p) in enumerate(zip(EV[:LIMIT], P.itertuples())):
    s, T = e["s"], int(e["t_in"]); a = K[s]; t = a["t"]; jK = int(np.searchsorted(t, T - 900))
    if jK >= len(t) or t[jK] != T - 900 or jK < 700: continue
    iK = jK - (e["j"] - e["i"])
    o, h, l, c = (a[x].astype(np.float64) for x in ("o", "h", "l", "c")); qv = a["qv"].astype(np.float64); tb = a["tb"].astype(np.float64); nt = a["n"].astype(np.float64)
    lr = np.diff(np.log(np.maximum(c[jK - 700:jK + 1], 1e-12)))
    r = dict(s=s, t=T, i=n_,
             mag=h[iK + 1:jK + 1].max() / c[iK] - 1, cret=c[jK] / c[iK] - 1, dur=(jK - iK) * 15,
             wick=(h[jK] - c[jK]) / max(h[jK] - l[jK], 1e-12), body=c[jK] / o[jK] - 1, last15=c[jK] / c[jK - 1] - 1,
             rb4=c[iK] / c[iK - 16] - 1, rb24=c[iK] / c[iK - 96] - 1, rb7=c[iK] / c[iK - 672] - 1,
             hi7=c[jK] / h[jK - 672:iK + 1].max() - 1, lo7=c[jK] / l[jK - 672:iK + 1].min() - 1,
             hi30=c[jK] / h[max(0, jK - 2880):iK + 1].max() - 1 if jK >= 2880 else np.nan,
             vtrig=qv[jK] / max(qv[jK - 96:jK].mean(), 1), v1h=qv[jK - 3:jK + 1].sum() / max(qv[jK - 96:jK - 3].sum() / 23.25, 1),
             v24_7=qv[jK - 95:jK + 1].sum() / max(qv[jK - 671:jK - 95].sum() / 6, 1), v24=qv[jK - 95:jK + 1].sum(), vpump=qv[iK + 1:jK + 1].sum(),
             tb_trig=tb[jK] / max(qv[jK], 1), tb_1h=tb[jK - 3:jK + 1].sum() / max(qv[jK - 3:jK + 1].sum(), 1),
             tb_pump=tb[iK + 1:jK + 1].sum() / max(qv[iK + 1:jK + 1].sum(), 1), tb_pre=tb[iK - 96:iK].sum() / max(qv[iK - 96:iK].sum(), 1),
             ntr=nt[jK] / max(nt[jK - 96:jK].mean(), 1),
             tsize=(qv[iK + 1:jK + 1].sum() / max(nt[iK + 1:jK + 1].sum(), 1)) / max(qv[iK - 96:iK].sum() / max(nt[iK - 96:iK].sum(), 1), 1e-9),
             vol24=lr[-97:-1].std(), vol7=lr.std(), price=np.log10(max(c[jK], 1e-12)), pref=int(strip(s) != s),
             age=(T - t[0]) / 86400, old=int(t[0] <= GT[0]), hour=(T // 3600) % 24, dow=(T // 86400 + 3) % 7)
    # фандинг
    f = FC.get(s)
    if f is not None:
        k = np.searchsorted(f[0], T, "right") - 1
        if k >= 0:
            iv = float(f[2][k]) or 8.0; r.update(f_last=f[3][k], f_iv=iv, f_24=fsum(s, T - 86400, T), f_72=fsum(s, T - 3 * 86400, T),
                                                  f_next=((T // int(iv * 3600) + 1) * int(iv * 3600) - T) / 60)
    # рынок
    bi = bt_ix.get(T - 900)
    if bi and bi >= 96: r.update(btc1=bc[bi] / bc[bi - 4] - 1, btc4=bc[bi] / bc[bi - 16] - 1, btc24=bc[bi] / bc[bi - 96] - 1)
    gi = np.searchsorted(GT, T - 900)
    if gi < len(GT) and GT[gi] == T - 900 and gi >= 96:
        rr = GC[gi] / GC[gi - 96] - 1; rr = rr[~np.isnan(rr)]; r["breadth"] = (rr > 0).mean() if len(rr) > 50 else np.nan; r["alt24"] = np.median(rr) if len(rr) > 50 else np.nan
    a0 = np.searchsorted(evt_sorted, T - 86400); a1 = np.searchsorted(evt_sorted, T); r["pumps24"] = a1 - a0; r["pumps1h"] = a1 - np.searchsorted(evt_sorted, T - 3600)
    # история монеты
    hist = prev.get(s, [])
    r["prev30"] = sum(1 for tt, _, _ in hist if tt > T - 30 * 86400)
    done = [(tt, pn, ks) for tt, pn, ks in hist if tt + 48 * 3600 <= T]
    r["prev_pnl"] = done[-1][1] if done else np.nan; r["prev_gap"] = (T - hist[-1][0]) / 86400 if hist else np.nan
    # площадки
    r.update(korea=int(bool(p.korea)), kshare=p.kshare if p.korea else 0.0, has_try=int(bool(p.has)), fshare=p.fshare if p.has else 0.0)
    def fix(pr):        # премия площадки к фьючерсу; у 1000X и подобных цены в разных единицах — берём множитель, при котором отношение ближе к 1
        if not (pr == pr) or pr <= -1: return np.nan
        q = pr + 1; return min((q * m for m in (1e-6, 1e-3, 1, 1e3, 1e4, 1e5, 1e6)), key=lambda z: abs(np.log(z))) - 1
    sp = SPOT.get((s, T)); r["has_spot"] = int(bool(sp and sp.get("has")))
    if sp and sp.get("has"): r.update(sshare=sp["share"], snorm=sp["norm"], sx=sp["x"], sbuy=sp["sbuy"], sprem=fix(sp["prem"]))
    th = THB.get((s, T)); r["thai"] = th["tshare"] if th and th.get("thas") else np.nan
    for v, d in VEN.items():
        x = d.get((s, T))
        if x and x.get("has"): r[f"{v}_sh"] = x["share"]; r[f"{v}_x"] = x["x"]; r[f"{v}_prem"] = fix(x["prem"])
    w = e["w"]; j = e["j"]; ka = kr_arrays(e, w)
    if ka is not None:
        vol, kc = ka; hv = [vol[m - 3:m + 1].sum() / max(vol[m - 3:m + 1].sum() + w[m - 3:m + 1, 4].sum(), 1) for m in range(j - 4, max(j - 96, 3), -4)]
        r["k_norm"] = np.median(hv) if hv else np.nan
        r["k_prem"] = fix(kc[j] / w[j, 3] - 1) if not np.isnan(kc[j]) else np.nan
        pre = vol[max(0, j - 96):j - 3].sum(); r["k_v1h"] = vol[j - 3:j + 1].sum() / max(pre / 23.25, 1)
    mt = MET.get((s, T))
    if mt:
        for kk, vv in mt.items():
            if kk not in ("s", "t"): r[f"m_{kk}"] = vv
        if mt.get("oi_usd") == mt.get("oi_usd"): r["m_oi_v24"] = mt["oi_usd"] / max(r["v24"], 1)
    r.update(outcomes(s, jK))
    prev.setdefault(s, []).append((T, r.get("S_10_25", np.nan), r["kshare"]))
    rows.append(r)
    if n_ % 1000 == 0: print(n_, flush=True)
D = pd.DataFrame(rows); D["y"] = np.where(D.t < datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp(), 1, 2)
D.to_pickle("s6/feat.pkl" if LIMIT == len(EV) else "s6/feat_test.pkl"); print(D.shape); print(D.notna().mean().round(2).to_string())
