"""Шорт после пампа по правилу: первый момент в течение 24 ч после +15%, где выполняется условие; одна сделка на памп.
Итог с комиссией 0,1% и оценкой фандинга по 15-мин индексу премии (шорт платит при отрицательном)."""
import pickle, datetime
import numpy as np
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_all.pkl", "rb")); POS = pickle.load(open("kaia/positions.pkl", "rb")); PREM, FUND = POS["PREM"], POS["FUND"]
F = pickle.load(open("mm2/rev_feats_pnl.pkl", "rb"))
MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
def fund_short(s, t_in, t_out):
    p = PREM.get(s); fu = FUND.get(s)
    if p is None: return 0.0
    iv = int(fu[-1, 1]) if fu is not None and len(fu) else 8
    tot, t = 0.0, (int(t_in) // (iv * 3600) + 1) * iv * 3600
    while t <= t_out:
        m = (p[:, 0] >= t - iv * 3600) & (p[:, 0] < t)
        if m.any():
            pr = p[m, 4].mean(); tot += float(np.clip((pr + np.clip(0.0001 - pr, -0.0005, 0.0005)) * iv / 8, -0.02, 0.02))
        t += iv * 3600
    return tot
def trade(s, i, tp, sl, hold):
    k = K[s]; e = k[i, 4]; t_in = k[i, 0] + 900
    for j in range(i + 1, min(i + 1 + hold, len(k))):
        if k[j, 2] >= e * (1 + sl): return -sl, k[j, 0] + 900, "стоп"
        if k[j, 3] <= e * (1 - tp): return tp, k[j, 0] + 900, "тейк"
    j = min(i + hold, len(k) - 1); return 1 - k[j, 4] / e, k[j, 0] + 900, "время"
EV = {}
for f in F: EV.setdefault(f["ev"], []).append(f)
for v in EV.values(): v.sort(key=lambda f: f["i"])
def run(name, cond, tp=0.15, sl=0.15, hold=96):
    rows = []
    for ev, ms in EV.items():
        m = next((f for f in ms if cond(f)), None)
        if m is None: continue
        pnl, t_out, ex = trade(m["s"], m["i"], tp, sl, hold); fd = fund_short(m["s"], m["t0"], t_out)
        rows.append((m["t0"], m["s"], pnl - 0.001 + fd, fd, ex))
    if not rows: print(f"{name:52s} нет сделок"); return
    a = np.array([r[2] for r in rows]); t = np.array([r[0] for r in rows]); fd = np.array([r[3] for r in rows])
    h1, h2 = a[t < MID], a[t >= MID]
    print(f"{name:52s} сделок {len(a):3d} (монет {len({r[1] for r in rows}):3d}) | итог {a.mean():+.2%} | в плюсе {np.mean(a > 0):.0%} | "
          f"фандинг {fd.mean():+.2%} | 1-я пол. {h1.mean():+.2%} ({len(h1)}) | 2-я пол. {h2.mean():+.2%} ({len(h2)})")
g = lambda f, k, d=np.nan: f.get(k, d) if f.get(k) is not None else d
for tp, sl, hold in ((0.15, 0.15, 96), (0.15, 0.25, 192)):
    print(f"\n=== тейк {tp:.0%} / стоп {sl:.0%} / {hold // 4} ч")
    run("все пампы, вход сразу при +15%", lambda f: True, tp, sl, hold)
    run("через ≥ 6 ч после +15%", lambda f: f["since_h"] >= 6, tp, sl, hold)
    run("в Корее (Upbit/Bithumb)", lambda f: g(f, "kr_listed", 0) == 1, tp, sl, hold)
    run("НЕ в Корее", lambda f: g(f, "kr_listed", 0) == 0, tp, sl, hold)
    for q in (0.1, 0.2, 0.3):
        run(f"доля Кореи в объёме за 1 ч ≥ {q:.0%}", lambda f, q=q: g(f, "kr_share_1h", 0) >= q, tp, sl, hold)
    run("доля Кореи за 1 ч ≥ 20% и премия Кореи > 0", lambda f: g(f, "kr_share_1h", 0) >= 0.2 and g(f, "kr_prem", -9) > 0, tp, sl, hold)
    run("доля Кореи за 1 ч < 5% (в Корее)", lambda f: g(f, "kr_listed", 0) == 1 and g(f, "kr_share_1h", 1) < 0.05, tp, sl, hold)
    run("в канале ≥ 20 ч подряд", lambda f: g(f, "ch_run_h", 0) >= 20, tp, sl, hold)
    run("в канале ≥ 4 ч подряд", lambda f: g(f, "ch_run_h", 0) >= 4, tp, sl, hold)
