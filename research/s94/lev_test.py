"""s94 — снижение максимального плеча фьючерса на Binance (тексты объявлений s22/ann_text.pkl): вход через 1 ч после
объявления, направление по последнему начислению фандинга (≥ 0 — шорт, < 0 — лонг), выход через 1 ч после вступления
в силу, стоп 25%. Для отчёта — всё время шорт; окно «за 1 ч до вступления → 24 ч после»; повышения плеча (контроль).
Плацебо — та же монета за 45/90/135 сут. Гипотеза — ВЫВОДЫ.md, записана до расчёта.
Запуск из папки с данными: python3 <путь>/s94/lev_test.py"""
import datetime as dt
import html
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

T0 = dt.datetime(2024, 10, 1, tzinfo=dt.timezone.utc).timestamp()


def events():
    A = pickle.load(open("s10/ann.pkl", "rb")); TX = pickle.load(open("s22/ann_text.pkl", "rb"))
    lev = sorted([r for r in A.values() if r["ts"] / 1000 >= T0 and r["code"] in TX and re.search(r"Margin Tier", r["title"], re.I)],
                 key=lambda r: r["ts"])
    ev = []
    for r in lev:
        ps = [html.unescape(p).strip() for p in TX[r["code"]]]
        for i, p in enumerate(ps):
            m = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(UTC\)", p)
            if not m or i + 1 >= len(ps):
                continue
            teff = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp()
            syms = re.findall(r"([A-Z0-9]{2,20})USDT\b", ps[i + 1])
            levs = []
            for q in ps[i + 2:i + 62]:
                if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} \(UTC\)", q):
                    break
                mm = re.fullmatch(r"(?:\d+-)?(\d+)x", q.replace(" ", ""))
                if mm:
                    levs.append(int(mm.group(1)))
                if len(levs) == 2:
                    break
            if syms and len(levs) == 2:
                for s in syms:
                    ev.append((s, r["ts"] / 1000, teff, levs[0], levs[1]))
    return pd.DataFrame(ev, columns=["s", "ann", "teff", "lev0", "lev1"]).drop_duplicates(["s", "teff"])


def run(s, t_in, hold_h, side):
    i = idx_at(s, t_in)
    if i is None or hold_h <= 0:
        return np.nan, np.nan
    x = trade(s, i, tp=None, sl=0.25, hold_h=hold_h, side=side)
    p = [y["net"] for dd in (45, 90, 135) if (k := idx_at(s, t_in - dd * DAY)) is not None
         and (y := trade(s, k, tp=None, sl=0.25, hold_h=hold_h, side=side))]
    return (x["net"] if x else np.nan), (np.mean(p) if p else np.nan)


def main():
    E = events()
    rows = []
    for s, ann, teff, l0, l1 in E.itertuples(index=False):
        if s not in K:
            continue
        fr = funding(s)
        f = fr[fr[:, 0] <= ann, 1] if len(fr) else np.zeros(0)
        f_last = float(f[-1]) if len(f) else 0.0
        side = -1 if f_last >= 0 else 1
        t_in = ann + 3600; hold = (teff + 3600 - t_in) / 3600
        r = dict(s=s, t=t_in, teff=teff, lev0=l0, lev1=l1, cut=l1 < l0, f=f_last, side=side)
        r["main"], r["pl_main"] = run(s, t_in, hold, side)
        r["short"], r["pl_short"] = run(s, t_in, hold, -1)
        r["post"], r["pl_post"] = run(s, teff - 3600, 25, side)
        rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle("s94/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    C = X[X.cut]
    print(f"Событий (монета есть в архиве): {len(X)}, снижений {len(C)} ({len(C) / months:.1f} в месяц) за {months:.1f} мес.;"
          f" фандинг ≥ 0 у {(C.f >= 0).mean():.0%}")
    for lab, x0, col in (("снижение, по фандингу (основная)", C, "main"), ("снижение, всё время шорт", C, "short"),
                         ("снижение, 1 ч до → 24 ч после", C, "post"), ("снижение, фандинг ≥ 0 (шорт)", C[C.f >= 0], "main"),
                         ("снижение, фандинг < 0 (лонг)", C[C.f < 0], "main"), ("повышение (контроль)", X[~X.cut], "main")):
        x = x0[x0[col].notna()]
        if len(x) < 8:
            print(f"  {lab:34s} n={len(x)}")
            continue
        m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        print(f"  {lab:34s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
              f" половины {ct(h1[col], h1.t)[0]:+6.2%} / {ct(h2[col], h2.t)[0]:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%},"
              f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
