"""s167 — Р1 (ход фьючерса за 24 ч до входа −5…+5%) на событиях после конца периода s160 (s167_post.pkl из post_check.py);
свечи — дневные архивы data.binance.vision (кэш s167/post). Запуск из /home/user/mc_data: python3 <repo>/research/s167/post_slice.py"""
import importlib.util
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("pc", os.path.join(HERE, "post_check.py"))
pc = importlib.util.module_from_spec(spec); spec.loader.exec_module(pc)


def main():
    X = pd.read_pickle("s167_post.pkl"); r24 = []
    for r in X.itertuples():
        sym = r.s + "USDT"
        days = sorted({pd.Timestamp(x, unit="s").strftime("%Y-%m-%d") for x in (r.t - 86400 - 900, r.t - 900)})
        parts = [pc.day_klines(sym, d) for d in days]
        if any(p is None for p in parts):
            r24.append(np.nan); continue
        k = pd.concat(parts).drop_duplicates("t").set_index("t").c
        a, b = k.get(r.t - 900), k.get(r.t - 86400 - 900)
        r24.append(a / b - 1 if a is not None and b is not None else np.nan)
    X["r24"] = r24
    c = X[(X.r24 >= -0.05) & (X.r24 <= 0.05)]
    print(f"после конца периода: спокойный рынок n={len(c)} {c.net.mean():+.2%} (медиана {c.net.median():+.2%}, в плюсе {(c.net > 0).mean():.0%}) | "
          f"прочие n={len(X) - len(c)} {X[~X.index.isin(c.index)].net.mean():+.2%} | без хода {int(X.r24.isna().sum())}")


if __name__ == "__main__":
    main()
