import pickle, datetime, os, numpy as np
os.environ["SIGFILE"] = "signals_scan_full.pkl"
import bv
from fund_est import estimate
MSK = datetime.timezone(datetime.timedelta(hours=3)); UTC = datetime.timezone.utc
f = lambda t: datetime.datetime.fromtimestamp(t, MSK).strftime("%d.%m %H:%M")
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
P = [r for r in pickle.load(open("kaia/patterns_relaxed.pkl", "rb")) if r["R"] <= 85]
import realism as R
from sim import SIG
rows = []
for r in sorted(P, key=lambda r: r["ti"]):
    days = sorted({day(t) for t in range(int(r["ti"]) - 86400, int(r["t2"]) + 3600, 3600)})
    mt = bv.metrics(r["sym"], days); pr = bv.klines(r["sym"], "premiumIndexKlines", "1m", (), days)
    oi0 = mt[mt[:, 0] <= r["ti"]][-1, 2] if mt is not None and (mt[:, 0] <= r["ti"]).any() else np.nan
    oi1 = mt[mt[:, 0] <= r["t1"] + 900][-1, 2] if mt is not None else np.nan
    oiL = mt[mt[:, 0] <= r["tl"] + 900][-1, 2] if mt is not None else np.nan
    w = (pr[:, 0] >= r["ti"]) & (pr[:, 0] <= r["t2"]) if pr is not None else None
    pmin = pr[w, 4].min() * 100 if pr is not None and w.any() else np.nan
    fr = []
    for m in ("2026-08", "2026-09"):
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{r['sym']}USDT/{r['sym']}USDT-fundingRate-{m}.zip")):
            try: fr.append((int(p[0]) // 1000, int(float(p[1])), float(p[2])))
            except (ValueError, IndexError): pass
    fr.sort(); fl = None; iv0 = None
    if fr:
        prev = [x for x in fr if x[0] <= r["ti"]]
        if prev and r["ti"] < datetime.datetime(2026, 10, 1, tzinfo=UTC).timestamp():
            iv0 = prev[-1][1]; fl = min((x[2] for x in fr if r["ti"] < x[0] <= r["t2"]), default=None)
        else:
            iv0 = fr[-1][1]; est = estimate(r["sym"], fr[-1][0], fr[-1][1], int(r["t2"]), iv0)
            fl = min((x for t, x in est if r["ti"] < t <= r["t2"]), default=None)
    sig = [s for s in SIG if s["sym"] == r["sym"] and r["ti"] - 3600 <= s["ep"] <= r["t2"]]
    sres = []
    for s in sig:
        ph = ("импульс/пауза" if s["ep"] < r["ti"] + 1800 else "рост к вершине 1" if s["ep"] < r["t1"] - 900 else "у вершины 1" if s["ep"] <= r["t1"] + 1800
              else "откат" if s["ep"] <= r["tl"] + 900 else "вторая волна")
        a, b = R.trade2(s, 15, 25, slip_sl=0.002), R.trade2(s, 6, 20, slip_sl=0.002)
        sres.append(f"{f(s['ep'])} ({ph}, правило {s['rule']}): 15/25 {a['kind']} {a['pnl']:+.2f}, 6/20 {b['kind']} {b['pnl']:+.2f}")
    rows.append(dict(r, oi_x=oi1 / oi0 if oi0 else np.nan, oi_L=oiL / oi1 if oi1 else np.nan, pmin=pmin, fmin=fl, iv0=iv0, sig=sres))
pickle.dump(rows, open("kaia/patterns_feat.pkl", "wb"))
for r in rows:
    print(f"{r['sym']:6s} {f(r['ti'])}: импульс {r['imp']:+.0f}% → вершина 1 +{r['up1']:.0f}% → откат −{r['drop']:.0f}% ({r['R']:.0f}% роста) → волна 2 {r['h2vs1']:+.1f}% к вершине 1"
          f" | OI ×{r['oi_x']:.1f} к вершине 1, в откате {(r['oi_L']-1)*100:+.0f}% | премия до {r['pmin']:+.1f}% | фандинг: интервал {r['iv0']} ч, мин. ставка {r['fmin']*100 if r['fmin'] is not None else float('nan'):+.2f}%")
    for x in r["sig"]: print("      сигнал бота", x)
