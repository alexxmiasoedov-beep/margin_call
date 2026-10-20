"""Предвестники пампов (+15% за ≤ 2 ч из спокойного состояния) против контрольных моментов без пампа, 19.09–18.10.
Всё считается по данным до момента старта t0 (закрытие 15-мин свечи); метрики Binance — со сдвигом +5 мин."""
import pickle, datetime, json, re, random
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
random.seed(7)
UTC = datetime.timezone.utc; MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
# ---- события: последний «спокойный» момент перед ростом +15% за ≤ 2 ч
ev, ctl = [], []
for s, k in K.items():
    t, h, l, c = k[:, 0], k[:, 2], k[:, 3], k[:, 4]
    q = [i for i in range(96 * 7, len(k) - 8) if T0 <= t[i] + 900 <= T1 and abs(c[i] / c[i - 8] - 1) <= 0.05 and h[i + 1:i + 9].max() >= c[i] * 1.15]
    groups = []
    for i in q:
        if groups and i - groups[-1][-1] <= 8: groups[-1].append(i)
        else: groups.append([i])
    for g in groups: ev.append((s, g[-1]))
    calm = [i for i in range(96 * 7, len(k) - 8) if T0 <= t[i] + 900 <= T1 and abs(c[i] / c[i - 8] - 1) <= 0.05 and h[i + 1:i + 9].max() < c[i] * 1.05]
    if calm and any(e[0] == s for e in ev[-len(groups):] if groups):
        ctl += [(s, i) for i in random.sample(calm, min(25, len(calm)))]
ev_syms = {s for s, _ in ev}; ctl = [(s, i) for s, i in ctl if s in ev_syms]
print(f"пампов {len(ev)} у {len(ev_syms)} монет | контрольных моментов {len(ctl)}", flush=True)
# ---- данные: метрики (OI, LSR, тейкеры) и премия для нужных дней
need = sorted({(s, day(K[s][i, 0] + 900 - dd)) for s, i in ev + ctl for dd in (0, 86400)})
def met(sd):
    try: return sd, bv.metrics(sd[0], [sd[1]])
    except Exception: return sd, None
with ThreadPoolExecutor(24) as ex: MR = dict(ex.map(met, need))
MET = {}
for (s, d), a in MR.items():
    if a is not None and len(a): MET.setdefault(s, []).append(a)
MET = {s: (lambda x: x[np.argsort(x[:, 0])])(np.vstack(v)) for s, v in MET.items()}
def prem(s):
    try: return s, bv.klines(s, "premiumIndexKlines", "15m", ("2026-09",), [f"2026-10-{d:02d}" for d in range(1, 19)])
    except Exception: return s, None
with ThreadPoolExecutor(24) as ex: PREM = {s: a for s, a in ex.map(prem, sorted(ev_syms)) if a is not None}
print("метрики", len(MET), "премия", len(PREM), flush=True)
# ---- канал маржинальных данных: время появления монеты в постах
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)(?:\s+(-?[\d.]+))?\s*$')
CH = {}
for fn in ("posts_new.jsonl", "posts_oct.jsonl"):
    for ln in open(fn):
        pid, ts, txt = json.loads(ln); ep = datetime.datetime.fromisoformat(ts).timestamp()
        for row in txt.splitlines():
            m = rx.match(row.strip())
            if m: CH.setdefault(m.group(1), []).append((ep, float(m.group(4))))
CH = {s: np.array(sorted(v)) for s, v in CH.items()}
def feats(s, i):
    k = K[s]; t, o, h, l, c, v, qv, n, tb = (k[:, j] for j in range(9)); te = t[i] + 900
    base = qv[i - 96:i - 4].mean() + 1e-9; nb = n[i - 96:i - 4].mean() + 1e-9
    r = dict(vol_1h=qv[i - 3:i + 1].sum() / (base * 4), vol_15m=qv[i] / base, trades_1h=n[i - 3:i + 1].sum() / (nb * 4),
             buy_1h=tb[i - 3:i + 1].sum() / max(qv[i - 3:i + 1].sum(), 1e-9), ret_1h=c[i] / c[i - 4] - 1, ret_4h=c[i] / c[i - 16] - 1,
             ret_24h=c[i] / c[i - 96] - 1, ret_7d=c[i] / c[i - 96 * 7] - 1, range_4h=h[i - 15:i + 1].max() / l[i - 15:i + 1].min() - 1,
             range_24h=h[i - 95:i + 1].max() / l[i - 95:i + 1].min() - 1, from_high_24h=c[i] / h[i - 95:i + 1].max() - 1,
             vol_24h_vs_7d=qv[i - 95:i + 1].mean() / (qv[i - 96 * 7:i - 95].mean() + 1e-9))
    m = MET.get(s)
    if m is not None:
        w = m[m[:, 0] <= te - 300]                                   # метрика с отметкой t известна в t+5 мин
        if len(w) > 300:
            g = lambda dt: w[w[:, 0] <= te - 300 - dt][-1] if (w[:, 0] <= te - 300 - dt).any() else None
            now, h1, h4, h24 = g(0), g(3600), g(4 * 3600), g(86400)
            if h1 is not None and h4 is not None and h24 is not None:
                r.update(oi_1h=now[1] / h1[1] - 1, oi_4h=now[1] / h4[1] - 1, oi_24h=now[1] / h24[1] - 1, top_pos=now[4], top_pos_4h=now[4] / h4[4] - 1,
                         glob=now[5], glob_4h=now[5] / h4[5] - 1, taker_1h=np.nanmean(w[w[:, 0] > te - 300 - 3600, 6]))
    p = PREM.get(s)
    if p is not None:
        w = p[(p[:, 0] < te) & (p[:, 0] >= te - 3600)]
        if len(w): r["prem_1h"] = w[:, 4].mean() * 100
    ch = CH.get(s)
    r["in_channel_4h"] = float(ch is not None and ((ch[:, 0] > te - 4 * 3600) & (ch[:, 0] <= te)).any())
    return r
F_ev = [feats(s, i) for s, i in ev]; F_ct = [feats(s, i) for s, i in ctl]
pickle.dump(dict(ev=ev, ctl=ctl, F_ev=F_ev, F_ct=F_ct), open("mm/pump_study.pkl", "wb"))
def auc(a, b):
    a, b = np.asarray(a), np.asarray(b); a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if not len(a) or not len(b): return np.nan
    allv = np.concatenate([a, b]); rk = allv.argsort().argsort() + 1
    return (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
print("\nпризнак            медиана перед пампом | медиана в контроле | AUC (0,5 = не различает; дальше от 0,5 — сильнее)")
keys = sorted({k for x in F_ev for k in x})
rows = []
for k in keys:
    a = [x.get(k, np.nan) for x in F_ev]; b = [x.get(k, np.nan) for x in F_ct]
    rows.append((abs(auc(a, b) - 0.5), k, np.nanmedian(a), np.nanmedian(b), auc(a, b)))
for _, k, ma, mb, au in sorted(rows, reverse=True):
    print(f"{k:18s} {ma:10.4f} | {mb:10.4f} | {au:.2f}")
