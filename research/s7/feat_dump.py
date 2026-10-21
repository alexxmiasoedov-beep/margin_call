"""Признаки каждого дампа (−15% за ≤ 2 ч из покоя) строго до момента T и исходы сделок в обе стороны — зеркало s6/feat.py.
Доли площадок считаются здесь же: Корея (Upbit + Bithumb), пара к лире, спот Binance (доля, обычная доля, тейкеры, премия)."""
import pickle, re, os, glob, datetime
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
UTC = datetime.timezone.utc
src = open("s6/feat.py").read()
# общие части: загрузка K, F, фандинг, исходы, корейские окна, рынок
exec(src.split("P = pd.read_pickle")[0])
exec("FX = {}" + src.split("FX = {}")[1].split("prev = {}")[0].replace('evt = np.array([e["t_in"] for e in EV])', 'evt = np.array([e["t_in"] for e in pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]])'))
EV = pickle.load(open("s7/dumps.pkl", "rb")); dvt = np.sort(np.array([e["t_in"] for e in EV]))
X = pickle.load(open("s2/fiat_TRY.pkl", "rb")); TP, TD = X["pairs"], X["D"]; tfx = TD["USDTTRY"]
key = lambda d: {(s, int(t)): r for s, t, r in zip(d.s, d.t, d.to_dict("records"))}
MET = key(pd.read_pickle("s7/ev_metrics_dump.pkl")) if os.path.exists("s7/ev_metrics_dump.pkl") else {}
PRE = key(pd.read_pickle("s7/ev_premium_dump.pkl")) if os.path.exists("s7/ev_premium_dump.pkl") else {}
MAR = key(pd.read_pickle("s7/ev_margin_dump.pkl")) if os.path.exists("s7/ev_margin_dump.pkl") else {}
SPC = {}
def spot(s):
    if s not in SPC:
        SPC[s] = None
        for n in (s, strip(s)):
            fn = f"s5/spot/{n}USDT.npy"
            if os.path.exists(fn):
                a = np.load(fn)
                if len(a): SPC[s] = a; break
    return SPC[s]
def fixp(pr):
    if not (pr == pr) or pr <= -1: return np.nan
    q = pr + 1; return min((q * m for m in (1e-6, 1e-3, 1, 1e3, 1e4, 1e5, 1e6)), key=lambda z: abs(np.log(z))) - 1
