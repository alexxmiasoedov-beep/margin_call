"""Скользящая проверка: градиентный бустинг учится на всём прошлом (минус сутки) и предсказывает доходность к рынку на 24 ч
в следующем квартале. Сделки — по сильным предсказаниям (порог на предсказанную доходность), одна на монету за 24 ч,
итог — абсолютный (шорт: −цена + фандинг, лонг: цена − фандинг), комиссия 0,1%."""
import pickle, datetime, time
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
P = pd.read_pickle("s3/panel2.pkl")
P["lv24"] = np.log10(P.v24.clip(1)); P["lvx"] = np.log10(P.vx.clip(1e-3))
FEAT = ["age", "r1", "r4", "r24", "r7d", "d1", "d4", "d24", "lv24", "lvx", "v1x", "tsz", "nrate", "rng24", "rng7", "fromhi24", "fromlo24",
        "fromhi7", "fromlo7", "fund24", "fund72", "flast", "fiv", "tsh1", "tsh24", "tshx", "btc4", "btc24", "hour", "dow", "mkt24", "breadth",
        "r24_rank", "vx_rank", "fund24_rank"]
UTC = datetime.timezone.utc
Q = [datetime.datetime(y, m, 1, tzinfo=UTC).timestamp() for y, m in ((2025, 4), (2025, 7), (2025, 10), (2026, 1), (2026, 4), (2026, 7), (2026, 10), (2026, 11))]
y = P.f24m.clip(-0.5, 0.5).values; X = P[FEAT].values.astype(np.float32); T = P.t.values
P["pred"] = np.nan
for qa, qb in zip(Q[:-1], Q[1:]):
    tr = np.flatnonzero(T < qa - 86400); te = np.flatnonzero((T >= qa) & (T < qb))
    rng = np.random.default_rng(1); tr = rng.choice(tr, min(len(tr), 2_000_000), replace=False)
    t0 = time.time()
    m = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=2000, l2_regularization=1.0, random_state=1)
    m.fit(X[tr], y[tr]); P.loc[te, "pred"] = m.predict(X[te])
    print(datetime.datetime.fromtimestamp(qa, UTC).strftime("%Y-%m"), f"обучение {len(tr)} строк, {time.time() - t0:.0f} с", flush=True)
P[["s", "t", "pred", "f24", "f24m", "ffund24", "fmax24", "fmin24"]].to_pickle("s3/wf_pred.pkl")
def trades(side, thr):
    d = P[P.pred.notna() & ((P.pred <= thr) if side == "short" else (P.pred >= thr))].sort_values(["s", "t"])
    keep, last = [], {}
    for i, s, t in zip(d.index, d.s.values, d.t.values):
        if t - last.get(s, -10**12) >= 86400: keep.append(i); last[s] = t
    d = P.loc[keep]
    pnl = (-d.f24 + d.ffund24 - 0.001) if side == "short" else (d.f24 - d.ffund24 - 0.001)
    q = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str)
    return pd.DataFrame({"q": q.values, "p": pnl.values, "s": d.s.values})
for side, thrs in (("short", (-0.01, -0.02, -0.03, -0.05)), ("long", (0.01, 0.02, 0.03, 0.05))):
    for thr in thrs:
        d = trades(side, thr)
        if not len(d): continue
        qm = d.groupby("q").p.mean()
        print(f"{side:5s} предсказание {'≤' if side == 'short' else '≥'} {thr:+.0%}: {len(d):5d} сделок ({d.s.nunique()} монет) | {d.p.mean() * 100:+.2f}% | плюс {(d.p > 0).mean():.0%} | "
              f"кв.+ {(qm > 0).sum()}/{len(qm)} | " + " ".join(f"{k[2:]}:{v * 100:+.1f}({(d.q == k).sum()})" for k, v in qm.items()), flush=True)
