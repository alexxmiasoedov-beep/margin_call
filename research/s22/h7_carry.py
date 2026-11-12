"""Г7. Базис и фандинг поперечно по всем перпам (Cao et al. JFM 2024: базис — главный поперечный предиктор доходности
фьючерсов; Chi et al. 2023; PERP3; Schmeling–Schrimpf–Todorov «Crypto Carry»; китайский аналог — структура сроков на
товарных фьючерсах). Каждый день в 00:00 UTC монеты, у которых фьючерс торгуется ≥ 30 суток и будет торговаться ещё
7 суток, без стейблкоинов, металлов и акций, без нижних 30% по обороту за сутки; ранжирование по
  - премии к индексу — среднее premiumIndex за прошлые 24 ч (15-мин свечи, s12/prem.pkl);
  - фандингу — среднее за 3 суток в пересчёте на 8 ч;
  - для контроля — доходности за 14 суток (моментум).
Портфели на 1, 3 и 7 суток: (а) лонг нижнего квинтиля + шорт верхнего, (б) только шорт верхнего + лонг BTC на ту же
сумму. Доход ноги = цена ± фандинг − комиссия 0,1% за круг. Равные веса и веса по обороту; дневной ряд с перекрытием —
t Ньюи–Уэста с h − 1 лагами; половины (до/после 01.12.2025), годы; Фама–Макбет на непересекающихся неделях с моментумом.
Запуск из папки с данными."""
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import BAR, CUT, DAY, FEE, GR, H, K, NONCRYPTO, funding, live
from h2_dtc import nw_t

HD = (1, 3, 7)


