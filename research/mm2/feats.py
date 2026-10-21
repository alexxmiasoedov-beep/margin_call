"""Признаки моментов из НОВЫХ источников (стакан, спот, минутки, займы канала, Корея, время, контекст рынка)
+ старые 15-мин и метрики для сравнения. Всё — строго по данным до t0 (закрытие 15-мин свечи момента).
Вход: MOM — pickle со списком (метка, монета, индекс 15-мин свечи); RAW — папка с данными монет; OUT — куда сохранить."""
import pickle, datetime, json, re, os, multiprocessing as mp
import numpy as np
import bv
UTC = datetime.timezone.utc
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
MOM = pickle.load(open(os.environ.get("MOM", "mm2/moments.pkl"), "rb"))
RAW = os.environ.get("RAW", "mm2/raw")
KO = pickle.load(open("mm2/korea.pkl", "rb")) if os.path.exists("mm2/korea.pkl") else {}
PREM = pickle.load(open("kaia/positions.pkl", "rb"))["PREM"]
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
# ---- канал: занято / возвращено / B/R и место в посте
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+)([KMB]?)\s+([\d.]+)([KMB]?)\s+(inf|[\d.]+(?:e[+-]?\d+)?)(?:\s+(-?[\d.]+))?\s*$')
mult = {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}; CH, POSTS = {}, set()
for fn in ("posts.jsonl", "posts_oct.jsonl", "posts_oct2.jsonl"):
    for ln in open(fn):
        pid, ts, txt = json.loads(ln)
        if ts < "2026-09-10": continue
        ep = datetime.datetime.fromisoformat(ts).timestamp(); POSTS.add(ep); rank = 0
        for row in txt.splitlines():
            m = rx.match(row.strip())
            if m:
                rank += 1; bo = float(m.group(2)) * mult[m.group(3)]; rp = float(m.group(4)) * mult[m.group(5)]
                CH.setdefault(m.group(1), []).append((ep, bo, rp, bo / rp if rp > 0 else 1e4, rank))
POSTS = np.array(sorted(POSTS)); CH = {s: np.array(sorted(set(v))) for s, v in CH.items()}
# ---- контекст рынка: BTC и пампы/дампы других монет, закончившиеся до t0
BTC = K["BTC"]; BT = {t: j for j, t in enumerate(BTC[:, 0])}
EV = pickle.load(open("mm2/events.pkl", "rb"))
EVT = {g: (np.array([K[s][i, 0] + 900 for s, i in EV[g]]), np.array([s for s, i in EV[g]])) for g in ("памп", "дамп")}
def ctx(s, t0, i):
    j = BT.get(K[s][i, 0]); r = {}
    if j is not None:
        c = BTC[:, 4]; r.update(btc_1h=c[j] / c[j - 4] - 1, btc_4h=c[j] / c[j - 16] - 1, btc_24h=c[j] / c[j - 96] - 1)
    for g, nm in (("памп", "pumps_prev24"), ("дамп", "dumps_prev24")):
        te, ss = EVT[g]; r[nm] = int(((ss != s) & (te + 7200 <= t0) & (te >= t0 - 86400)).sum())
    h = datetime.datetime.fromtimestamp(t0, UTC); r["hour"] = h.hour; r["dow"] = h.weekday()
    r["to_fund8"] = ((8 - h.hour % 8) * 60 - h.minute) % 480
    return r
