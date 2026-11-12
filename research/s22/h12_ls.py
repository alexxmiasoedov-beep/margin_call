"""Г12. Розница по счетам против крупных по позициям — только хвосты (KOSPI200: иностранцы торговали в сторону будущей
доходности, розница — против; тайваньский индекс розницы и позиции крупных в КНР вне выборки слабы). Каждый день в
00:00 UTC по 100 самым торгуемым перпам (5-мин метрики data.binance.vision, почасовые отметки, s22/metrics_full):
  Δtop — изменение за 24 ч отношения лонг/шорт топ-трейдеров по позициям (sum_toptrader_long_short_ratio, в логарифмах);
  Δall — то же для всех счетов (count_long_short_ratio);
  D = ранг Δtop − ранг Δall (крупные покупают против розницы → D высокий).
Вход — на закрытии следующего часа (сдвиг на 1 бар), доход лонга за 1 и 3 суток (цена − фандинг − комиссия) к среднему
по тем же 100 монетам. Крайние децили D; регрессия Фамы–Макбета по дням с контролем базиса (премия за 24 ч), фандинга за
3 суток, моментума 14 суток и доходности за 24 ч; t Ньюи–Уэста; половины. Запуск из папки с данными."""
import glob
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import CUT, DAY, FEE, GR, H, funding, live
from h2_dtc import nw_t


def load(sym):
    a = [np.load(f) for f in sorted(glob.glob(f"s22/metrics_full/{sym}/*.npy"))]
    a = [x for x in a if len(x)]
    if not a:
        return None
    a = np.concatenate(a)
    return a[np.argsort(a[:, 0])]


if __name__ == "__main__":
    top = open("s22/top100.txt").read().split()
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    g, C = GR["grid"], GR["C"]
    rows = []
    for s in top:
        m = load(s)
        if m is None or s not in GR["row"]:
            continue
        t = m[:, 0]; c = C[GR["row"][s]].astype(float)
        lo, hi = live(s)
        days = np.arange(max(t[0] // DAY + 2, lo // DAY + 15) * DAY, min(t[-1] // DAY, hi // DAY - 4) * DAY, DAY)
        i1, i0 = np.searchsorted(t, days), np.searchsorted(t, days - DAY)
        ok = (i1 < len(t)) & (i0 < len(t))
        days, i1, i0 = days[ok], i1[ok], i0[ok]
        ok = (t[i1] == days) & (t[i0] == days - DAY)
        days, i1, i0 = days[ok], i1[ok], i0[ok]
        dtop = np.log(m[i1, 4] / m[i0, 4]); dall = np.log(m[i1, 5] / m[i0, 5])
        k = np.searchsorted(g, days + H)                         # вход на закрытии 01:00
        k0 = np.searchsorted(g, days)
        pt, pv = PR.get(s, (np.zeros(0, np.int64), np.zeros(0)))
        cp = np.r_[0.0, np.cumsum(pv.astype(float))]
        a0, a1 = np.searchsorted(pt, days - DAY), np.searchsorted(pt, days)
        prem = np.where(a1 > a0, (cp[a1] - cp[a0]) / np.maximum(a1 - a0, 1), np.nan)
        fr = funding(s)
        for n, d in enumerate(days):
            kk = k[n]
            if kk + 72 >= len(g):
                continue
            r = dict(s=s, d=d, dtop=dtop[n], dall=dall[n], prem=prem[n],
                     fav=float(fr[(fr[:, 0] > d - 3 * DAY) & (fr[:, 0] <= d), 1].mean()) if len(fr) else np.nan,
                     mom=c[k0[n]] / c[max(k0[n] - 14 * 24, 0)] - 1, r24=c[k0[n]] / c[max(k0[n] - 24, 0)] - 1)
            for h in (24, 72):
                px = c[kk + h] / c[kk] - 1
                f = float(fr[(fr[:, 0] > g[kk]) & (fr[:, 0] <= g[kk + h]), 1].sum()) if len(fr) else 0.0
                r[f"l{h}"] = px - f - FEE
            rows.append(r)
    P = pd.DataFrame(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=["dtop", "dall", "l24"])
    P["l24x"] = P.l24 - P.groupby("d").l24.transform("mean"); P["l72x"] = P.l72 - P.groupby("d").l72.transform("mean")
    P["D"] = P.groupby("d").dtop.rank(pct=True) - P.groupby("d").dall.rank(pct=True)
    print(f"монето-дней {len(P):,}, дней {P.d.nunique()}, монет в день {P.groupby('d').size().mean():.0f}; "
          f"корреляция Δtop и Δall {P.dtop.corr(P.dall):.2f}")
    for h in (24, 72):
        top_, bot_ = [], []
        for d, gd in P.groupby("d"):
            if len(gd) < 30:
                continue
            q = gd.D.rank(pct=True)
            top_.append((d, gd[f"l{h}x"][q > 0.9].mean(), gd[f"l{h}x"][q <= 0.1].mean()))
        R = pd.DataFrame(top_, columns=["d", "hi", "lo"]); R["sp"] = R.hi - R.lo
        print(f"\n{h // 24} сут, лонг к среднему 100 монет: верхний дециль D (крупные покупают против розницы) "
              f"{R.hi.mean() * 100:+.2f}%, нижний {R.lo.mean() * 100:+.2f}%; разница {R.sp.mean() * 100:+.2f}% "
              f"(t НУ {nw_t(R.sp, h // 24 - 1 if h > 24 else 0):+.1f}; половины {R.sp[R.d < CUT].mean() * 100:+.2f}/"
              f"{R.sp[R.d >= CUT].mean() * 100:+.2f}%)")
    print("\nФама–Макбет по дням (зависимая — лонг к среднему за 1 / 3 суток), регрессоры — ранги 0…1:")
    cols = ["D", "dtop", "dall", "prem", "fav", "mom", "r24"]
    for h in (24, 72):
        co = []
        for d, gd in P.dropna(subset=cols).groupby("d"):
            if len(gd) < 30:
                continue
            X = np.column_stack([np.ones(len(gd))] + [gd[c].rank(pct=True).values for c in ["D", "prem", "fav", "mom", "r24"]])
            co.append(np.linalg.lstsq(X, gd[f"l{h}x"].values, rcond=None)[0][1:])
        Cf = np.array(co)
        print(f"  {h // 24} сут: " + "; ".join(f"{c} {Cf[:, i].mean() * 100:+.2f}% (t НУ {nw_t(Cf[:, i], h // 24 - 1 if h > 24 else 0):+.1f})"
                                     for i, c in enumerate(["D", "prem", "fav", "mom", "r24"])) + f" [дней {len(Cf)}]")
    P.to_pickle("s22/h12_panel.pkl")
