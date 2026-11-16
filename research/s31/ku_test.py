"""s31 — шорт фьючерса Binance после объявления о листинге на KuCoin (гипотеза — ВЫВОДЫ.md, записана до проверки).
Объявления — s31/ku_ann.json (ku_fetch.py). Событие — первое за 30 сут объявление о листинге спота монеты, у которой
фьючерс USDT-M Binance торгуется ≥ 1 сут; вход на закрытии ближайшего часа, шорт 7 сут (и 30 сут), стоп +50%, без тейка,
комиссия 0,1%, фактический фандинг (s15/common.trade). Плацебо — та же монета за 45/90/135 сут, половины до и после
01.12.2025, t по дням. Пересечение с корейскими листингами (s15/kr_listings.pkl) и 🅱️ (s22/h10_ann.pkl) за ±3 сут.
Итог — s31/trades.pkl. Запуск из папки с данными."""
import json
import os
import pickle
import re
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
from common import K, fut_of, live, trade  # noqa: E402

DAY = 86400
CUT = 1764547200
PL = (45, 90, 135)
SKIP = re.compile(r"Futures|Margin|Earn|Pre-Market|Saving|Campaign|Reward|Opening Time|Trading Bot|Convert", re.I)


def events():
    A = json.load(open("s31/ku_ann.json"))
    rows = []
    for a in A:
        if "new-listings" not in (a["types"] or []) or SKIP.search(a["title"]):
            continue
        m = re.search(r"\(([A-Z0-9]{2,12})\)", a["title"])
        if not m:
            continue
        rows.append(dict(coin=m.group(1), t=a["t"] / 1000, title=a["title"]))
    E = pd.DataFrame(rows).sort_values("t")
    keep, last = [], {}
    for r in E.itertuples():
        if r.t - last.get(r.coin, -np.inf) >= 30 * DAY:
            keep.append(r.Index)
        last[r.coin] = r.t
    E = E.loc[keep].copy()
    E["s"] = [fut_of(c)[0] for c in E.coin]
    E = E[E.s.notna()].copy()
    E = E[[live(s)[0] <= t - DAY and live(s)[1] >= t for s, t in zip(E.s, E.t)]].copy()
    E["te"] = (E.t // 3600 + 1) * 3600
    return E


def idx(s, te):
    t = K[s]["t"]; i = int(np.searchsorted(t, te - 900))
    return i if i < len(t) and t[i] == te - 900 else None


def short(s, te, h):
    i = idx(s, te)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.5, hold_h=h, side=-1)
    return r["net"] if r else None


def ct(x, T):
    d = pd.Series(np.asarray(x, float), index=pd.to_datetime(np.asarray(T), unit="s").date).dropna()
    if len(d) < 5:
        return np.nan, np.nan, len(d)
    q = d.groupby(level=0).mean()
    return d.mean(), (q.mean() / q.std() * np.sqrt(len(q)) if len(q) > 2 and q.std() > 0 else np.nan), len(d)


def overlap(E):
    kr = pd.DataFrame(pickle.load(open("s15/kr_listings.pkl", "rb")))
    kr["s"] = [fut_of(b)[0] for b in kr.base]
    bl = pd.read_pickle("s22/h10_ann.pkl")
    out = []
    for r in E.itertuples():
        a = ((kr.s == r.s) & ((kr.t - r.t).abs() <= 3 * DAY)).any()
        b = ((bl.s == r.s) & ((bl["T"] - r.t).abs() <= 3 * DAY)).any()
        out.append("кор" if a else "bin" if b else "")
    return out


if __name__ == "__main__":
    E = events()
    E["ov"] = overlap(E)
    print(f"событий: {len(E)} (из них корейский листинг ±3 сут — {(E.ov == 'кор').sum()}, 🅱️ ±3 сут — {(E.ov == 'bin').sum()})")
    res = {}
    for h in (168, 720):
        rows = []
        for r in E.itertuples():
            n = short(r.s, r.te, h)
            if n is None:
                continue
            p = [short(r.s, r.te - d * DAY, h) for d in PL]
            p = [x for x in p if x is not None]
            rows.append(dict(s=r.s, te=r.te, net=n, plac=np.mean(p) if p else np.nan, ov=r.ov, title=r.title))
        D = pd.DataFrame(rows); res[h] = D
        for lab, x in (("все", D), ("без корейских и 🅱️", D[D.ov == ""])):
            m, t, n = ct(x.net, x.te)
            h1, h2 = x[x.te < CUT].net, x[x.te >= CUT].net
            print(f"  {h // 24} сут, {lab}: n={n} {m:+.2%} (t {t:+.1f}), медиана {x.net.median():+.2%}, в плюсе "
                  f"{(x.net > 0).mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) / {h2.mean():+.2%} ({len(h2)}) | "
                  f"плацебо {x.plac.mean():+.2%}")
    pickle.dump(res, open("s31/trades.pkl", "wb"))
