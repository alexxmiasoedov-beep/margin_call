"""s26 — сделки шорт по корейским событиям (s26/events.pkl, объединение бирж как в kr_study.py): вход в закрытии 15-мин
свечи, внутри которой вышел пост (≤ 15 мин после поста), срок 1–30 сут, стоп +25% / +50% / без стопа, комиссия 0,1%,
фактический фандинг (common.trade). «К рынку» — плюс медиана простой доходности всех фьючерсов за срок сделки.
Плацебо — та же монета за 28, 56, 84, 112 сут до события. Пересечение с 📢: объявление Binance (Monitoring Tag, делистинг
спота или фьючерса) о той же монете за 30 сут до события (s10/ann.pkl, по 22.10.2026).
Запуск из папки с данными: python3 kr_trades.py"""
import os
import pickle
import re
import sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kr_study import BAR, CUT, DAY, EV, GR, K, bar_of, ct, live, trade      # noqa: E402

g = GR["grid"]; C = GR["C"]
BTC = K["BTC"]


def mkt_simple(t0, t1):
    k0, k1 = np.searchsorted(g, t0), np.searchsorted(g, t1)
    if k1 >= len(g) or k1 == k0:
        return 0.0 if k1 == k0 else np.nan
    with np.errstate(all="ignore"):
        return float(np.nanmedian(C[:, k1] / C[:, k0] - 1))


def btc_ret(t0, t1):
    t = BTC["t"]; i0 = np.searchsorted(t, t0 - BAR); i1 = np.searchsorted(t, t1 - BAR)
    if i1 >= len(t):
        return np.nan
    return float(BTC["c"][i1] / BTC["c"][i0] - 1)


def run(s, ts, hold_d, sl):
    i0 = bar_of(s, ts)
    if i0 is None:
        return None
    r = trade(s, i0, tp=None, sl=sl, hold_h=hold_d * 24, side=-1)
    if r is None:
        return None
    t0 = float(K[s]["t"][i0]) + BAR; t1 = t0 + r["bars"] * BAR
    r["mkt"] = r["net"] + mkt_simple(t0, t1)
    r["hedge"] = r["net"] + btc_ret(t0, t1)
    return r


# ------------------------------------------------------------------ объявления Binance (📢)
A = pd.DataFrame(pickle.load(open("s10/ann.pkl", "rb")).values())
A["ts"] = A.ts / 1000
A = A[A.title.str.contains(r"Monitoring Tag.*Include|^Binance Will Delist|Futures Will Delist", regex=True)]
A_END = A.ts.max()


def binance_prior(tok, ts, days=30):
    x = A[(A.ts < ts) & (A.ts > ts - days * DAY)]
    return any(re.search(rf"\b{re.escape(tok)}\b", t) for t in x.title)


def table(rows, label):
    R = pd.DataFrame(rows)
    if R.empty:
        return
    print(f"\n{label}")
    for (hd, sl), x in R.groupby(["hold", "sl"]):
        m, t, n = ct(x.net.values, x.ts.values) if len(x) >= 10 else (x.net.mean(), np.nan, len(x))
        mm, tm, _ = ct(x.mkt.values, x.ts.values) if len(x) >= 10 else (x.mkt.mean(), np.nan, len(x))
        h1, h2 = x[x.ts < CUT], x[x.ts >= CUT]
        print(f"  {hd:2d} сут, стоп {('нет' if sl is None or (isinstance(sl, float) and np.isnan(sl)) else f'{sl:.0%}'):>4s}: "
              f"n={n:3d} чистыми {m*100:+6.2f}% (t {t:+4.1f}, медиана {x.net.median()*100:+5.1f}%, в плюсе "
              f"{(x.net > 0).mean():.0%}, стопов {(x.why == 'стоп').mean():.0%}) к рынку {mm*100:+6.2f}% (t {tm:+4.1f}) "
              f"хедж BTC {x.hedge.mean()*100:+6.2f}% фандинг {x.fund.mean()*100:+5.2f}%  половины "
              f"{h1.net.mean()*100:+.1f}/{h2.net.mean()*100:+.1f}% ({len(h1)}/{len(h2)})")


if __name__ == "__main__":
    EV["bin30"] = [binance_prior(r.tok, r.ts) for r in EV.itertuples()]
    print("доля событий с объявлением Binance о монете за 30 сут до:",
          EV.groupby("kind").bin30.mean().round(2).to_dict())
    SETS = [(1, 0.25), (3, 0.25), (7, 0.25), (7, 0.5), (14, 0.5), (14, None), (30, 0.5), (30, None)]
    allrows = {}
    for k in ("촉구", "предупреждение", "делистинг", "снятие", "продление"):
        rows = []
        for r in EV[EV.kind == k].itertuples():
            for hd, sl in SETS:
                x = run(r.s, r.ts, hd, sl)
                if x:
                    rows.append(dict(s=r.s, ts=r.ts, hold=hd, sl=sl if sl else np.nan, bin30=r.bin30, **x))
        allrows[k] = rows
        table(rows, f"=== {k}: шорт после поста")
    # плацебо к предупреждению и делистингу
    evs = {s: EV[EV.s == s].ts.values for s in EV.s.unique()}
    for k in ("предупреждение", "делистинг"):
        rows = []
        for r in EV[EV.kind == k].itertuples():
            for back in (28, 56, 84, 112):
                tp = r.ts - back * DAY
                if np.any(np.abs(evs[r.s] - tp) < 14 * DAY):
                    continue
                for hd, sl in SETS:
                    x = run(r.s, tp, hd, sl)
                    if x:
                        rows.append(dict(s=r.s, ts=tp, hold=hd, sl=sl if sl else np.nan, **x))
        table(rows, f"--- плацебо к «{k}»")
    # без пересечения с 📢 (только события до конца архива объявлений)
    for k in ("предупреждение", "делистинг"):
        R = [x for x in allrows[k] if x["ts"] < A_END]
        table([x for x in R if not x["bin30"]], f"=== {k}: без объявления Binance о монете за 30 сут до")
        table([x for x in R if x["bin30"]], f"=== {k}: с объявлением Binance за 30 сут до")
    pickle.dump(allrows, open("s26/trades.pkl", "wb"))
