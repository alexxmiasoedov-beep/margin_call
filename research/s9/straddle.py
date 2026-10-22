"""Стрэдл автора: покупка ATM колла и пута (экспирация 1 / 2 / 3 сут) в моменты низкой исторической волатильности и флэта.
Премия — Блэк–Шоулз по DVOL (Deribit, годовая IV 30 дней) + комиссия 0,03% базового актива на опцион и спред 5% премии.
Выплата — |S_T − K| на экспирации по фьючерсу Binance. Сравнение: все часы против «низкой воли»."""
import json, subprocess, pickle, math, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb"))
def dvol(cur):
    out = []; st = 1729000000000; end = 1792600000000
    while st < end:
        en = min(st + 1000 * 3600 * 1000, end)
        u = f"https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={cur}&start_timestamp={st}&end_timestamp={en}&resolution=3600"
        r = json.loads(subprocess.run(["curl", "-sS", "-m", "60", u], capture_output=True, text=True).stdout)
        d = r["result"]["data"]; out += d
        st = en + 1
    a = np.array(sorted({x[0]: x[4] for x in out}.items())); return a[:, 0] / 1000, a[:, 1] / 100
N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
def bs_straddle(S, sig, T):           # ATM, r = 0
    if T <= 0 or sig <= 0: return 0.0
    d1 = 0.5 * sig * math.sqrt(T); return S * (2 * N(d1) - 1) * 2       # call + put при K = S
CUT = datetime.datetime(2025, 10, 15, tzinfo=datetime.timezone.utc).timestamp()
for cur, sym in (("BTC", "BTC"), ("ETH", "ETH")):
    tv, iv = dvol(cur)
    a = K[sym]; t = a["t"] + 900; c = a["c"].astype(np.float64)
    # часовая сетка
    hrs = np.arange(int(tv[0] // 3600 * 3600) + 3600, int(min(tv[-1], t[-1]) - 4 * 86400), 3600)
    ci = np.searchsorted(t, hrs) ; ok = (ci < len(t)) & (np.abs(t[np.minimum(ci, len(t) - 1)] - hrs) < 900); hrs, ci = hrs[ok], ci[ok]
    S = c[ci]; IV = np.interp(hrs, tv, iv)
    lr = np.diff(np.log(c)); 
    def rv(j, n):                    # реализованная дневная воля по 15-мин доходностям за n свечей, в %
        x = lr[max(0, j - n):j]; return float(np.std(x) * math.sqrt(96) * 100) if len(x) > 10 else np.nan
    rows = []
    for k, (h, j) in enumerate(zip(hrs, ci)):
        rv48 = rv(j, 192); rng48 = c[max(0, j - 191):j + 1].max() / c[max(0, j - 191):j + 1].min() - 1
        for dd in (1, 2, 3):
            jT = np.searchsorted(t, h + dd * 86400)
            if jT >= len(t): continue
            prem = bs_straddle(S[k], IV[k], dd / 365) * 1.05 + 2 * 0.0003 * S[k]
            pay = abs(c[jT] - S[k]); rows.append(dict(t=h, dd=dd, rv48=rv48, rng48=rng48, iv=IV[k], prem=prem / S[k], pay=pay / S[k], roi=pay / prem - 1,
                                                      wd=datetime.datetime.utcfromtimestamp(h).weekday()))
    X = pd.DataFrame(rows); X["half"] = np.where(X.t < CUT, 1, 2)
    q20 = X[X.dd == 1].rv48.quantile(0.2); q10 = X[X.dd == 1].rv48.quantile(0.1)
    print(f"===== {cur}: часов {X.t.nunique()}, реализованная воля за 48 ч (дневная): 10% {q10:.2f}%, 20% {q20:.2f}%, медиана {X.rv48.median():.2f}%")
    for dd in (1, 2, 3):
        g0 = X[X.dd == dd]
        for nm, m in (("все часы", g0.rv48 > -1), ("воля ≤ 20-го перцентиля", g0.rv48 <= q20), ("воля ≤ 10-го перцентиля", g0.rv48 <= q10),
                      ("воля ≤ 1%", g0.rv48 <= 1.0), ("воля ≤ 20% и размах 48 ч ≤ 3%", (g0.rv48 <= q20) & (g0.rng48 <= 0.03)),
                      ("воля ≤ 20%, вход в сб/вс", (g0.rv48 <= q20) & (g0.wd >= 5))):
            g = g0[m]
            if len(g) < 30: continue
            h1, h2 = g[g.half == 1], g[g.half == 2]
            print(f"  эксп. {dd} сут, {nm:34s} n={len(g):5d} премия {g.prem.mean()*100:.2f}% выплата {g.pay.mean()*100:.2f}% | ROI {g.roi.mean()*100:+.1f}% "
                  f"(1-я {h1.roi.mean()*100:+.1f} / 2-я {h2.roi.mean()*100:+.1f}), в плюсе {(g.roi > 0).mean():.0%}")
