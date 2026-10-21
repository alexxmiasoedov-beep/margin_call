"""Проверка на 6,5 месяца: шорт после пампа, когда корейские биржи (Upbit + Bithumb) дают ≥ X% объёма за последний час.
Памп — причинное обнаружение из pump_short6m.py; правило ищется в течение 24 ч после пампа, одна сделка на памп."""
import pickle, datetime, re, os, glob
import numpy as np
from pump_short6m import K, fund_short, trade
MSK = datetime.timezone(datetime.timedelta(hours=3))
EV = pickle.load(open("mm2/pumps6m.pkl", "rb"))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
FX = {}
for ex in ("upbit", "bithumb"):
    a = np.vstack([np.load(f) for f in glob.glob(f"mm2/korea6/{ex}_USDT_*.npy") if os.path.getsize(f) > 200])
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True); FX[ex] = a[u]
def kr_arrays(s, j):
    k = K[s]; n = len(k); vol = np.zeros(n); close = np.full(n, np.nan); listed = False; t_in = k[j, 0] + 900
    for ex in ("upbit", "bithumb"):
        fn = f"mm2/korea6/{ex}_{strip(s)}_{int(t_in + 26 * 3600)}.npy"
        if not os.path.exists(fn): continue
        a = np.load(fn)
        if not len(a): continue
        listed = True
        idx = np.searchsorted(k[:, 0], a[:, 0]); ok = idx < n; ok[ok] &= k[idx[ok], 0] == a[ok, 0]
        fxv = np.interp(a[:, 0], FX[ex][:, 0], FX[ex][:, 4]); np.add.at(vol, idx[ok], a[ok, 5] / fxv[ok])
        sel = idx[ok]; fill = np.isnan(close[sel]); close[sel[fill]] = (a[ok, 4] / fxv[ok])[fill]
    return (vol, close) if listed else None
def share(vol, k, m):
    v = vol[m - 3:m + 1].sum(); f = k[m - 3:m + 1, 6].sum(); return v / (v + f + 1e-9)
rows = {}
for s, j, i in EV:
    k = K[s]
    if j + 2 >= len(k) or j < 100: continue
    ka = kr_arrays(s, j); t_in = k[j, 0] + 900
    rows.setdefault("все пампы (вход сразу)", []).append((s, j, t_in))
    if ka is None: rows.setdefault("нет в Корее (вход сразу)", []).append((s, j, t_in)); continue
    vol, close = ka
    rows.setdefault("в Корее (вход сразу)", []).append((s, j, t_in))
    sh0 = share(vol, k, j)
    rows.setdefault("в Корее, доля < 5% в момент пампа", []).append((s, j, t_in)) if sh0 < 0.05 else None
    for q in (0.1, 0.2, 0.3):
        m = next((m for m in range(j, min(j + 96, len(k) - 2)) if share(vol, k, m) >= q), None)
        if m is not None: rows.setdefault(f"доля Кореи за 1 ч ≥ {q:.0%} (первый раз за 24 ч)", []).append((s, m, k[m, 0] + 900))
for tp, sl, hold in ((0.15, 0.15, 96), (0.15, 0.25, 192)):
    print(f"\n=== тейк {tp:.0%} / стоп {sl:.0%} / {hold // 4} ч, с комиссией 0,1% и фандингом")
    for name, lst in rows.items():
        res = []
        for s, m, t_in in lst:
            pnl, t_out = trade(K[s], m, tp, sl, hold); res.append((t_in, pnl - 0.001 + fund_short(s, t_in, t_out)))
        a = np.array(res); line = f"{name:48s} {len(a):4d} сд. | итог {a[:, 1].mean():+.2%} | плюс {np.mean(a[:, 1] > 0):.0%} |"
        for mo in range(4, 11):
            t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
            b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]; line += f" {mo:02d}: {b.mean():+.1%} ({len(b)})" if len(b) else f" {mo:02d}: —"
        print(line)