def base15(k, i):
    t, o, h, l, c, v, qv, n, tb = (k[:, j] for j in range(9))
    if i < 96: return {"qv_24h": qv[max(0, i - 95):i + 1].sum(), "short_hist": 1.0}
    base = qv[i - 96:i - 4].mean() + 1e-9; nb = n[i - 96:i - 4].mean() + 1e-9
    return dict(vol_1h=qv[i - 3:i + 1].sum() / (base * 4), trades_1h=n[i - 3:i + 1].sum() / (nb * 4),
                buy_1h=tb[i - 3:i + 1].sum() / max(qv[i - 3:i + 1].sum(), 1e-9), ret_1h=c[i] / c[i - 4] - 1, ret_4h=c[i] / c[i - 16] - 1,
                ret_24h=c[i] / c[i - 96] - 1, ret_7d=c[i] / c[i - 96 * 7] - 1 if i >= 96 * 7 else np.nan, range_4h=h[i - 15:i + 1].max() / l[i - 15:i + 1].min() - 1,
                range_24h=h[i - 95:i + 1].max() / l[i - 95:i + 1].min() - 1, from_high_24h=c[i] / h[i - 95:i + 1].max() - 1,
                from_low_24h=c[i] / l[i - 95:i + 1].min() - 1, vol_24h_vs_7d=qv[i - 95:i + 1].mean() / (qv[i - 96 * 7:i - 95].mean() + 1e-9) if i >= 96 * 7 else np.nan,
                qv_24h=qv[i - 95:i + 1].sum(), h_since_high24=(95 - int(np.argmax(h[i - 95:i + 1]))) / 4,
                imp_ret=c[i] / c[i - 1] - 1, imp_wick=(h[i] - c[i]) / (h[i] - l[i] + 1e-12), imp_vol=qv[i] / (qv[i - 96:i - 1].mean() + 1e-9),
                imp_buy=tb[i] / max(qv[i], 1e-9), imp_trades=n[i] / (n[i - 96:i - 1].mean() + 1e-9))
def moves(k):
    """up8/dn8[j] — максимальный рост / падение за 2 ч после свечи j (окно j+1…j+8)."""
    from numpy.lib.stride_tricks import sliding_window_view as sw
    h, l, c = k[:, 2], k[:, 3], k[:, 4]; n = len(k); up, dn = np.full(n, np.nan), np.full(n, np.nan)
    up[:n - 8] = sw(h[1:], 8).max(1)[:n - 8] / c[:n - 8] - 1; dn[:n - 8] = sw(l[1:], 8).min(1)[:n - 8] / c[:n - 8] - 1
    return up, dn
def history(mv, i):
    up, dn = mv; a, b = max(0, i - 96 * 7), i - 8                # окна, закончившиеся до t0
    if b <= a: return {}
    u, d = up[a:b], dn[a:b]; u24, d24 = up[max(a, i - 96):b], dn[max(a, i - 96):b]
    return dict(prior_up7d=np.nanmax(u), prior_dn7d=np.nanmin(d), prior_up24=np.nanmax(u24) if len(u24) else np.nan,
                prior_dn24=np.nanmin(d24) if len(d24) else np.nan, n_pumps7d=int(((u >= 0.15) & (np.r_[True, u[:-1] < 0.15])).sum()),
                n_dumps7d=int(((d <= -0.15) & (np.r_[True, d[:-1] > -0.15])).sum()))
def win(t, a, b):
    return np.searchsorted(t, a, "left"), np.searchsorted(t, b, "right")
LV = {0.2: (5, 6), 1: (4, 7), 2: (3, 8), 5: (0, 11)}
def book_f(b, t0, qv_h):
    if b is None: return {}
    T, A = b
    n0, n1 = win(T, t0 - 900, t0 - 60); b0, b1 = win(T, t0 - 86400, t0 - 3601); h0, h1 = win(T, t0 - 4500, t0 - 3601); l0, l1 = win(T, t0 - 3600, t0 - 60)
    if n1 - n0 < 5 or b1 - b0 < 300: return {}
    r = {}
    for lv, (bi, ai) in LV.items():
        bid, ask = A[:, bi].astype(float), A[:, ai].astype(float); tag = str(lv).replace(".", "")
        bn, an = np.nanmean(bid[n0:n1]), np.nanmean(ask[n0:n1])
        bb, ab = bid[b0:b1], ask[b0:b1]
        r[f"imb{tag}"] = (bn - an) / (bn + an); r[f"d_imb{tag}"] = r[f"imb{tag}"] - np.nanmedian((bb - ab) / (bb + ab))
        r[f"ask_rel{tag}"] = an / np.nanmedian(ab); r[f"bid_rel{tag}"] = bn / np.nanmedian(bb)
        if h1 - h0 >= 5: r[f"ask_1h{tag}"] = an / np.nanmean(ask[h0:h1]); r[f"bid_1h{tag}"] = bn / np.nanmean(bid[h0:h1])
        if lv in (1, 2): r[f"ask_vs_vol{tag}"] = an / qv_h; r[f"bid_vs_vol{tag}"] = bn / qv_h
        if lv == 1 and l1 - l0 >= 30:
            r["flick_ask1"] = np.nanstd(ask[l0:l1]) / np.nanmean(ask[l0:l1]); r["flick_bid1"] = np.nanstd(bid[l0:l1]) / np.nanmean(bid[l0:l1])
    r["conc_ask"] = np.nanmean(A[n0:n1, 7]) / np.nanmean(A[n0:n1, 11]); r["conc_bid"] = np.nanmean(A[n0:n1, 4]) / np.nanmean(A[n0:n1, 0])
    return r
