"""Г8. Фактор «умных денег» (开源金工 «聪明钱因子», на А-акциях после публикации RankIC −6,4…−7,2%, IR 2,1–3,2) на 15-мин
свечах перпов Binance. Каждый понедельник 00:00 UTC для каждой монеты (фьючерс торгуется ≥ 30 суток и ещё 7, без
стейблкоинов, металлов и акций, без нижних 30% по обороту за 10 суток) по 960 свечам прошлых 10 суток:
  S = |доходность свечи (закрытие к закрытию)| / оборот^β, β = 0,1 / 0,25 / 0,5 — все три заданы заранее;
  свечи по убыванию S набираются, пока их оборот не достигнет 20% оборота окна («умные»);
  Q = VWAP умных свечей / VWAP всех (цена свечи — (H+L+C)/3, объём в монетах = оборот / цена).
Исход — доход лонга за следующую неделю (цена − фандинг). Недельный RankIC (Спирмен), его t; спред децилей: лонг нижнего
дециля Q + шорт верхнего, с фандингом и комиссией 0,1% за круг на ногу; половины; ликвидная и менее ликвидная половины.
Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import BAR, CUT, DAY, FEE, GR, K, NONCRYPTO, funding, live

BETAS = (0.1, 0.25, 0.5)


def weeks():
    g = GR["grid"]
    t0 = int(g[0] // DAY + 40) * DAY; t1 = int(g[-1] // DAY - 8) * DAY
    d = np.arange(t0, t1, DAY)
    return d[pd.to_datetime(d, unit="s").weekday == 0]


def factor_rows():
    W = weeks(); g, C = GR["grid"], GR["C"]; rows = []
    for s, a in K.items():
        if s in NONCRYPTO:
            continue
        lo, hi = live(s)
        t = a["t"].astype(np.int64); c = a["c"].astype(float); qv = a["qv"].astype(float)
        p = (a["h"].astype(float) + a["l"].astype(float) + c) / 3
        r = np.r_[np.nan, c[1:] / c[:-1] - 1]
        cg = C[GR["row"][s]].astype(float)
        fr = funding(s)
        for w in W:
            if w - 30 * DAY < lo or w + 7 * DAY > hi:
                continue
            i0, i1 = np.searchsorted(t, w - 10 * DAY), np.searchsorted(t, w)
            if i1 - i0 < 900:
                continue
            rr, vv, pp = r[i0:i1], qv[i0:i1], p[i0:i1]
            ok = np.isfinite(rr) & (vv > 0)
            if ok.sum() < 900:
                continue
            rr, vv, pp = rr[ok], vv[ok], pp[ok]
            k = int(np.searchsorted(g, w))
            if k + 168 >= len(g) or not (np.isfinite(cg[k]) and np.isfinite(cg[k + 168])):
                continue
            px = cg[k + 168] / cg[k] - 1
            f = float(fr[(fr[:, 0] > w) & (fr[:, 0] <= w + 7 * DAY), 1].sum()) if len(fr) else 0.0
            vw_all = vv.sum() / (vv / pp).sum()
            row = dict(s=s, w=w, turn=vv.sum() / 10, px=px, f=f)
            for b in BETAS:
                o = np.argsort(-(np.abs(rr) / vv ** b))
                cum = np.cumsum(vv[o]); m = o[:int(np.searchsorted(cum, 0.2 * cum[-1])) + 1]
                row[f"q{b}"] = (vv[m].sum() / (vv[m] / pp[m]).sum()) / vw_all
            rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    F = factor_rows()
    F = F[F.groupby("w").turn.rank(pct=True) > 0.3].copy()
    F["lr"] = F.px - F.f                                        # доход лонга с фандингом
    print(f"монето-недель {len(F):,}, недель {F.w.nunique()}, монет в неделю {F.groupby('w').size().mean():.0f}")
    for b in BETAS:
        col = f"q{b}"; ics, spr, ics_liq, ics_ill = [], [], [], []
        for w, gw in F.groupby("w"):
            if len(gw) < 30:
                continue
            ics.append((w, gw[col].rank().corr(gw.lr.rank())))
            q = gw[col].rank(pct=True)
            lo, hi = gw[q <= 0.1], gw[q > 0.9]
            spr.append((w, (lo.lr.mean() - FEE) + (-hi.lr.mean() - FEE), lo.px.mean() - hi.px.mean()))
            liq = gw.turn.rank(pct=True) > 0.5
            ics_liq.append(gw[liq][col].rank().corr(gw[liq].lr.rank())); ics_ill.append(gw[~liq][col].rank().corr(gw[~liq].lr.rank()))
        I = pd.DataFrame(ics, columns=["w", "ic"]); S = pd.DataFrame(spr, columns=["w", "net", "px"])
        tt = lambda x: np.mean(x) / np.std(x) * np.sqrt(len(x))
        h1, h2 = I.w < CUT, I.w >= CUT
        print(f"\nβ = {b}: RankIC {I.ic.mean() * 100:+.2f}% (t {tt(I.ic):+.1f}; IR за год {I.ic.mean() / I.ic.std() * np.sqrt(52):+.2f}; "
              f"недель с IC < 0 {(I.ic < 0).mean():.0%}; половины {I.ic[h1].mean() * 100:+.2f}/{I.ic[h2].mean() * 100:+.2f}%)")
        print(f"   ликвидная половина IC {np.nanmean(ics_liq) * 100:+.2f}% (t {tt(np.array(ics_liq)[np.isfinite(ics_liq)]):+.1f}), "
              f"менее ликвидная {np.nanmean(ics_ill) * 100:+.2f}% (t {tt(np.array(ics_ill)[np.isfinite(ics_ill)]):+.1f})")
        print(f"   лонг нижнего дециля Q + шорт верхнего за неделю: {S.net.mean() * 100:+.2f}% с фандингом и комиссией "
              f"(t {tt(S.net):+.1f}; только цена {S.px.mean() * 100:+.2f}%; половины {S.net[S.w < CUT].mean() * 100:+.2f}/"
              f"{S.net[S.w >= CUT].mean() * 100:+.2f}%)")
    F.to_pickle("s22/h8_panel.pkl")
