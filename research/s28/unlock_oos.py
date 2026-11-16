"""s28 — проверка вне выборки: разлоки 01.2023–09.2024, до архива свечей s2/k2y.pkl. Правило и пороги — как в основной
части, записаны до запуска (ВЫВОДЫ, «Проверка вне выборки»).
- События — прошлые разлоки CMC глубже 08.2024: кэш s28/ev_old/<id>.json; страницы с первой, до событий старше 01.12.2022,
  не больше 40 страниц.
- Монеты в обращении — история CMC 11.2022–08.2024 (s28/hist_old/<id>.json) вместе с s28/hist.
- Свечи 15 мин и фандинг — месячные архивы data.binance.vision (кэш s26/old/, функции s26/kr_old.py).
- Монеты — те же 457 с фьючерсом Binance в архиве s2; делистингованные до 10.2024 не попадают.
Сделки: шорт T − 7 → T + 1 сут, стоп +50% и без стопа; лонг T − 14 → T − 7 сут («памп перед разлоком»). Комиссия 0,1%,
фактический фандинг, стоп с проскальзыванием 0,2%. Плацебо — та же монета за 45, 90, 135 сут без разлоков ≥ 1% в ±10 сут.
Запуск из папки с данными: python3 unlock_oos.py fetch; python3 unlock_oos.py"""
import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "s26"))
from cmc_fetch import API, get, tokens       # noqa: E402
from kr_old import fetch, series             # noqa: E402

DAY, BAR, FEE = 86400, 900, 0.001
T0, T1 = 1672531200, 1727740800              # 01.01.2023 … 01.10.2024
CUT = 1704067200                             # половины: 2023 / 2024
OLDEST = "2022-12-01"
EVDIR, HDIR = "s28/ev_old", "s28/hist_old"


def ev_old(cid):
    path = f"{EVDIR}/{cid}.json"
    if os.path.exists(path):
        return
    main = f"s28/ev/{cid}_past.json"
    if os.path.exists(main):
        ev = json.load(open(main))
        if len(ev) % 100 or not ev:                     # последняя страница неполная — в основном кэше все события
            json.dump(ev, open(path, "w"))
            return
    ev, page = [], 1
    while page <= 40:
        d = get(f"{API}/token-unlock/event?cryptoId={cid}&type=past&page={page}&limit=100")
        if d is None or "data" not in d:
            return                                       # сбой — не кэшируем
        x = d["data"].get("tokenEvent") or []
        ev += x
        if len(x) < 100 or x[-1]["time"][:10] < OLDEST:
            break
        page += 1
    json.dump(ev, open(path + ".tmp", "w"))
    os.replace(path + ".tmp", path)


def hist_old(cid):
    path = f"{HDIR}/{cid}.json"
    if os.path.exists(path):
        return
    out = []
    for a, b in ((1667260800, 1698796800), (1698796800, 1722470400)):      # 01.11.2022–01.11.2023–01.08.2024
        d = get(f"{API}/cryptocurrency/historical?id={cid}&convertId=2781&timeStart={a}&timeEnd={b}&interval=1d")
        if d is None or "data" not in d:
            return
        for q in d["data"].get("quotes") or []:
            u = q["quote"]
            out.append([q["timeClose"][:10], u.get("close"), u.get("volume"), u.get("marketCap"), u.get("circulatingSupply")])
    json.dump(out, open(path + ".tmp", "w"))
    os.replace(path + ".tmp", path)


def ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def events(cid):
    p = f"{EVDIR}/{cid}.json"
    if not os.path.exists(p):
        return []
    seen, ev = set(), []
    for e in json.load(open(p)):
        k = (e["time"], e["amount"])
        if k not in seen:
            seen.add(k); ev.append(e)
    return sorted(ev, key=lambda e: e["time"])


