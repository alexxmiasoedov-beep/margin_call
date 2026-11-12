"""Г5 — у каждой монеты свой механизм? Для признака X (аргумент): коэффициент дохода вперёд на ранг X по каждой монете
отдельно — на первой и на второй половине; корреляция коэффициентов монет между половинами (есть ли устойчивая
«личность»). Затем вне выборки: эмпирический Байес — коэффициент монеты по её прошлому (только срезы, чей горизонт
закрылся до T), сжатый к общему; сравнение IC прогноза с IC общего признака. Запуск: python3 g5_personal.py X h"""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT, build, days, fwd_ex, nw_t, universe

X, h = sys.argv[1], int(sys.argv[2])
F = build(24); D = days(F); Y = fwd_ex(F["C"], h)
# панель срез × монета: ранг признака по срезу и доход вперёд (винсоризация по срезу)
xr, yv = {}, {}
for T in D:
    idx = universe(F, T)
    x, y = F[X].loc[T, idx], Y.loc[T, idx]
    ok = x.notna() & y.notna()
    if ok.sum() < 30:
        continue
    xr[T] = x[ok].rank(pct=True) - 0.5
    yv[T] = y[ok].clip(y[ok].quantile(0.01), y[ok].quantile(0.99))
XR, YV = pd.DataFrame(xr).T, pd.DataFrame(yv).T


def slope(x, y):
    ok = x.notna() & y.notna()
    if ok.sum() < 40:
        return np.nan, np.nan
    x, y = x[ok] - x[ok].mean(), y[ok] - y[ok].mean()
    b = (x * y).sum() / (x * x).sum()
    se = np.sqrt(((y - b * x) ** 2).sum() / (len(x) - 2) / (x * x).sum()) * np.sqrt(max(1, h // 24))   # поправка на перекрытие
    return b, se


h1, h2 = XR.index < CUT, XR.index >= CUT
B = pd.DataFrame({s: [*slope(XR.loc[h1, s], YV.loc[h1, s]), *slope(XR.loc[h2, s], YV.loc[h2, s])] for s in XR.columns},
                 index=["b1", "se1", "b2", "se2"]).T.dropna()
print(f"{X}, горизонт {h // 24} сут: монет с ≥ 40 срезами в обеих половинах {len(B)}")
print(f"  средний коэффициент монет: первая {B.b1.mean() * 100:+.2f} п. п., вторая {B.b2.mean() * 100:+.2f}")
sd_true1 = np.sqrt(max(B.b1.var() - (B.se1 ** 2).mean(), 0)); sd_true2 = np.sqrt(max(B.b2.var() - (B.se2 ** 2).mean(), 0))
print(f"  разброс коэффициентов: наблюдаемый {B.b1.std() * 100:.2f} / {B.b2.std() * 100:.2f}, ожидаемый от шума "
      f"{np.sqrt((B.se1 ** 2).mean()) * 100:.2f} / {np.sqrt((B.se2 ** 2).mean()) * 100:.2f} → «настоящий» "
      f"{sd_true1 * 100:.2f} / {sd_true2 * 100:.2f}")
r = np.corrcoef(B.b1, B.b2)[0, 1]; rs = B.b1.rank().corr(B.b2.rank())
print(f"  корреляция коэффициентов монет между половинами: {r:+.3f} (ранговая {rs:+.3f}; n={len(B)}, "
      f"порог 5% ≈ ±{2 / np.sqrt(len(B)):.3f})")

# вне выборки: эмпирический Байес по прошлому монеты
ics_pool, ics_eb, dates = [], [], []
for k, T in enumerate(XR.index):
    if T < XR.index[0] + 120 * 86400:
        continue
    past = XR.index[XR.index <= T - h * 3600]                     # срезы, чей доход вперёд уже известен к T
    xp, yp = XR.loc[past], YV.loc[past]
    xa, ya = xp.values.ravel(), yp.values.ravel()
    fin = np.isfinite(xa) & np.isfinite(ya)
    bp = np.polyfit(xa[fin], ya[fin], 1)[0]                         # общий коэффициент
    xx = (xp - xp.mean()); yy = (yp - yp.mean())
    nb = xp.notna().sum()
    bi = (xx * yy).sum() / (xx * xx).sum()
    resid = (yy - bi * xx)
    se = np.sqrt((resid ** 2).sum() / (nb - 2) / (xx * xx).sum()) * np.sqrt(max(1, h // 24))
    good = (nb >= 40) & bi.notna() & se.notna()
    tau2 = max(bi[good].var() - (se[good] ** 2).mean(), 0) if good.sum() > 20 else 0.0
    w = (tau2 / (tau2 + se ** 2)).where(good, 0.0)
    beb = w * bi.fillna(0) + (1 - w) * bp
    x, y = XR.loc[T], YV.loc[T]
    ok = x.notna() & y.notna()
    pred_eb = beb.reindex(x.index).fillna(bp)[ok] * x[ok]
    ics_pool.append((x[ok] * np.sign(bp)).rank().corr(y[ok].rank()))
    ics_eb.append(pred_eb.rank().corr(y[ok].rank()))
    dates.append(T)
ip, ie = pd.Series(ics_pool, index=dates), pd.Series(ics_eb, index=dates)
lag = max(1, h // 24)
for nm, s in (("общий признак", ip), ("персональный (Байес)", ie), ("разница", ie - ip)):
    a, b = s[s.index < CUT], s[s.index >= CUT]
    print(f"  IC {nm:>22}: {s.mean() * 100:+.2f}% (t {nw_t(s, lag):+.1f}) | первая {a.mean() * 100:+.2f}% | "
          f"вторая {b.mean() * 100:+.2f}% (t {nw_t(b, lag):+.1f})")