def minute_f(F, S, t0):
    r = {}
    if F is None: return r
    a0, a1 = win(F[:, 0], t0 - 86400, t0 - 60); f = F[a0:a1]
    if len(f) < 600: return r
    f1, f4 = f[np.searchsorted(f[:, 0], t0 - 3600):], f[np.searchsorted(f[:, 0], t0 - 4 * 3600):]
    if len(f1) < 20: return r
    lr, lr1 = np.diff(np.log(f[:, 4])), np.diff(np.log(f1[:, 4]))
    r["rv_1h_24h"] = lr1.std() / (lr.std() + 1e-12)
    r["vspike_1h"] = f1[:, 6].max() / (f[:, 6].mean() + 1e-9)
    r["tsize_1h"] = (f1[:, 6].sum() / max(f1[:, 7].sum(), 1)) / (f[:, 6].sum() / max(f[:, 7].sum(), 1))
    r["dead_1h"] = 1 - (f1[:, 7] > 0).sum() / 60
    r["upwick_4h"] = (f4[:, 2] / f4[:, 1] - 1).max(); r["dnwick_4h"] = (1 - f4[:, 3] / f4[:, 1]).max()
    m4 = f4[:, 4] / f4[:, 1] - 1; r["jumps_4h"] = int((m4 > 0.01).sum()) - int((m4 < -0.01).sum())
    f15 = f[np.searchsorted(f[:, 0], t0 - 900):]
    for nm, w in (("15m", f15), ("1h", f1), ("4h", f4)):
        if len(w): r[f"fcvd_{nm}"] = (2 * w[:, 8] - w[:, 6]).sum() / max(w[:, 6].sum(), 1e-9)
    if len(f15) >= 10:
        r["m_late5"] = f15[-1, 4] / f15[-6, 4] - 1; r["m_from_high15"] = f15[-1, 4] / f15[:, 2].max() - 1
        r["m_max1m"] = (f15[:, 4] / f15[:, 1] - 1).max(); r["m_vol_last5"] = f15[-5:, 6].sum() / max(f15[:, 6].sum(), 1e-9)
    if S is None: return r
    a0, a1 = win(S[:, 0], t0 - 86400, t0 - 60); s = S[a0:a1]
    if len(s) < 300: return r
    s1, s4 = s[np.searchsorted(s[:, 0], t0 - 3600):], s[np.searchsorted(s[:, 0], t0 - 4 * 3600):]
    sq1, fq1 = s1[:, 6].sum(), f1[:, 6].sum()
    s15 = s[np.searchsorted(s[:, 0], t0 - 900):]
    if len(s15) and len(f15):
        r["sp_share_15m"] = s15[:, 6].sum() / (s15[:, 6].sum() + f15[:, 6].sum() + 1e-9)
        r["sp_buy_15m"] = s15[:, 8].sum() / max(s15[:, 6].sum(), 1e-9); r["fut_buy_15m"] = f15[:, 8].sum() / max(f15[:, 6].sum(), 1e-9)
    r["sp_share_1h"] = sq1 / (sq1 + fq1 + 1e-9); r["sp_share_24h"] = s[:, 6].sum() / (s[:, 6].sum() + f[:, 6].sum() + 1e-9)
    r["sp_share_rel"] = r["sp_share_1h"] / (r["sp_share_24h"] + 1e-9)
    r["sp_vol_rel"] = sq1 / (s[:, 6].sum() / 24 + 1e-9)
    for nm, a, b in (("1h", s1, f1), ("4h", s4, f4)):
        sb = a[:, 8].sum() / max(a[:, 6].sum(), 1e-9); fb = b[:, 8].sum() / max(b[:, 6].sum(), 1e-9)
        r[f"sp_buy_{nm}"] = sb; r[f"fut_buy_{nm}"] = fb; r[f"buy_gap_{nm}"] = sb - fb
    ct, ia, ib = np.intersect1d(f[:, 0], s[:, 0], assume_unique=True, return_indices=True)
    if len(ct) > 300:
        ratio = f[ia, 4] / s[ib, 4]; sc = 10 ** np.round(np.log10(np.median(ratio))); bas = (ratio / sc - 1) * 100
        last = ct >= t0 - 900
        if last.sum():
            r["basis_now"] = bas[last].mean(); r["basis_rel"] = r["basis_now"] - np.median(bas)
            j = ct >= t0 - 3600
            if j.sum() > 30:
                fa, sa = f[ia[j], 4], s[ib[j], 4]; r["spot_lead_1h"] = (sa[-1] / sa[0]) - (fa[-1] / fa[0])
    return r
