"""Г2. «Дни на покрытие»: займ к обороту вместо долларов (Hong et al.: DTC 1,19% в месяц, t 6,67, против 0,71% у доли
шортов; Boehmer et al.: DTC — самая устойчивая мера в 38 странах). Оборот — объём фьючерса в USDT за 24 ч (15-мин свечи).
  А. Внутри событий 💸 (s22/h1_panel.pkl: отдача ×1,5 за 4 ч, займ не вырос, цена ±5%): терцили REP к обороту против
     терцилей REP в долларах — сделки 7 суток со стопом 50% и доход к рынку за 7 суток.
  Б. Корзина как у 🏦: каждый день в 01:00 UTC монеты, бывшие в канале за прошлые 7 суток (фьючерс старше 30 суток,
     оборот ≥ 10 млн $ в сутки); сортировка по (1) доле часов в канале (мера 🏦), (2) среднему BOR в долларах,
     (3) среднему BOR к обороту. Шорт верхнего квинтиля на 7 суток к рынку (медиана всех фьючерсов) и с фандингом;
     t — Ньюи–Уэст с 6 лагами по дневному ряду.
  В. Фама–Макбет на непересекающихся неделях: доход шорта к рынку за 7 суток на ранги мер (1)–(3), доходность и
     волатильность за 7 суток, фандинг за 7 суток. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import BAR, CUT, DAY, GR, H, K, ct, funding, fwd, live, summ, thin
from borrow_trades import sims


def turn24(D):
    out = np.full(len(D), np.nan)
    for s, idx in D.groupby("s").groups.items():
        a = K[s]; t = a["t"].astype(np.int64); cs = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
        j = np.searchsorted(t, D.loc[idx, "T"].values - BAR)
        ok = (j < len(t)) & (j >= 95)
        v = np.full(len(j), np.nan); jj = j[ok]
        v[ok] = cs[jj + 1] - cs[jj + 1 - 96]
        out[D.index.get_indexer(idx)] = v
    return out


def nw_t(x, lags=6):
    x = pd.Series(x).dropna().values; n = len(x)
    if n < 20:
        return np.nan
    u = x - x.mean(); v = (u @ u) / n
    for l in range(1, lags + 1):
        v += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return x.mean() / np.sqrt(v / n)


if __name__ == "__main__":
    P = pd.read_pickle("s22/h1_panel.pkl")
    P["turn"] = turn24(P); P["rep_t"] = P.rep / P.turn
    acc_b = (P.bor >= 1.5 * P.bor4) & (P.bor >= 50e3); acc_r = (P.rep >= 1.5 * P.rep4) & (P.rep >= 20e3)
    E = thin(P[acc_r & ~acc_b & P.px & np.isfinite(P.rep_t)])
    print(f"А. События 💸 с оборотом: {len(E)}")
    R = sims(E, sl=0.5, hold_h=168).merge(E[["s", "T", "rep", "rep_t"]], on=["s", "T"])
    R["x7"] = [fwd(s, T, 168) for s, T in zip(R.s, R["T"])]
    for col, nm in (("rep_t", "REP к обороту"), ("rep", "REP в долларах")):
        q = pd.qcut(R[col], 3, labels=False)
        print(f"  терцили по {nm}: " + " | ".join(
            f"T{k + 1}: сделки {R.net[q == k].mean() * 100:+.2f}% (t {ct(R.net[q == k].values, R['T'][q == k].values)[1]:+.1f}), "
            f"к рынку {R.x7[q == k].mean() * 100:+.2f}%" for k in range(3)))
    print(f"  корреляция рангов REP к обороту и REP в долларах: {R.rep_t.rank().corr(R.rep.rank()):.2f}")

    print("\nБ. Корзина как у 🏦 (каждый день в 01:00 UTC, шорт на 7 суток):")
    D = pd.read_pickle("s21/panel.pkl")[["s", "T", "bor"]].reset_index(drop=True)
    D["turn"] = turn24(D); D["bt"] = D.bor / D.turn
    days = np.arange((D["T"].min() // DAY + 8) * DAY, (D["T"].max() // DAY - 7) * DAY, DAY)
    g, C = GR["grid"], GR["C"]
    rows = []
    Ts = D["T"].values
    for d in days:
        w = D[(Ts >= d - 7 * DAY) & (Ts < d)]
        if not len(w):
            continue
        agg = w.groupby("s").agg(share=("T", "size"), bor=("bor", "mean"), bt=("bt", "mean"))
        agg["share"] /= 168
        T = d + H; k = int(np.searchsorted(g, T)); k7 = int(np.searchsorted(g, T - 7 * DAY))
        for s, r in agg.iterrows():
            lo, hi = live(s)
            if lo > d - 30 * DAY or T + 168 * H > hi:
                continue
            a = K[s]; t = a["t"].astype(np.int64)
            m = (t >= d - 7 * DAY) & (t < d)
            tv = a["qv"][m].sum() / 7
            if tv < 10e6:
                continue
            c = C[GR["row"][s]]
            r7 = c[k] / c[k7] - 1 if np.isfinite(c[k]) and np.isfinite(c[k7]) else np.nan
            hr = np.diff(np.log(c[k7:k + 1].astype(float)))
            fr = funding(s); f7 = float(fr[(fr[:, 0] > d - 7 * DAY) & (fr[:, 0] <= d), 1].sum()) if len(fr) else 0.0
            rows.append(dict(d=d, s=s, share=r.share, bor=r.bor, bt=r.bt, r7=r7, vol=np.nanstd(hr), f7=f7,
                             x=fwd(s, T, 168), n=fwd(s, T, 168, net=True)))
    U = pd.DataFrame(rows).dropna(subset=["x", "bt", "bor"])
    print(f"  дней {U.d.nunique()}, монето-дней {len(U)}, монет в день в среднем {U.groupby('d').size().mean():.0f}")
    for col, nm in (("share", "доля часов в канале (мера 🏦)"), ("bor", "BOR в долларах"), ("bt", "BOR к обороту")):
        top, bot, nett = [], [], []
        for d, gd in U.groupby("d"):
            if len(gd) < 10:
                continue
            qq = gd[col].rank(pct=True)
            top.append((d, gd.x[qq > 0.8].mean() - gd.x.mean(), gd.n[qq > 0.8].mean(), gd.x[qq <= 0.2].mean() - gd.x.mean()))
        tb = pd.DataFrame(top, columns=["d", "top", "net", "bot"])
        h1, h2 = tb[tb.d < CUT], tb[tb.d >= CUT]
        print(f"  {nm:30s}: верхний квинтиль к среднему по корзине {tb.top.mean() * 100:+.2f}% за 7 сут (t НУ {nw_t(tb.top):+.1f}; "
              f"половины {h1.top.mean() * 100:+.2f}/{h2.top.mean() * 100:+.2f}), нижний {tb.bot.mean() * 100:+.2f}%; "
              f"шорт верхнего с фандингом {tb.net.mean() * 100:+.2f}% (t НУ {nw_t(tb.net):+.1f})")

    print("\nВ. Фама–Макбет (непересекающиеся недели), зависимая — шорт к рынку за 7 суток, регрессоры — ранги 0…1:")
    U["lb"] = np.log(U.bor); U["lbt"] = np.log(U.bt)
    cols = ["share", "lb", "lbt", "r7", "vol", "f7"]
    names = {"share": "доля в канале", "lb": "log BOR $", "lbt": "log BOR/оборот", "r7": "доходность 7 сут",
             "vol": "волатильность", "f7": "фандинг 7 сут"}
    coefs = []
    wk = sorted(U.d.unique())[::7]
    for d in wk:
        gd = U[U.d == d].dropna(subset=cols + ["x"])
        if len(gd) < 15:
            continue
        X = np.column_stack([np.ones(len(gd))] + [gd[c].rank(pct=True).values for c in cols])
        b = np.linalg.lstsq(X, gd.x.values, rcond=None)[0]
        coefs.append(b[1:])
    Cf = np.array(coefs)
    print(f"  недель {len(Cf)}: " + "; ".join(f"{names[c]} {Cf[:, i].mean() * 100:+.2f}% (t {Cf[:, i].mean() / Cf[:, i].std() * np.sqrt(len(Cf)):+.1f})"
                                              for i, c in enumerate(cols)))
    print("  (коэффициент — разница дохода шорта за 7 суток между монетой с наибольшим и наименьшим рангом)")
    U.to_pickle("s22/h2_basket.pkl")
