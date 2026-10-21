"""Скрытая периодичность (графики разлоков): у монеты в один и тот же день месяца почти каждый месяц провал относительно рынка.
Поиск — 1-й год (19.10.2024–30.09.2025), проверка — 2-й (10.2025–10.2026). Окно: [d−k, d+m) суток по UTC, доходность к рынку
(минус среднее по всем монетам за те же дни). Шорт на 2-м году: вход в 00:00 UTC дня d−k, выход в 00:00 дня d+m, с фандингом."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
D0 = datetime.datetime(2024, 10, 1, tzinfo=UTC).timestamp(); CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
days = np.arange(D0, datetime.datetime(2026, 10, 19, tzinfo=UTC).timestamp(), 86400)
C = {}
for s, a in K.items():
    t = a["t"] + 900; c = a["c"].astype(np.float64)
    idx = np.searchsorted(t, days); ok = (idx < len(t)) & (t[np.clip(idx, 0, len(t) - 1)] == days)
    v = np.full(len(days), np.nan); v[ok] = c[idx[ok]]; C[s] = v                       # закрытие ровно в 00:00 UTC каждого дня
coins = sorted(C); M = np.vstack([C[s] for s in coins])                              # монеты × дни
def window_returns(k, m):
    """Доходность каждой монеты за окно [день−k, день+m) по всем дням + та же доходность рынка (среднее по монетам)."""
    R = M[:, np.r_[np.arange(k + m, len(days))]] / M[:, np.arange(0, len(days) - k - m)] - 1   # старт в день i, конец i+k+m
    mk = np.nanmean(np.where(np.abs(R) < 3, R, np.nan), axis=0)
    return R, mk                                                                        # R[:, i]: окно начинается в days[i]
dom = np.array([datetime.datetime.fromtimestamp(d, UTC).day for d in days])
def study(k, m, min_neg=0.75, max_mean=-0.02, min_months=8):
    R, mk = window_returns(k, m); rel = R - mk
    starts = days[:R.shape[1]]
    sel = []
    for ci, s in enumerate(coins):
        for d in range(1 + k, 29):
            idx = np.flatnonzero((dom[:R.shape[1]] == d - k) & (starts < CUT - (k + m) * 86400))
            v = rel[ci, idx]; v = v[np.isfinite(v)]
            if len(v) >= min_months and (v < 0).mean() >= min_neg and v.mean() <= max_mean: sel.append((s, d, len(v), (v < 0).mean(), v.mean()))
    out = []
    for s, d, n, neg, mean in sel:
        ci = coins.index(s); fr = F.get(s)
        for i in np.flatnonzero((dom[:R.shape[1]] == d - k) & (starts >= CUT)):
            if not np.isfinite(R[ci, i]): continue
            t_in, t_out = starts[i], starts[i] + (k + m) * 86400
            fund = float(fr[(fr[:, 0] > t_in) & (fr[:, 0] <= t_out), 2].sum()) if fr is not None else 0.0
            out.append((s, d, t_in, -R[ci, i] + fund - 0.001, -rel[ci, i]))
    T = pd.DataFrame(out, columns=["s", "d", "t", "short", "short_rel"])
    base = -np.nanmean(rel[:, starts >= CUT])                       # фон: случайный «шорт к рынку» в то же время
    return sel, T, base
for k, m in ((2, 1), (1, 2), (0, 3), (3, 0), (1, 1)):
    for min_neg, max_mean in ((0.75, -0.02), (0.8, -0.04)):
        sel, T, base = study(k, m, min_neg, max_mean)
        print(f"окно [d−{k}, d+{m}), отбор: провал ≥ {min_neg:.0%} месяцев и в среднем ≤ {max_mean:.0%}: найдено {len(sel):4d} (монета, день) | "
              f"2-й год: {len(T):4d} сделок, шорт {T.short.mean() * 100:+.2f}% (к рынку {T.short_rel.mean() * 100:+.2f}%, фон {base * 100:+.2f}%), в плюсе {(T.short > 0).mean():.0%}", flush=True)