prev = {}; rows = []
for n_, e in enumerate(EV):
    s, T, jK, iK = e["s"], int(e["t_in"]), e["jK"], e["iK"]; a = K[s]; t = a["t"]
    if jK < 700: continue
    o, h, l, c = (a[x].astype(np.float64) for x in ("o", "h", "l", "c")); qv = a["qv"].astype(np.float64); tb = a["tb"].astype(np.float64); nt = a["n"].astype(np.float64)
    lr = np.diff(np.log(np.maximum(c[jK - 700:jK + 1], 1e-12)))
    r = dict(s=s, t=T, mag=1 - l[iK + 1:jK + 1].min() / c[iK], cret=c[jK] / c[iK] - 1, dur=(jK - iK) * 15,
             wick=(c[jK] - l[jK]) / max(h[jK] - l[jK], 1e-12), body=c[jK] / o[jK] - 1, last15=c[jK] / c[jK - 1] - 1,
             rb4=c[iK] / c[iK - 16] - 1, rb24=c[iK] / c[iK - 96] - 1, rb7=c[iK] / c[iK - 672] - 1,
             hi7=c[jK] / h[jK - 672:iK + 1].max() - 1, lo7=c[jK] / l[jK - 672:iK + 1].min() - 1,
             lo30=c[jK] / l[max(0, jK - 2880):iK + 1].min() - 1 if jK >= 2880 else np.nan,
             vtrig=qv[jK] / max(qv[jK - 96:jK].mean(), 1), v1h=qv[jK - 3:jK + 1].sum() / max(qv[jK - 96:jK - 3].sum() / 23.25, 1),
             v24_7=qv[jK - 95:jK + 1].sum() / max(qv[jK - 671:jK - 95].sum() / 6, 1), v24=qv[jK - 95:jK + 1].sum(), vmove=qv[iK + 1:jK + 1].sum(),
             tb_trig=tb[jK] / max(qv[jK], 1), tb_1h=tb[jK - 3:jK + 1].sum() / max(qv[jK - 3:jK + 1].sum(), 1),
             tb_move=tb[iK + 1:jK + 1].sum() / max(qv[iK + 1:jK + 1].sum(), 1), tb_pre=tb[iK - 96:iK].sum() / max(qv[iK - 96:iK].sum(), 1),
             ntr=nt[jK] / max(nt[jK - 96:jK].mean(), 1),
             tsize=(qv[iK + 1:jK + 1].sum() / max(nt[iK + 1:jK + 1].sum(), 1)) / max(qv[iK - 96:iK].sum() / max(nt[iK - 96:iK].sum(), 1), 1e-9),
             vol24=lr[-97:-1].std(), vol7=lr.std(), price=np.log10(max(c[jK], 1e-12)), pref=int(strip(s) != s),
             age=(T - t[0]) / 86400, old=int(t[0] <= GT[0]), hour=(T // 3600) % 24, dow=(T // 86400 + 3) % 7)
    f = FC.get(s)
    if f is not None:
        k = np.searchsorted(f[0], T, "right") - 1
        if k >= 0:
            iv = float(f[2][k]) or 8.0; r.update(f_last=f[3][k], f_iv=iv, f_24=fsum(s, T - 86400, T), f_72=fsum(s, T - 3 * 86400, T),
                                                  f_next=((T // int(iv * 3600) + 1) * int(iv * 3600) - T) / 60)
    bi = bt_ix.get(T - 900)
    if bi and bi >= 96: r.update(btc1=bc[bi] / bc[bi - 4] - 1, btc4=bc[bi] / bc[bi - 16] - 1, btc24=bc[bi] / bc[bi - 96] - 1)
    gi = np.searchsorted(GT, T - 900)
    if gi < len(GT) and GT[gi] == T - 900 and gi >= 96:
        rr = GC[gi] / GC[gi - 96] - 1; rr = rr[~np.isnan(rr)]; r["breadth"] = (rr > 0).mean() if len(rr) > 50 else np.nan; r["alt24"] = np.median(rr) if len(rr) > 50 else np.nan
    r["pumps24"] = np.searchsorted(evt_sorted, T) - np.searchsorted(evt_sorted, T - 86400)
    r["dumps24"] = np.searchsorted(dvt, T) - np.searchsorted(dvt, T - 86400); r["dumps1h"] = np.searchsorted(dvt, T) - np.searchsorted(dvt, T - 3600)
    hist = prev.get(s, []); r["prev30"] = sum(1 for tt, _ in hist if tt > T - 30 * 86400)
    done = [(tt, pn) for tt, pn in hist if tt + 48 * 3600 <= T]; r["prev_pnl"] = done[-1][1] if done else np.nan
    r["prev_gap"] = (T - hist[-1][0]) / 86400 if hist else np.nan
    fut = qv[jK - 3:jK + 1].sum()
    # Корея
    w = np.column_stack([t[jK - 200:jK + 111], h[jK - 200:jK + 111], l[jK - 200:jK + 111], c[jK - 200:jK + 111], qv[jK - 200:jK + 111]])
    ka = kr_arrays({"s": s, "t_in": T}, w); j = 200
    r["korea"] = int(ka is not None)
    if ka is not None:
        vol, kc = ka; v = vol[j - 3:j + 1].sum(); r["kshare"] = v / (v + fut + 1e-9)
        hv = [vol[m - 3:m + 1].sum() / max(vol[m - 3:m + 1].sum() + w[m - 3:m + 1, 4].sum(), 1) for m in range(j - 4, max(j - 96, 3), -4)]
        r["k_norm"] = np.median(hv) if hv else np.nan; r["k_prem"] = fixp(kc[j] / w[j, 3] - 1) if not np.isnan(kc[j]) else np.nan
        r["k_v1h"] = v / max(vol[max(0, j - 96):j - 3].sum() / 23.25, 1)
    else: r["kshare"] = 0.0
    # лира
    nm = TP.get(s); b = TD.get(f"{nm}TRY") if nm else None; r["has_try"] = int(b is not None and b[0, 0] <= T - 8 * 86400)
    if r["has_try"]:
        m = (b[:, 0] >= T - 3600) & (b[:, 0] < T); tr = float((b[m, 2] / np.interp(b[m, 0], tfx[:, 0], tfx[:, 1])).sum()) if m.any() else 0.0
        r["fshare"] = tr / (tr + fut + 1e-9)
    else: r["fshare"] = 0.0
    # спот Binance
    sp = spot(s); r["has_spot"] = int(sp is not None and sp[0, 0] <= T - 8 * 86400)
    if r["has_spot"]:
        tt = t[jK - 671:jK + 1]; ix = np.searchsorted(sp[:, 0], tt); ok = ix < len(sp); ok[ok] &= sp[ix[ok], 0] == tt[ok]
        sv = np.zeros(672); stb = np.zeros(672); sv[ok] = sp[ix[ok], 2]; stb[ok] = sp[ix[ok], 3]
        hs = sv.reshape(168, 4).sum(1); hf = qv[jK - 671:jK + 1].reshape(168, 4).sum(1); sh = hs / np.maximum(hs + hf, 1)
        r.update(sshare=sh[-1], snorm=np.median(sh[:-1]), sx=sh[-1] / max(np.median(sh[:-1]), 1e-4), sbuy=stb[-4:].sum() / max(sv[-4:].sum(), 1),
                 sprem=fixp(sp[ix[-1], 1] / c[jK] - 1) if ok[-1] else np.nan)
    for d, pfx in ((MET.get((s, T)), "m_"), (PRE.get((s, T)), ""), (MAR.get((s, T)), "")):
        if d:
            for kk, vv in d.items():
                if kk not in ("s", "t"): r[pfx + kk] = vv
    if r.get("m_oi_usd") == r.get("m_oi_usd") and r.get("m_oi_usd") is not None: r["m_oi_v24"] = r["m_oi_usd"] / max(r["v24"], 1)
    r.update(outcomes(s, jK))
    prev.setdefault(s, []).append((T, r.get("L_10_25", np.nan)))
    rows.append(r)
    if n_ % 1000 == 0: print(n_, flush=True)
D = pd.DataFrame(rows); D["y"] = np.where(D.t < datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp(), 1, 2)
D.to_pickle("s7/feat_dump.pkl"); print(D.shape); print(D.notna().mean().round(2)[[c for c in D.columns if not c.startswith(("S_", "L_"))]].to_string())
