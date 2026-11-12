"""Кампании Binance (s24/events.pkl): доход шорта фьючерса к рынку (медиана монет) по окнам: объявление → начало,
первые сутки, весь период, после конца 1 / 3 / 7 / 14 суток; к фьючерсам того же возраста (s22 h10_margin.matched).
По видам, по токену награды, по половинам. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s22")
from common22 import CUT, H, ct, fwd                             # noqa: E402
from h10_margin import hour_up, matched                          # noqa: E402

E = pd.read_pickle("s24/events.pkl")
E = E[E.live_ok].copy()
E["S"] = [hour_up(x - 1) for x in E.start]; E["Eh"] = [hour_up(x - 1) for x in E.end]; E["A"] = [hour_up(x) for x in E.ts]
# одна строка на (монета, период): одинаковые события (два объявления одной кампании) — оставляем первое
E = E.drop_duplicates(["s", "start", "end"])


def win(s, T, h):
    return fwd(s, T, h) if h > 0 else np.nan


rows = []
for r in E.itertuples():
    d = int(round((r.Eh - r.S) / H))
    row = dict(s=r.s, kind=r.kind, in_tok=r.reward_in_tok, T=r.S, age=r.age_d,
               pre=win(r.s, r.A, int(round((r.S - r.A) / H))) if r.S > r.A else np.nan,
               first1=win(r.s, r.S, 24), during=win(r.s, r.S, d))
    for k in (1, 3, 7, 14):
        row[f"post{k}"] = win(r.s, r.Eh, 24 * k)
        row[f"post{k}_age"] = matched(r.Eh, r.s, 24 * k, "age")
    rows.append(row)
R = pd.DataFrame(rows)


def st(x, T):
    x = np.asarray(x, float); T = np.asarray(T, float); ok = np.isfinite(x)
    m, t, n = ct(x[ok], T[ok])
    if not n or n < 8:
        return f"n={n}"
    return (f"{m * 100:+.2f}% (t {t:+.1f}, n {n}; {np.nanmean(x[ok & (T < CUT)]) * 100:+.1f}/{np.nanmean(x[ok & (T >= CUT)]) * 100:+.1f}; "
            f"шорт в плюсе {(x[ok] > 0).mean():.0%})")


cols = [("pre", "объявление → начало"), ("first1", "первые сутки"), ("during", "весь период"), ("post1", "после конца 1 сут"),
        ("post3", "после 3 сут"), ("post7", "после 7 сут"), ("post14", "после 14 сут"), ("post7_age", "после 7 сут, к сверстникам"),
        ("post14_age", "после 14 сут, к сверстникам")]
for nm, g in [("ВСЕ", R)] + [(k, x) for k, x in R.groupby("kind")] + [("награда в том же токене", R[R.in_tok]),
                                                                      ("награда в BNB/USDC", R[~R.in_tok])]:
    print(f"\n== {nm}: событий {len(g)}, монет {g.s.nunique()}; шорт к рынку (+ — монета слабее рынка)")
    for c, lab in cols:
        print(f"  {lab:>28}: {st(g[c], g['T'])}")
R.to_pickle("s24/g1.pkl")
