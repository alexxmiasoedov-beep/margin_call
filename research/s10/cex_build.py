"""Ончейн-балансы кошельков Binance по токенам (DefiLlama, protocol/binance-cex): таблица день × токен (сумма по сетям, в штуках
и в $), проверка на артефакты — дни, когда баланс меняется скачком у многих токенов сразу (трекер добавил/убрал адреса)."""
import json, datetime, collections
import numpy as np, pandas as pd
j = json.load(open("s10/binance_cex.json"))
qty, usd = collections.defaultdict(dict), collections.defaultdict(dict)
for ch, c in j["chainTvls"].items():
    if "-" in ch or ch in ("staking", "pool2", "borrowed"): continue          # производные разрезы DefiLlama
    for kind, store in (("tokens", qty), ("tokensInUsd", usd)):
        for p in c.get(kind, []):
            d = datetime.datetime.utcfromtimestamp(p["date"]).strftime("%Y-%m-%d")
            for sym, v in p["tokens"].items():
                store[sym][d] = store[sym].get(d, 0.0) + float(v)
Q = pd.DataFrame(qty).sort_index(); U = pd.DataFrame(usd).sort_index()
Q.index = pd.to_datetime(Q.index); U.index = pd.to_datetime(U.index)
print("дней:", len(Q), Q.index.min().date(), "→", Q.index.max().date(), "| токенов:", Q.shape[1])
px = (U / Q).replace([np.inf, -np.inf], np.nan)
ch = Q.pct_change(fill_method=None)
big = (ch.abs() > 0.3).sum(axis=1)                       # сколько токенов за день изменили баланс больше чем на 30%
act = Q.notna().sum(axis=1)
art = big[big > 0.15 * act].sort_values(ascending=False)
print("дни-артефакты (больше 15% токенов изменились на 30%+):", len(art)); print(art.head(15).to_string())
Q.to_pickle("s10/cex_qty.pkl"); U.to_pickle("s10/cex_usd.pkl")
tot = U.sum(axis=1); print("всего на Binance, млрд $: старт", round(tot.iloc[0] / 1e9, 1), "сейчас", round(tot.iloc[-1] / 1e9, 1))
