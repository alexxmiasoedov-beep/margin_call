"""Признаки позиций для каждого бурного окна (сутки до конца окна te)."""
import pickle, datetime
import numpy as np
W = pickle.load(open("kaia/motif_windows.pkl", "rb")); D = pickle.load(open("kaia/positions.pkl", "rb"))
MET, PREM, FUND = D["MET"], D["PREM"], D["FUND"]
SYMS = sorted(pickle.load(open("kaia/k15_6m.pkl", "rb")).keys())
OCT1 = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc).timestamp()
def zrow(x):
    x = x - x.mean(); s = np.sqrt((x * x).sum()); return x / s if s > 0 else None
_fest = {}
def fund_oct(sym):
    """Фандинг за октябрь по премии (15 мин): та же формула, что в fund_est, с переходом на 1 ч при упоре в −2%."""
    if sym in _fest: return _fest[sym]
    f, p = FUND.get(sym), PREM.get(sym); out = []
    if f is not None and p is not None and len(f):
        t = int(f[-1, 0]); iv = int(f[-1, 1]); orig = iv if iv in (4, 8) else 4; calm = 0
        while t + iv * 3600 <= p[-1, 0] + 900:
            nt = t + iv * 3600; m = (p[:, 0] >= t) & (p[:, 0] < nt)
            if m.sum() >= max(1, iv * 2):
                P = p[m, 4].mean(); r = float(np.clip((P + np.clip(0.0001 - P, -0.0005, 0.0005)) * iv / 8, -0.02, 0.02))
                out.append((nt, iv, r))
                if iv in (4, 8) and r <= -0.01999: iv = 1; calm = 0
                elif iv == 1 and orig != 1:
                    calm = calm + 1 if r > -0.0005 else 0
                    if calm >= 4: iv = orig; calm = 0
            t = nt
    _fest[sym] = np.array(out) if out else None
    return _fest[sym]
def feats(sym, te):
    t0 = te - 86400; r = dict()
    m = MET.get(sym)
    if m is not None:
        w = m[(m[:, 0] >= t0) & (m[:, 0] < te)]
        if len(w) >= 200 and np.all(w[:, 1] > 0):
            grid = np.arange(t0 + 900, te + 1, 900)
            oi = np.interp(grid, w[:, 0], np.log(w[:, 1])); r["oi_shape"] = zrow(oi)
            r["oi_x"] = w[-1, 1] / w[0, 1]
            w4 = w[w[:, 0] >= te - 4 * 3600]; r["oi_4h"] = w4[-1, 1] / w4[0, 1] if len(w4) > 10 else np.nan
            for name, col in (("top_acc", 3), ("top_pos", 4), ("glob", 5)):
                a = w[:, col]; r[name + "_ch"] = a[-12:].mean() / a[:12].mean() if a[:12].mean() > 0 else np.nan
            r["glob_end"] = w[-12:, 5].mean(); r["taker"] = np.nanmean(w[:, 6]); r["taker_4h"] = np.nanmean(w4[:, 6]) if len(w4) else np.nan
    p = PREM.get(sym)
    if p is not None:
        w = p[(p[:, 0] >= t0) & (p[:, 0] < te)]
        if len(w) >= 80:
            r["prem_min"] = w[:, 4].min() * 100; r["prem_end"] = w[-16:, 4].mean() * 100; r["prem_mean"] = w[:, 4].mean() * 100
    f = FUND.get(sym)
    rates = []
    if f is not None and len(f): rates += [(t, iv, x) for t, iv, x in f if t0 < t <= te]
    if te > OCT1:
        fe = fund_oct(sym)
        if fe is not None: rates += [(t, iv, x) for t, iv, x in fe if t0 < t <= te and t > (f[-1, 0] if f is not None and len(f) else 0)]
    if rates:
        r["fund_min"] = min(x for _, _, x in rates) * 100; r["fund_sum"] = sum(x for _, _, x in rates) * 100
        r["floor"] = any(x <= -0.01999 for _, _, x in rates); r["iv1"] = any(iv == 1 for _, iv, _ in rates)
    return r
out = {}
for per, w in W.items():
    F = [feats(SYMS[s], te) for s, te in zip(w["S"], w["TE"])]
    out[per] = F
    have = np.mean(["oi_x" in x for x in F]); hp = np.mean(["prem_min" in x for x in F]); hf = np.mean(["fund_min" in x for x in F])
    print(f"{per}: окон {len(F)} | есть OI/LSR {have*100:.0f}% | премия {hp*100:.0f}% | фандинг {hf*100:.0f}%", flush=True)
pickle.dump(out, open("kaia/posfeat.pkl", "wb"))