def hist(cid):
    rows = []
    for p in (f"{HDIR}/{cid}.json", f"s28/hist/{cid}.json"):
        if os.path.exists(p):
            rows += json.load(open(p))
    if not rows:
        return None
    h = pd.DataFrame(rows, columns=["d", "px", "vol", "mcap", "circ"])
    h["t"] = (pd.to_datetime(h.d) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s") + 86400   # закрытие дня d
    return h.sort_values("t").drop_duplicates("t").reset_index(drop=True)


def build(toks):
    rows = []
    for cid, sym, fut in toks:
        h = hist(cid)
        grp = []
        for e in events(cid):
            t = ts(e["time"])
            if t < T0 - 160 * DAY or t >= T1 + 30 * DAY:      # шире окна — для плацебо (без разлоков в ±10 сут)
                continue
            vt = {a["vestingType"] for a in e["allocations"]}
            if grp and t - grp[-1]["t"] <= 2 * DAY:
                grp[-1]["amount"] += e["amount"]; grp[-1]["pct_total"] += e["percentage"] or 0; grp[-1]["vt"] |= vt
            else:
                grp.append(dict(t=t, amount=e["amount"], pct_total=e["percentage"] or 0, vt=vt))
        for x in grp:
            circ = px = np.nan
            if h is not None:
                b = h[h.t < x["t"] - 6 * 3600]
                if len(b) and x["t"] - b.t.iloc[-1] < 5 * DAY:
                    circ, px = b.circ.iloc[-1], b.px.iloc[-1]
            rows.append(dict(cid=cid, sym=sym, s=fut + "USDT", t=x["t"], amount=x["amount"], pct_total=x["pct_total"],
                             pct_circ=x["amount"] / circ * 100 if circ and circ > 0 else np.nan, px=px,
                             cliff="cliff" in x["vt"]))
    E = pd.DataFrame(rows)
    E["size"] = E.pct_circ.where(E.pct_circ.notna(), E.pct_total)
    return E


def months(a, b):
    return [str(p) for p in pd.period_range(pd.Timestamp(a, unit="s"), pd.Timestamp(b, unit="s"), freq="M")]


def trade(k, f, btc, t_in, hold_d, sl, side):
    t = k[:, 0]
    i = int(np.searchsorted(t, t_in, "right") - 1)
    n = int(hold_d * 96)
    if i < 0 or t[i] < t_in - BAR or i + n >= len(t) or t[i + n] != t[i] + n * BAR or k[i:i + n, 5].sum() <= 0:
        return None
    p0 = k[i, 4]; seg = k[i + 1:i + n + 1]
    hit = []
    if sl:
        lvl = p0 * (1 + sl) if side < 0 else p0 * (1 - sl)
        hit = np.flatnonzero(seg[:, 2] >= lvl) if side < 0 else np.flatnonzero(seg[:, 3] <= lvl)
    if len(hit):
        x = int(hit[0]); o = seg[x, 1]
        px = max(lvl, o) * 1.002 if side < 0 else min(lvl, o) * 0.998
        xi, why = i + 1 + x, "стоп"
    else:
        px, xi, why = k[i + n, 4], i + n, "время"
    t0, t1 = t[i] + BAR, t[xi] + BAR
    fr = float(f[(f[:, 0] > t0) & (f[:, 0] <= t1), 1].sum()) if f is not None and len(f) else 0.0
    price = 1 - px / p0 if side < 0 else px / p0 - 1
    fund = fr if side < 0 else -fr
    b = btc[:, 0]; j0, j1 = np.searchsorted(b, t0 - BAR), np.searchsorted(b, t1 - BAR)
    hb = btc[min(j1, len(b) - 1), 4] / btc[min(j0, len(b) - 1), 4] - 1
    net = price + fund - FEE
    return dict(net=net, fund=fund, why=why, hedge=net + (hb if side < 0 else -hb))


def px_ok(k, r):
    if not (np.isfinite(r.px) and r.px):
        return True
    t = k[:, 0]; i = int(np.searchsorted(t, r.t - DAY, "right") - 1)
    if i < 0 or t[i] < r.t - DAY - 3600:
        return True                                      # свечей нет — сделки всё равно не будет
    mult = 1e6 if r.s.startswith("1000000") else 1000.0 if r.s.startswith("1000") else 1.0
    return bool(0.8 <= k[i, 4] / (r.px * mult) <= 1.25)


PLANS = {"шорт T−7→T+1": (-7, 8, -1), "лонг T−14→T−7": (-14, 7, 1)}


def run(E, shift_d=0):
    rows = []
    for r in E.itertuples():
        t = r.t - shift_d * DAY
        ms = months(t - 25 * DAY, t + 3 * DAY)
        if all(fetch("klines", r.s, m) is None for m in ms):
            continue
        k = series("klines", r.s, ms)
        if k is None:
            continue
        if not shift_d and not px_ok(k, r):
            continue
        f = series("fundingRate", r.s, ms); btc = series("klines", "BTCUSDT", ms)
        for plan, (a, hold, side) in PLANS.items():
            for sl in (0.5, None):
                x = trade(k, f, btc, t + a * DAY, hold, sl, side)
                if x:
                    rows.append(dict(s=r.s, t=t, size=r.size, cliff=r.cliff, plan=plan, sl=sl or 0, **x))
    return pd.DataFrame(rows)


def ct(x, t):
    d = pd.Series(x, index=pd.to_datetime(t, unit="s").date).groupby(level=0).mean()
    return x.mean(), (d.mean() / d.std() * np.sqrt(len(d)) if len(d) > 2 else np.nan), len(x)


def line(x, label):
    if not len(x):
        print(f"  {label:34s} n=   0")
        return
    m, t, n = ct(x.net.values, x.t.values)
    h1, h2 = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
    hb = x.hedge.mean() if "hedge" in x else np.nan
    print(f"  {label:34s} n={n:4d} {m*100:+6.2f}% (t {t:+4.1f}) медиана {x.net.median()*100:+5.1f}% в плюсе "
          f"{(x.net > 0).mean():.0%} стопов {(x.why == 'стоп').mean():.0%} хедж BTC {hb*100:+6.2f}% "
          f"2023 {h1*100:+6.2f}% / 2024 {h2*100:+6.2f}%")


SETS = {"cliff ≥ 5% или ≥ 25% (правило)": lambda x: (x.cliff & (x["size"] >= 5)) | (x["size"] >= 25),
        "≥ 25%": lambda x: x["size"] >= 25, "cliff ≥ 5%": lambda x: x.cliff & (x["size"] >= 5),
        "≥ 10%": lambda x: x["size"] >= 10, "≥ 5%": lambda x: x["size"] >= 5}


if __name__ == "__main__":
    T = tokens()
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        os.makedirs(EVDIR, exist_ok=True); os.makedirs(HDIR, exist_ok=True)
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(ev_old, [c for c, _, _ in T]))
        need = [c for c, _, _ in T if any(T0 - 30 * DAY <= ts(e["time"]) < T1 for e in events(c))]
        print(f"монет с разлоками 01.2023–09.2024: {len(need)}", flush=True)
        with ThreadPoolExecutor(3) as ex:
            list(ex.map(hist_old, need))
        print("готово", flush=True)
        raise SystemExit
    E = build(T)
    W = E[(E.t >= T0) & (E.t < T1) & (E["size"] >= 5)].copy()
    print(f"разлоков ≥ 5% в 01.2023–09.2024: {len(W)}, монет {W.s.nunique()}; с долей в обращении {W.pct_circ.notna().sum()}",
          flush=True)
    need = {("BTCUSDT", m) for m in months(T0 - 170 * DAY, T1 + 5 * DAY)}
    for r in W.itertuples():
        for back in (0, 45, 90, 135):
            need |= {(r.s, m) for m in months(r.t - (back + 25) * DAY, r.t - (back - 3) * DAY)}
    with ThreadPoolExecutor(8) as ex:                    # заранее, параллельно: архивы data.binance.vision
        list(ex.map(lambda p: (fetch("klines", *p), fetch("fundingRate", *p)), sorted(need)))
    print(f"месячных архивов: {len(need)}", flush=True)
    R = run(W)
    R.to_pickle("s28/oos_trades.pkl")
    allt = {s: E[(E.s == s) & (E["size"] >= 1)].t.values for s in E.s.unique()}
    P = []
    for back in (45, 90, 135):
        Q = W[[not np.any(np.abs(allt[r.s] - (r.t - back * DAY)) < 10 * DAY) for r in W.itertuples()]]
        P.append(run(Q, shift_d=back))
    P = pd.concat(P, ignore_index=True)
    P.to_pickle("s28/oos_placebo.pkl")
    for plan in PLANS:
        for sl in (0.5, 0):
            print(f"\n=== {plan}, стоп {'50%' if sl else 'нет'}")
            for name, f in SETS.items():
                x = R[(R.plan == plan) & (R.sl == sl)]
                line(x[f(x)], name)
                y = P[(P.plan == plan) & (P.sl == sl)]
                line(y[f(y)], "   плацебо")
    # замечено после проверки: возраст монеты (от первого события CMC) — в основной части (s28/robust.pkl) и вне выборки
    first = {}
    for cid, sym, fut in T:
        tt = [ts(e["time"]) for e in events(cid)]
        if os.path.exists(f"s28/ev/{cid}_past.json"):
            tt += [ts(e["time"]) for e in json.load(open(f"s28/ev/{cid}_past.json"))]
        if tt:
            first[fut + "USDT"] = min(tt)
    rule = SETS["cliff ≥ 5% или ≥ 25% (правило)"]
    IS = pd.read_pickle("s28/robust.pkl")
    IS = IS[IS.sl == 0.5].assign(s=lambda x: x.s + "USDT")
    OS = R[(R.plan == "шорт T−7→T+1") & (R.sl == 0.5)]
    print("\n=== возраст монеты (замечено после проверки): правило, стоп 50%")
    for lab, X in (("основная 10.2024–10.2026", IS[rule(IS)]), ("вне выборки 01.2023–09.2024", OS[rule(OS)])):
        age = (X.t - X.s.map(first)) / 86400 / 365
        line(X[age < 2], f"{lab}: моложе 2 лет")
        line(X[age >= 2], f"{lab}: 2 года и старше")