def panel():
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    g, C = GR["grid"], GR["C"]
    d0 = int(g[0] // DAY + 31) * DAY; d1 = int(g[-1] // DAY - 7) * DAY
    days = np.arange(d0, d1, DAY)
    kd = np.searchsorted(g, days)
    rows = []
    for s, a in K.items():
        if s in NONCRYPTO or s not in PR:
            continue
        lo, hi = live(s)
        ok = (days - 30 * DAY >= lo) & (days + 7 * DAY <= hi) & (kd + 7 * 24 < len(g)) & (g[np.minimum(kd, len(g) - 1)] == days)
        if not ok.any():
            continue
        dd, kk = days[ok], kd[ok]
        c = C[GR["row"][s]].astype(float)
        t = a["t"].astype(np.int64); cq = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
        turn = cq[np.searchsorted(t, dd)] - cq[np.searchsorted(t, dd - DAY)]
        pt, pv = PR[s]; cp = np.r_[0.0, np.cumsum(pv.astype(float))]
        i0, i1 = np.searchsorted(pt, dd - DAY), np.searchsorted(pt, dd)
        prem = np.where(i1 > i0, (cp[i1] - cp[i0]) / np.maximum(i1 - i0, 1), np.nan)
        fr = funding(s)
        if len(fr):
            ft = fr[:, 0]; gap = np.r_[8.0, np.maximum(1.0, np.round(np.diff(ft) / H))]
            cn = np.r_[0.0, np.cumsum(fr[:, 1] * 8 / gap)]; cr = np.r_[0.0, np.cumsum(fr[:, 1])]
            j0, j1 = np.searchsorted(ft, dd - 3 * DAY, "right"), np.searchsorted(ft, dd, "right")
            fav = np.where(j1 > j0, (cn[j1] - cn[j0]) / np.maximum(j1 - j0, 1), np.nan)
        else:
            fav = np.full(len(dd), np.nan)
        c14 = c[np.maximum(kk - 14 * 24, 0)]
        r = dict(s=s, d=dd, turn=turn, prem=prem, fav=fav, mom=c[kk] / c14 - 1)   # fav — фандинг за прошлые 3 сут; f1/f3/f7 — будущий
        for h in HD:
            px = c[kk + h * 24] / c[kk] - 1
            if len(fr):
                fh = cr[np.searchsorted(ft, dd + h * DAY, "right")] - cr[np.searchsorted(ft, dd, "right")]
            else:
                fh = np.zeros(len(dd))
            r[f"px{h}"] = px; r[f"f{h}"] = fh
        rows.append(pd.DataFrame(r))
    P = pd.concat(rows, ignore_index=True)
    P = P[np.isfinite(P.px1) & np.isfinite(P.turn) & (P.turn > 0)]
    P = P[P.groupby("d").turn.rank(pct=True) > 0.3]               # без нижних 30% по обороту
    return P


def legs(g, col, h, w=None):
    q = g[col].rank(pct=True)
    lo, hi = g[q <= 0.2], g[q > 0.8]
    def avg(x, sub):
        return np.average(x, weights=sub.turn) if w else x.mean()
    lp, lf = avg(lo[f"px{h}"], lo), avg(-lo[f"f{h}"], lo)            # лонг: цена, фандинг (платит положительный)
    sp, sf = avg(-hi[f"px{h}"], hi), avg(hi[f"f{h}"], hi)            # шорт: цена, фандинг (получает положительный)
    return lp, lf, sp, sf


if __name__ == "__main__":
    P = panel()
    print(f"монето-дней {len(P):,}, дней {P.d.nunique()}, монет в день {P.groupby('d').size().mean():.0f}; "
          f"корреляция рангов премии и фандинга {P.groupby('d').apply(lambda g: g.prem.rank().corr(g.fav.rank())).mean():.2f}")
    g, C = GR["grid"], GR["C"]                                       # BTC — из сетки (мог выпасть из корзины по обороту)
    cb = C[GR["row"]["BTC"]].astype(float); frb = funding("BTC")
    def btc_long(d, h):
        k = int(np.searchsorted(g, d)); px = cb[k + h * 24] / cb[k] - 1
        f = float(frb[(frb[:, 0] > d) & (frb[:, 0] <= d + h * DAY), 1].sum())
        return px - f - FEE
    for col, nm in (("prem", "премия к индексу за 24 ч"), ("fav", "фандинг за прошлые 3 сут")):
        print(f"\n=== сортировка: {nm} (верхний квинтиль = самые «перегруженные лонги») ===")
        for w in (False, True):
            for h in HD:
                rows = []
                for d, gd in P.dropna(subset=[col]).groupby("d"):
                    if len(gd) < 25:
                        continue
                    lp, lf, sp, sf = legs(gd, col, h, w)
                    rows.append((d, lp, lf, sp, sf, btc_long(d, h)))
                R = pd.DataFrame(rows, columns=["d", "lp", "lf", "sp", "sf", "btc"])
                R["ls"] = R.lp + R.lf + R.sp + R.sf - 2 * FEE
                R["s_btc"] = R.sp + R.sf - FEE + R.btc
                h1, h2 = R.d < CUT, R.d >= CUT
                y = pd.to_datetime(R.d, unit="s").dt.year
                print(f"  {'по обороту' if w else 'поровну':10s} {h} сут: (а) лонг Q1 + шорт Q5 {R.ls.mean() * 100:+.2f}% (t {nw_t(R.ls, h - 1 if h > 1 else 0):+.1f}; "
                      f"цена {(R.lp + R.sp).mean() * 100:+.2f}, фандинг {(R.lf + R.sf).mean() * 100:+.2f}; половины "
                      f"{R.ls[h1].mean() * 100:+.2f}/{R.ls[h2].mean() * 100:+.2f}; " +
                      ", ".join(f"{yy}: {R.ls[y == yy].mean() * 100:+.2f}" for yy in sorted(y.unique())) +
                      f") | (б) шорт Q5 + лонг BTC {R.s_btc.mean() * 100:+.2f}% (t {nw_t(R.s_btc, h - 1 if h > 1 else 0):+.1f}; "
                      f"шорт: цена {R.sp.mean() * 100:+.2f}, фандинг {R.sf.mean() * 100:+.2f}; половины "
                      f"{R.s_btc[h1].mean() * 100:+.2f}/{R.s_btc[h2].mean() * 100:+.2f})")
    print("\nФама–Макбет (непересекающиеся недели), зависимая — доход лонга за 7 суток (цена − фандинг), ранги 0…1:")
    for cols in (["prem"], ["fav"], ["mom"], ["prem", "mom"], ["fav", "mom"], ["prem", "fav", "mom"]):
        co = []
        for d in sorted(P.d.unique())[::7]:
            gd = P[P.d == d].dropna(subset=cols + ["px7"])
            if len(gd) < 25:
                continue
            X = np.column_stack([np.ones(len(gd))] + [gd[c].rank(pct=True).values for c in cols])
            co.append(np.linalg.lstsq(X, (gd.px7 - gd.f7).values, rcond=None)[0][1:])
        Cf = np.array(co)
        print(f"  {' + '.join(cols):17s}: " + "; ".join(f"{c} {Cf[:, i].mean() * 100:+.2f}% (t {Cf[:, i].mean() / Cf[:, i].std() * np.sqrt(len(Cf)):+.1f})"
                                                for i, c in enumerate(cols)) + f"  [недель {len(Cf)}]")
    P.to_pickle("s22/h7_panel.pkl")