def chan_f(s, t0):
    r = {}
    j = np.searchsorted(POSTS, t0) - 1
    if j < 0 or t0 - POSTS[j] > 1800: return r
    lp = POSTS[j]; a = CH.get(s); r["ch_now"] = 0.0; r["ch_any24"] = 0.0
    if a is None: return r
    w = a[(a[:, 0] <= lp) & (a[:, 0] > t0 - 86400)]
    if not len(w): return r
    r["ch_any24"] = 1.0; r["ch_hours24"] = len(np.unique(w[:, 0])) / 12
    if w[-1, 0] == lp:
        r.update(ch_now=1.0, ch_bor=w[-1, 1], ch_br=min(w[-1, 3], 1e4), ch_rank=w[-1, 4])
        p4 = w[(w[:, 0] <= lp - 3.5 * 3600) & (w[:, 0] >= lp - 4.5 * 3600)]
        r["ch_bor_4h"] = w[-1, 1] / p4[-1, 1] if len(p4) else np.nan
        p1 = w[(w[:, 0] <= lp - 3000) & (w[:, 0] >= lp - 4200)]
        r["ch_bor_1h"] = w[-1, 1] / p1[-1, 1] if len(p1) else np.nan
        gaps = np.where(np.diff(w[:, 0]) > 3600)[0]; st = w[gaps[-1] + 1, 0] if len(gaps) else w[0, 0]
        r["ch_run_h"] = (lp - st) / 3600
    return r
def korea_prep(s, k):
    c = strip(s); n = len(k); vol = np.zeros(n); close = np.full(n, np.nan); listed = False
    for ex in ("upbit", "bithumb"):
        a = KO.get(ex, {}).get(c); fx = KO.get(ex, {}).get("USDT")
        if a is None or fx is None or not len(a): continue
        listed = True
        idx = np.searchsorted(k[:, 0], a[:, 0]); ok = idx < n; ok[ok] &= k[idx[ok], 0] == a[ok, 0]
        fxv = np.interp(a[:, 0], fx[:, 0], fx[:, 4])
        np.add.at(vol, idx[ok], a[ok, 5] / fxv[ok])
        fill = idx[ok][np.isnan(close[idx[ok]])]; close[fill] = (a[ok, 4] / fxv[ok])[np.isnan(close[idx[ok]])]
    if not listed: return None
    pr = close / k[:, 4]; sc = 10 ** np.round(np.log10(np.nanmedian(pr))) if np.isfinite(pr).any() else 1
    return vol, (pr / sc - 1) * 100
