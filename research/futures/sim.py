"""Симуляция сделок по signals.pkl на минутных свечах фьючерсов Binance.
Вход: open минуты после поста, рыночный (taker 0,05%). Стоп: марк-цена ≥ уровня → рыночный выход по уровню +0,1% проскальзывания (taker).
Тейк: лимитный, исполнен, если цена сделок ушла НИЖЕ уровня (maker 0,02%). Стоп и тейк в одной минуте — стоп.
Выход по времени — close минуты (taker). Фандинг Binance по факту. Маржа 1, плечо 10 (номинал 10).
Портфель: одна позиция на монету, пауза после стопа по монете."""
import pickle, bisect, datetime
import numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
D = pickle.load(open("signals.pkl", "rb")); SIG = sorted(D["sig"], key=lambda s: s["ep"]); FUND = D["fund"]
N, TAKER, MAKER, SLIP = 10.0, 0.0005, 0.0002, 0.001

def fh_entry(s):
    f = FUND.get(s["sym"])
    if f is None or len(f) < 2: return None
    k = bisect.bisect_right(f[:, 0], s["te"]) - 1
    if k < 1: return None
    return f[k, 1] / max((f[k, 0] - f[k - 1, 0]) / 3600, 1)

def trade(s, tp, sl, hold_h=48, fexit=None, mark=True, strict=True, fees=True, slip=True):
    e = s["entry"]; n = min(int(hold_h * 60), len(s["t"]))
    if n == 0: return None
    slp, tpp = e * (1 + sl / 100), (e * (1 - tp / 100) if tp else None)
    H = s["mh"] if mark else s["h"]
    hit_sl = np.nonzero(H[:n] >= slp)[0]; j_sl = hit_sl[0] if len(hit_sl) else n
    if tpp is not None:
        hit = np.nonzero((s["l"][:n] < tpp) if strict else (s["l"][:n] <= tpp))[0]; j_tp = hit[0] if len(hit) else n
    else: j_tp = n
    f = FUND.get(s["sym"]); j_fx = n
    if fexit and f is not None and len(f) > 1:
        k0 = bisect.bisect_right(f[:, 0], s["te"])
        for k in range(max(k0, 1), len(f)):
            if f[k, 0] >= s["t"][n - 1]: break
            if f[k, 1] / max((f[k, 0] - f[k - 1, 0]) / 3600, 1) * 100 <= -fexit:
                j_fx = int(np.searchsorted(s["t"], f[k, 0])); break
    j = min(j_sl, j_tp, j_fx)
    if j == n:
        kind = "время" if n >= hold_h * 60 else "обрыв"; j = n - 1; px = s["c"][j]; fee_x = TAKER
    elif j == j_sl: kind = "стоп"; px = slp * (1 + SLIP if slip else 1); fee_x = TAKER
    elif j == j_tp: kind = "тейк"; px = tpp; fee_x = MAKER
    else: kind = "фандинг"; px = s["c"][j]; fee_x = TAKER
    xt = s["t"][j] + 60
    fund = float(f[(f[:, 0] > s["te"]) & (f[:, 0] <= xt), 1].sum()) * N if f is not None else 0.0
    price = (1 - px / e) * N
    fee = N * (TAKER + fee_x) if fees else N * 2 * TAKER
    return dict(kind=kind, price=price, fund=fund, fee=fee, pnl=price + fund - fee, hours=(xt - s["te"]) / 3600, xt=xt,
                maxup=(H[:j + 1].max() / e - 1) * 100)

def run(tp=6, sl=20, hold_h=48, pause_h=48, fexit=None, sel=None, params=None, with_fund=True, **kw):
    open_until = {}; last_stop = {}; rows = []
    for s in SIG:
        if sel and not sel(s): continue
        if open_until.get(s["sym"], 0) > s["ep"]: continue
        if pause_h and s["ep"] - last_stop.get(s["sym"], -1e18) < pause_h * 3600: continue
        a, b = params(fh_entry(s)) if params else (tp, sl)
        r = trade(s, a, b, hold_h, fexit, **kw)
        if r is None: continue
        if not with_fund: r["pnl"] -= r["fund"]; r["fund"] = 0.0
        open_until[s["sym"]] = r["xt"]
        if r["kind"] == "стоп": last_stop[s["sym"]] = r["xt"]
        rows.append(dict(ep=s["ep"], sym=s["sym"], rule=s["rule"], **r))
    return pd.DataFrame(rows)

def summ(x, label=""):
    if not len(x): return f"{label:24s} нет сделок"
    eq = x.pnl.cumsum(); dd = (eq - eq.cummax()).min(); mid = x.ep.median(); vc = x.kind.value_counts(normalize=True) * 100
    return (f"{label:24s} n={len(x):3d} тейк {vc.get('тейк',0):3.0f}% стоп {vc.get('стоп',0):3.0f}% время {vc.get('время',0)+vc.get('фандинг',0)+vc.get('обрыв',0):3.0f}% | "
            f"итого {x.pnl.sum():+6.1f} (1-я пол. {x[x.ep<mid].pnl.sum():+5.1f} / 2-я {x[x.ep>=mid].pnl.sum():+5.1f}) | на сделку {x.pnl.mean():+.3f} | "
            f"фандинг {x.fund.sum():+5.1f} | просадка {dd:+5.1f}")
