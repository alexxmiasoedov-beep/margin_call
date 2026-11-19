"""s200 (изучение) — сводка задержки «завод держателя на адрес пополнения → сметание на кошелёк Binance» по кэшу
sweep_delay.py. Только время, без цен и доходов. Запуск из /home/user/mc_data: python3 sweep_stats.py"""
import json

import numpy as np
import pandas as pd

OUT = "/home/user/mc_data"
c = json.load(open(f"{OUT}/s200/sweep_cache.json"))
bt = json.load(open(f"{OUT}/s160/cache_blocktime.json"))
A = np.array(sorted((int(k), v) for k, v in bt.items()), float)
E = pd.read_pickle(f"{OUT}/s182_origin.pkl")
E["key"] = E.tok + ":" + E.frm + ":" + E.block.astype(int).astype(str)
E = E.set_index("key")
rows = []
for k, v in c.items():
    if v is None or k not in E.index:
        continue
    r = E.loc[k]
    if isinstance(r, pd.DataFrame):
        r = r.iloc[0]
    b, li = int(r.block), int(r.li)
    prev = [g for g in v if g[0] < b or (g[0] == b and g[1] < li)]
    if not prev:
        rows.append((k, r.t, np.nan, 0, r.end, np.nan))
        continue
    last = max(prev)
    tl = np.interp(last[0], A[:, 0], A[:, 1])
    # сколько входящих за последние сутки до сметания и доля последнего
    rows.append((k, r.t, (b - last[0]), len(prev), r.end, (r.t - tl) / 3600))
X = pd.DataFrame(rows, columns=["key", "t", "dblocks", "nin", "end", "delay_h"])
X["year"] = pd.to_datetime(X.t, unit="s").dt.year
print("событий:", len(X), "без входящих в окне:", int(X.delay_h.isna().sum()))
q = X.delay_h.quantile([0.1, 0.25, 0.5, 0.75, 0.9])
print("задержка, ч — квантили 10/25/50/75/90%:", " / ".join(f"{v:.2f}" for v in q.values))
print("доля ≤ 15 мин:", f"{(X.delay_h <= 0.25).mean():.0%}", "≤ 1 ч:", f"{(X.delay_h <= 1).mean():.0%}",
      "≤ 6 ч:", f"{(X.delay_h <= 6).mean():.0%}", "> 24 ч:", f"{(X.delay_h > 24).mean():.0%}")
print(X.groupby("year").delay_h.median().round(2).to_dict())
print(X.groupby("year").delay_h.apply(lambda s: (s <= 0.25).mean()).round(2).to_dict())