def korea_f(kp, k, i):
    if kp is None: return {"kr_listed": 0.0}
    vol, pr = kp; fqv = k[:, 6]
    v1, v24 = vol[i - 3:i + 1].sum(), vol[i - 95:i + 1].sum()
    if v24 <= 0: return {"kr_listed": 0.0}
    f1, f24 = fqv[i - 3:i + 1].sum(), fqv[i - 95:i + 1].sum()
    r = dict(kr_listed=1.0, kr_share_1h=v1 / (v1 + f1 + 1e-9), kr_share_24h=v24 / (v24 + f24 + 1e-9), kr_vol_rel=v1 / (v24 / 24 + 1e-9))
    r["kr_share_rel"] = r["kr_share_1h"] / (r["kr_share_24h"] + 1e-9); r["kr_share_15m"] = vol[i] / (vol[i] + fqv[i] + 1e-9)
    w = pr[i - 95:i + 1]
    if np.isfinite(w[-4:]).any() and np.isfinite(w).sum() > 20:
        last = w[-4:][np.isfinite(w[-4:])][-1]
        r.update(kr_prem=last, kr_prem_rel=last - np.nanmedian(w), kr_prem_1h=np.nanmean(w[-4:]) - np.nanmean(w[:-4]))
        if np.isfinite(w[-1]) and np.isfinite(w[-2]): r["kr_dprem_15m"] = w[-1] - w[-2]
    return r
def met_f(m, t0, qv24):
    if m is None or not len(m): return {}
    j = np.searchsorted(m[:, 0], t0 - 600, "right")       # отметка t описывает t+5 мин → берём ≤ t0−10 мин
    if j < 200: return {}
    w = m[:j]; g = lambda dt: w[np.searchsorted(w[:, 0], t0 - 600 - dt, "right") - 1] if w[0, 0] <= t0 - 600 - dt else None
    now, h1, h4, h24 = g(0), g(3600), g(4 * 3600), g(86400 - 1200)
    if any(x is None for x in (now, h1, h4)): return {}
    r = dict(oi_1h=now[1] / h1[1] - 1, oi_4h=now[1] / h4[1] - 1, top_acc=now[3], top_pos=now[4], glob=now[5], glob_4h=now[5] / h4[5] - 1,
             taker_1h=np.nanmean(w[w[:, 0] > t0 - 600 - 3600, 6]), oi_vs_vol=now[2] / (qv24 + 1e-9), top_vs_glob=now[4] / now[5])
    if h24 is not None: r["oi_24h"] = now[1] / h24[1] - 1
    return r
def prem_f(p, t0):
    if p is None: return {}
    j = np.searchsorted(p[:, 0], t0, "left"); w = p[max(0, j - 96):j]
    if len(w) < 50: return {}
    return dict(prem_1h=w[-4:, 4].mean() * 100, prem_rel=(w[-4:, 4].mean() - np.median(w[:, 4])) * 100)
BY = {}
for x in MOM: BY.setdefault(x[1], []).append(x)
def coin(s):
    raw = pickle.load(open(f"{RAW}/{s}.pkl", "rb")) if os.path.exists(f"{RAW}/{s}.pkl") else {}
    k = K[s]; days = sorted({day(k[i, 0] + 900 - dd) for g, s2, i in BY[s] for dd in (1, 86400)})
    try: met = bv.metrics(s, days)
    except Exception: met = None
    kp = korea_prep(s, k); mv = moves(k); out = []
    for g, s2, i in BY[s]:
        t0 = k[i, 0] + 900; r = dict(g=g, s=s, i=i, t0=t0)
        r.update(base15(k, i)); r.update(history(mv, i)); qv_h = r["qv_24h"] / 24
        r.update(book_f(raw.get("book"), t0, qv_h)); r.update(minute_f(raw.get("fut"), raw.get("spot"), t0))
        r.update(chan_f(s, t0)); r.update(korea_f(kp, k, i)); r.update(met_f(met, t0, r["qv_24h"])); r.update(prem_f(PREM.get(s), t0)); r.update(ctx(s, t0, i))
        r["has_book"] = float(raw.get("book") is not None); r["has_spot"] = float(raw.get("spot") is not None)
        out.append(r)
    return out
if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    with mp.get_context("fork").Pool(4) as pool:
        res = [r for rows in pool.imap_unordered(coin, sorted(BY), chunksize=2) for r in rows]
    pickle.dump(res, open(os.environ.get("OUT", "mm2/feats.pkl"), "wb"))
    print("моментов", len(res), "| со стаканом", sum(r["has_book"] for r in res), "| со спотом", sum(r["has_spot"] for r in res),
          "| в Корее", sum(r.get("kr_listed", 0) for r in res), "| в канале сейчас", sum(r.get("ch_now", 0) for r in res), flush=True)
