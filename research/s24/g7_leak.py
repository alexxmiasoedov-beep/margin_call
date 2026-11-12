"""Утечки перед листингом: путь фьючерса к рынку (лонг) и поток агрессивных покупок (Φ, панель s23) до первой сделки
корейского листинга (s15/kr_journal.pkl, 205) и до объявления Binance (s22/h10_ann.pkl, 63). Окна: −7 сут … −1 ч,
−24 ч … −1 ч, −4 ч … −1 ч (до момента t события). Сравнение: та же монета в случайные моменты за 60 суток до события
(плацебо, 20 на событие). Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s23")
from common23 import CUT, G, P, ROW, ct                          # noqa: E402

C = P["C"]; Q = P["Q"]; TB = P["TB"]
lr = np.log(C[:, 1:] / C[:, :-1]); lr = np.c_[np.full(len(C), np.nan), lr]
mk = np.nanmedian(lr, axis=0)
ex = lr - mk
rng = np.random.default_rng(3)


def win(s, t_ev, a_h, b_h):
    """Доход к рынку (сумма часовых лог-доходов) и чистый поток за часы (t_ev − a_h, t_ev − b_h]; поток — в долях оборота."""
    j = ROW.get(s)
    if j is None:
        return np.nan, np.nan
    k = int(np.searchsorted(G, t_ev)) - b_h                     # последний час окна кончается до события на b_h ч
    lo = k - (a_h - b_h)
    if lo < 1 or k >= len(G):
        return np.nan, np.nan
    r = ex[j, lo + 1:k + 1]
    q, tb = Q[j, lo + 1:k + 1], TB[j, lo + 1:k + 1]
    if np.isnan(r).mean() > 0.2 or np.nansum(q) <= 0:
        return np.nan, np.nan
    return np.nansum(r), (2 * np.nansum(tb) - np.nansum(q)) / np.nansum(q)


KJ = pd.read_pickle("s15/kr_journal.pkl")
BL = pd.read_pickle("s22/h10_ann.pkl")
events = [("корейский листинг (первая сделка)", list(zip(KJ.sym, KJ.t0))), ("листинг Binance (объявление)", list(zip(BL.s, BL.ts)))]
for nm, ev in events:
    print(f"\n== {nm}: событий {len(ev)}")
    for a_h, b_h in ((168, 1), (24, 1), (4, 1)):
        x = np.array([win(s, t, a_h, b_h) for s, t in ev])
        pl = np.array([[win(s, t - rng.integers(3, 60) * 86400 - rng.integers(0, 24) * 3600, a_h, b_h) for _ in range(20)] for s, t in ev])
        ts = np.array([t for _, t in ev])
        m, t, n = ct(x[:, 0], ts)
        pm = np.nanmean(pl[:, :, 0]); pf = np.nanmean(pl[:, :, 1])
        d = x[:, 0] - np.nanmean(pl[:, :, 0], axis=1); md, td, _ = ct(d, ts)
        df = x[:, 1] - np.nanmean(pl[:, :, 1], axis=1); mf, tf, _ = ct(df, ts)
        print(f"  окно −{a_h} ч … −{b_h} ч: доход к рынку {m * 100:+.2f}% (t {t:+.1f}, n {n}), плацебо {pm * 100:+.2f}% → "
              f"разница {md * 100:+.2f} п. п. (t {td:+.1f}); доля чистых покупок {np.nanmean(x[:, 1]) * 100:+.2f}% против "
              f"{pf * 100:+.2f}% (разница {mf * 100:+.2f} п. п., t {tf:+.1f})")
