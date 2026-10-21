"""Устойчивость корейского шорта: без лучших сделок, по монетам, по биржам, месяц 19.09–18.10, примеры (время МСК)."""
import pickle, datetime, re, os
import numpy as np
from pump_short6m import K, fund_short, trade
import korea_short6m as ks
MSK = datetime.timezone(datetime.timedelta(hours=3))
rows = []
for s, j, i in ks.EV:
    k = K[s]
    if j + 2 >= len(k) or j < 100: continue
    ka = ks.kr_arrays(s, j)
    if ka is None: continue
    vol, close = ka
    m = next((m for m in range(j, min(j + 96, len(k) - 2)) if ks.share(vol, k, m) >= 0.2), None)
    if m is None: continue
    t_in = k[m, 0] + 900; pnl, t_out = trade(k, m, 0.15, 0.25, 192); fd = fund_short(s, t_in, t_out)
    exs = [ex for ex in ("upbit", "bithumb") if os.path.exists(f"mm2/korea6/{ex}_{ks.strip(s)}_{int(k[j, 0] + 900 + 26 * 3600)}.npy")]
    rows.append(dict(s=s, t=t_in, pnl=pnl - 0.001 + fd, fund=fd, gain=k[m, 4] / k[i, 4] - 1, share=ks.share(vol, k, m), ex="+".join(exs), wait=(m - j) / 4))
a = np.array([r["pnl"] for r in rows])
print(f"сделок {len(a)}, монет {len({r['s'] for r in rows})}, средний итог {a.mean():+.2%}, медиана {np.median(a):+.2%}")
srt = np.sort(a)
for cut in (0.02, 0.05, 0.10):
    n = int(len(a) * cut); print(f"без {cut:.0%} лучших сделок: {srt[:-n].mean():+.2%}")
by = {}
for r in rows: by.setdefault(r["s"], []).append(r["pnl"])
tot = sorted(((sum(v), s, len(v)) for s, v in by.items()), reverse=True)
print("монет в плюсе:", sum(1 for x in tot if x[0] > 0), "из", len(tot), "| 10 лучших монет дают", f"{sum(x[0] for x in tot[:10]) / a.sum():.0%}", "суммы")
print("без 10 лучших монет:", f"{np.mean([p for s, v in by.items() if s not in {x[1] for x in tot[:10]} for p in v]):+.2%}")
for ex in ("upbit", "bithumb", "upbit+bithumb"):
    b = np.array([r["pnl"] for r in rows if r["ex"] == ex]); print(f"биржа {ex:14s}: {len(b):3d} сделок, {b.mean():+.2%}")
for lo, hi in ((0.15, 0.3), (0.3, 0.6), (0.6, 9)):
    b = np.array([r["pnl"] for r in rows if lo <= r["gain"] < hi]); print(f"рост к моменту входа {lo:.0%}–{hi:.0%}: {len(b):3d} сделок, {b.mean():+.2%}")
for lo, hi in ((0, 0.25), (0.25, 2), (2, 6), (6, 25)):
    b = np.array([r["pnl"] for r in rows if lo <= r["wait"] < hi]); print(f"вход через {lo}–{hi} ч после пампа: {len(b):3d} сделок, {b.mean():+.2%}")
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()
mo = [r for r in rows if T0 <= r["t"] <= T1]; b = np.array([r["pnl"] for r in mo])
print(f"\nмесяц 19.09–18.10 (причинно): {len(b)} сделок у {len({r['s'] for r in mo})} монет, {b.mean():+.2%}, в плюсе {np.mean(b > 0):.0%}")
print("фандинг в среднем", f"{np.mean([r['fund'] for r in rows]):+.2%}")
pickle.dump(rows, open("mm2/korea_short_trades.pkl", "wb"))
